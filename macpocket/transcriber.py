"""
transcriber.py — Local transcription using OpenAI's Whisper model.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import os

if TYPE_CHECKING:
    import numpy as np

# Set thread limits to prevent PyTorch from hanging or crashing serverless workers
os.environ.setdefault("TORCH_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

from config import (
    DEFAULT_FP16,
    DEFAULT_WHISPER_MODEL,
    OPENAI_COMPATIBLE_BACKENDS,
    SAMPLE_RATE,
    TRANSCRIPTION_BACKEND,
    TRANSCRIPTION_BACKENDS,
    WHISPER_MODELS,
    _TRANSCRIPTION_DEFAULTS,
)


class TranscriptionError(Exception):
    """Raised when transcription cannot proceed."""


class InsufficientCreditsError(TranscriptionError):
    """Raised when the OpenAI API rejects requests due to no credits left.

    Carries an actionable message: top up the account's API credits, or run
    MacPocket locally with TRANSCRIPTION_BACKEND=local so transcription uses
    a local Whisper model instead of the hosted API.
    """


_CREDITS_ERROR_MESSAGE = (
    "The configured transcription API account has no credits remaining. "
    "Options: add credits in the provider's billing settings, switch to a "
    "free API tier with TRANSCRIPTION_BACKEND=groq (GROQ_API_KEY) or "
    "TRANSCRIPTION_BACKEND=assembler (ASSEMBLER_API_KEY), or run MacPocket "
    "locally with TRANSCRIPTION_BACKEND=local."
)

_LOCAL_WHISPER_MISSING_MESSAGE = (
    "[MacPocket] Local transcription requires the 'openai-whisper' package "
    "(and ffmpeg). Install them with:\n"
    "    pip install -r requirements.txt\n"
    "    brew install ffmpeg\n"
    "On a hosted worker without those dependencies, use the OpenAI "
    "transcription API instead by setting OPENAI_API_KEY and removing "
    "TRANSCRIPTION_BACKEND=local."
)


def _ensure_ffmpeg_on_path():
    """Ensure ffmpeg binary is discoverable in PATH, using imageio_ffmpeg if needed."""
    import os
    import shutil
    if not shutil.which("ffmpeg"):
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            if ffmpeg_exe:
                ffmpeg_dir = str(Path(ffmpeg_exe).parent)
                current_path = os.environ.get("PATH", "")
                if ffmpeg_dir not in current_path:
                    os.environ["PATH"] = f"{ffmpeg_dir}{os.pathsep}{current_path}"
        except Exception:
            pass


def _load_whisper():
    _ensure_ffmpeg_on_path()
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
        # Fallback to 'tiny' model if loading a larger model fails (e.g. OOM on server)
        if model_size != "tiny":
            print(f"[MacPocket] Loading '{model_size}' failed ({exc}), falling back to 'tiny' model...")
            try:
                model = whisper.load_model("tiny")
            except Exception as inner_exc:
                raise TranscriptionError(
                    f"[MacPocket] Failed to load Whisper model: {inner_exc}"
                ) from inner_exc
        else:
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
    import numpy as np

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


def _local_whisper_available() -> bool:
    """Return True if the local Whisper stack can actually be used here."""
    try:
        import whisper  # noqa: F401
    except ImportError:
        return False
    return True


def _is_insufficient_credits_error(exc: Exception) -> bool:
    """Detect OpenAI errors caused by the account having no credits left.

    The API signals this with HTTP 429 and error codes such as
    'insufficient_quota' (billing hard stop) or 'usage_limit_reached', with
    messages like "You exceeded your current quota, please check your plan
    and billing details".
    """
    status = getattr(exc, "status_code", None)
    body = str(getattr(exc, "body", "") or "").lower()
    message = str(exc).lower()
    haystack = f"{body} {message}"

    credit_markers = (
        "insufficient_quota",
        "insufficient_credit",
        "credit_balance_too_low",
        "exceeded your current quota",
        "no credits remaining",
        "credits remaining",
        "billing",
    )
    if any(marker in haystack for marker in credit_markers):
        return True
    # A bare 429 without a recognizable billing phrase is usually a rate
    # limit, not an exhausted balance, so only treat quota-flavoured 429s
    # as credit problems.
    if status == 429 and "quota" in haystack:
        return True
    return False


def _api_backend_for_auto() -> str | None:
    """Pick a hosted API backend for 'auto' mode, or None to use local Whisper.

    Free-tier backends (Groq, AssemblerAPI) are preferred when their key is
    configured; the paid OpenAI API is used only as the last resort so that
    an exhausted OpenAI balance never blocks transcription unnecessarily.
    """
    for backend in ("groq", "assembler", "openai"):
        key_env = _TRANSCRIPTION_DEFAULTS[backend]["key_env"]
        if os.environ.get(key_env):
            return backend
    return None


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

    backend = TRANSCRIPTION_BACKEND
    if backend not in TRANSCRIPTION_BACKENDS:
        raise TranscriptionError(
            f"Unknown transcription backend '{backend}'. Choose from: "
            f"{', '.join(TRANSCRIPTION_BACKENDS)}"
        )

    # Hosted workers are a poor fit for loading and running local Whisper:
    # the model download and inference happen inside the request and can cause
    # the platform proxy to return 502 before FastAPI can send a response.
    # In auto mode, use an API backend whenever a key is configured (free
    # tiers first). A keyless local installation continues to use local
    # Whisper as before.
    api_backend = backend
    if backend == "auto":
        api_backend = _api_backend_for_auto()

    if api_backend in OPENAI_COMPATIBLE_BACKENDS:
        key_env = _TRANSCRIPTION_DEFAULTS[api_backend]["key_env"]
        api_key = os.environ.get(key_env)
        if not api_key:
            raise TranscriptionError(
                f"{key_env} is required when TRANSCRIPTION_BACKEND={api_backend}."
            )
        try:
            return _transcribe_file_api(path, api_backend, api_key)
        except InsufficientCreditsError as exc:
            # The configured account has run out of credits. Try cheaper/
            # free options before failing outright: local Whisper if it is
            # installed on this host, then any other API backend whose key
            # happens to be configured.
            if _local_whisper_available():
                print(
                    "[MacPocket] The configured transcription API account "
                    "has no credits remaining. Falling back to local "
                    "Whisper for this request. Add credits in the provider's "
                    "billing settings, or switch to a free tier with "
                    "TRANSCRIPTION_BACKEND=groq / assembler."
                )
                return _transcribe_file_local(path, model_size, fp16)
            for alt in ("groq", "assembler", "openai"):
                if alt == api_backend:
                    continue
                alt_key_env = _TRANSCRIPTION_DEFAULTS[alt]["key_env"]
                alt_key = os.environ.get(alt_key_env)
                if alt_key:
                    print(
                        f"[MacPocket] {api_backend} is out of credits; "
                        f"trying TRANSCRIPTION_BACKEND alternative '{alt}'..."
                    )
                    try:
                        return _transcribe_file_api(path, alt, alt_key)
                    except InsufficientCreditsError:
                        continue
            raise TranscriptionError(str(exc)) from exc

    if backend == "local" and not _local_whisper_available():
        # Explicit local mode was requested but this machine cannot run
        # Whisper (e.g. a slim cloud worker without the heavy dependencies).
        # Give the user a clear, actionable error rather than an ImportError.
        raise TranscriptionError(_LOCAL_WHISPER_MISSING_MESSAGE)

    openai_key = os.environ.get("OPENAI_API_KEY")
    model = _get_model(model_size)

    print("[MacPocket] Transcribing audio locally with Whisper "
          f"({'fp16' if fp16 else 'fp32'})... this may take a few minutes.")

    try:
        result = model.transcribe(str(path), fp16=fp16, verbose=False)
    except Exception as exc:
        # Explicit local mode retains the API fallback for compatibility.
        if openai_key:
            print(f"[MacPocket] Local Whisper failed ({exc}). Falling back to OpenAI Whisper API...")
            return _transcribe_file_api(path, "openai", openai_key)
        raise TranscriptionError(f"[MacPocket] Whisper transcription failed: {exc}") from exc

    text = result.get("text", "").strip()
    print("[MacPocket] Transcription complete.")
    return text


def _transcribe_file_local(
    path: Path,
    model_size: str = DEFAULT_WHISPER_MODEL,
    fp16: bool = DEFAULT_FP16,
) -> str:
    """Run a local Whisper model over *path* (no API involved)."""
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


def _transcribe_file_api(path: Path, backend: str, api_key: str) -> str:
    """Transcribe *path* via an OpenAI-compatible transcription API.

    Supports the paid OpenAI endpoint as well as free-tier providers that
    expose the same /v1/audio/transcriptions interface (Groq, AssemblerAPI),
    without initializing the heavyweight local model.
    """
    defaults = _TRANSCRIPTION_DEFAULTS[backend]
    key_env = defaults["key_env"]
    model = os.environ.get(defaults["model_env"], defaults["model"])
    base_url = None
    if defaults.get("base_url_env"):
        base_url = os.environ.get(defaults["base_url_env"],
                                  defaults.get("base_url_default"))

    label = {"openai": "OpenAI", "groq": "Groq", "assembler": "AssemblerAPI"}[backend]
    print(f"[MacPocket] Transcribing audio with the {label} transcription API "
          f"(model '{model}')...")
    try:
        from openai import OpenAI

        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = OpenAI(**kwargs)
        with path.open("rb") as audio_file:
            response = client.audio.transcriptions.create(
                model=model,
                file=audio_file,
            )
    except Exception as exc:
        if _is_insufficient_credits_error(exc):
            raise InsufficientCreditsError(_CREDITS_ERROR_MESSAGE) from exc
        if _is_missing_model_error(exc):
            raise TranscriptionError(
                f"[MacPocket] {label} transcription failed: model '{model}' "
                f"was rejected. Set {defaults['model_env']} to a model your "
                f"account has access to. Original error: {exc}"
            ) from exc
        raise TranscriptionError(
            f"[MacPocket] {label} transcription failed: {exc}"
        ) from exc

    text = response.text.strip()
    print("[MacPocket] Transcription complete.")
    return text


def _is_missing_model_error(exc: Exception) -> bool:
    """True when the provider rejects the requested model name/deployment."""
    message = str(exc).lower()
    return any(marker in message for marker in (
        "model_not_found",
        "does not exist",
        "unknown model",
        "not a valid model",
    ))


def _ensure_16k_mono(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """Whisper is trained on 16kHz audio; resample if our capture rate differs."""
    import numpy as np

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
