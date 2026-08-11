#!/usr/bin/env python3
"""Send raw requests that are useful during the assignment demo video."""

from __future__ import annotations

import argparse
import socket

CASES = {
    "200 OK": b"GET /index.html HTTP/1.0\r\nHost: localhost\r\n\r\n",
    "400 Bad Request": b"THIS IS NOT HTTP\r\n\r\n",
    "403 Forbidden directory": (
        b"GET /private/secret.txt HTTP/1.0\r\nHost: localhost\r\n\r\n"
    ),
    "403 Directory traversal": (
        b"GET /../server.py HTTP/1.0\r\nHost: localhost\r\n\r\n"
    ),
    "404 Not Found": (
        b"GET /does-not-exist.html HTTP/1.0\r\nHost: localhost\r\n\r\n"
    ),
}


def send_request(host: str, port: int, request: bytes) -> bytes:
    with socket.create_connection((host, port), timeout=3.0) as sock:
        sock.sendall(request)
        response = bytearray()
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                return bytes(response)
            response.extend(chunk)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    for title, request in CASES.items():
        response = send_request(args.host, args.port, request)
        status_line = response.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
        print(f"{title:28} -> {status_line}")


if __name__ == "__main__":
    main()
