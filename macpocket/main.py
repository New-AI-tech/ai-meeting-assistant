"""
main.py — MacPocket FastAPI server.

Serves the mobile-first web UI (static/index.html) and an /upload-audio
endpoint: the browser records audio locally (MediaRecorder API) and
uploads the finished clip here for local transcription (Whisper) and
summarization (Ollama or OpenAI). Any device on the same network can
connect to this server's local IP and use MacPocket from its browser.

Run with:  python run.py
Or:        uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import (
    DEFAULT_BACKEND,
    DEFAULT_FP16,
    DEFAULT_MEETING_TITLE,
    DEFAULT_WHISPER_MODEL,
    FILENAME_PREFIX,
    FILENAME_TIMESTAMP_FMT,
    NOTES_DIR,
    STATIC_DIR,
    SUMMARY_BACKENDS,
    TUNNEL_INFO_FILE,
    UPLOAD_FOLDER,
    WHISPER_MODELS,
)
from summarizer import SummarizationError, summarize
from transcriber import TranscriptionError, transcribe_file

load_dotenv()

app = FastAPI(title="MacPocket")

# Local-network use: phones/tablets on the same Wi-Fi hit this server by IP,
# so the origin is unpredictable ahead of time. Restrict methods instead.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/tunnel-info")
def tunnel_info() -> JSONResponse:
    """
    Reports the public tunnel URL when the server was started with
    `python run.py --tunnel`, so the web UI can display it (and a QR
    code) without the user needing to read the terminal.
    """
    if TUNNEL_INFO_FILE.is_file():
        try:
            data = json.loads(TUNNEL_INFO_FILE.read_text())
            return JSONResponse({"url": data.get("url"), "provider": data.get("provider")})
        except (json.JSONDecodeError, OSError):
            pass
    return JSONResponse({"url": None, "provider": None})


def _ensure_dirs() -> None:
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)


def _convert_to_wav(src_path: Path, dst_path: Path) -> None:
    """Normalize whatever format the browser recorded (webm/opus, mp4/aac,
    ogg, ...) into a mono 16kHz WAV file using pydub (which shells out to
    ffmpeg). Whisper can technically decode most formats directly via
    ffmpeg too, but converting up front lets us fail fast on a corrupt
    upload with a clear error instead of a confusing Whisper stack trace.
    """
    try:
        from pydub import AudioSegment
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "The 'pydub' package is not installed on the server. "
                "Install it with: pip install -r requirements.txt"
            ),
        ) from exc

    try:
        audio = AudioSegment.from_file(src_path)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "Could not decode the uploaded audio. Make sure ffmpeg is "
                f"installed on the server. Original error: {exc}"
            ),
        ) from exc

    audio = audio.set_channels(1).set_frame_rate(16000)
    audio.export(dst_path, format="wav")


def _write_note(title: str, transcript: str, summary: str) -> Path:
    timestamp = datetime.now().strftime(FILENAME_TIMESTAMP_FMT)
    note_path = NOTES_DIR / f"{FILENAME_PREFIX}{timestamp}.txt"
    content = (
        f"Title: {title}\n"
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"{'=' * 60}\n\n"
        f"TRANSCRIPT\n"
        f"{'-' * 60}\n"
        f"{transcript.strip()}\n\n"
        f"SUMMARY & ACTION ITEMS\n"
        f"{'-' * 60}\n"
        f"{summary.strip()}\n"
    )
    note_path.write_text(content, encoding="utf-8")
    return note_path


@app.post("/upload-audio")
async def upload_audio(
    file: UploadFile = File(...),
    backend: str = Form(DEFAULT_BACKEND),
    model: str = Form(DEFAULT_WHISPER_MODEL),
    title: str = Form(""),
) -> JSONResponse:
    if backend not in SUMMARY_BACKENDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown backend '{backend}'. Choose from: {', '.join(SUMMARY_BACKENDS)}",
        )
    if model not in WHISPER_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown Whisper model '{model}'. Choose from: {', '.join(WHISPER_MODELS)}",
        )

    _ensure_dirs()

    # Unique filenames so concurrent uploads from different devices never
    # collide or clobber each other's temp files.
    upload_id = uuid.uuid4().hex
    suffix = Path(file.filename or "").suffix or ".webm"
    raw_path = UPLOAD_FOLDER / f"{upload_id}_upload{suffix}"
    wav_path = UPLOAD_FOLDER / f"{upload_id}.wav"

    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")
        raw_path.write_bytes(contents)

        _convert_to_wav(raw_path, wav_path)

        try:
            transcript = transcribe_file(str(wav_path), model_size=model, fp16=DEFAULT_FP16)
        except TranscriptionError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        if not transcript.strip():
            raise HTTPException(
                status_code=422,
                detail="Whisper produced an empty transcript (silence or inaudible audio).",
            )

        try:
            summary = summarize(transcript, backend=backend)
        except SummarizationError as exc:
            # Still return the transcript — a summarizer outage shouldn't
            # throw away a transcription that already succeeded.
            summary = f"(Summary unavailable: {exc})"

        note_title = title.strip() or DEFAULT_MEETING_TITLE
        note_path = _write_note(note_title, transcript, summary)

        return JSONResponse(
            {
                "transcript": transcript,
                "summary": summary,
                "note_path": str(note_path),
            }
        )
    finally:
        raw_path.unlink(missing_ok=True)
        wav_path.unlink(missing_ok=True)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    Reserved for future live-streaming transcription (send audio chunks as
    they're captured instead of waiting for the full recording to upload).
    Not used by the current frontend, which uploads a complete clip to
    /upload-audio once recording stops.
    """
    await websocket.accept()
    try:
        await websocket.send_json(
            {"error": "Live streaming isn't implemented yet — use POST /upload-audio."}
        )
    finally:
        await websocket.close()
