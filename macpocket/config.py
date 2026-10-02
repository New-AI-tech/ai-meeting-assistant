"""
config.py — MacPocket default settings and constants.
"""

import os
import tempfile
from pathlib import Path

# --- Paths -------------------------------------------------------------

NOTES_DIR = Path(os.path.expanduser("~/MacPocket/Notes"))

# Scratch space for in-flight uploads (raw browser recording + converted
# wav), deleted immediately after each request. Based on tempfile.gettempdir()
# rather than ~/MacPocket/uploads so it's guaranteed writable on Linux cloud
# instances/containers, where $HOME may be unset or read-only even if the
# rest of the filesystem is fine.
UPLOAD_FOLDER = Path(tempfile.gettempdir()) / "macpocket-uploads"

FILENAME_TIMESTAMP_FMT = "%Y-%m-%d_%H-%M-%S"
FILENAME_PREFIX = "Meeting_"

STATIC_DIR = Path(__file__).parent / "static"

# --- Server ---------------------------------------------------------------

SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000

# Written by run.py --tunnel with the active public tunnel URL, and read by
# GET /tunnel-info so the web UI can display/QR-code it. Removed when the
# tunnel shuts down.
TUNNEL_INFO_FILE = Path(os.path.expanduser("~/MacPocket/tunnel_url.json"))

# --- Audio ---------------------------------------------------------------

SAMPLE_RATE = 16000  # Hz — matches what Whisper expects internally
CHANNELS = 1
CHUNK_SECONDS = 10  # size of each recording buffer chunk
DTYPE = "float32"

# Name of the virtual audio device used for capturing system audio on macOS.
BLACKHOLE_DEVICE_NAME = "BlackHole 2ch"
BLACKHOLE_INSTALL_CMD = "brew install blackhole-2ch"

# --- Transcription ---------------------------------------------------------

WHISPER_MODELS = ("tiny", "base", "small", "medium", "large")
DEFAULT_WHISPER_MODEL = "tiny"

# Apple Silicon (M1/M2/M3) users may set this to True (or pass --fp16) for
# faster transcription. Intel Macs should leave this False to avoid
# instability/crashes with fp16 on CPU.
DEFAULT_FP16 = False

# ``auto`` keeps local-first behaviour on Macs, but avoids loading PyTorch and
# downloading a Whisper model on a cloud worker when an OpenAI key is present.
# Loading the local model during an HTTP request can exhaust a small worker or
# outlive a reverse proxy's timeout, which surfaces in the browser as a 502.
TRANSCRIPTION_BACKENDS = ("auto", "local", "openai")
TRANSCRIPTION_BACKEND = os.environ.get("TRANSCRIPTION_BACKEND", "auto").lower()

# --- Summarization ---------------------------------------------------------

SUMMARY_BACKENDS = ("local", "openai")
DEFAULT_BACKEND = "local"

OLLAMA_MODEL = "llama3.2"
OLLAMA_INSTALL_URL = "https://ollama.com/download"

OPENAI_MODEL = "gpt-4o-mini"
OPENAI_API_KEY_ENV_VAR = "OPENAI_API_KEY"

SUMMARY_PROMPT_TEMPLATE = """You are an assistant that turns raw meeting \
transcripts into crisp, actionable notes.

Given the transcript below, produce output in EXACTLY this format, and \
nothing else:

## Summary
- <bullet 1>
- <bullet 2>
- <bullet 3>

## Breaking Points & Discussion
- <breaking/key point 1>
- <breaking/key point 2>

## Important Points
- <important point 1>
- <important point 2>

## Action Items
- [ ] <action item 1> (Owner: <name or "Unassigned">)
- [ ] <action item 2> (Owner: <name or "Unassigned">)
- [ ] <action item 3> (Owner: <name or "Unassigned">)

Rules:
- The summary must be EXACTLY 3 bullet points capturing the high-level overview of the meeting.
- The "Breaking Points & Discussion" section must list key turning points, debate topics, decisions made, or major shifts in conversation.
- The "Important Points" section must list key takeaways, technical or business facts, dates, numbers, or critical context mentioned.
- Action items (To-Do List) must be formatted as a markdown checkbox list.
- Infer the most likely owner for each action item from context (who \
volunteered, who was addressed, who is responsible for that area). If no \
owner can be reasonably inferred, use "Unassigned".
- If there truly are no action items, write a single line under Action Items: \
"- [ ] No action items identified"
- Do not include any text before "## Summary" or after the last action item.

Transcript:
\"\"\"
{transcript}
\"\"\"
"""

DEFAULT_MEETING_TITLE = "Untitled Meeting"
