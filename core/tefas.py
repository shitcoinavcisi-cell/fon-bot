"""TEFAS public veri çekici (yeni API, Nisan 2026 sonrası).

Eski ``/api/DB/BindHistoryInfo`` endpoint'leri 2026'da emekliye ayrıldı.
Yeni JSON endpoint'leri:

- ``POST /api/funds/fonGetiriBazliBilgiGetir`` — tüm fonların listesi + getiriler
- ``POST /api/funds/fonFiyatBilgiGetir``         — tek fonun fiyat geçmişi

Ücretsiz, anahtarsız, public.
"""
from __future__ import annotations

import datetime as dt
import logging
import math
from dataclasses import dataclass
from typing import Iterable

import requests

log = logging.getLogger(__name__)

ROOT = "https://www.tefas.gov.tr"
LIST_ENDPOINT = "/api/funds/fonGetiriBazliBilgiGetir"
PRICE_ENDPOINT = "/api/funds/fonFiyatBilgiGetir"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Origin": ROOT,
    "Referer": f"{ROOT}/FonKarsilastirma.aspx",
}

# TEFAS fontip kodları:
#   YAT  -> Yatırım Fonu (Menkul Kıymet Yat. Fonları dahil)
#   EMK  -> Emeklilik Fonu
#   BYF  -> Borsa Yatırım Fonu (ETF)
FUND_TYPE_INVESTMENT = "YAT"

# Yeni API'nin kabul ettiği geriye-dönük periyot (ay) değerleri.
_VALID_PERIODS = (1, 3, 6, 12, 36, 60)


@dataclass
class FundRow:
    code: str
    title: str
    fund_type: str | None
    risk: str | None
    return_1m: float | None
    return_ytd: float | None
    return_1y: float | None


@dataclass
class PriceRow:
    code: str
    date: dt.date
    price: float
    market_cap: float | None
    n_investors: int | None
    n_shares: float | None


def _post(endpoint: str, payload: dict) -> dict:
    r = requests.post(f"{ROOT}{endpoint}", json=payload, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json() or {}


def list_investment_funds(_date: dt.date | None = None) -> list[FundRow]:
    """Tüm aktif Menkul Kıymet Yatırım Fonlarını (YAT) döner.

    Yeni API tek seferde 1000+ fonu liste halinde verir; eski tarih-bazlı
    filtreye gerek yok. ``_date`` parametresi geriye dönük uyumluluk için.
    """
    payload = {
        "dil": "TR",
        "fonTipi": FUND_TYPE_INVESTMENT,
        "kurucuKodu": None,
        "sfonTurKod": None,
        "fonTurAciklama": None,
        "islem": 1,
        "fonTurKod": None,
        "fonGrubu": None,
        "donemGetiri1a": "1",
        "donemGetiri3a": "1",
        "donemGetiri6a": "1",
        "donemGetiri1y": "1",
        "donemGetiriyb": "1",
        "donemGetiri3y": "1",
        "donemGetiri5y": "1",
        "basTarih": None,
        "bitTarih": None,
        "calismaTipi": 2,
        "getiriOrani": "1",
    }
    try:
        data = _post(LIST_ENDPOINT, payload)
    except Exception as e:
        log.warning("TEFAS list error: %s", e)
        return []
    return [_parse_list_row(r) for r in (data.get("resultList") or []) if r.get("fonKodu")]


def _parse_list_row(r: dict) -> FundRow:
    return FundRow(
        code=(r.get("fonKodu") or "").strip().upper(),
        title=(r.get("fonUnvan") or "").strip(),
        fund_type=(r.get("fonTurAciklama") or None),
        risk=(str(r.get("riskDegeri")) if r.get("riskDegeri") is not None else None),
        return_1m=_to_float(r.get("getiri1a")),
        return_ytd=_to_float(r.get("getiriyb")),
        return_1y=_to_float(r.get("getiri1y")),
    )


def get_fund_history(code: str, days: int = 30) -> list[PriceRow]:
    """Tek fonun son N günlük fiyat geçmişi (yeni per-fund endpoint'ten)."""
    period = _months_back(days)
    payload = {"fonKodu": code.upper(), "dil": "TR", "periyod": period}
    try:
        data = _post(PRICE_ENDPOINT, payload)
    except Exception as e:
        log.warning("TEFAS price error %s: %s", code, e)
        return []
    rows = data.get("resultList") or []
    cutoff = dt.date.today() - dt.timedelta(days=days)
    out: list[PriceRow] = []
    for r in rows:
        d = _parse_tefas_date(r.get("tarih") or r.get("TARIH"))
        if d < cutoff:
            continue
        out.append(
            PriceRow(
                code=code.upper(),
                date=d,
                price=_to_float(r.get("fiyat") or r.get("FIYAT")) or 0.0,
                market_cap=_to_float(r.get("portfoyBuyukluk") or r.get("PORTFOYBUYUKLUK")),
                n_investors=_to_int(r.get("yatirimciSayisi") or r.get("KISISAYISI")),
                n_shares=_to_float(r.get("tedavuldekiPaySayisi") or r.get("TEDPAYSAYISI")),
            )
        )
    return sorted(out, key=lambda x: x.date)


def get_latest_price(code: str) -> PriceRow | None:
    rows = get_fund_history(code, days=10)
    return rows[-1] if rows else None


# --- helpers ---

def _months_back(days: int) -> int:
    needed = math.ceil(days / 30) + 1
    for p in _VALID_PERIODS:
        if p >= needed:
            return p
    return _VALID_PERIODS[-1]


def _parse_tefas_date(raw) -> dt.date:
    if raw is None:
        return dt.date.today()
    if isinstance(raw, (int, float)):
        return dt.datetime.utcfromtimestamp(int(raw) / 1000).date()
    if isinstance(raw, str):
        s = raw.strip()
        if s.isdigit():
            return dt.datetime.utcfromtimestamp(int(s) / 1000).date()
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                return dt.datetime.strptime(s[: len(fmt) + 2], fmt).date()
            except ValueError:
                continue
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
