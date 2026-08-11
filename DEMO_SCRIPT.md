# Demo Video Script (Target: 4-5 Minutes)

The assignment recommends a demo of up to about five minutes. Keep the server terminal visible whenever possible so the worker-thread names can be seen.

## 0:00-0:25 - Repository and project structure

Show the GitHub repository. Point out:

- `server.py`
- `static/` and its approved subdirectories
- `tests/`
- the demo scripts

Say briefly: the implementation uses Python's low-level `socket` API and `threading`, with no web framework.

## 0:25-0:50 - Start the server

Run:

```bash
python server.py --verbose
```

Point out the local address and port. Mention that `accept()` receives clients and each accepted socket is handed to a new worker thread.

## 0:50-1:35 - Static files in the browser

Open:

```text
http://127.0.0.1:8080/
```

Show that the page, CSS, and image render. Open Developer Tools -> Network and select a resource. Show:

- `200 OK`
- `Content-Length`
- `Content-Type`

Also open one subdirectory resource, for example:

```text
http://127.0.0.1:8080/pages/about.html
```

## 1:35-2:10 - Raw HTTP/1.0 response with curl

Run:

```bash
curl --http1.0 -v http://127.0.0.1:8080/index.html
```

Point out:

- request line using HTTP/1.0
- `HTTP/1.0 200 OK`
- `Content-Length`
- `Content-Type`
- the blank line separating headers from the body

## 2:10-2:50 - Error and security responses

Run:

```bash
python demo_requests.py
```

Point out the `400`, `403`, and `404` results.

Then show encoded traversal explicitly:

```bash
curl --http1.0 -v --path-as-is http://127.0.0.1:8080/%2e%2e/server.py
```

Explain that the URL is decoded before the `..` check, so the request is blocked with `403 Forbidden`.

## 2:50-3:30 - Prove slow-client concurrency

Run:

```bash
python demo_slow_client.py
```

Explain that one client deliberately leaves its headers incomplete, so its worker thread is waiting in `recv()`. The second client still receives `200 OK` immediately. This proves one slow client does not block the server.

## 3:30-4:00 - Many simultaneous clients

Run:

```bash
python demo_concurrent.py --clients 30
```

Show that all clients succeed. In the server terminal, point out the different thread names handling requests.

## 4:00-4:35 - Automated tests

Run:

```bash
python -m unittest discover -s tests -v
```

Show that all tests pass. Mention the partial-read test, traversal tests, response-format test, slow-client test, and 30-client test.

## 4:35-4:55 - Submission proof

Show the top of `README.md` with:

- student name(s)
- student ID(s)
- working demo-video link

Finally show that the GitHub repository is public, or state that course staff access has been granted.
