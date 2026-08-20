"""
transcriber.py — Local transcription using OpenAI's Whisper model.
"""

import sys
import tempfile
from pathlib import Path
from typing import Optional

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
    if model_size not in WHISPER_MODELS:
        raise TranscriptionError(
            f"Unknown Whisper model '{model_size}'. Choose from: "
            f"{', '.join(WHISPER_MODELS)}"
        )

    if audio.size == 0:
        raise TranscriptionError(
            "No audio was recorded, so there is nothing to transcribe."
        )

    whisper = _load_whisper()

    print(f"[MacPocket] Loading Whisper '{model_size}' model "
          "(first run may take a while to download)...")
    try:
        model = whisper.load_model(model_size)
    except Exception as exc:
        raise TranscriptionError(
            f"[MacPocket] Failed to load Whisper model '{model_size}': {exc}"
        ) from exc

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
