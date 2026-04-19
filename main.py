import logging
import sys
from datetime import datetime
from pathlib import Path

from config import BASE_DIR, RECORDINGS_DIR, SPEAKER_NAME, SECRETS_FILE, load_secret

# Log to both console and file
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "recorder.log"),
    ],
)
log = logging.getLogger("recorder")
from importer import find_new_files, mark_processed
from transcriber import transcribe_and_save
from watcher import watch_for_dji


def on_drive_connected(drive_path: Path):
    """Called when a DJI Mic 3 transmitter is plugged in."""
    log.info(f"\nProcessing drive: {drive_path}")
    new_files = find_new_files(drive_path)
    if not new_files:
        return

    app_id = load_secret("XFYUN_APP_ID")
    secret_key = load_secret("XFYUN_SECRET_KEY")
    if not app_id or not secret_key:
        log.info(f"\n  WARNING: iFlytek credentials not set in {SECRETS_FILE.name}. Skipping transcription.")
        return

    success = 0
    failed = []

    for wav_path, file_key in new_files:
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            out_dir = RECORDINGS_DIR / today
            out_dir.mkdir(parents=True, exist_ok=True)
            md_path = out_dir / (wav_path.stem + ".md")

            transcribe_and_save(wav_path, md_path)
            mark_processed(file_key, wav_path, md_path)
            success += 1
        except Exception as e:
            log.info(f"  ERROR transcribing {wav_path.name}: {e}")
            failed.append(wav_path.name)

    # Report
    log.info("")
    log.info(f"  === Report ===")
    log.info(f"  Total:       {len(new_files)} file(s)")
    log.info(f"  Transcribed: {success}")
    log.info(f"  Failed:      {len(failed)}")
    if failed:
        for name in failed:
            log.info(f"    - {name}")
    log.info("")
    log.info("Done! You can safely disconnect the transmitter.")


def main():
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

    app_id = load_secret("XFYUN_APP_ID")
    secret_key = load_secret("XFYUN_SECRET_KEY")
    if not app_id or not secret_key or "paste" in (app_id + secret_key):
        log.info(f"WARNING: Set XFYUN_APP_ID and XFYUN_SECRET_KEY in {SECRETS_FILE}")
        log.info("Files will not be transcribed.\n")
    else:
        log.info("iFlytek credentials loaded from secrets.json")

    log.info(f"Speaker 1 will be labeled as \"{SPEAKER_NAME}\"")

    try:
        watch_for_dji(on_connected=on_drive_connected)
    except KeyboardInterrupt:
        log.info("\nStopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
