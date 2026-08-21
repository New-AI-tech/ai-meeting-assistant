# MacPocket

A local-first, cross-platform AI voice note-taker — a software clone of
the Pocket AI hardware device. Run one Python server on your computer
(Mac, Windows, or Linux), then open a web page from **any device on the
same network** — your laptop, phone, or tablet — hit record, and get a
transcript and summary with action items, generated entirely on your own
machine.

Your audio and transcript never leave your computer unless you
explicitly choose the `openai` summarization backend.

## Features

- 🌐 **Cross-platform web app** — one server, any browser, any device, anywhere with `--tunnel`
- 🔒 **Zero-config public HTTPS** via `python run.py --tunnel` (cloudflared) — no certificates, no account, works on iOS Safari
- 🎙️ Record straight from the browser's microphone
- 🖥️ **Tab Audio capture** on desktop Chrome/Edge — record a Zoom/Meet tab's audio without installing anything
- 📝 Local, offline transcription with Whisper
- 🤖 Summarization + action items via local LLM (Ollama/llama3.2) or OpenAI (gpt-4o-mini)
- 💾 Notes saved as timestamped `.txt` files on the server, in `~/MacPocket/Notes/`
- 📱 Mobile-first UI: big record button, live volume meter, clean results cards
- 🖥️ Terminal CLI (`cli.py`) still available for debugging, with mic + system-audio (BlackHole) capture on macOS

## How it works

```
Your phone / laptop browser  <-- Wi-Fi -->  Python server on your computer
        (records mic)                        FastAPI + Whisper + Ollama/OpenAI
```

You run `python run.py` once, on one computer. Every device on the same
network can then open that computer's address in a browser and use
MacPocket — recording happens in the browser, everything else
(transcription, summarization, storage) happens on the server.

## Requirements

