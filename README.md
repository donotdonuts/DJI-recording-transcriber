# DJI Mic 3 Recorder & Transcriber

Auto-transcribe recordings from your DJI Mic 3 transmitter with speaker diarization. Supports Chinese-English mixed language transcription.

## How It Works

1. Press the **record button** on your DJI Mic 3 transmitter throughout the day
2. Plug the transmitter into your PC via USB
3. The app detects the drive, finds new recordings, and transcribes them using iFlytek's speech recognition API
4. Markdown transcripts with speaker labels and timestamps are saved to `recordings/YYYY-MM-DD/`

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Get iFlytek API credentials

1. Sign up at [xfyun.cn](https://www.xfyun.cn/)
2. Create an app and enable the 语音转写 (Speech Transcription) service
3. Copy your `app_id` and `secret_key`

### 3. Configure credentials

```bash
cp secrets.example.json secrets.json
```

Edit `secrets.json` and paste your credentials.

### 4. Run

```bash
python main.py
```

The app watches for the DJI Mic 3 transmitter. Plug it in and it processes automatically.

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
- Speaker labels with timestamps
- Full transcript with speaker diarization
- Native Chinese-English mixed language support

## File Structure

| File | Purpose |
|---|---|
| `main.py` | Entry point |
| `watcher.py` | Detects DJI Mic 3 USB drive |
| `importer.py` | Finds new files, tracks processed recordings |
| `transcriber.py` | iFlytek transcription with speaker diarization |
| `config.py` | Settings (paths, speaker name, poll interval) |
| `secrets.json` | Your API credentials (git-ignored) |
| `.processed.json` | Central record of processed files (git-ignored) |

## Features

- **Chinese-English mixed language** — native support, no configuration needed
- **Speaker diarization** — auto-detects speakers
- **Long recordings** — supports files up to 5 hours / 500MB
- **Deduplication** — tracks processed files so nothing gets transcribed twice
- **Auto-start** — runs silently on Windows boot
