"""Supabase persistence katmanı."""
from __future__ import annotations

import datetime as dt
import logging
from dataclasses import asdict
from typing import Iterable

from supabase import Client, create_client

from .config import get_settings
from .kap import PdrSnapshot
from .tefas import FundRow

log = logging.getLogger(__name__)


def _client() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_key)


# ---- funds ----

def upsert_funds(rows: Iterable[FundRow]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    payload = [
        {"code": r.code, "title": r.title, "type": "YAT"}
        for r in rows if r.code
    ]
    _client().table("funds").upsert(payload, on_conflict="code").execute()
    return len(payload)


def get_fund(code: str) -> dict | None:
    res = _client().table("funds").select("*").eq("code", code.upper()).limit(1).execute()
    return (res.data or [None])[0]


# ---- pdr snapshots ----

def save_pdr(snapshot: PdrSnapshot) -> None:
    _client().table("pdr_snapshots").upsert(
        {
            "fund_code": snapshot.fund_code,
            "period": snapshot.period.isoformat(),
            "holdings": [asdict(h) for h in snapshot.holdings],
            "source_url": snapshot.source_url,
        },
        on_conflict="fund_code,period",
    ).execute()


def latest_pdrs(code: str, limit: int = 2) -> list[dict]:
    res = (
        _client()
        .table("pdr_snapshots")
        .select("*")
        .eq("fund_code", code.upper())
        .order("period", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


# ---- watchlist ----

def add_watch(chat_id: int, code: str) -> None:
    _client().table("watchlist").upsert(
        {"chat_id": chat_id, "fund_code": code.upper()},
        on_conflict="chat_id,fund_code",
    ).execute()


def remove_watch(chat_id: int, code: str) -> None:
    _client().table("watchlist").delete().eq("chat_id", chat_id).eq(
        "fund_code", code.upper()
    ).execute()


def list_watch(chat_id: int) -> list[str]:
    res = (
        _client()
        .table("watchlist")
        .select("fund_code")
        .eq("chat_id", chat_id)
        .execute()
    )
    return [r["fund_code"] for r in (res.data or [])]
