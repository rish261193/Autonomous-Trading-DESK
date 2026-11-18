"""Loopback HTTP interface for untrusted paper strategy intents.

Run this service as a DIFFERENT OS user/container than the strategy agents.
Keep its database inaccessible to agents. Loopback binding alone does NOT
provide authentication or process isolation. Do not expose this port publicly.
No broker integration, secrets, or real-money execution.
"""
from __future__ import annotations

from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json

from .trusted_paper_intents import PaperBuyIntent


def handler_for(service):
    class PaperIntentHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/v1/paper/intents":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096:
                    self.send_error(413)
                    return
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict) or set(payload) != {
                        "order_id", "strategy_id", "symbol", "quantity",
                        "stop_price"}:
                    self.send_error(400)
                    return
                intent = PaperBuyIntent(**payload)
                allowed = service.submit(intent)
            except (TypeError, ValueError, UnicodeDecodeError):
                self.send_error(400)
                return
            body = json.dumps({"reserved": bool(allowed)}).encode("utf-8")
            self.send_response(200 if allowed else 403)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return  # Avoid accidental strategy payload logging.

    return PaperIntentHandler


def serve_paper_intents(service, *, host="127.0.0.1", port=8765):
    if host != "127.0.0.1":
        raise ValueError("Paper API must bind to IPv4 loopback")
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("Invalid port")
    return ThreadingHTTPServer((host, port), handler_for(service))
