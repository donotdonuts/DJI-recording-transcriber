import base64
import os
import tempfile
import wave
from datetime import datetime
from pathlib import Path

from openai import OpenAI

from config import load_secret, SPEAKER_NAME, VOICE_SAMPLE

DIARIZE_MODEL = "gpt-4o-transcribe-diarize"
MAX_FILE_SIZE = 24 * 1024 * 1024  # 24MB to stay safely under 25MB API limit
CHUNK_DURATION = 1200  # 20 minutes per chunk — safe for any sample rate / bit depth


def _get_client() -> OpenAI:
    api_key = load_secret("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Set OPENAI_API_KEY in secrets.json for transcription."
        )
    return OpenAI(api_key=api_key)


def _get_wav_duration(wav_path: Path) -> float:
    """Return duration in seconds."""
    try:
        with wave.open(str(wav_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / rate if rate else 0
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


def _format_timestamp(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _to_data_url(path: Path) -> str:
    """Convert an audio file to a base64 data URL for the API."""
    with open(path, "rb") as f:
        return "data:audio/wav;base64," + base64.b64encode(f.read()).decode("utf-8")


def _split_wav(wav_path: Path) -> list[tuple[Path, float]]:
    """Split a large WAV into chunks. Returns list of (chunk_path, time_offset) pairs.
    If file is small enough, returns the original path with offset 0."""
    file_size = wav_path.stat().st_size
    if file_size <= MAX_FILE_SIZE:
        return [(wav_path, 0.0)]

    chunks = []
    with wave.open(str(wav_path), "rb") as wf:
        rate = wf.getframerate()
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        total_frames = wf.getnframes()
        frames_per_chunk = rate * CHUNK_DURATION

        chunk_idx = 0
        frames_read = 0
        while frames_read < total_frames:
            n = min(frames_per_chunk, total_frames - frames_read)
            data = wf.readframes(n)
            time_offset = frames_read / rate

            tmp = tempfile.NamedTemporaryFile(
                suffix=f"_chunk{chunk_idx}.wav", delete=False, dir=wav_path.parent
            )
            with wave.open(tmp.name, "wb") as out:
                out.setnchannels(channels)
                out.setsampwidth(sampwidth)
                out.setframerate(rate)
                out.writeframes(data)
            chunks.append((Path(tmp.name), time_offset))

            frames_read += n
            chunk_idx += 1

    return chunks


def _transcribe_single(client: OpenAI, wav_path: Path, extra: dict) -> list[dict]:
    """Transcribe a single WAV file (must be under 25MB)."""
    with open(wav_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model=DIARIZE_MODEL,
            file=f,
            response_format="diarized_json",
            chunking_strategy="auto",
            **({} if not extra else {"extra_body": extra}),
        )

    segments = []
    for seg in result.segments:
        segments.append({
            "speaker": seg.speaker,
            "text": seg.text,
            "start": seg.start,
            "end": seg.end,
        })
    return segments


def transcribe(wav_path: Path) -> list[dict]:
    """Send a WAV file to OpenAI with diarization. Splits large files into chunks."""
    client = _get_client()

    extra = {}
    if VOICE_SAMPLE.exists():
        extra["known_speaker_names"] = [SPEAKER_NAME]
        extra["known_speaker_references"] = [_to_data_url(VOICE_SAMPLE)]

    chunks = _split_wav(wav_path)
    is_chunked = len(chunks) > 1

    if is_chunked:
        print(f"    Large file — split into {len(chunks)} chunks")

    all_segments = []
    for i, (chunk_path, time_offset) in enumerate(chunks):
        if is_chunked:
            print(f"    Transcribing chunk {i + 1}/{len(chunks)}...")

        segments = _transcribe_single(client, chunk_path, extra)

        # Adjust timestamps by the chunk's offset
        for seg in segments:
            seg["start"] += time_offset
            seg["end"] += time_offset
        all_segments.extend(segments)

        # Clean up temp chunk files
        if chunk_path != wav_path:
            chunk_path.unlink()

    return all_segments


def _segments_to_markdown(segments: list[dict]) -> str:
    """Format diarized segments into readable markdown."""
    if not segments:
        return "*No speech detected.*"

    lines = []
    current_speaker = None
    for seg in segments:
        speaker = seg["speaker"]
        timestamp = _format_timestamp(seg["start"])
        text = seg["text"].strip()
        if not text:
            continue

        if speaker != current_speaker:
            current_speaker = speaker
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

    speakers = sorted(set(seg["speaker"] for seg in segments if seg.get("speaker")))
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
