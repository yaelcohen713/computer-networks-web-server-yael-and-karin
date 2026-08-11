#!/usr/bin/env python3
"""Demonstrate that one stalled client does not block another client."""

from __future__ import annotations

import argparse
import socket
import time


def receive_all(sock: socket.socket) -> bytes:
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

    # Client A deliberately sends only part of its headers and then stalls.
    slow = socket.create_connection((args.host, args.port), timeout=3.0)
    slow.sendall(b"GET /index.html HTTP/1.0\r\nHost: slow-client\r\n")
    print("Slow client: connected and intentionally left its HTTP header incomplete.")

    try:
        # While client A is still waiting, client B should still be served immediately.
        started = time.perf_counter()
        with socket.create_connection((args.host, args.port), timeout=3.0) as fast:
            fast.sendall(b"GET /pages/about.html HTTP/1.0\r\nHost: fast-client\r\n\r\n")
            response = receive_all(fast)
        elapsed = time.perf_counter() - started

        status = response.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
        print(f"Fast client: {status} in {elapsed:.3f}s while slow client was still open.")
        if status == "HTTP/1.0 200 OK":
            print("PASS: the stalled connection did not block another client.")
        else:
            raise SystemExit("FAIL: fast client did not receive 200 OK.")
    finally:
        slow.close()


if __name__ == "__main__":
    main()
