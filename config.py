import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
RECORDINGS_DIR = BASE_DIR / "recordings"
PROCESSED_LOG = BASE_DIR / ".processed.json"

# Drive detection
POLL_INTERVAL = 2  # seconds between checking for new drives
# DJI Mic 3 uses folders like TX_MIC001_20260323_125129

# Secrets
SECRETS_FILE = BASE_DIR / "secrets.json"

# Speaker identification
SPEAKER_NAME = "Leon"  # How your segments are labeled in transcripts


def load_secret(key: str) -> str | None:
    """Load a secret from secrets.json."""
    if not SECRETS_FILE.exists():
        return None
    secrets = json.loads(SECRETS_FILE.read_text())
    return secrets.get(key)
