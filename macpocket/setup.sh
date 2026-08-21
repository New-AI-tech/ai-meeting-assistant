#!/usr/bin/env bash
#
# setup.sh — One-shot setup for the MacPocket web app on macOS/Linux.
#
# - Verifies Homebrew is installed (installs it if missing, with confirmation)
# - Installs BlackHole 2ch (for system-audio capture) if missing
# - Installs ffmpeg and portaudio (required by whisper / sounddevice / pydub)
# - Creates a Python virtual environment in ./venv
# - Installs Python dependencies from requirements.txt (FastAPI, uvicorn,
#   python-multipart, pydub, whisper, ...)
# - Optionally sets up a local HTTPS certificate (mkcert) so phones on your
#   Wi-Fi can grant microphone access to the page
#
# Windows users: this is a bash script and won't run natively. Install
# Python 3.9+ and ffmpeg (e.g. `choco install ffmpeg` or `scoop install
# ffmpeg`) yourself, then run:
#   python -m venv venv
#   venv\Scripts\activate
#   pip install -r requirements.txt
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

info()  { printf "\n\033[1;34m[MacPocket setup]\033[0m %s\n" "$1"; }
warn()  { printf "\n\033[1;33m[MacPocket setup] WARNING:\033[0m %s\n" "$1"; }
error() { printf "\n\033[1;31m[MacPocket setup] ERROR:\033[0m %s\n" "$1"; }

# --- 0. macOS check ----------------------------------------------------

if [[ "$(uname -s)" != "Darwin" ]]; then
    warn "This setup script is designed for macOS. Continuing anyway, but some steps (BlackHole, CoreAudio) will not apply."
fi

# --- 1. Homebrew ---------------------------------------------------------

if ! command -v brew >/dev/null 2>&1; then
    warn "Homebrew is not installed."
    read -r -p "Install Homebrew now? [y/N] " reply
    if [[ "$reply" =~ ^[Yy]$ ]]; then
        info "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    else
        error "Homebrew is required to install BlackHole, ffmpeg, and portaudio. Aborting."
        exit 1
    fi
else
    info "Homebrew found: $(command -v brew)"
fi

# --- 2. BlackHole 2ch (system audio capture) ------------------------------

if brew list --cask blackhole-2ch >/dev/null 2>&1; then
    info "BlackHole 2ch is already installed."
else
    info "Installing BlackHole 2ch (for system audio capture)..."
    if ! brew install blackhole-2ch; then
        warn "BlackHole installation failed or requires manual steps."
        warn "You can retry later with: brew install blackhole-2ch"
        warn "MacPocket will still work with your microphone in the meantime."
    else
        info "BlackHole 2ch installed. See README.md to set up a Multi-Output Device in Audio MIDI Setup so you can hear meetings while recording them."
    fi
fi

# --- 3. ffmpeg (required by Whisper) --------------------------------------

if command -v ffmpeg >/dev/null 2>&1; then
    info "ffmpeg is already installed."
else
    info "Installing ffmpeg (required by Whisper)..."
    brew install ffmpeg
fi

# --- 4. portaudio (required by sounddevice/PortAudio bindings) ------------

if brew list portaudio >/dev/null 2>&1; then
    info "portaudio is already installed."
else
    info "Installing portaudio (required by sounddevice)..."
    brew install portaudio
fi

# --- 5. Python virtual environment -----------------------------------------

PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    error "python3 not found. Install Python 3 (e.g. 'brew install python') and re-run this script."
    exit 1
fi

if [[ ! -d "venv" ]]; then
    info "Creating virtual environment in ./venv..."
    "$PYTHON_BIN" -m venv venv
else
    info "Virtual environment already exists at ./venv."
fi

# shellcheck disable=SC1091
source venv/bin/activate

info "Upgrading pip..."
pip install --upgrade pip >/dev/null

info "Installing Python dependencies from requirements.txt..."
pip install -r requirements.txt

# --- 6. Ollama (optional, for local summarization) --------------------------

if command -v ollama >/dev/null 2>&1; then
    info "Ollama found. You can pull the default model with:"
    echo "    ollama pull llama3.2"
else
    warn "Ollama is not installed. It's required for the '--backend local' summarizer."
    warn "Install it from https://ollama.com/download, or run:"
    echo "    brew install ollama"
    warn "Then pull the model with: ollama pull llama3.2"
    warn "Alternatively, use '--backend openai' with an OPENAI_API_KEY set."
fi

# --- 7. Optional: local HTTPS for phone access (mkcert) --------------------
#
# Phones (especially iOS Safari) block microphone access on pages loaded
# over plain HTTP unless the host is "localhost". To record from a phone
# on your Wi-Fi, the server needs a real HTTPS certificate for its local
# IP -- mkcert generates one that's automatically trusted on this Mac.

if [[ -f "certs/cert.pem" && -f "certs/key.pem" ]]; then
    info "Local HTTPS certificate already exists in ./certs."
else
    echo
    read -r -p "Set up local HTTPS now so phones can use the microphone? [y/N] " reply
    if [[ "$reply" =~ ^[Yy]$ ]]; then
        if ! command -v mkcert >/dev/null 2>&1; then
            info "Installing mkcert..."
            brew install mkcert nss || warn "mkcert install failed -- you can retry with: brew install mkcert nss"
        fi
        if command -v mkcert >/dev/null 2>&1; then
            mkcert -install
            mkdir -p certs
            LOCAL_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')"
            if [[ -n "$LOCAL_IP" ]]; then
                info "Generating certificate for localhost, 127.0.0.1, and $LOCAL_IP..."
                mkcert -cert-file certs/cert.pem -key-file certs/key.pem localhost 127.0.0.1 "$LOCAL_IP"
            else
                warn "Could not detect your local IP automatically."
                warn "Run manually: mkcert -cert-file certs/cert.pem -key-file certs/key.pem localhost 127.0.0.1 <your-local-ip>"
            fi
        fi
    else
        info "Skipping local HTTPS. You can set it up later -- see README.md."
    fi
fi

info "Setup complete!"
echo
echo "To get started:"
echo "  1. source venv/bin/activate"
echo "  2. python run.py"
echo "  3. Open the printed URL on this computer, or from your phone on the"
echo "     same Wi-Fi using this Mac's local IP (see README.md)."
echo
echo "See README.md for how to set up a Multi-Output Device so you can"
echo "capture system audio (e.g. Zoom/Meet calls) while still hearing them,"
echo "and for the CLI fallback (python cli.py) used for debugging."
