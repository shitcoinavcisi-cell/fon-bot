"""Telegram bot webhook'unu Vercel deploy URL'sine yönlendirir.

Kullanım:
    python scripts/set_webhook.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from core.config import get_settings


def main() -> int:
    s = get_settings()
    if not s.public_base_url:
        print("PUBLIC_BASE_URL boş. .env / Vercel env'e Vercel URL'ini ekleyin.")
        return 1

    webhook_url = f"{s.public_base_url}/api/webhook"
    api = f"https://api.telegram.org/bot{s.telegram_bot_token}/setWebhook"
    payload = {
        "url": webhook_url,
        "secret_token": s.telegram_webhook_secret,
        "drop_pending_updates": True,
        "allowed_updates": ["message", "edited_message"],
    }
    r = requests.post(api, json=payload, timeout=20)
    print(r.status_code, r.text)
    return 0 if r.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
