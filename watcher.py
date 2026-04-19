import ctypes
import string
import time
from pathlib import Path

from config import POLL_INTERVAL


def _get_drives() -> set[str]:
    """Return set of drive letters currently mounted (e.g. {'C', 'D', 'E'})."""
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    drives = set()
    for i, letter in enumerate(string.ascii_uppercase):
        if bitmask & (1 << i):
            drives.add(letter)
    return drives


def _is_dji_drive(drive_letter: str) -> bool:
    """Check if a drive looks like a DJI Mic transmitter."""
    root = Path(f"{drive_letter}:\\")
    if not root.exists():
        return False
    try:
        dirs = [p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")]
    except OSError:
        return False
    # DJI Mic 3 uses folders like TX_MIC001_20260323_125129
    return any(d.startswith("TX_MIC") for d in dirs)


def watch_for_dji(on_connected, on_disconnected=None):
    """Poll for DJI Mic transmitter drive. Calls on_connected(drive_path) when found."""
    known_drives = _get_drives()
    connected_drive = None
    print("Watching for DJI Mic 3 transmitter... (plug it in via USB)")

    while True:
        time.sleep(POLL_INTERVAL)
        current_drives = _get_drives()
        new_drives = current_drives - known_drives
        removed_drives = known_drives - current_drives

        # Check if connected drive was removed
        if connected_drive and connected_drive in removed_drives:
            print(f"DJI Mic 3 disconnected (drive {connected_drive}:)")
            if on_disconnected:
                on_disconnected()
            connected_drive = None

        # Check new drives for DJI
        for letter in new_drives:
            if _is_dji_drive(letter):
                print(f"DJI Mic 3 detected on drive {letter}:\\")
                connected_drive = letter
                on_connected(Path(f"{letter}:\\"))

        known_drives = current_drives
