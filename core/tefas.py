"""TEFAS public veri çekici.

TEFAS resmi web sitesinin AJAX endpoint'lerini kullanır
(https://www.tefas.gov.tr/api/DB/BindHistoryInfo ve BindHistoryAllocation).
Ücretsiz, anahtarsız, public olarak erişilebilir.
"""
from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Iterable

import requests

log = logging.getLogger(__name__)

BASE = "https://www.tefas.gov.tr/api/DB"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TefasBot/1.0)",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://www.tefas.gov.tr",
    "Referer": "https://www.tefas.gov.tr/TarihselVeriler.aspx",
}

# TEFAS fontip kodları:
#   YAT  -> Yatırım Fonu (Menkul Kıymet Yat. Fonları dahil)
#   EMK  -> Emeklilik Fonu
FUND_TYPE_INVESTMENT = "YAT"


@dataclass
class FundRow:
    code: str
    title: str
    date: dt.date
    price: float
    market_cap: float | None
    n_investors: int | None
    n_shares: float | None


def _post(path: str, payload: dict) -> dict:
    url = f"{BASE}/{path}"
    r = requests.post(url, data=payload, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def list_investment_funds(date: dt.date | None = None) -> list[FundRow]:
    """O güne (varsayılan: bugün) ait tüm Menkul Kıymet Yatırım Fonlarını döner.

    TEFAS aynı gün içinde fiyat olmayan fonlar için boş döner; o yüzden
    bulamazsak son 7 günü geriye doğru deneriz.
    """
    target = date or dt.date.today()
    for back in range(0, 7):
        d = target - dt.timedelta(days=back)
        payload = {
            "fontip": FUND_TYPE_INVESTMENT,
            "sfontur": "",
            "fonkod": "",
            "fongrup": "",
            "bastarih": d.strftime("%d.%m.%Y"),
            "bittarih": d.strftime("%d.%m.%Y"),
            "fonturkod": "",
            "fonunvantip": "",
        }
        try:
            data = _post("BindHistoryInfo", payload)
        except Exception as e:
            log.warning("TEFAS list error for %s: %s", d, e)
            continue
        rows = data.get("data") or []
        if rows:
            return [_parse_row(r) for r in rows]
    return []


def _parse_row(r: dict) -> FundRow:
    return FundRow(
        code=(r.get("FONKODU") or "").strip(),
        title=(r.get("FONUNVAN") or "").strip(),
        date=_parse_tefas_date(r.get("TARIH")),
        price=float(r.get("FIYAT") or 0),
        market_cap=_to_float(r.get("PORTFOYBUYUKLUK")),
        n_investors=_to_int(r.get("KISISAYISI")),
        n_shares=_to_float(r.get("TEDPAYSAYISI")),
    )


def get_fund_history(code: str, days: int = 30) -> list[FundRow]:
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    payload = {
        "fontip": FUND_TYPE_INVESTMENT,
        "sfontur": "",
        "fonkod": code.upper(),
        "fongrup": "",
        "bastarih": start.strftime("%d.%m.%Y"),
        "bittarih": end.strftime("%d.%m.%Y"),
        "fonturkod": "",
        "fonunvantip": "",
    }
    data = _post("BindHistoryInfo", payload)
    rows = data.get("data") or []
    return [_parse_row(r) for r in rows]


def get_allocation(code: str, days: int = 7) -> dict | None:
    """TEFAS portföy dağılımı (hisse, tahvil, vs. ağırlıkları). En son tarihli kaydı döner."""
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    payload = {
        "fontip": FUND_TYPE_INVESTMENT,
        "sfontur": "",
        "fonkod": code.upper(),
        "fongrup": "",
        "bastarih": start.strftime("%d.%m.%Y"),
        "bittarih": end.strftime("%d.%m.%Y"),
        "fonturkod": "",
        "fonunvantip": "",
    }
    data = _post("BindHistoryAllocation", payload)
    rows = data.get("data") or []
    if not rows:
        return None
    rows.sort(key=lambda r: r.get("TARIH", ""), reverse=True)
    return rows[0]


# --- helpers ---

def _parse_tefas_date(raw) -> dt.date:
    if isinstance(raw, str) and raw.isdigit():
        # epoch ms
        return dt.datetime.utcfromtimestamp(int(raw) / 1000).date()
    if isinstance(raw, (int, float)):
        return dt.datetime.utcfromtimestamp(int(raw) / 1000).date()
    if isinstance(raw, str) and "." in raw:
        return dt.datetime.strptime(raw, "%d.%m.%Y").date()
    return dt.date.today()


def _to_float(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _to_int(v) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def codes(rows: Iterable[FundRow]) -> list[str]:
    return [r.code for r in rows if r.code]
