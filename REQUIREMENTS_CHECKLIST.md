# Assignment Requirements Checklist

This file maps the assignment requirements directly to the submitted implementation so they are easy to verify.

| Assignment requirement | Where it is implemented / demonstrated | Status |
|---|---|---|
| Low-level networking API only | `server.py` uses Python `socket`; no web framework | PASS |
| Bind and listen on a TCP port | `MultiThreadedHTTPServer.start()` | PASS |
| Accept incoming TCP connections | `serve_forever()` calls `accept()` | PASS |
| Handle partial reads | `_read_headers()` buffers repeated `recv()` calls | PASS |
| Read until `\r\n\r\n` | `_read_headers()` checks `HEADER_TERMINATOR` | PASS |
| Parse method, path, HTTP version | `_parse_request_line()` | PASS |
| Support GET static files | `_handle_client()` + `_resolve_target()` | PASS |
| At least five static files in subdirectories | Six files under `css/`, `images/`, `pages/`, `documents/` | PASS |
| Allow selected subdirectories | `allowed_directories` set | PASS |
| Block other subdirectories | `_resolve_target()` returns `403` | PASS |
| Prevent `..` traversal | `_resolve_target()` rejects `..` after URL decoding | PASS |
| Prevent escaping static root | `Path.resolve()` + `relative_to(static_root)` | PASS |
| HTTP/1.0 status line | `_send_response()` | PASS |
| `Content-Length` header | `_send_response()` | PASS |
| `Content-Type` header | `_guess_content_type()` + `_send_response()` | PASS |
| Blank line before body | response uses `\r\n\r\n` | PASS |
| Raw file bytes in body | `read_bytes()` + `sendall()` | PASS |
| `200 OK` | successful resource tests | PASS |
| `400 Bad Request` | malformed request handling | PASS |
| `404 Not Found` | missing resource handling | PASS |
| Stateless behavior | one request/response per connection, then close | PASS |
| Concurrent clients | one worker `threading.Thread` per accepted client | PASS |
| Slow client must not block others | `demo_slow_client.py` + automated test | PASS |
| Browser verification | instructions in `README.md` and `DEMO_SCRIPT.md` | READY TO RECORD |
| `curl -v` verification | commands in `README.md` and `DEMO_SCRIPT.md` | READY TO RECORD |
| Demo video link in README | placeholder at top of `README.md` | MUST COMPLETE |
| GitHub repository | upload instructions in `README.md` | MUST COMPLETE |
| Repository public/shared with staff | final checklist in `README.md` | MUST COMPLETE |
| Student name and ID | placeholders in `README.md` | MUST COMPLETE |

## Final human-only items

The code portion is ready to test and submit, but the following cannot be completed automatically:

1. Student name(s) and ID(s).
2. Recording and uploading the demo video.
3. Pasting the demo link into the README.
4. Uploading/pushing the repository to the student's GitHub account.
5. Making the repository public or granting the course staff access.
