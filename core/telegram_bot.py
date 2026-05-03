"""Telegram update router (webhook tabanlı, polling yok).

python-telegram-bot v21 ile Bot/Application sınıflarını import etmeden, ham
HTTPS API'sine `requests` ile cevap dönüyoruz. Bu sayede Vercel serverless
runtime'ında soğuk başlangıç hızlı kalır.
"""
from __future__ import annotations

import logging
import re

import requests

from . import analyzer, storage
from .config import get_settings

log = logging.getLogger(__name__)

TG_API = "https://api.telegram.org/bot{token}/{method}"

WELCOME = (
    "👋 *TEFAS & KAP Fon İstihbarat Botu*\n\n"
    "Komutlar:\n"
    "• `/analiz FON_KODU` — Fonun en büyük 5 hissesi ve değişimi\n"
    "• `/takip FON_KODU` — Fonu takip listene ekle\n"
    "• `/listem` — Takip ettiğin fonlar\n"
    "• `/sil FON_KODU` — Takipten çıkar\n\n"
    "Örnek: `/analiz TTE`"
)

CMD_RE = re.compile(r"^/(\w+)(?:@\w+)?(?:\s+(.+))?$", re.DOTALL)


def handle_update(update: dict) -> None:
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = (msg.get("text") or "").strip()
    if not chat_id or not text:
        return

    m = CMD_RE.match(text)
    if not m:
        return
    command = m.group(1).lower()
    arg = (m.group(2) or "").strip()

    try:
        if command == "start" or command == "yardim" or command == "help":
            _send(chat_id, WELCOME)
        elif command == "analiz":
            _cmd_analiz(chat_id, arg)
        elif command == "takip":
            _cmd_takip(chat_id, arg)
        elif command == "sil":
            _cmd_sil(chat_id, arg)
        elif command == "listem":
            _cmd_listem(chat_id)
        else:
            _send(chat_id, "Komutu anlayamadım. /start ile yardım al.")
    except Exception as e:
        log.exception("handler error")
        _send(chat_id, f"⚠️ Hata: `{e}`")


# ---- commands ----

def _cmd_analiz(chat_id: int, arg: str) -> None:
    code = _norm_code(arg)
    if not code:
        _send(chat_id, "Kullanım: `/analiz FON_KODU` (örn: `/analiz TTE`)")
        return
    _send(chat_id, f"⏳ `{code}` için KAP'taki en güncel PDR çekiliyor...")
    a = analyzer.analyze_fund(code, top_n=5, refresh=True)
    if not a:
        _send(chat_id, f"`{code}` için PDR bulunamadı. Fon kodunu kontrol et.")
        return
    _send(chat_id, analyzer.format_analysis(a))


def _cmd_takip(chat_id: int, arg: str) -> None:
    code = _norm_code(arg)
    if not code:
        _send(chat_id, "Kullanım: `/takip FON_KODU`")
        return
    storage.add_watch(chat_id, code)
    _send(chat_id, f"✅ `{code}` takibe alındı.")


def _cmd_sil(chat_id: int, arg: str) -> None:
    code = _norm_code(arg)
    if not code:
        _send(chat_id, "Kullanım: `/sil FON_KODU`")
        return
    storage.remove_watch(chat_id, code)
    _send(chat_id, f"🗑️ `{code}` listeden çıkarıldı.")


def _cmd_listem(chat_id: int) -> None:
    codes = storage.list_watch(chat_id)
    if not codes:
        _send(chat_id, "Takip listeniz boş. `/takip FON_KODU` ile ekleyin.")
        return
    body = "\n".join(f"• `{c}`" for c in codes)
    _send(chat_id, f"📌 *Takip Listen*\n{body}")


# ---- helpers ----

def _norm_code(arg: str) -> str:
    arg = arg.strip().upper()
    return arg.split()[0] if arg else ""


def _send(chat_id: int, text: str) -> None:
    s = get_settings()
    url = TG_API.format(token=s.telegram_bot_token, method="sendMessage")
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        requests.post(url, json=payload, timeout=15)
    except Exception:
        log.exception("telegram send failed")
