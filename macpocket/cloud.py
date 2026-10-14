"""Cloud entry point with resource-safe defaults.

The regular application remains local-first.  Hosted workers, however, must
not attempt to download and initialize a local Whisper/PyTorch model during an
HTTP request: doing so can kill the worker and surface as a gateway 502.
"""

import os


# Set this before importing ``main`` (and therefore ``config``). Assignment is
# intentional rather than ``setdefault``: an old deployment may still have
# TRANSCRIPTION_BACKEND=openai configured from an earlier release. The cloud
# entry point is specifically the AssemblyAI deployment; use ``macpocket.main``
# when an explicitly selectable backend is required.
os.environ["TRANSCRIPTION_BACKEND"] = "assemblyai"

from .main import app  # noqa: E402  (configuration must precede app import)


__all__ = ["app"]
