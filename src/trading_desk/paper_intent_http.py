"""Authenticated, loopback-only HTTP API for PAPER trade reservations.

Use separate OS users/containers and restrict the service ledger. Loopback
alone is not isolation. This service does not submit exchange orders.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from hmac import compare_digest, new as hmac_new
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
import json
import time

from .trusted_paper_intents import PaperBuyIntent


def sign_intent(secret: bytes, timestamp: int, nonce: str, body: bytes) -> str:
    """Client/server shared HMAC over exact bytes and request metadata."""
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise ValueError("At least 32 bytes of key material required")
    message = str(timestamp).encode() + b"\n" + nonce.encode() + b"\n" + body
    return hmac_new(secret, message, sha256).hexdigest()


def handler_for(service, *, secret: bytes, clock=time.time):
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise ValueError("At least 32 bytes of key material required")
    used_nonces: dict[str, float] = {}
    nonce_lock = Lock()

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
                body = self.rfile.read(length)
                stamp_raw = self.headers.get("X-Paper-Timestamp", "")
                nonce = self.headers.get("X-Paper-Nonce", "")
                signature = self.headers.get("X-Paper-Signature", "")
                if (not stamp_raw.isascii() or not stamp_raw.isdecimal() or
                        not 16 <= len(nonce) <= 128 or not nonce.isascii() or
                        not nonce.isalnum() or len(signature) != 64):
                    self.send_error(401)
                    return
                stamp = int(stamp_raw)
                current = float(clock())
                if abs(current - stamp) > 30:
                    self.send_error(401)
                    return
                expected = sign_intent(secret, stamp, nonce, body)
                if not compare_digest(expected, signature):
                    self.send_error(401)
                    return
                with nonce_lock:
                    for key, expiry in list(used_nonces.items()):
                        if expiry < current:
                            del used_nonces[key]
                    if nonce in used_nonces:
                        self.send_error(409)
                        return
                    used_nonces[nonce] = current + 60
                payload = json.loads(body)
                if not isinstance(payload, dict) or set(payload) != {
                        "order_id", "strategy_id", "symbol", "quantity",
                        "stop_price"}:
                    self.send_error(400)
                    return
                intent = PaperBuyIntent(**payload)
                allowed = service.submit(intent)
            except (TypeError, ValueError, UnicodeDecodeError, OverflowError):
                self.send_error(400)
                return
            response = json.dumps({"reserved": bool(allowed)}).encode("utf-8")
            self.send_response(200 if allowed else 403)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format, *args):
            return

    return PaperIntentHandler


def serve_paper_intents(service, *, secret: bytes, host="127.0.0.1",
                        port=8765, clock=time.time):
    if host != "127.0.0.1":
        raise ValueError("Paper API must bind to IPv4 loopback")
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("Invalid port")
    return ThreadingHTTPServer(
        (host, port), handler_for(service, secret=secret, clock=clock))
