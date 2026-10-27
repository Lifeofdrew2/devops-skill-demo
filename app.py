"""Small, stateless internal lab API; not a general-purpose production web server."""
import json
import os
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

COUNTS = {200: 0, 404: 0, 503: 0}
LOCK = threading.Lock()
VERSION = os.getenv("APP_VERSION", "local")
FAULT = os.getenv("DEMO_FAIL_REQUESTS", "0") == "1"

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # No raw URLs, headers or customer data in logs.

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/metrics":
            with LOCK:
                body = "# TYPE demo_requests_total counter\n" + "".join(
                    f'demo_requests_total{{status="{s}"}} {n}\n' for s, n in COUNTS.items())
            self.reply(200, body.encode(), "text/plain; version=0.0.4")
            return
        if path in ("/healthz", "/readyz"):
            self.reply(200, b'{"status":"ok"}')
            return
        status = (503 if FAULT else 200) if path == "/" else 404
        if path == "/":
            with LOCK:
                COUNTS[status] += 1
        self.reply(status, json.dumps({"version": VERSION, "status": status}).encode())
        print(json.dumps({"event": "request", "status": status}), flush=True)

    def reply(self, code, body, content_type="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    server = ThreadingHTTPServer((os.getenv("HOST", "127.0.0.1"), int(os.getenv("PORT", "8080"))), Handler)
    server.daemon_threads = False
    def stop(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()
