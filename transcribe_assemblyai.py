#!/usr/bin/env python3
"""Transcribe a local audio file with the official AssemblyAI Python SDK.

The command submits a local file without blocking, polls the resulting job at
a fixed three-second interval, and writes only the completed transcript text
to standard output. Credentials are read from ``ASSEMBLYAI_API_KEY``.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
import time
import traceback
from types import ModuleType
from typing import NoReturn, Optional, Sequence


POLL_INTERVAL_SECONDS = 3
DEFAULT_AUDIO_FILE = "audio.mp3"


class DependencyError(RuntimeError):
    """Raised when the official AssemblyAI SDK cannot be imported."""


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    """Parse command-line arguments from *argv*."""
    parser = argparse.ArgumentParser(
        description="Transcribe a local audio file with AssemblyAI."
    )
    parser.add_argument(
        "audio_file",
        nargs="?",
        default=DEFAULT_AUDIO_FILE,
        help=f"local audio file to transcribe (default: {DEFAULT_AUDIO_FILE})",
    )
    return parser.parse_args(argv)


def _load_assemblyai() -> ModuleType:
    """Import and return the official SDK with an actionable failure message."""
    try:
        return importlib.import_module("assemblyai")
    except ImportError as exc:
        raise DependencyError(
            "The AssemblyAI SDK is not installed. Run: pip install assemblyai"
        ) from exc


def _exit_with_error(message: str) -> NoReturn:
    """Write a user-facing error to stderr and terminate unsuccessfully."""
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(1)


def main(argv: Optional[Sequence[str]] = None) -> NoReturn:
    """Run the transcription CLI and terminate with a conventional exit code.

    Expected configuration and provider failures are presented as concise
    errors. Any unexpected exception includes its traceback to make production
    diagnostics possible while still returning exit status 1.
    """
    try:
        args = _parse_args(argv)
        assemblyai = _load_assemblyai()

        if not os.path.exists(args.audio_file):
            _exit_with_error(f"audio file does not exist: {args.audio_file}")

        api_key = os.environ.get("ASSEMBLYAI_API_KEY")
        if not api_key:
            _exit_with_error(
                "ASSEMBLYAI_API_KEY is not set. Export it before running this script."
            )

        assemblyai.settings.api_key = api_key
        transcriber = assemblyai.Transcriber()
        transcript = transcriber.submit(args.audio_file)

        terminal_statuses = {
            assemblyai.TranscriptStatus.completed,
            assemblyai.TranscriptStatus.error,
        }
        while transcript.status not in terminal_statuses:
            time.sleep(POLL_INTERVAL_SECONDS)
            transcript = transcriber.get_transcript(transcript.id)

        if transcript.status == assemblyai.TranscriptStatus.error:
            _exit_with_error(
                f"AssemblyAI transcription failed: {transcript.error}"
            )

        print(transcript.text or "")
        raise SystemExit(0)
    except SystemExit:
        raise
    except DependencyError as exc:
        _exit_with_error(str(exc))
    except Exception:
        print("Error: unexpected transcription failure", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
