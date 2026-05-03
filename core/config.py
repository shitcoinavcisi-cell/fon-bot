"""Centralized environment / configuration management."""
from __future__ import annotations

import os
from dataclasses import dataclass

try:
    # Yerelde .env varsa yükle. Vercel/GitHub Actions ortamında env zaten injected.
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _req(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_webhook_secret: str
    public_base_url: str
    supabase_url: str
    supabase_service_key: str

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            telegram_bot_token=_req("TELEGRAM_BOT_TOKEN"),
            telegram_webhook_secret=os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
            or "no-secret",
            public_base_url=os.getenv("PUBLIC_BASE_URL", "").rstrip("/"),
            supabase_url=_req("SUPABASE_URL"),
            supabase_service_key=_req("SUPABASE_SERVICE_KEY"),
        )


def get_settings() -> Settings:
    """Lazy singleton."""
    global _SETTINGS
    try:
        return _SETTINGS  # type: ignore[name-defined]
    except NameError:
        _SETTINGS = Settings.load()
        return _SETTINGS
