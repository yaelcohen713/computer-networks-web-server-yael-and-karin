#!/usr/bin/env python3
"""Integration tests for the multi-threaded socket server."""

from __future__ import annotations

import socket
import sys
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from server import MultiThreadedHTTPServer  # noqa: E402


class ServerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = MultiThreadedHTTPServer(
            host="127.0.0.1",
            port=0,
            static_root=PROJECT_ROOT / "static",
        )
        cls.server.start()
        cls.port = cls.server.bound_port
        cls.server_thread = threading.Thread(
            target=cls.server.serve_forever,
            daemon=True,
            name="test-server",
        )
        cls.server_thread.start()
        time.sleep(0.05)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server_thread.join(timeout=2.0)

    def request(self, raw_request: bytes, chunks: list[int] | None = None) -> bytes:
        with socket.create_connection(("127.0.0.1", self.port), timeout=2.0) as sock:
            if chunks:
                start = 0
                for length in chunks:
                    sock.sendall(raw_request[start : start + length])
                    start += length
                    time.sleep(0.01)
                if start < len(raw_request):
                    sock.sendall(raw_request[start:])
            else:
                sock.sendall(raw_request)

            response = bytearray()
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                response.extend(data)
            return bytes(response)

    @staticmethod
    def split_response(response: bytes) -> tuple[str, dict[str, str], bytes]:
        head, body = response.split(b"\r\n\r\n", 1)
        lines = head.decode("iso-8859-1").split("\r\n")
        status_line = lines[0]
        headers = {}
        for line in lines[1:]:
            name, value = line.split(":", 1)
            headers[name.lower()] = value.strip()
        return status_line, headers, body

    def test_root_serves_index(self) -> None:
        response = self.request(b"GET / HTTP/1.0\r\nHost: localhost\r\n\r\n")
        status, headers, body = self.split_response(response)
        self.assertEqual(status, "HTTP/1.0 200 OK")
        self.assertIn(b"Multi-Threaded HTTP/1.0 Server", body)
        self.assertEqual(int(headers["content-length"]), len(body))
        self.assertTrue(headers["content-type"].startswith("text/html"))

    def test_static_subdirectory_file(self) -> None:
        response = self.request(
            b"GET /css/style.css HTTP/1.1\r\nHost: localhost\r\n\r\n"
        )
        status, headers, body = self.split_response(response)
        self.assertEqual(status, "HTTP/1.0 200 OK")
        self.assertIn(b".hero", body)
        self.assertTrue(headers["content-type"].startswith("text/css"))

    def test_partial_tcp_reads(self) -> None:
        raw = b"GET /pages/about.html HTTP/1.0\r\nHost: localhost\r\n\r\n"
        response = self.request(raw, chunks=[2, 5, 3, 8, 1, 7])
        status, _, body = self.split_response(response)
        self.assertEqual(status, "HTTP/1.0 200 OK")
        self.assertIn(b"From raw TCP bytes", body)

    def test_missing_file_returns_404(self) -> None:
        response = self.request(
            b"GET /pages/missing.html HTTP/1.0\r\nHost: localhost\r\n\r\n"
        )
        status, _, body = self.split_response(response)
        self.assertEqual(status, "HTTP/1.0 404 Not Found")
        self.assertIn(b"404 Not Found", body)

    def test_malformed_request_returns_400(self) -> None:
        response = self.request(b"BROKEN REQUEST\r\n\r\n")
        status, _, body = self.split_response(response)
        self.assertEqual(status, "HTTP/1.0 400 Bad Request")
        self.assertIn(b"400 Bad Request", body)

    def test_unsupported_method_returns_405(self) -> None:
        response = self.request(
            b"POST /index.html HTTP/1.0\r\nHost: localhost\r\n\r\n"
        )
        status, headers, _ = self.split_response(response)
        self.assertEqual(status, "HTTP/1.0 405 Method Not Allowed")
        self.assertEqual(headers.get("allow"), "GET")

    def test_unknown_subdirectory_returns_403(self) -> None:
        response = self.request(
            b"GET /private/secret.txt HTTP/1.0\r\nHost: localhost\r\n\r\n"
        )
        status, _, body = self.split_response(response)
        self.assertEqual(status, "HTTP/1.0 403 Forbidden")
        self.assertIn(b"subdirectory", body)

    def test_plain_directory_traversal_returns_403(self) -> None:
        response = self.request(
            b"GET /../server.py HTTP/1.0\r\nHost: localhost\r\n\r\n"
        )
        status, _, _ = self.split_response(response)
        self.assertEqual(status, "HTTP/1.0 403 Forbidden")

    def test_encoded_directory_traversal_returns_403(self) -> None:
        response = self.request(
            b"GET /%2e%2e/server.py HTTP/1.0\r\nHost: localhost\r\n\r\n"
        )
        status, _, _ = self.split_response(response)
        self.assertEqual(status, "HTTP/1.0 403 Forbidden")


    def test_response_has_required_http_1_0_format(self) -> None:
        response = self.request(b"GET /documents/info.txt HTTP/1.0\r\nHost: localhost\r\n\r\n")
        head, body = response.split(b"\r\n\r\n", 1)
        lines = head.decode("ascii").split("\r\n")
        self.assertEqual(lines[0], "HTTP/1.0 200 OK")
        self.assertTrue(any(line.startswith("Content-Length: ") for line in lines[1:]))
        self.assertTrue(any(line.startswith("Content-Type: ") for line in lines[1:]))
        declared_length = next(
            int(line.split(":", 1)[1].strip())
            for line in lines[1:]
            if line.startswith("Content-Length:")
        )
        self.assertEqual(declared_length, len(body))

    def test_slow_client_does_not_block_fast_client(self) -> None:
        slow = socket.create_connection(("127.0.0.1", self.port), timeout=2.0)
        try:
            # Deliberately omit the final CRLF CRLF so this worker remains blocked in recv().
            slow.sendall(b"GET /index.html HTTP/1.0\r\nHost: slow\r\n")
            started = time.perf_counter()
            response = self.request(
                b"GET /pages/about.html HTTP/1.0\r\nHost: fast\r\n\r\n"
            )
            elapsed = time.perf_counter() - started
            status, _, _ = self.split_response(response)
            self.assertEqual(status, "HTTP/1.0 200 OK")
            self.assertLess(elapsed, 1.0)
        finally:
            slow.close()

    def test_network_path_request_target_is_rejected(self) -> None:
        response = self.request(
            b"GET //example.com/index.html HTTP/1.0\r\nHost: localhost\r\n\r\n"
        )
        status, _, _ = self.split_response(response)
        self.assertEqual(status, "HTTP/1.0 400 Bad Request")

    def test_many_concurrent_clients(self) -> None:
        paths = [
            "/index.html",
            "/pages/about.html",
            "/pages/contact.html",
            "/css/style.css",
            "/images/network.svg",
            "/documents/info.txt",
        ] * 5

        def fetch(path: str) -> str:
            raw = f"GET {path} HTTP/1.0\r\nHost: localhost\r\n\r\n".encode("ascii")
            response = self.request(raw)
            status, _, _ = self.split_response(response)
            return status

        with ThreadPoolExecutor(max_workers=15) as pool:
            statuses = list(pool.map(fetch, paths))

        self.assertEqual(len(statuses), 30)
        self.assertTrue(all(status == "HTTP/1.0 200 OK" for status in statuses))


if __name__ == "__main__":
    unittest.main(verbosity=2)
