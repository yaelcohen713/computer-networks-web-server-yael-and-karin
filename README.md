# Multi-Threaded HTTP/1.0 Web Server

**Computer Networks - Programming Assignment**

Student 1: `Yael Cohen - 216002677`
Student 2: `Karin Canarutto - 214669541`  
Demo video: `https://youtu.be/-pZ8oZrL36U`

## Project overview

This project implements a functional multi-threaded web server from scratch with Python's low-level `socket` API. The server manually manages TCP connections, reads raw byte streams, parses HTTP request lines, serves static files, constructs HTTP/1.0 responses, restricts directory access, blocks directory traversal, and handles multiple clients concurrently.

No web framework, routing framework, or existing HTTP server implementation is used.

## Requirements

- Python 3.10 or newer
- No third-party Python packages
- A browser and/or `curl` for manual verification

## Project structure

```text
multi_threaded_web_server/
|-- server.py                  # Main low-level socket server
|-- demo_requests.py           # Demonstrates 200/400/403/404 responses
|-- demo_concurrent.py         # Demonstrates many concurrent clients
|-- demo_slow_client.py        # Proves a stalled client does not block another
|-- README.md
|-- DEMO_SCRIPT.md             # Suggested demo-video flow
|-- REQUIREMENTS_CHECKLIST.md  # Assignment-to-code compliance map
|-- static/
|   |-- index.html
|   |-- css/
|   |   `-- style.css
|   |-- images/
|   |   `-- network.svg
|   |-- pages/
|   |   |-- about.html
|   |   `-- contact.html
|   `-- documents/
|       |-- info.txt
|       `-- protocol.txt
`-- tests/
    |-- test_server.py
    `-- manual_requests.txt
