#!/usr/bin/env python3
"""Run ``transcribe_assemblyai.py`` with a temporary AssemblyAI API key.

The key can be supplied with ``--api-key`` or entered at a non-echoing prompt.
It is exported only to this launcher and its child process; the value is
restored when the transcription command finishes.
"""

from __future__ import annotations

import argparse
import getpass
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence


API_KEY_ENV_VAR = "95eb8778d7fa48aba9165a9c3b8a1d14"
TRANSCRIBER_SCRIPT = Path(__file__).resolve().with_name("transcribe_assemblyai.py")


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    """Return validated launcher arguments."""
    parser = argparse.ArgumentParser(
        description="Set an AssemblyAI API key and run the transcription CLI."
    )
    parser.add_argument(
        "--api-key",
        help=(
            "AssemblyAI API key; omit this option to enter it securely at a prompt. "
            "Using the prompt avoids saving the key in shell history."
        ),
    )
    parser.add_argument(
        "audio_file",
        nargs="?",
        help="audio path forwarded to transcribe_assemblyai.py (default: audio.mp3)",
    )
    return parser.parse_args(argv)


def _read_api_key(argument: Optional[str]) -> str:
    """Return a non-empty key from the argument or a secure terminal prompt."""
    key = argument if argument is not None else getpass.getpass(
        "AssemblyAI API key: "
    )
    key = key.strip()
    if not key:
        raise ValueError("an AssemblyAI API key is required")
    return key


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Temporarily export the API key and run the transcription child process."""
    args = _parse_args(argv)

    try:
        api_key = _read_api_key(args.api_key)
    except (EOFError, KeyboardInterrupt):
        print("\nError: API key entry was cancelled.", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    command = [sys.executable, str(TRANSCRIBER_SCRIPT)]
    if args.audio_file:
        command.append(args.audio_file)

    # subprocess.run inherits stdout and stderr by default, so output from the
    # transcription CLI appears directly in the current terminal.
    previous_key = os.environ.get(API_KEY_ENV_VAR)
    os.environ[API_KEY_ENV_VAR] = api_key
    try:
        completed = subprocess.run(command, check=False)
        return completed.returncode
    except OSError as exc:
        print(f"Error: could not launch transcription script: {exc}", file=sys.stderr)
        return 1
    finally:
        if previous_key is None:
            os.environ.pop(API_KEY_ENV_VAR, None)
        else:
            os.environ[API_KEY_ENV_VAR] = previous_key


if __name__ == "__main__":
    raise SystemExit(main())
