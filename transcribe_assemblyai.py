#!/usr/bin/env python3
"""Transcribe a local audio file with the official AssemblyAI SDK.

The script uses the SDK to upload and submit the local file, then explicitly
polls AssemblyAI until the job reaches a terminal status. The API key is read
from ``ASSEMBLYAI_API_KEY`` and is never stored in this source file.
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path


POLL_INTERVAL_SECONDS = 3


def transcribe_file(audio_path: Path, api_key: str) -> str:
    """Upload *audio_path*, wait for AssemblyAI, and return its transcript."""
    try:
        import assemblyai as aai
    except ImportError as exc:
        raise RuntimeError(
            "The AssemblyAI SDK is not installed. Run: pip install assemblyai"
        ) from exc

    # Configure the official SDK from the environment-provided key. ``submit``
    # uploads local files and returns after AssemblyAI has queued the job.
    aai.settings.api_key = api_key
    transcriber = aai.Transcriber()
    transcript = transcriber.submit(str(audio_path))

    # Poll until AssemblyAI reports a terminal status. Keeping this loop
    # explicit makes progress and failure behavior easy to customize.
    while transcript.status not in {
        aai.TranscriptStatus.completed,
        aai.TranscriptStatus.error,
    }:
        print(f"Status: {transcript.status}; waiting...", flush=True)
        time.sleep(POLL_INTERVAL_SECONDS)
        transcript = transcriber.get_transcript(transcript.id)

    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(f"AssemblyAI transcription failed: {transcript.error}")
    if transcript.status != aai.TranscriptStatus.completed:
        raise RuntimeError(
            f"AssemblyAI returned unexpected status: {transcript.status}"
        )

    return transcript.text or ""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Transcribe a local audio file with AssemblyAI."
    )
    parser.add_argument(
        "audio_file",
        nargs="?",
        default="audio.mp3",
        type=Path,
        help="local audio file to transcribe (default: audio.mp3)",
    )
    args = parser.parse_args()

    if not args.audio_file.is_file():
        parser.error(f"audio file does not exist: {args.audio_file}")

    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    if not api_key:
        parser.error(
            "ASSEMBLYAI_API_KEY is not set. Export it before running this script."
        )

    try:
        text = transcribe_file(args.audio_file, api_key)
    except RuntimeError as exc:
        parser.exit(1, f"Error: {exc}\n")

    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
