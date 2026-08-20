# MacPocket

A local-first AI voice note-taker for macOS — a software clone of the
Pocket AI hardware device. MacPocket records a meeting (from your
microphone and/or system audio), transcribes it locally with OpenAI's
Whisper, and produces a concise summary with action items using either a
local LLM (Ollama) or OpenAI's API.

Everything runs on your Mac. Your audio and transcript never leave your
machine unless you explicitly choose the `openai` summarization backend.

## Features

- 🎙️ Record from your microphone, system audio (via BlackHole), or both
- 📝 Local, offline transcription with Whisper
- 🤖 Summarization + action items via local LLM (Ollama/llama3.2) or
  OpenAI (gpt-4o-mini)
- 💾 Notes saved as timestamped `.txt` files in `~/MacPocket/Notes/`
- 🧠 Chunked recording so long meetings don't blow up memory

## Requirements

- macOS
- [Homebrew](https://brew.sh)
- Python 3.9+
- [Ollama](https://ollama.com/download) (only if using the `local`
  summarization backend, which is the default)
- An OpenAI API key (only if using the `openai` summarization backend)

## Installation

```bash
git clone <this-repo>
cd macpocket
chmod +x setup.sh
./setup.sh
```

`setup.sh` will:

1. Check for Homebrew (and offer to install it if missing).
2. Install `blackhole-2ch` (system audio capture) via Homebrew, if not
   already installed.
3. Install `ffmpeg` and `portaudio` (required by Whisper and
   `sounddevice`).
4. Create a virtual environment (`./venv`) and install everything in
   `requirements.txt`.
5. Check for Ollama and tell you how to pull the `llama3.2` model if
   you plan to use the local summarization backend.

If you'd rather do it by hand:

```bash
brew install blackhole-2ch ffmpeg portaudio
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
source venv/bin/activate
python main.py
```

By default, MacPocket will list your available input devices and ask you
to pick one, record using the local Whisper `base` model, summarize with
Ollama's `llama3.2`, and record until you press `CTRL+C`.

### CLI flags

| Flag | Short | Description | Default |
|---|---|---|---|
| `--device` | `-d` | Input device name (e.g. `"BlackHole 2ch"` or `"MacBook Pro Microphone"`). If omitted, MacPocket lists devices and prompts you. | *(interactive)* |
| `--backend` | `-b` | Summarization backend: `local` (Ollama) or `openai` (GPT-4o-mini). | `local` |
| `--model` | `-m` | Whisper model size: `tiny`, `base`, `small`, `medium`, `large`. | `base` |
| `--duration` | `-t` | Fixed recording duration in seconds. If omitted, records until `CTRL+C`. | *(infinite)* |
| `--fp16` | | Enable fp16 inference in Whisper. Speeds things up on Apple Silicon (M1/M2/M3). Leave off on Intel Macs. | off |
| `--title` | | Title for the note. If omitted, you'll be prompted after transcription. | *(prompted)* |

### Examples

Record your microphone until you hit `CTRL+C`, transcribe with the
`base` model, and summarize locally:

```bash
python main.py --device "MacBook Pro Microphone"
```

Record a Zoom call's system audio via BlackHole, use the more accurate
`small` Whisper model, and summarize with OpenAI:

```bash
export OPENAI_API_KEY="sk-..."
python main.py --device "BlackHole 2ch" --model small --backend openai
```

Record for a fixed 30-minute block (e.g. a scheduled standup):

```bash
python main.py --duration 1800
```

Let MacPocket list devices and prompt you interactively:

```bash
python main.py
```

## Capturing system audio (e.g. Zoom, Google Meet) with BlackHole

BlackHole is a virtual audio driver that lets MacPocket "listen in" on
whatever your Mac is playing. By itself, routing your system output to
BlackHole means *you* won't hear the meeting anymore — so you'll want to
create a **Multi-Output Device** that sends audio to both your speakers
*and* BlackHole simultaneously.

1. Install BlackHole (done automatically by `setup.sh`, or manually via
   `brew install blackhole-2ch`).
2. Open **Audio MIDI Setup** (Spotlight search → "Audio MIDI Setup").
3. Click the **`+`** button in the bottom-left corner and choose
   **Create Multi-Output Device**.
4. In the new Multi-Output Device's checklist, check both:
   - Your normal output (e.g. "MacBook Pro Speakers")
   - **BlackHole 2ch**
5. Rename it if you like (e.g. "Meeting Output").
6. Go to **System Settings → Sound → Output** and select your new
   Multi-Output Device.
7. In whatever meeting app you're using (Zoom, Meet, etc.), leave its
   output as your Multi-Output Device (or System Default), and run
   MacPocket with `--device "BlackHole 2ch"` to capture that audio.

To capture **both** your microphone and the other participants' system
audio in one recording, you can instead create an **Aggregate Device**
combining your microphone and BlackHole 2ch, then select that aggregate
device in MacPocket.

If BlackHole isn't installed, MacPocket will detect this and print
install instructions instead of crashing:

```
[MacPocket] Could not find the 'BlackHole 2ch' input device.
...
To install it, run:
    brew install blackhole-2ch
```

## Output format

Notes are saved to `~/MacPocket/Notes/Meeting_YYYY-MM-DD_HH-MM-SS.txt`,
containing:

```
Title: <your title>
Date: 2026-08-20 14:32:10
============================================================

TRANSCRIPT
------------------------------------------------------------
<full transcript text>

SUMMARY & ACTION ITEMS
------------------------------------------------------------
## Summary
- ...
- ...
- ...

## Action Items
- [ ] ... (Owner: ...)
- [ ] ... (Owner: ...)
```

The summary and action items are also printed to the terminal when the
run finishes.

## Choosing a summarization backend

### Local (default) — Ollama + llama3.2

Runs entirely on-device, no API key or internet connection required
after the model is pulled.

```bash
brew install ollama   # or download from https://ollama.com/download
ollama pull llama3.2
python main.py --backend local
```

If Ollama isn't running or the model hasn't been pulled, MacPocket will
catch the error and print these exact steps.

### Cloud — OpenAI GPT-4o-mini

Requires an API key set via the `OPENAI_API_KEY` environment variable
(or a `.env` file in the project directory, since MacPocket loads
`python-dotenv` automatically):

```bash
export OPENAI_API_KEY="sk-..."
python main.py --backend openai
```

## Whisper model sizes & performance

| Model | Relative speed | Notes |
|---|---|---|
| `tiny` | fastest | Lower accuracy, good for quick tests |
| `base` | fast | Default — good balance for most meetings |
| `small` | moderate | Better accuracy, still reasonably fast |
| `medium` | slow | High accuracy, needs more RAM/CPU |
| `large` | slowest | Best accuracy, requires significant resources |

By default, MacPocket runs Whisper with `fp16=False` for compatibility
with Intel Macs (fp16 on CPU can be unstable). If you're on Apple
Silicon (M1/M2/M3), pass `--fp16` for a speed boost:

```bash
python main.py --model small --fp16
```

## Troubleshooting

**"No input devices found" / microphone not detected**
Check **System Settings → Privacy & Security → Microphone** and make
sure Terminal (or whichever app you're running Python from) has
permission to access the microphone.

**BlackHole device not found**
Run `brew install blackhole-2ch`, then restart Terminal. MacPocket will
also print this instruction automatically if it detects the issue.

**Ollama connection errors**
Make sure the Ollama app/daemon is running and you've pulled the model:
`ollama pull llama3.2`.

**Whisper is slow**
Try a smaller model (`--model tiny` or `--model base`), or add `--fp16`
if you're on Apple Silicon.

## Project structure

```
macpocket/
├── main.py          # CLI entry point — orchestrates record → transcribe → summarize → save
├── recorder.py       # Audio capture (sounddevice), device resolution, BlackHole handling
├── transcriber.py    # Local Whisper transcription
├── summarizer.py      # Ollama / OpenAI summarization backends
├── config.py          # Defaults, paths, prompt template, constants
├── requirements.txt
├── setup.sh
└── README.md
```

## Privacy

- Audio and transcripts stay on your Mac at all times when using the
  default `local` backend.
- The `openai` backend sends only the **transcript text** (not audio) to
  OpenAI's API for summarization.
- Notes are stored locally in `~/MacPocket/Notes/`. Nothing is uploaded
  or synced anywhere by MacPocket itself.
