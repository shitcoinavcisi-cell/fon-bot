"""Vercel Serverless Function — Telegram webhook entrypoint.

Vercel @vercel/python runtime, BaseHTTPRequestHandler subclass'ını
otomatik handler olarak kabul eder.
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

# Vercel dağıtımında repo root sys.path'te olmayabilir.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.telegram_bot import handle_update  # noqa: E402
from core.config import get_settings  # noqa: E402


class handler(BaseHTTPRequestHandler):  # Vercel sözleşmesi: lower-case "handler"
    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"TEFAS & KAP bot webhook is alive.")

    def do_POST(self):  # noqa: N802
        # Telegram secret-token doğrulaması
        try:
            settings = get_settings()
        except Exception as e:
            self._json(500, {"error": f"config: {e}"})
            return

        sent_secret = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if settings.telegram_webhook_secret and sent_secret != settings.telegram_webhook_secret:
            self._json(401, {"ok": False, "error": "bad secret"})
            return

        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            update = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"ok": False, "error": "invalid json"})
            return

        try:
            handle_update(update)
        except Exception as e:  # asla 500 dönmemeliyiz; Telegram retry yapar
            self._json(200, {"ok": True, "warn": str(e)})
            return

        self._json(200, {"ok": True})

    # ---- helpers ----

    def _json(self, code: int, body: dict) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode("utf-8"))

    def log_message(self, format, *args):  # noqa: A002 - sustain
        return  # Vercel logging'i zaten stdout/stderr'i yakalar
