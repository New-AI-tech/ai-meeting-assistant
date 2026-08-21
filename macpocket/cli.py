#!/usr/bin/env python3
"""
cli.py — MacPocket command-line interface (terminal-only fallback).

The primary way to use MacPocket is now the web app (`python run.py`,
see main.py). This CLI records a meeting from a microphone or system
audio (via BlackHole) directly in the terminal, transcribes it locally
with Whisper, and produces a summary + action items — useful for
debugging the recording/transcription/summarization pipeline without a
browser in the loop.

Usage: python cli.py [options]  (see --help)
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from config import (
    DEFAULT_BACKEND,
    DEFAULT_FP16,
    DEFAULT_MEETING_TITLE,
    DEFAULT_WHISPER_MODEL,
    FILENAME_PREFIX,
    FILENAME_TIMESTAMP_FMT,
    NOTES_DIR,
    SAMPLE_RATE,
    SUMMARY_BACKENDS,
    WHISPER_MODELS,
)
from recorder import (
    BlackHoleNotInstalledError,
    DeviceNotFoundError,
    Recorder,
    resolve_device,
)
from summarizer import SummarizationError, summarize
from transcriber import TranscriptionError, transcribe_audio


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="macpocket-cli",
        description="MacPocket CLI — terminal-only fallback for debugging the record/transcribe/summarize pipeline.",
    )
    parser.add_argument(
        "-d", "--device",
        type=str,
        default=None,
        help=(
            "Input device name (e.g. 'BlackHole 2ch' or 'MacBook Pro "
            "Microphone'). If omitted, MacPocket lists available devices "
            "and lets you choose interactively."
        ),
    )
    parser.add_argument(
        "-b", "--backend",
        type=str,
        choices=SUMMARY_BACKENDS,
        default=DEFAULT_BACKEND,
        help=f"Summarization backend to use. Default: '{DEFAULT_BACKEND}'.",
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        choices=WHISPER_MODELS,
        default=DEFAULT_WHISPER_MODEL,
        help=f"Whisper model size for transcription. Default: '{DEFAULT_WHISPER_MODEL}'.",
    )
    parser.add_argument(
        "-t", "--duration",
        type=float,
        default=None,
        help="Fixed recording duration in seconds. If omitted, records until CTRL+C.",
    )
    parser.add_argument(
        "--fp16",
        action="store_true",
        default=DEFAULT_FP16,
        help=(
            "Enable fp16 inference for Whisper (faster on Apple Silicon "
            "M1/M2/M3). Leave disabled on Intel Macs to avoid instability."
        ),
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Title for the meeting note. Defaults to a prompt at save time.",
    )
    return parser.parse_args(argv)


def ensure_notes_dir() -> Path:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    return NOTES_DIR


def build_output_path() -> Path:
    timestamp = datetime.now().strftime(FILENAME_TIMESTAMP_FMT)
    filename = f"{FILENAME_PREFIX}{timestamp}.txt"
    return NOTES_DIR / filename


def write_note(path: Path, title: str, transcript: str, summary: str) -> None:
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
    path.write_text(content, encoding="utf-8")


def main(argv=None) -> int:
    load_dotenv()
    args = parse_args(argv)

    print("MacPocket — AI voice note-taker for macOS\n")

    # --- Resolve audio device -------------------------------------------
    try:
        device = resolve_device(args.device)
    except BlackHoleNotInstalledError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except DeviceNotFoundError as exc:
        print(f"[MacPocket] {exc}", file=sys.stderr)
        return 1

    print(f"[MacPocket] Using input device: {device['name']} (index {device['index']})")

    channels = min(2, max(1, device.get("max_input_channels", 1)))

    # --- Record ------------------------------------------------------------
    recorder = Recorder(
        device_index=device["index"],
        sample_rate=SAMPLE_RATE,
        channels=channels,
    )
    try:
        audio = recorder.record(duration=args.duration)
    except Exception as exc:
        print(f"[MacPocket] Recording failed: {exc}", file=sys.stderr)
        return 1

    if audio.size == 0:
        print("[MacPocket] No audio was captured. Exiting without saving a note.",
              file=sys.stderr)
        return 1

    # --- Transcribe ------------------------------------------------------
    try:
        transcript = transcribe_audio(
            audio,
            model_size=args.model,
            sample_rate=SAMPLE_RATE,
            fp16=args.fp16,
        )
    except TranscriptionError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not transcript.strip():
        print("[MacPocket] Whisper produced an empty transcript "
              "(silence or inaudible audio). Exiting without saving a note.",
              file=sys.stderr)
        return 1

    # --- Summarize -------------------------------------------------------
    try:
        summary = summarize(transcript, backend=args.backend)
    except SummarizationError as exc:
        print(str(exc), file=sys.stderr)
        print("\n[MacPocket] Saving the transcript anyway (without a summary).\n",
              file=sys.stderr)
        summary = "(Summary unavailable — see error above.)"

    # --- Save + print ------------------------------------------------------
    title = args.title
    if not title:
        try:
            title = input(f"\nMeeting title [{DEFAULT_MEETING_TITLE}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            title = ""
        if not title:
            title = DEFAULT_MEETING_TITLE

    ensure_notes_dir()
    output_path = build_output_path()
    write_note(output_path, title, transcript, summary)

    print(f"\n[MacPocket] Note saved to: {output_path}\n")
    print("=" * 60)
    print(summary)
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
