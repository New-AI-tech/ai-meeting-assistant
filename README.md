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

### Standalone AssemblyAI transcription

The included `transcribe_assemblyai.py` script uses AssemblyAI's official
Python SDK to upload a local audio file, submit it for transcription, poll
until processing finishes, and print the resulting text.

Install the SDK:

```bash
python -m pip install assemblyai
```

Set your key in an environment variable rather than pasting it into the
script. Copy the key from your AssemblyAI dashboard and run:

```bash
# macOS / Linux
export ASSEMBLYAI_API_KEY="paste-your-key-here"

# Transcribe audio.mp3, or pass another local file path.
python transcribe_assemblyai.py audio.mp3
```

In PowerShell:

```powershell
$env:ASSEMBLYAI_API_KEY = "paste-your-key-here"
python transcribe_assemblyai.py audio.mp3
```

Environment variables set this way last only for the current shell session.
The script exits with a clear message when the file, SDK, API key, or remote
transcription is unavailable.

Alternatively, use the cross-platform launcher. Omitting `--api-key` opens a
secure, non-echoing prompt, which keeps the key out of shell history:

```bash
python run_with_key.py audio.mp3
```

For non-interactive automation, pass the key explicitly. Be aware that command
arguments may be visible in shell history or process listings, so the prompt is
preferred for interactive use:

```bash
python run_with_key.py --api-key "your-key" audio.mp3
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

**Hosted `/upload-audio` requests return 502**
Cloud workers can time out or run out of memory while downloading and running
the local Whisper model. The checked-in FastAPI Cloud and Procfile entry points
use `macpocket.cloud`, which selects API transcription without installing the
large local audio/ML dependency stack. Configure an API key in the deployment
(`GROQ_API_KEY` for the free Groq tier, or `OPENAI_API_KEY` for the paid
OpenAI API) and redeploy. Local installs continue to use `macpocket.main` and
run Whisper on-device. You can override either choice with
`TRANSCRIPTION_BACKEND=local`, `auto`, `openai`, `groq`, or `assembler`.

**"OpenAI transcription is unavailable ... no credits remaining"**
The OpenAI account behind your `OPENAI_API_KEY` has an exhausted API balance
(the API returns a 429 `insufficient_quota` error). Free alternatives:

1. **Use a free API tier** — MacPocket supports OpenAI-compatible
   transcription providers with free tiers:
   - Groq (recommended): create a free key at https://console.groq.com/keys,
     then set `TRANSCRIPTION_BACKEND=groq` and `GROQ_API_KEY=gsk_...`
     (uses `whisper-large-v3-turbo`; override with `GROQ_WHISPER_MODEL`).
   - AssemblerAPI: free developer account at https://www.assemblerapi.co,
     then set `TRANSCRIPTION_BACKEND=assembler` and `ASSEMBLER_API_KEY=...`
     (override the model with `ASSEMBLER_MODEL`).
2. **Run fully local for free** — on a machine with the local Whisper stack
   installed (`pip install openai-whisper`, `brew install ffmpeg`), set
   `TRANSCRIPTION_BACKEND=local`. No API costs at all.
3. Top up credits at https://platform.openai.com/account/billing.

In `auto` mode MacPocket prefers configured free-tier keys (Groq,
AssemblerAPI) over the paid OpenAI key, and if any API account runs out of
credits it automatically falls back to local Whisper when available, or to
another configured backend, before surfacing this message.

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
  default local transcription and summarization backends.
- Selecting OpenAI only as the summarizer sends the **transcript text** (not
  audio) to OpenAI. The resource-safe `macpocket.cloud` deployment entry point
  sends uploaded audio to Groq for transcription. Set
  `TRANSCRIPTION_BACKEND=local` only on a host provisioned to run local Whisper.
- Notes are stored locally in `~/MacPocket/Notes/`. Nothing is uploaded
  or synced anywhere by MacPocket itself.
