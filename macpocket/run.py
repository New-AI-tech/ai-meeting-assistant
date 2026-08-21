#!/usr/bin/env python3
"""
run.py — Launch the MacPocket web server.

Usage: python run.py

Looks for a TLS certificate in ./certs (cert.pem/key.pem) and serves over
HTTPS if found. Mobile browsers (iOS Safari in particular) block
microphone access on non-HTTPS, non-localhost origins, so phones on your
Wi-Fi need HTTPS to record — see README.md for how to generate a local
certificate with mkcert. Without one, MacPocket still runs over plain
HTTP; the local machine (via localhost) can record, but other devices
will hit the browser's mic-permission block.
"""

from pathlib import Path

import uvicorn

from config import SERVER_HOST, SERVER_PORT


def main() -> None:
    cert_dir = Path(__file__).parent / "certs"
    certfile = cert_dir / "cert.pem"
    keyfile = cert_dir / "key.pem"

    ssl_kwargs = {}
    if certfile.is_file() and keyfile.is_file():
        ssl_kwargs = {"ssl_certfile": str(certfile), "ssl_keyfile": str(keyfile)}
        print(f"[MacPocket] TLS certificate found — serving over HTTPS on "
              f"{SERVER_HOST}:{SERVER_PORT}")
    else:
        print(f"[MacPocket] No TLS certificate in ./certs — serving over plain "
              f"HTTP on {SERVER_HOST}:{SERVER_PORT}.")
        print("[MacPocket] NOTE: phones (especially iOS Safari) block microphone "
              "access on non-HTTPS, non-localhost pages. To record from another "
              "device on your network, set up local HTTPS — see README.md.")

    uvicorn.run("main:app", host=SERVER_HOST, port=SERVER_PORT, reload=True, **ssl_kwargs)


if __name__ == "__main__":
    main()
