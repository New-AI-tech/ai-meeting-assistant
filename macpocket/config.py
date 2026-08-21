"""
config.py — MacPocket default settings and constants.
"""

import os
from pathlib import Path

# --- Paths -------------------------------------------------------------

NOTES_DIR = Path(os.path.expanduser("~/MacPocket/Notes"))
UPLOAD_FOLDER = Path(os.path.expanduser("~/MacPocket/uploads"))
FILENAME_TIMESTAMP_FMT = "%Y-%m-%d_%H-%M-%S"
FILENAME_PREFIX = "Meeting_"

STATIC_DIR = Path(__file__).parent / "static"

# --- Server ---------------------------------------------------------------

SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000

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
DEFAULT_WHISPER_MODEL = "base"

# Apple Silicon (M1/M2/M3) users may set this to True (or pass --fp16) for
# faster transcription. Intel Macs should leave this False to avoid
# instability/crashes with fp16 on CPU.
DEFAULT_FP16 = False

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

## Action Items
- [ ] <action item 1> (Owner: <name or "Unassigned">)
- [ ] <action item 2> (Owner: <name or "Unassigned">)
- [ ] <action item 3> (Owner: <name or "Unassigned">)

Rules:
- The summary must be EXACTLY 3 bullet points capturing the most important \
points of the meeting.
- Action items must be formatted as a markdown checkbox list.
- Infer the most likely owner for each action item from context (who \
volunteered, who was addressed, who is responsible for that area). If no \
owner can be reasonably inferred, use "Unassigned".
- If there truly are no action items, write a single line: \
"- [ ] No action items identified"
- Do not include any text before "## Summary" or after the last action item.

Transcript:
\"\"\"
{transcript}
\"\"\"
"""

DEFAULT_MEETING_TITLE = "Untitled Meeting"
