"""
macpocket package.

The modules in this package (main.py, config.py, transcriber.py, ...) use
flat imports (`from config import ...`) rather than relative ones, so
that `python run.py` / `python cli.py` keep working unmodified when run
directly from inside this directory. That only resolves correctly when
this directory itself is on sys.path.

Running `python run.py` from inside macpocket/ already puts this
directory on sys.path automatically (Python does that for the script's
own directory). But when this package is imported from *outside* --
e.g. FastAPI Cloud loading the app via the "macpocket.main:app"
entrypoint from the repo root -- this directory is normally not on
sys.path. Add it here, at package-import time, so both invocation
styles work without duplicating every module's import style.
"""

import sys
from pathlib import Path

_PACKAGE_DIR = str(Path(__file__).resolve().parent)
if _PACKAGE_DIR not in sys.path:
    sys.path.insert(0, _PACKAGE_DIR)
