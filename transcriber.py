import hashlib
import hmac
import base64
import json
import math
import subprocess
import tempfile
import time
import wave
from datetime import datetime
from pathlib import Path

import requests

from config import load_secret, SPEAKER_NAME

BASE_URL = "https://raasr.xfyun.cn/api"
SLICE_SIZE = 10 * 1024 * 1024  # 10MB per slice
POLL_INTERVAL = 5  # seconds between progress checks


def _get_credentials() -> tuple[str, str]:
    app_id = load_secret("XFYUN_APP_ID")
    secret_key = load_secret("XFYUN_SECRET_KEY")
    if not app_id or not secret_key:
        raise RuntimeError(
            "Set XFYUN_APP_ID and XFYUN_SECRET_KEY in secrets.json"
        )
    return app_id, secret_key


def _sign(app_id: str, secret_key: str) -> tuple[str, str]:
    """Generate timestamp and HMAC-SHA1 signature for iFlytek API."""
    ts = str(int(time.time()))
    base_string = app_id + ts
    md5_hash = hashlib.md5(base_string.encode()).hexdigest()
    signa = base64.b64encode(
        hmac.new(secret_key.encode(), md5_hash.encode(), hashlib.sha1).digest()
    ).decode()
    return ts, signa


def _get_wav_duration(wav_path: Path) -> float:
    try:
        with wave.open(str(wav_path), "rb") as wf:
            return wf.getnframes() / wf.getframerate() if wf.getframerate() else 0
    except Exception:
        return 0


def _format_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def _format_timestamp(ms: int) -> str:
    """Format milliseconds to readable timestamp."""
    total_seconds = ms // 1000
    m, s = divmod(total_seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _api_request(endpoint: str, app_id: str, secret_key: str, **extra) -> dict:
    """Make a signed request to the iFlytek API."""
    ts, signa = _sign(app_id, secret_key)
    data = {"app_id": app_id, "signa": signa, "ts": ts, **extra}
    resp = requests.post(f"{BASE_URL}/{endpoint}", data=data)
    resp.raise_for_status()
    result = resp.json()
    if result.get("ok") != 0:
        raise RuntimeError(f"iFlytek API error: {result}")
    return result


def _convert_for_xfyun(wav_path: Path) -> Path | None:
    """Convert audio to 16kHz/16-bit WAV if needed. Returns temp path or None if no conversion needed."""
    try:
        with wave.open(str(wav_path), "rb") as wf:
            rate = wf.getframerate()
            width = wf.getsampwidth()
    except Exception:
        rate, width = 0, 0

    if rate == 16000 and width == 2:
        return None  # Already in correct format

    print(f"    Converting to 16kHz/16-bit for iFlytek...")
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(wav_path), "-ar", "16000", "-ac", "1",
         "-sample_fmt", "s16", tmp.name],
        capture_output=True, check=True,
    )
    return Path(tmp.name)