```

There are **six static files inside approved subdirectories** (`css`, `images`, `pages`, and `documents`), plus the root `index.html`. Any other first-level subdirectory is rejected with `403 Forbidden`.

## Running the server

From the project directory:

```bash
python server.py --verbose
```

The default address is:

```text
http://127.0.0.1:8080/
```

Optional arguments:

```bash
python server.py --host 127.0.0.1 --port 8080 --root static --verbose
```

Stop the server with `Ctrl+C`.

## Browser verification

Open:

```text
http://127.0.0.1:8080/
http://127.0.0.1:8080/index.html
http://127.0.0.1:8080/pages/about.html
http://127.0.0.1:8080/pages/contact.html
http://127.0.0.1:8080/images/network.svg
http://127.0.0.1:8080/documents/info.txt
```

Use the browser Developer Tools **Network** tab to inspect status codes, response headers, MIME types, and timing.

> Browsers normally send HTTP/1.1 request lines. The server accepts HTTP/1.0 and HTTP/1.1 request lines for browser compatibility, but it always constructs an HTTP/1.0 response, closes the connection after the response, and implements no persistent sessions or cookies.

## `curl` verification

Use `--http1.0` when demonstrating the assignment protocol explicitly.

Successful request:

```bash
curl --http1.0 -v http://127.0.0.1:8080/index.html
```

Missing file (`404`):

```bash
curl --http1.0 -v http://127.0.0.1:8080/does-not-exist.html
```

Forbidden subdirectory (`403`):

```bash
curl --http1.0 -v http://127.0.0.1:8080/private/secret.txt
```

Directory traversal (`403`):

```bash
curl --http1.0 -v --path-as-is http://127.0.0.1:8080/../server.py
```

Percent-encoded traversal (`403`):

```bash
curl --http1.0 -v --path-as-is http://127.0.0.1:8080/%2e%2e/server.py
```

## Demonstrating malformed requests

Run:

```bash
python demo_requests.py
```

It sends raw socket requests and demonstrates:

- `200 OK`
- `400 Bad Request`
- `403 Forbidden` for an unapproved directory
- `403 Forbidden` for directory traversal
- `404 Not Found`

The file `tests/manual_requests.txt` also contains requests that can be entered manually with `nc`/netcat.

## Demonstrating concurrency

Many clients at once:

```bash
python demo_concurrent.py --clients 30
```

A stronger head-of-line blocking demonstration is included as well:

```bash
python demo_slow_client.py
```

That script deliberately leaves one client's HTTP header incomplete. While that client is still stalled, a second client requests a file and should immediately receive `HTTP/1.0 200 OK`. This directly demonstrates that one slow connection does not block other clients.

## Automated tests

Run:

```bash
python -m unittest discover -s tests -v
```

The integration tests verify:

- socket-based file serving
- required HTTP/1.0 response structure
- `Content-Length` correctness
- MIME/`Content-Type` handling
- partial TCP reads until `\r\n\r\n`
- `400 Bad Request`
- `403 Forbidden` for unapproved directories
- plain and percent-encoded directory traversal blocking
- `404 Not Found`
- `405 Method Not Allowed` for non-GET methods
- rejection of ambiguous network-path request targets
- a stalled client does not block another client
- 30 concurrent successful requests

## Implementation details

### Socket lifecycle

The server creates an IPv4 TCP socket with `socket.socket(AF_INET, SOCK_STREAM)`, enables address reuse, binds to the configured address and port, calls `listen()`, and repeatedly calls `accept()` for new TCP clients.

### Robust stream reading

TCP is stream-based, so the complete HTTP header is not guaranteed to arrive in a single `recv()` call. `_read_headers()` appends received chunks to a dynamic buffer until it finds the mandatory `\r\n\r\n` marker. It also applies a maximum header size.

### HTTP request parsing

`_parse_request_line()` parses the first line into exactly three values:

```text
METHOD REQUEST-TARGET HTTP-VERSION
```

The server supports only the `GET` method for resources. A malformed request line returns `400 Bad Request`; a non-GET method returns `405 Method Not Allowed`.

### Static file serving

`_resolve_target()` maps the requested URL path to the local `static` directory. Static resources are read as raw bytes, so text and image content can both be sent. MIME types are selected with Python's `mimetypes` standard-library module.

### Directory traversal prevention

Before a file is served, the server:

1. Parses the request target as a local path.
2. Percent-decodes the URL path.
3. Converts backslashes to forward slashes.
4. Rejects any path segment equal to `..`.
5. Allows only the approved first-level subdirectories.
6. Resolves the final filesystem path.
7. Confirms that the resolved path is still inside the configured static root.

This blocks ordinary traversal, percent-encoded traversal, and paths that would escape the root through filesystem resolution.

### HTTP response format

Every response is constructed manually in this form:

```text
HTTP/1.0 <status-code> <reason-phrase>\r\n
Content-Length: <body-size>\r\n
Content-Type: <MIME-type>\r\n
Connection: close\r\n
\r\n
<body bytes>
```

The required `Content-Length` and `Content-Type` headers are included, followed by the mandatory blank line and the raw response body.

### Stateless multi-threading

Every accepted client socket is assigned to a new `threading.Thread`. A worker handles one request, sends one response, and closes that connection. The server keeps no cookies, sessions, or persistent per-client memory.

## Status codes

| Code | Meaning | Example |
|---|---|---|
| `200 OK` | Static resource served | `/index.html` |
| `400 Bad Request` | Malformed request syntax | `THIS IS NOT HTTP` |
| `403 Forbidden` | Traversal or disallowed directory | `/../server.py` |
| `404 Not Found` | File does not exist | `/missing.html` |
| `405 Method Not Allowed` | Method other than GET | `POST /index.html` |
| `414 URI Too Long` | Request target exceeds the limit | More than 2048 characters |
| `431 Request Header Fields Too Large` | Header exceeds the configured limit | Oversized header |
| `505 HTTP Version Not Supported` | Unsupported HTTP version | `HTTP/2.0` request line |

The assignment-required success/error cases (`200`, `400`, `404`) are included; `403` is used for forbidden directory/security attempts, and additional standards-based errors are handled defensively.

## GitHub submission

Create a repository and push the project:

```bash
git init
git add .
git commit -m "Implement multi-threaded HTTP server"
git branch -M main
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

## Before submission

Do not submit until all of these are complete:

- [ ] Replace the student-name placeholder at the top of this README.
- [ ] Replace the student-ID placeholder.
- [ ] Record the demo using `DEMO_SCRIPT.md` (about five minutes or less is recommended).
- [ ] Upload the demo to YouTube or Google Drive and paste the viewable link above.
- [ ] Run the automated tests and confirm they all pass.
- [ ] Run the browser and `curl --http1.0 -v` checks.
- [ ] Push all source code and static files to GitHub.
- [ ] Make the GitHub repository public **or** share access with the course staff before the deadline.
- [ ] Verify the video link opens in a private/incognito browser window.
