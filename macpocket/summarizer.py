"""
summarizer.py — Summarization and action-item extraction.

Supports two interchangeable backends:
  - "local":  Ollama running the llama3.2 model on-device.
  - "openai": OpenAI's GPT-4o-mini via API (requires OPENAI_API_KEY).
"""

import os

from config import (
    OLLAMA_INSTALL_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY_ENV_VAR,
    OPENAI_MODEL,
    SUMMARY_BACKENDS,
    SUMMARY_PROMPT_TEMPLATE,
)


class SummarizationError(Exception):
    """Raised when a summary cannot be produced."""


def summarize(transcript: str, backend: str = "local") -> str:
    """
    Produce a 3-bullet summary + action-item checklist from a transcript,
    using the requested backend ("local" or "openai").
    """
    if backend not in SUMMARY_BACKENDS:
        raise SummarizationError(
            f"Unknown summarization backend '{backend}'. Choose from: "
            f"{', '.join(SUMMARY_BACKENDS)}"
        )

    if not transcript.strip():
        raise SummarizationError(
            "The transcript is empty, so there is nothing to summarize."
        )

    prompt = SUMMARY_PROMPT_TEMPLATE.format(transcript=transcript)

    if backend == "local":
        return _summarize_with_ollama(prompt)
    return _summarize_with_openai(prompt)


def _summarize_with_ollama(prompt: str) -> str:
    try:
        import ollama
    except ImportError as exc:
        raise SummarizationError(
            "\n[MacPocket] The 'ollama' Python package is not installed.\n"
            "Install it with:\n"
            "    pip install -r requirements.txt\n"
        ) from exc

    print(f"[MacPocket] Summarizing locally with Ollama ('{OLLAMA_MODEL}')...")
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        raise SummarizationError(
            "\n[MacPocket] Could not reach Ollama, or the "
            f"'{OLLAMA_MODEL}' model isn't available locally.\n\n"
            "1. Install Ollama (if you haven't already):\n"
            f"   {OLLAMA_INSTALL_URL}\n"
            "2. Make sure the Ollama app/daemon is running.\n"
            "3. Pull the model:\n"
            f"    ollama pull {OLLAMA_MODEL}\n\n"
            f"Original error: {exc}\n"
        ) from exc

    content = response.get("message", {}).get("content", "").strip()
    if not content:
        raise SummarizationError("[MacPocket] Ollama returned an empty response.")
    return content


def _summarize_with_openai(prompt: str) -> str:
    api_key = os.environ.get(OPENAI_API_KEY_ENV_VAR)
    if not api_key:
        raise SummarizationError(
            "\n[MacPocket] The OpenAI backend requires an API key.\n"
            f"Set the {OPENAI_API_KEY_ENV_VAR} environment variable, e.g.:\n"
            f'    export {OPENAI_API_KEY_ENV_VAR}="sk-..."\n'
            "or add it to a .env file in this directory.\n"
        )

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise SummarizationError(
            "\n[MacPocket] The 'openai' package is not installed.\n"
            "Install it with:\n"
            "    pip install openai\n"
        ) from exc

    print(f"[MacPocket] Summarizing with OpenAI ('{OPENAI_MODEL}')...")
    client = OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
    except Exception as exc:
        raise SummarizationError(
            f"[MacPocket] OpenAI API request failed: {exc}"
        ) from exc

    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise SummarizationError("[MacPocket] OpenAI returned an empty response.")
    return content