def transcribe(wav_path: Path) -> list[dict]:
    """Upload a WAV file to iFlytek and get diarized transcription."""
    app_id, secret_key = _get_credentials()

    # Convert if needed (DJI Mic 3 records at 48kHz/24-bit)
    converted = _convert_for_xfyun(wav_path)
    upload_path = converted or wav_path

    file_size = upload_path.stat().st_size
    file_name = wav_path.name
    slice_num = math.ceil(file_size / SLICE_SIZE)

    # Step 1: Prepare
    print(f"    Uploading to iFlytek...")
    result = _api_request(
        "prepare", app_id, secret_key,
        file_len=str(file_size),
        file_name=file_name,
        slice_num=str(slice_num),
        has_seperate="true",
        speaker_number="0",  # 0 = auto-detect number of speakers
    )
    task_id = result["data"]

    # Step 2: Upload slices
    # slice_id must be 10 chars: aaaaaaaaaa, aaaaaaaaab, ...
    with open(upload_path, "rb") as f:
        for i in range(slice_num):
            chunk = f.read(SLICE_SIZE)
            slice_id = "a" * (10 - len(str(i))) + chr(ord("a") + i % 26)
            if i < 26:
                slice_id = "a" * 9 + chr(ord("a") + i)
            else:
                slice_id = "a" * 8 + chr(ord("a") + i // 26) + chr(ord("a") + i % 26)
            ts, signa = _sign(app_id, secret_key)
            data = {
                "app_id": app_id,
                "signa": signa,
                "ts": ts,
                "task_id": task_id,
                "slice_id": slice_id,
            }
            resp = requests.post(
                f"{BASE_URL}/upload",
                data=data,
                files={"content": ("audio.wav", chunk, "application/octet-stream")},
            )
            resp.raise_for_status()

    # Step 3: Merge
    _api_request("merge", app_id, secret_key, task_id=task_id)

    # Step 4: Poll for completion
    print(f"    Processing...")
    while True:
        time.sleep(POLL_INTERVAL)
        result = _api_request("getProgress", app_id, secret_key, task_id=task_id)
        status = json.loads(result["data"]) if isinstance(result["data"], str) else result["data"]
        desc = status.get("desc", "")
        if status.get("status") == 9:
            print(f"    Transcription complete.")
            break
        print(f"    Status: {desc}")

    # Step 5: Get result
    result = _api_request("getResult", app_id, secret_key, task_id=task_id)
    raw_data = result["data"]
    if isinstance(raw_data, str):
        raw_data = json.loads(raw_data)

    # Clean up temp file
    if converted:
        converted.unlink(missing_ok=True)

    # Parse into segments
    segments = []
    for item in raw_data:
        segments.append({
            "speaker": item.get("speaker", "0"),
            "text": item.get("onebest", ""),
            "start": int(item.get("bg", 0)),
            "end": int(item.get("ed", 0)),
        })
    return segments


def _segments_to_markdown(segments: list[dict]) -> str:
    """Format diarized segments into readable markdown."""
    if not segments:
        return "*No speech detected.*"

    lines = []
    current_speaker = None
    for seg in segments:
        speaker_id = seg["speaker"]
        speaker = SPEAKER_NAME if speaker_id == "1" else f"Speaker {speaker_id}"
        timestamp = _format_timestamp(seg["start"])
        text = seg["text"].strip()
        if not text:
            continue

        if speaker_id != current_speaker:
            current_speaker = speaker_id
            lines.append(f"\n**{speaker}** [{timestamp}]:\n{text}")
        else:
            lines.append(text)

    return "\n".join(lines).strip()


def save_markdown(wav_path: Path, segments: list[dict], md_path: Path = None) -> Path:
    """Create a markdown transcript file."""
    if md_path is None:
        md_path = wav_path.with_suffix(".md")
    duration = _get_wav_duration(wav_path)
    stat = wav_path.stat()
    recorded_dt = datetime.fromtimestamp(stat.st_mtime)

    speaker_ids = sorted(set(seg["speaker"] for seg in segments if seg.get("speaker")))
    speakers = []
    for sid in speaker_ids:
        speakers.append(SPEAKER_NAME if sid == "1" else f"Speaker {sid}")
    speaker_info = f"**Speakers:** {', '.join(speakers)}\n" if len(speakers) > 1 else ""

    transcript_md = _segments_to_markdown(segments)

    content = f"""# Recording: {wav_path.stem}

**Date:** {recorded_dt.strftime('%Y-%m-%d %H:%M:%S')}
**Duration:** {_format_duration(duration)}
**Source:** DJI Mic 3
{speaker_info}
## Transcript

{transcript_md}
"""
    md_path.write_text(content, encoding="utf-8")
    return md_path


def transcribe_and_save(wav_path: Path, md_path: Path = None) -> Path:
    """Transcribe a WAV file with speaker diarization and save as markdown."""
    print(f"  Transcribing: {wav_path.name}...")
    segments = transcribe(wav_path)
    speaker_count = len(set(seg["speaker"] for seg in segments if seg.get("speaker")))
    print(f"  Detected {speaker_count} speaker(s).")
    md_path = save_markdown(wav_path, segments, md_path)
    print(f"  Saved transcript: {md_path.name}")
    return md_path
