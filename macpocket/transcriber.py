"""
transcriber.py — Local transcription using OpenAI's Whisper model.
"""

from pathlib import Path

import numpy as np

from config import DEFAULT_FP16, DEFAULT_WHISPER_MODEL, SAMPLE_RATE, WHISPER_MODELS


class TranscriptionError(Exception):
    """Raised when transcription cannot proceed."""


def _load_whisper():
    try:
        import whisper
    except ImportError as exc:
        raise TranscriptionError(
            "\n[MacPocket] The 'openai-whisper' package is not installed.\n"
            "Install it with:\n"
            "    pip install -r requirements.txt\n"
            "Note: Whisper also requires ffmpeg. If you haven't installed it:\n"
            "    brew install ffmpeg\n"
        ) from exc
    return whisper


# Whisper models are large (tens to hundreds of MB) and slow to load. The
# server handles one upload after another, so cache loaded models by size
# instead of reloading on every request.
_MODEL_CACHE = {}


def _get_model(model_size: str):
    if model_size not in WHISPER_MODELS:
        raise TranscriptionError(
            f"Unknown Whisper model '{model_size}'. Choose from: "
            f"{', '.join(WHISPER_MODELS)}"
        )

    if model_size in _MODEL_CACHE:
        return _MODEL_CACHE[model_size]

    whisper = _load_whisper()
    print(f"[MacPocket] Loading Whisper '{model_size}' model "
          "(first run may take a while to download)...")
    try:
        model = whisper.load_model(model_size)
    except Exception as exc:
        raise TranscriptionError(
            f"[MacPocket] Failed to load Whisper model '{model_size}': {exc}"
        ) from exc

    _MODEL_CACHE[model_size] = model
    return model


def transcribe_audio(
    audio: np.ndarray,
    model_size: str = DEFAULT_WHISPER_MODEL,
    sample_rate: int = SAMPLE_RATE,
    fp16: bool = DEFAULT_FP16,
) -> str:
    """
    Transcribe a mono float32 numpy array of audio samples using a local
    Whisper model. Returns the transcript text.
    """
    if audio.size == 0:
        raise TranscriptionError(
            "No audio was recorded, so there is nothing to transcribe."
        )

    model = _get_model(model_size)

    # Whisper expects 16kHz mono float32 audio in [-1, 1]. Resample if needed.
    audio = _ensure_16k_mono(audio, sample_rate)

    print("[MacPocket] Transcribing audio locally with Whisper "
          f"({'fp16' if fp16 else 'fp32'})... this may take a few minutes.")

    try:
        result = model.transcribe(audio, fp16=fp16, verbose=False)
    except Exception as exc:
        raise TranscriptionError(f"[MacPocket] Whisper transcription failed: {exc}") from exc

    text = result.get("text", "").strip()
    print("[MacPocket] Transcription complete.")
    return text


def transcribe_file(
    file_path: str,
    model_size: str = DEFAULT_WHISPER_MODEL,
    fp16: bool = DEFAULT_FP16,
) -> str:
    """
    Transcribe an audio file on disk (any format ffmpeg can decode: wav,
    webm, m4a, mp3, ...) using a local Whisper model. Returns the
    transcript text. Used by the FastAPI upload endpoint.
    """
    path = Path(file_path)
    if not path.is_file() or path.stat().st_size == 0:
        raise TranscriptionError(
            f"Audio file '{file_path}' is missing or empty, so there is "
            "nothing to transcribe."
        )

    model = _get_model(model_size)

    print("[MacPocket] Transcribing audio locally with Whisper "
          f"({'fp16' if fp16 else 'fp32'})... this may take a few minutes.")

    try:
        result = model.transcribe(str(path), fp16=fp16, verbose=False)
    except Exception as exc:
        raise TranscriptionError(f"[MacPocket] Whisper transcription failed: {exc}") from exc

    text = result.get("text", "").strip()
    print("[MacPocket] Transcription complete.")
    return text


def _ensure_16k_mono(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """Whisper is trained on 16kHz audio; resample if our capture rate differs."""
    if sample_rate == 16000:
        return audio.astype(np.float32)

    try:
        import scipy.signal as signal
    except ImportError as exc:
        raise TranscriptionError(
            "scipy is required to resample audio to 16kHz for Whisper. "
            "Install it with: pip install -r requirements.txt"
        ) from exc

    target_len = int(len(audio) * 16000 / sample_rate)
    resampled = signal.resample(audio, target_len)
    return resampled.astype(np.float32)
