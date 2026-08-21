#!/usr/bin/env python3
"""
run.py — Launch the MacPocket web server.

Usage:
    python run.py              # plain HTTP, or HTTPS if ./certs has a cert
    python run.py --tunnel     # also expose a public HTTPS URL via cloudflared

Mobile browsers (iOS Safari in particular) block microphone access on
non-HTTPS, non-localhost origins. Without --tunnel, MacPocket looks for a
TLS certificate in ./certs (cert.pem/key.pem, e.g. from mkcert) and serves
over HTTPS if found — see README.md. With --tunnel, MacPocket instead
opens a public https://*.trycloudflare.com URL via cloudflared, which
works from any device with internet access (not just your Wi-Fi) and
needs no certificate setup at all. The two are mutually exclusive: when
tunneling, the local server runs over plain HTTP (cloudflared terminates
HTTPS for you), and any local certs are ignored.
"""

import argparse
import json
from pathlib import Path

import uvicorn

from config import SERVER_HOST, SERVER_PORT, TUNNEL_INFO_FILE
from tunnel import TunnelError, start_tunnel


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="Launch the MacPocket web server.",
    )
    parser.add_argument(
        "--tunnel",
        action="store_true",
        help=(
            "Expose a public HTTPS URL via cloudflared (or pyngrok as a "
            "fallback), so any device with internet access -- not just your "
            "Wi-Fi -- can record. No manual certificate setup needed."
        ),
    )
    return parser.parse_args(argv)


def _print_boxed(lines) -> None:
    width = max(len(line) for line in lines) + 4
    print("+" + "-" * width + "+")
    for line in lines:
        print("| " + line.ljust(width - 2) + " |")
    print("+" + "-" * width + "+")


def _write_tunnel_info(url: str, provider: str) -> None:
    TUNNEL_INFO_FILE.parent.mkdir(parents=True, exist_ok=True)
    TUNNEL_INFO_FILE.write_text(json.dumps({"url": url, "provider": provider}))


def _clear_tunnel_info() -> None:
    TUNNEL_INFO_FILE.unlink(missing_ok=True)


def main() -> None:
    args = parse_args()
    tunnel = None
    ssl_kwargs = {}

    if args.tunnel:
        print("[MacPocket] Starting public tunnel...")
        try:
            tunnel = start_tunnel(SERVER_PORT)
        except TunnelError as exc:
            print(str(exc))
            raise SystemExit(1) from exc

        _write_tunnel_info(tunnel.url, tunnel.provider)
        print()
        _print_boxed([
            "MacPocket is available at:",
            tunnel.url,
            "(open this on any device, or scan the QR code in the web UI)",
        ])
        print()
        print(f"[MacPocket] Local server still running at http://{SERVER_HOST}:{SERVER_PORT} "
              "-- any local mkcert certificate in ./certs is ignored while tunneling.")
    else:
        cert_dir = Path(__file__).parent / "certs"
        certfile = cert_dir / "cert.pem"
        keyfile = cert_dir / "key.pem"
        if certfile.is_file() and keyfile.is_file():
            ssl_kwargs = {"ssl_certfile": str(certfile), "ssl_keyfile": str(keyfile)}
            print(f"[MacPocket] TLS certificate found — serving over HTTPS on "
                  f"{SERVER_HOST}:{SERVER_PORT}")
        else:
            print(f"[MacPocket] No TLS certificate in ./certs — serving over plain "
                  f"HTTP on {SERVER_HOST}:{SERVER_PORT}.")
            print("[MacPocket] NOTE: phones (especially iOS Safari) block microphone "
                  "access on non-HTTPS, non-localhost pages. Run with --tunnel for "
                  "zero-config HTTPS, or see README.md to set up local HTTPS.")

    try:
        uvicorn.run("main:app", host=SERVER_HOST, port=SERVER_PORT, reload=True, **ssl_kwargs)
    finally:
        if tunnel:
            print("\n[MacPocket] Shutting down tunnel...")
            tunnel.stop()
            _clear_tunnel_info()


if __name__ == "__main__":
    main()
