import logging
import sys
from datetime import datetime
from pathlib import Path

from config import BASE_DIR, RECORDINGS_DIR, VOICE_SAMPLE, SPEAKER_NAME, SECRETS_FILE, load_secret

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

    api_key = load_secret("OPENAI_API_KEY")
    if not api_key:
        log.info(f"\n  WARNING: No API key in {SECRETS_FILE.name}. Skipping transcription.")
        return

    success = 0
    failed = []

    for wav_path, file_key in new_files:
        try:
            # Determine output path for the transcript
            today = datetime.now().strftime("%Y-%m-%d")
            out_dir = RECORDINGS_DIR / today
            out_dir.mkdir(parents=True, exist_ok=True)
            md_path = out_dir / (wav_path.stem + ".md")

            # Transcribe directly from the drive
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

    api_key = load_secret("OPENAI_API_KEY")
    if not api_key or api_key == "paste-your-key-here":
        log.info(f"WARNING: Set your OpenAI API key in {SECRETS_FILE}")
        log.info("Files will not be transcribed.\n")
    else:
        log.info("OpenAI API key loaded from secrets.json")

    if VOICE_SAMPLE.exists():
        log.info(f"Voice sample loaded - your segments will be labeled as \"{SPEAKER_NAME}\"")
    else:
        log.info(f"TIP: Record a short voice sample and save it as {VOICE_SAMPLE.name}")
        log.info("     This lets the transcriber identify which parts are you.\n")

    try:
        watch_for_dji(on_connected=on_drive_connected)
    except KeyboardInterrupt:
        log.info("\nStopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
