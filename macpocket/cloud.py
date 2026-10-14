"""Cloud entry point with resource-safe defaults.

The regular application remains local-first.  Hosted workers, however, must
not attempt to download and initialize a local Whisper/PyTorch model during an
HTTP request: doing so can kill the worker and surface as a gateway 502.
"""

import os


# Set this before importing ``main`` (and therefore ``config``). Deployments
# can still override it, but the checked-in cloud entry point is safe without
# relying on an undocumented provider-specific environment variable.
os.environ.setdefault("TRANSCRIPTION_BACKEND", "openai")

from .main import app  # noqa: E402  (configuration must precede app import)


__all__ = ["app"]