- Python 3.9+
- [Homebrew](https://brew.sh) (macOS/Linux, used by `setup.sh`)
- ffmpeg (installed by `setup.sh`, or manually on Windows)
- [Ollama](https://ollama.com/download) (only for the `local` summarization backend, the default)
- An OpenAI API key (only for the `openai` summarization backend)

## Installation

### macOS / Linux

```bash
git clone <this-repo>
cd macpocket
chmod +x setup.sh
./setup.sh
```

`setup.sh` will:

1. Check for Homebrew (offering to install it if missing).
2. Install `ffmpeg` and `portaudio` (needed by Whisper, `pydub`, and the CLI fallback).
3. Install BlackHole 2ch (optional — only used by the CLI fallback for system-audio capture).
4. Create a virtual environment (`./venv`) and install everything in `requirements.txt` (FastAPI, uvicorn, python-multipart, pydub, Whisper, ...).
5. Check for Ollama and tell you how to pull the `llama3.2` model.
6. **Optionally install [cloudflared](https://github.com/cloudflare/cloudflared)** — powers `python run.py --tunnel`, the recommended zero-config way to get a public HTTPS URL for phone access.
7. **Optionally set up local HTTPS** with [mkcert](https://github.com/FiloSottile/mkcert) as a LAN-only alternative to `--tunnel` — see [Recording from a phone](#recording-from-a-phone) below.

### Windows

`setup.sh` is a bash script and won't run natively on Windows. Instead:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Install ffmpeg (required by Whisper and `pydub` for decoding uploaded audio):

```powershell
choco install ffmpeg
# or
scoop install ffmpeg
```

`python-multipart` (for file uploads) is already in `requirements.txt` and
installs automatically with the command above.

## Running the server

```bash
source venv/bin/activate      # Windows: venv\Scripts\activate
python run.py --tunnel
```

This starts the FastAPI server on port `8000` **and** opens a public
HTTPS URL via cloudflared — printed in the terminal in a box, and shown
in the web UI as a banner with a scannable QR code. Open that URL on
*any* device with internet access, no Wi-Fi requirement, no certificate
setup. This is the recommended way to get microphone access working on
a phone with zero configuration.

Prefer to stay LAN-only (no public URL at all)? Drop the flag:

```bash
python run.py
```

Equivalent manual command for either mode:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open **http://localhost:8000** in a browser on the same computer to try
it immediately, regardless of which mode you used.

## Connecting from your phone or another device

### Recommended: `python run.py --tunnel`

The printed URL (`https://<random-words>.trycloudflare.com`) works from
any device with internet access — scan the QR code shown in the web UI,
or open the URL directly. This is a secure HTTPS origin, so microphone
access just works, including on iOS Safari. No account or signup is
needed for cloudflared's "quick tunnel" mode. The URL changes each time
you restart the server, and stops working when you stop it (`Ctrl+C`).

### Alternative: stay on your local network

1. **Find this computer's local IP address:**

   | OS | Command |
   |---|---|
   | macOS | `ipconfig getifaddr en0` (Wi-Fi) or `ifconfig \| grep "inet "` |
   | Linux | `hostname -I` or `ip addr show` |
   | Windows | `ipconfig` (look for "IPv4 Address" under your active adapter) |

   You'll get something like `192.168.1.42`.

2. **Make sure your phone is on the same Wi-Fi network** as this computer.

3. Open `http://<that-ip>:8000` in your phone's browser, e.g.
   `http://192.168.1.42:8000`.

4. **Scan-to-open with a QR code** — paste your URL into this pattern and
   open (or embed) the image; it generates a scannable QR code for free
   via [api.qrserver.com](https://goqr.me/api/):

   ```html
   <img src="https://api.qrserver.com/v1/create-qr-code/?size=240x240&data=http://192.168.1.42:8000">
   ```

   Replace `192.168.1.42:8000` with your actual IP and port. Scan it with
   your phone's camera to jump straight to the page.

### Recording from a phone (HTTPS)

Browsers only allow microphone access (`getUserMedia`) on a **secure
context** — HTTPS, or the special case of `localhost`. Your phone
connecting to `http://192.168.x.x:8000` is *not* a secure context, so
**iOS Safari and most browsers will silently block the microphone** on
that URL. The MacPocket page detects this and shows a banner explaining
why the record button is disabled. `python run.py --tunnel` (above)
sidesteps this entirely; the options below are for staying LAN-only.

Give the server a real (locally-trusted) HTTPS certificate with
[mkcert](https://github.com/FiloSottile/mkcert):

```bash
brew install mkcert nss   # nss needed if you use Firefox
mkcert -install
mkdir -p certs
mkcert -cert-file certs/cert.pem -key-file certs/key.pem localhost 127.0.0.1 <your-local-ip>
```

`setup.sh` offers to do this for you automatically. Once `certs/cert.pem`
and `certs/key.pem` exist, `python run.py` (without `--tunnel`)
automatically serves over HTTPS — connect to
`https://<your-local-ip>:8000` from your phone instead. Because the
certificate is only trusted by mkcert's local root CA, your phone will
need that CA trusted too (mkcert prints instructions for this — usually
installing a profile on iOS, or a similar step on Android) or you'll see
a certificate warning you can click through for local testing. Note:
`--tunnel` and local certs are mutually exclusive — when tunneling, the
local server always runs plain HTTP and any `./certs` are ignored, since
cloudflared already provides HTTPS.

## Using the web app

1. Open the page (see above).
2. Choose **🎙️ Mic** or **🖥️ Tab Audio** as your source (see below).
3. Tap the gear icon to choose a Whisper model size, summarization
   backend, and an optional meeting title.
4. Tap the big red button to start recording — you'll see a live volume
   meter and timer.
5. Tap it again to stop. The recording uploads automatically and
   MacPocket transcribes and summarizes it.
6. Read the summary, action items, and full transcript on the results
   screen. The note is also saved to `~/MacPocket/Notes/` on the server.

## Tab Audio capture (system/meeting audio)

Desktop Chrome and Edge can capture a browser tab's audio directly — no
BlackHole or virtual audio driver needed. Select **🖥️ Tab Audio**, hit
record, and in the picker choose the tab playing your Zoom/Meet call
(or any audio), making sure to check **"Share tab audio"** (Chrome) or
**"Share audio"** (Edge) — it's easy to miss and unchecked means no
audio track gets captured, which MacPocket detects and reports as an
error asking you to retry with that box checked.

Browser support is uneven: this uses `getDisplayMedia`, which desktop
Chrome/Edge support well, Firefox partially supports (screen/window
audio, not always tab audio), and **iOS Safari and most mobile browsers
don't support at all** — the Tab Audio button is automatically disabled
on unsupported browsers. For system audio capture on unsupported
browsers, or to capture your Mac's system output more broadly than one
tab, use [the CLI with BlackHole](#capturing-system-audio-cli-only)
instead.

## API reference

### `GET /`

Serves the web UI (`static/index.html`).

### `POST /upload-audio`

Multipart form upload:

| Field | Type | Description |
|---|---|---|
| `file` | file | The recorded audio clip (webm, mp4/m4a, ogg, wav — anything ffmpeg can decode) |
| `backend` | string | `local` or `openai`. Default `local`. |
| `model` | string | Whisper model size: `tiny`, `base`, `small`, `medium`. Default `base`. |
| `title` | string | Optional meeting title. |

Response `200`:

```json
{
  "transcript": "...",
  "summary": "## Summary\n- ...\n\n## Action Items\n- [ ] ...",
  "note_path": "/Users/you/MacPocket/Notes/Meeting_2026-08-21_09-00-00.txt"
}
```

Errors return `4xx`/`5xx` with `{"detail": "..."}`.

### `WS /ws`

Reserved for future live-streaming transcription. Not used by the
current frontend, which uploads a complete clip after recording stops;
today it just accepts the connection and closes with an explanatory
message.

### `GET /tunnel-info`

Returns the active public tunnel URL when the server was started with
`--tunnel`, so the web UI can show it without reading the terminal:

```json
{"url": "https://random-words.trycloudflare.com", "provider": "cloudflared"}
```

Returns `{"url": null, "provider": null}` when no tunnel is active.

## The CLI fallback

For debugging the record → transcribe → summarize pipeline without a
browser, or for macOS system-audio capture via BlackHole:

```bash
python cli.py --device "BlackHole 2ch" --backend local --model base
```

See `python cli.py --help` for all flags. This is the same recording
flow MacPocket originally shipped with; it's kept around for local
debugging and for the BlackHole system-audio use case the browser can't
do on its own. See [Capturing system audio](#capturing-system-audio-cli-only)
below.

## Capturing system audio (CLI only)

Browsers can only record from the microphone, not "whatever the computer
is playing" — so capturing a Zoom/Meet call's audio still requires the
CLI and BlackHole, exactly as before:

1. Install BlackHole: `brew install blackhole-2ch`.
2. Open **Audio MIDI Setup** → **+** → **Create Multi-Output Device**,
   check both your speakers and **BlackHole 2ch**.
3. Set your Mac's output to that Multi-Output Device.
4. Run `python cli.py --device "BlackHole 2ch"`.

## Output format

Notes are saved to `~/MacPocket/Notes/Meeting_YYYY-MM-DD_HH-MM-SS.txt`:

```
Title: <your title>
Date: 2026-08-21 09:00:00
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
```

## Choosing a summarization backend

### Local (default) — Ollama + llama3.2

```bash
brew install ollama   # or https://ollama.com/download
ollama pull llama3.2
```

Runs entirely on-device. If Ollama isn't running or the model hasn't
been pulled, the server returns a clear error explaining these steps.

### Cloud — OpenAI GPT-4o-mini

```bash
export OPENAI_API_KEY="sk-..."
```

Set it before running `python run.py`, or put it in a `.env` file in the
project directory (loaded automatically via `python-dotenv`). Select
"Cloud (OpenAI)" in the app's settings panel.

## Whisper model sizes & performance

| Model | Relative speed | Notes |
|---|---|---|
| `tiny` | fastest | Lower accuracy, good for quick tests |
| `base` | fast | Default — good balance for most meetings |
| `small` | moderate | Better accuracy, still reasonably fast |
| `medium` | slow | High accuracy, needs more RAM/CPU |

The server keeps loaded Whisper models cached in memory between
requests, so only the first transcription with a given model size pays
the load-time cost.

## Troubleshooting

**Record button is disabled / grey**
You're on a non-HTTPS, non-localhost page — run with `--tunnel` for the
easiest fix, or see [Recording from a phone](#recording-from-a-phone-https) above.

**"Couldn't access the microphone" error**
Check your browser's site permissions for the page and allow microphone
access.

**"No audio track was captured" (Tab Audio)**
You picked a tab/window/screen in the share picker but didn't check
"Share tab audio" / "Share audio" — try again and make sure it's
checked. Some sources (e.g. sharing "Entire Screen" on macOS) don't
offer audio at all; pick a specific Chrome tab instead.

**Tab Audio button is disabled**
Your browser doesn't support `getDisplayMedia` audio capture (common on
iOS Safari and most mobile browsers) or the page isn't a secure
context. Use **🎙️ Mic** instead, or the CLI + BlackHole for system audio.

**`--tunnel` fails with "cloudflared isn't installed"**
Run `brew install cloudflared` (or see the printed download link), then
retry. Alternatively `pip install pyngrok` as a fallback (requires a
free ngrok account + authtoken).

**`--tunnel` times out waiting for a URL**
Check your internet connection. cloudflared needs to reach Cloudflare's
network to establish the quick tunnel.

**"Could not decode the uploaded audio"**
ffmpeg isn't installed (or isn't on `PATH`) on the machine running the
server. Re-run `setup.sh`, or install ffmpeg manually.

**Ollama connection errors**
Make sure the Ollama app/daemon is running and you've pulled the model:
`ollama pull llama3.2`.

**Phone can't reach the server at all (LAN mode)**
Confirm both devices are on the same Wi-Fi network (not a guest network
that isolates clients from each other), and that no firewall is blocking
port 8000 on the server machine. Or just use `--tunnel`, which doesn't
depend on Wi-Fi/firewall configuration at all.

**Whisper is slow**
Try a smaller model (`tiny` or `base`) in the settings panel.

## Project structure

```
macpocket/
├── main.py            # FastAPI app: serves the web UI, POST /upload-audio, /tunnel-info, /ws
├── run.py              # Launches uvicorn; --tunnel for cloudflared, or HTTPS if certs/ exists
├── tunnel.py            # cloudflared/pyngrok wrapper used by run.py --tunnel
├── cli.py                # Terminal CLI fallback (record/transcribe/summarize)
├── recorder.py             # Audio capture (sounddevice) used by cli.py
├── transcriber.py           # Local Whisper transcription (array- and file-based)
├── summarizer.py              # Ollama / OpenAI summarization backends
├── config.py                    # Defaults, paths, prompt template, constants
├── static/
│   └── index.html                  # Mobile-first web UI: Mic/Tab Audio toggle, tunnel banner, results
├── certs/                            # (optional, gitignored) local HTTPS cert/key
├── requirements.txt
├── setup.sh
└── README.md
```

## Privacy

- Audio and transcripts stay on your computer at all times when using
  the default `local` backend.
- The `openai` backend sends only the **transcript text** (not audio) to
  OpenAI's API for summarization.
- Notes are stored locally in `~/MacPocket/Notes/` on the server
  machine. Nothing is uploaded or synced anywhere by MacPocket itself.
- Recordings are converted and transcribed in a temporary upload folder
  (`~/MacPocket/uploads/`) and deleted immediately after processing.
- With `--tunnel`, cloudflared routes traffic between your device and
  this server through Cloudflare's network (this is how it gets you a
  public HTTPS URL without port-forwarding or a domain). The audio and
  transcript payloads pass through in transit but are not stored by
  MacPocket anywhere but your machine. If that's a concern, stay on the
  LAN-only mkcert flow instead — it never leaves your Wi-Fi.
