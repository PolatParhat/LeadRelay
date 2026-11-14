"""A tiny scripted web server on this Mac, used instead of the real internet in tests.

    server = FakeHttpServer()
    server.replies = [(500, b""), (200, b"ok")]   # answers given in this order
    ... code under test calls server.url ...
    server.requests                              # what the code sent us
    server.responder = lambda method, path: (200, b"...")  # or: answer by request path

Requests are handled one at a time, in the order they arrive.
"""

import http.server
import threading


class FakeHttpServer:
    def __init__(self):
        self.replies = []   # list of (status, body) or (status, body, headers)
        self.requests = []  # list of {"method", "path", "headers", "body"}
        self.responder = None  # optional function (method, path) -> reply; wins over `replies`
        fake = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def _handle(self):
                length = int(self.headers.get("Content-Length") or 0)
                fake.requests.append({
                    "method": self.command,
                    "path": self.path,
                    "headers": dict(self.headers),
                    "body": self.rfile.read(length),
                })
                if fake.responder is not None:
                    reply = fake.responder(self.command, self.path)
                else:
                    reply = fake.replies.pop(0) if fake.replies else (403, b"")
                status, body, headers = (reply + ({},))[:3]
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(body)

            do_GET = _handle
            do_POST = _handle

            def log_message(self, *args):  # keep test output quiet
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)  # port 0 = any free port
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        ).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
