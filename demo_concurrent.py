#!/usr/bin/env python3
"""Open many simultaneous connections to demonstrate concurrency."""

from __future__ import annotations

import argparse
import socket
import time
from concurrent.futures import ThreadPoolExecutor

PATHS = [
    "/index.html",
    "/pages/about.html",
    "/pages/contact.html",
    "/css/style.css",
    "/images/network.svg",
    "/documents/info.txt",
]


def fetch(host: str, port: int, number: int) -> tuple[int, str, int]:
    path = PATHS[number % len(PATHS)]
    request = f"GET {path} HTTP/1.0\r\nHost: localhost\r\n\r\n".encode("ascii")
    with socket.create_connection((host, port), timeout=4.0) as sock:
        sock.sendall(request)
        response = bytearray()
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response.extend(chunk)
    status = response.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
    return number, status, len(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--clients", type=int, default=30)
    args = parser.parse_args()

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=min(args.clients, 30)) as pool:
        results = list(
            pool.map(
                lambda number: fetch(args.host, args.port, number),
                range(args.clients),
            )
        )
    elapsed = time.perf_counter() - started

    for number, status, byte_count in results:
        print(f"Client {number + 1:02d}: {status} ({byte_count} bytes)")
    success_count = sum("200 OK" in status for _, status, _ in results)
    print(f"\nCompleted {success_count}/{args.clients} successfully in {elapsed:.3f}s")


if __name__ == "__main__":
    main()
