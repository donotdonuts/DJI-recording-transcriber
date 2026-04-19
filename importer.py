import json
from datetime import datetime
from pathlib import Path

from config import RECORDINGS_DIR, PROCESSED_LOG


def load_processed() -> dict:
    """Load the record of all processed files."""
    if PROCESSED_LOG.exists():
        return json.loads(PROCESSED_LOG.read_text())
    return {}


def save_processed(processed: dict):
    PROCESSED_LOG.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_LOG.write_text(json.dumps(processed, indent=2))


def _get_wav_files(drive_path: Path) -> list[Path]:
    """Find WAV files in TX_MIC* folders only (skip .Trashes and system folders)."""
    wav_files = []
    for folder in drive_path.iterdir():
        if folder.is_dir() and folder.name.startswith("TX_MIC"):
            wav_files.extend(folder.glob("*.wav"))
    return sorted(wav_files)


def _file_key(wav_path: Path, drive_path: Path) -> str:
    """Generate a unique key for a file based on relative path + size."""
    rel = str(wav_path.relative_to(drive_path))
    size = wav_path.stat().st_size
    return f"{rel}|{size}"


def find_new_files(drive_path: Path) -> list[tuple[Path, str]]:
    """Find WAV files on the drive that haven't been processed yet.

    Returns list of (wav_path, file_key) tuples.
    """
    processed = load_processed()
    wav_files = _get_wav_files(drive_path)

    if not wav_files:
        print("  No WAV files found on drive.")
        return []

    print(f"  Found {len(wav_files)} WAV file(s) on drive.")
    new_files = []

    for wav in wav_files:
        key = _file_key(wav, drive_path)
        if key not in processed:
            new_files.append((wav, key))

    if not new_files:
        print("  No new files to process.")
    else:
        print(f"  {len(new_files)} new file(s) to process.")

    return new_files


def mark_processed(file_key: str, wav_path: Path, md_path: Path = None):
    """Mark a file as processed in the central record."""
    processed = load_processed()
    entry = {
        "processed_at": datetime.now().isoformat(),
        "source": wav_path.name,
    }
    if md_path:
        entry["transcript"] = str(md_path)
    else:
        entry["skipped"] = True
    processed[file_key] = entry
    save_processed(processed)
