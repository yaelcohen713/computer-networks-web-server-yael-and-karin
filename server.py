#!/usr/bin/env python3
"""A small multi-threaded HTTP/1.0 static-file server.

This implementation intentionally uses only Python's low-level socket API and
standard-library helpers. It does not use a web framework or an existing HTTP
server implementation.
"""

from __future__ import annotations

import argparse
import html
import logging
import mimetypes
import socket
import threading
from pathlib import Path
from typing import Final
from urllib.parse import unquote, urlsplit

CRLF: Final[bytes] = b"\r\n"
HEADER_TERMINATOR: Final[bytes] = b"\r\n\r\n"
MAX_HEADER_SIZE: Final[int] = 64 * 1024
RECV_CHUNK_SIZE: Final[int] = 4096
CLIENT_TIMEOUT_SECONDS: Final[float] = 10.0

STATUS_REASONS: Final[dict[int, str]] = {
    200: "OK",
    400: "Bad Request",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    414: "URI Too Long",
    431: "Request Header Fields Too Large",
    500: "Internal Server Error",
    505: "HTTP Version Not Supported",
}


class RequestError(Exception):
    """An HTTP error that can safely be returned to the client."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class MultiThreadedHTTPServer:
    """Thread-per-connection HTTP/1.0 server for static files."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        static_root: str | Path = "static",
        allowed_directories: set[str] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.static_root = Path(static_root).resolve()
        self.allowed_directories = allowed_directories or {
            "css",
            "images",
            "pages",
            "documents",
        }
        self._server_socket: socket.socket | None = None
        self._shutdown_event = threading.Event()
        self._client_threads: set[threading.Thread] = set()
        self._threads_lock = threading.Lock()

    @property
    def bound_port(self) -> int:
        """Return the actual port after binding (useful when port=0 in tests)."""
        if self._server_socket is None:
            return self.port
        return int(self._server_socket.getsockname()[1])

    def start(self) -> None:
        """Create, bind, and listen on the TCP socket."""
        if not self.static_root.is_dir():
            raise FileNotFoundError(f"Static root does not exist: {self.static_root}")

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(128)
        server_socket.settimeout(0.5)
        self._server_socket = server_socket
        logging.info(
            "Serving %s on http://%s:%d",
            self.static_root,
            self.host,
            self.bound_port,
        )

    def serve_forever(self) -> None:
        """Accept clients and dispatch each connection to a new thread."""
        if self._server_socket is None:
            self.start()

        assert self._server_socket is not None
        try:
            while not self._shutdown_event.is_set():
                try:
                    client_socket, client_address = self._server_socket.accept()
                except socket.timeout:
                    self._remove_finished_threads()
                    continue
                except OSError:
                    if self._shutdown_event.is_set():
                        break
                    raise

                worker = threading.Thread(
                    target=self._handle_client_safely,
                    args=(client_socket, client_address),
                    daemon=True,
                    name=f"client-{client_address[0]}:{client_address[1]}",
                )
                with self._threads_lock:
                    self._client_threads.add(worker)
                worker.start()
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Stop accepting new clients and wait briefly for workers to finish."""
        if self._shutdown_event.is_set() and self._server_socket is None:
            return

        self._shutdown_event.set()
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None

        current = threading.current_thread()
        with self._threads_lock:
            workers = list(self._client_threads)
        for worker in workers:
            if worker is not current:
                worker.join(timeout=1.0)

    def _remove_finished_threads(self) -> None:
        with self._threads_lock:
            self._client_threads = {
                thread for thread in self._client_threads if thread.is_alive()
            }

    def _handle_client_safely(
        self, client_socket: socket.socket, client_address: tuple[str, int]
    ) -> None:
        try:
            self._handle_client(client_socket, client_address)
        except Exception:
            logging.exception("Unexpected error while handling %s", client_address)
            try:
                self._send_error(client_socket, 500, "Unexpected server error.")
            except OSError:
                pass
        finally:
            try:
                client_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            client_socket.close()
            with self._threads_lock:
                self._client_threads.discard(threading.current_thread())

    def _handle_client(
        self, client_socket: socket.socket, client_address: tuple[str, int]
    ) -> None:
        client_socket.settimeout(CLIENT_TIMEOUT_SECONDS)

        try:
            raw_headers = self._read_headers(client_socket)
            method, target, version = self._parse_request_line(raw_headers)
            logging.info("%s %s from %s", method, target, client_address)

            if method != "GET":
                raise RequestError(405, "Only the GET method is supported.")
            if version not in {"HTTP/1.0", "HTTP/1.1"}:
                raise RequestError(505, "Only HTTP/1.0 and HTTP/1.1 requests are accepted.")

            file_path = self._resolve_target(target)
            if not file_path.is_file():
                raise RequestError(404, "The requested resource does not exist.")

            body = file_path.read_bytes()
            content_type = self._guess_content_type(file_path)
            self._send_response(client_socket, 200, body, content_type)

        except socket.timeout:
            self._send_error(client_socket, 400, "The request timed out.")
        except UnicodeDecodeError:
            self._send_error(client_socket, 400, "The request header must be valid ASCII text.")
        except RequestError as error:
            self._send_error(client_socket, error.status_code, error.message)
        except OSError:
            logging.exception("Socket or file error while handling %s", client_address)
            self._send_error(client_socket, 500, "Unable to complete the request.")

    @staticmethod
    def _read_headers(client_socket: socket.socket) -> bytes:
        """Read until CRLF CRLF, correctly handling partial TCP reads."""
        buffer = bytearray()

        while HEADER_TERMINATOR not in buffer:
            chunk = client_socket.recv(RECV_CHUNK_SIZE)
            if not chunk:
                raise RequestError(400, "Connection closed before the HTTP header ended.")
            buffer.extend(chunk)
            if len(buffer) > MAX_HEADER_SIZE:
                raise RequestError(431, "The request header is too large.")

        header_end = buffer.index(HEADER_TERMINATOR) + len(HEADER_TERMINATOR)
        return bytes(buffer[:header_end])

    @staticmethod
    def _parse_request_line(raw_headers: bytes) -> tuple[str, str, str]:
        """Extract method, request target, and HTTP version from the first line."""
        text = raw_headers.decode("ascii", errors="strict")
        lines = text.split("\r\n")
        if not lines or not lines[0]:
            raise RequestError(400, "Missing request line.")

        parts = lines[0].split()
        if len(parts) != 3:
            raise RequestError(
                400,
                "The request line must contain METHOD, PATH, and HTTP VERSION.",
            )

        method, target, version = parts
        if not target.startswith("/"):
            raise RequestError(400, "The request target must start with '/'.")
        if len(target) > 2048:
            raise RequestError(414, "The requested URI is too long.")
        if not version.startswith("HTTP/"):
            raise RequestError(400, "Malformed HTTP version.")

        return method.upper(), target, version

    def _resolve_target(self, target: str) -> Path:
        """Safely map a URL path to a file below the static root."""
        split_target = urlsplit(target)
        # A normal origin-form request target is a local path (for example /index.html).
        # Reject network-path/absolute forms so they cannot be interpreted ambiguously.
        if split_target.scheme or split_target.netloc:
            raise RequestError(400, "The request target must be a local path.")

        try:
            decoded_path = unquote(split_target.path, errors="strict")
        except UnicodeDecodeError as exc:
            raise RequestError(400, "The URL contains invalid percent encoding.") from exc

        if "\x00" in decoded_path:
            raise RequestError(400, "The URL contains a null byte.")

        decoded_path = decoded_path.replace("\\", "/")
        segments = [segment for segment in decoded_path.split("/") if segment]

        # Reject traversal before path normalization, including percent-decoded forms.
        if any(segment == ".." for segment in segments):
            raise RequestError(403, "Directory traversal is forbidden.")

        if not segments:
            segments = ["index.html"]

        # Root-level files are allowed. Any subdirectory must be explicitly allowed.
        if len(segments) > 1 and segments[0] not in self.allowed_directories:
            raise RequestError(403, "Access to this subdirectory is forbidden.")

        candidate = self.static_root.joinpath(*segments).resolve()
        try:
            candidate.relative_to(self.static_root)
        except ValueError as exc:
            raise RequestError(403, "The requested path escapes the static root.") from exc

        return candidate

    @staticmethod
    def _guess_content_type(file_path: Path) -> str:
        guessed, _ = mimetypes.guess_type(file_path.name)
        content_type = guessed or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {
            "application/javascript",
            "application/json",
        }:
            return f"{content_type}; charset=utf-8"
        return content_type

    def _send_error(
        self, client_socket: socket.socket, status_code: int, message: str
    ) -> None:
        reason = STATUS_REASONS.get(status_code, "Error")
        safe_message = html.escape(message)
        body = (
            "<!doctype html>\n"
            '<html lang="en">\n'
            '<head><meta charset="utf-8"><title>'
            f"{status_code} {reason}</title></head>\n"
            "<body>"
            f"<h1>{status_code} {reason}</h1><p>{safe_message}</p>"
            "</body></html>\n"
        ).encode("utf-8")

        extra_headers: dict[str, str] = {}
        if status_code == 405:
            extra_headers["Allow"] = "GET"
        self._send_response(
            client_socket,
            status_code,
            body,
            "text/html; charset=utf-8",
            extra_headers,
        )

    @staticmethod
    def _send_response(
        client_socket: socket.socket,
        status_code: int,
        body: bytes,
        content_type: str,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        reason = STATUS_REASONS.get(status_code, "Unknown")
        header_lines = [
            f"HTTP/1.0 {status_code} {reason}",
            f"Content-Length: {len(body)}",
            f"Content-Type: {content_type}",
            "Connection: close",
        ]
        if extra_headers:
            header_lines.extend(f"{name}: {value}" for name, value in extra_headers.items())

        response_head = ("\r\n".join(header_lines) + "\r\n\r\n").encode("ascii")
        client_socket.sendall(response_head + body)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Multi-threaded HTTP/1.0 static-file server"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Address to bind")
    parser.add_argument("--port", type=int, default=8080, help="TCP port to bind")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).parent / "static"),
        help="Static files root directory",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable detailed logging"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(threadName)s] %(levelname)s: %(message)s",
    )

    server = MultiThreadedHTTPServer(args.host, args.port, args.root)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Stopping server...")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
