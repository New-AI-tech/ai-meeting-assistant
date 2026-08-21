"""
tunnel.py — Zero-config public HTTPS tunnel for MacPocket.

Wraps `cloudflared`'s quick-tunnel mode (no Cloudflare account or signup
required) to get a public `https://*.trycloudflare.com` URL that proxies
to the local server. This gives phones a real HTTPS origin without
manually setting up mkcert, which sidesteps browsers blocking
`getUserMedia`/`getDisplayMedia` on insecure origins. Falls back to
pyngrok if cloudflared isn't installed but pyngrok is.
"""

import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

CLOUDFLARE_URL_RE = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

INSTALL_HELP = (
    "\n[MacPocket] Couldn't start a public tunnel.\n\n"
    "Install cloudflared (recommended, no account needed):\n"
    "    brew install cloudflared\n"
    "or download it from:\n"
    "    https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/\n\n"
    "Alternatively, install pyngrok as a fallback:\n"
    "    pip install pyngrok\n"
    "(requires a free ngrok account + authtoken configured -- see "
    "https://dashboard.ngrok.com)\n"
)


class TunnelError(Exception):
    """Raised when a public tunnel could not be established."""


@dataclass
class Tunnel:
    provider: str
    url: str
    _stop: Callable[[], None]

    def stop(self) -> None:
        try:
            self._stop()
        except Exception:
            pass


def start_tunnel(port: int, timeout: float = 30.0) -> Tunnel:
    """
    Start a public HTTPS tunnel to http://localhost:<port>. Tries
    cloudflared first (no account required), then pyngrok if installed.
    Raises TunnelError if neither is available, or the tunnel URL never
    appears within `timeout` seconds.
    """
    tunnel = _start_cloudflared(port, timeout)
    if tunnel is not None:
        return tunnel

    tunnel = _start_ngrok(port)
    if tunnel is not None:
        return tunnel

    raise TunnelError(INSTALL_HELP)


def _start_cloudflared(port: int, timeout: float) -> Optional[Tunnel]:
    binary = shutil.which("cloudflared")
    if not binary:
        return None

    proc = subprocess.Popen(
        [binary, "tunnel", "--url", f"http://localhost:{port}", "--no-autoupdate"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    found = {}

    def _reader() -> None:
        for line in proc.stdout:
            print(f"[cloudflared] {line.rstrip()}")
            if "url" not in found:
                match = CLOUDFLARE_URL_RE.search(line)
                if match:
                    found["url"] = match.group(0)

    threading.Thread(target=_reader, daemon=True).start()

    deadline = time.time() + timeout
    while time.time() < deadline:
        if "url" in found:
            return Tunnel(
                provider="cloudflared",
                url=found["url"],
                _stop=lambda: _stop_process(proc),
            )
        if proc.poll() is not None:
            raise TunnelError(
                "[MacPocket] cloudflared exited before reporting a tunnel URL. "
                f"Try running it manually to see the error:\n"
                f"    cloudflared tunnel --url http://localhost:{port}\n"
            )
        time.sleep(0.25)

    _stop_process(proc)
    raise TunnelError(
        f"[MacPocket] Timed out waiting {timeout:.0f}s for cloudflared to "
        "report a tunnel URL. Check your internet connection and try again."
    )


def _stop_process(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _start_ngrok(port: int) -> Optional[Tunnel]:
    try:
        from pyngrok import ngrok
    except ImportError:
        return None

    try:
        ngrok_tunnel = ngrok.connect(port, "http")
    except Exception as exc:
        print(f"[MacPocket] pyngrok tunnel failed to start: {exc}")
        return None

    public_url = ngrok_tunnel.public_url
    if public_url.startswith("http://"):
        public_url = "https://" + public_url[len("http://") :]

    return Tunnel(
        provider="ngrok",
        url=public_url,
        _stop=lambda: ngrok.disconnect(ngrok_tunnel.public_url),
    )
