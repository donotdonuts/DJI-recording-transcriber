# DJI Mic 3 Recorder & Transcriber

Auto-transcribe recordings from your DJI Mic 3 transmitter with speaker diarization.

## How It Works

1. Press the **record button** on your DJI Mic 3 transmitter throughout the day
2. Plug the transmitter into your PC via USB
3. The app detects the drive, finds new recordings, and transcribes them using OpenAI's `gpt-4o-transcribe-diarize` model
4. Markdown transcripts with speaker labels and timestamps are saved to `recordings/YYYY-MM-DD/`

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure your API key

Copy the example secrets file and add your OpenAI API key:

```bash
cp secrets.example.json secrets.json
```

Edit `secrets.json` and paste your key.

### 3. (Optional) Add a voice sample

Record a short clip (5-10 seconds) of yourself speaking on the DJI Mic 3, then save it as `voice_sample.wav` in the project root. This lets the transcriber identify and label your segments by name.

You can change the speaker label in `config.py` → `SPEAKER_NAME`.

### 4. Run

```bash
python main.py
```

The app will watch for the DJI Mic 3 transmitter. Plug it in and it processes automatically.

## Auto-Start on Windows

Copy `start_recorder.vbs` to your Windows Startup folder:

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\
```

Edit the paths in the script to match your install location. The app runs silently in the background and logs to `recorder.log`.

## Output

Transcripts are saved as markdown files:

```
recordings/
  2026-04-19/
    TX01_MIC001_20260419_103636_orig.md
    TX01_MIC002_20260419_105059_orig.md
```

Each file includes:
- Date and duration
- Speaker labels (with your name if voice sample is provided)
- Timestamped transcript with speaker diarization

## File Structure

| File | Purpose |
|---|---|
| `main.py` | Entry point |
| `watcher.py` | Detects DJI Mic 3 USB drive |
| `importer.py` | Finds new files, tracks processed recordings |
| `transcriber.py` | OpenAI transcription with speaker diarization |
| `config.py` | Settings (paths, speaker name, poll interval) |
| `secrets.json` | Your API key (git-ignored) |
| `voice_sample.wav` | Your voice sample for speaker ID (git-ignored) |
| `.processed.json` | Central record of processed files (git-ignored) |

## Cost

Uses OpenAI's `gpt-4o-transcribe-diarize` model at ~$0.006/minute. A 10-minute recording costs about 6 cents.

Large files (>25MB) are automatically split into chunks for processing.
