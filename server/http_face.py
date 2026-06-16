"""Localhost HTTP face for a marginalia thread.

Serves the annotated page, accepts popup comments, serves reply cards, and
accepts the Done signal. Talks only to a ThreadStore. stdout is reserved for
MCP JSON-RPC, so request logging is silenced.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # never write to stdout/stderr from the request log

    @property
    def store(self):
        return self.server.store

    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            return json.loads(raw or b"{}")
        except (ValueError, TypeError):
            return {}

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, self.store.html, "text/html; charset=utf-8")
        elif self.path == "/replies":
            self._send(200, json.dumps(self.store.get_replies()))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        payload = self._read_json()
        if self.path == "/comment":
            self.store.add_comment(
                payload.get("element_id", ""),
                payload.get("comment", ""),
                label=payload.get("label", ""),
            )
            self._send(200, json.dumps({"ok": True}))
        elif self.path == "/done":
            self.store.mark_done()
            self._send(200, json.dumps({"ok": True}))
        else:
            self._send(404, json.dumps({"error": "not found"}))


class HttpFace:
    def __init__(self, store, preferred_port=8787):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", preferred_port), _Handler)
        except OSError:
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)  # ephemeral fallback
        httpd.store = store
        httpd.daemon_threads = True
        self.server = httpd
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def port(self):
        return self.server.server_address[1]

    def start(self):
        self.thread.start()

    def stop(self):
        if self.thread.is_alive():
            self.server.shutdown()
        self.server.server_close()
