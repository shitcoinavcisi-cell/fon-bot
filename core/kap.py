"""KAP (Kamuyu Aydınlatma Platformu) PDR (Portföy Dağılım Raporu) çekici.

KAP açık disclosure search API'sini kullanır:
  POST https://www.kap.org.tr/tr/api/disclosures
Filtreler: subjectList=2222 (Fon Portföy Dağılım Raporu), publishDateFrom/To.

Bir fon için son aylık portföy dağılımını bulur ve içindeki en yüksek
ağırlıklı hisse senetlerini döner. KAP raporları PDF veya HTML olabildiği için
en sağlam yol HTML görünümünü scrape etmektir.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

KAP_API = "https://www.kap.org.tr/tr/api/disclosures"
KAP_VIEW = "https://www.kap.org.tr/tr/Bildirim/{disclosure_id}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TefasBot/1.0)",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": "https://www.kap.org.tr",
    "Referer": "https://www.kap.org.tr/tr/bildirim-sorgu",
}

SUBJECT_PDR = "2222"  # Fon Portföy Dağılım Raporu


@dataclass
class Holding:
    symbol: str
    name: str
    weight: float  # yüzde (0-100)


@dataclass
class PdrSnapshot:
    fund_code: str
    period: dt.date
    source_url: str
    holdings: list[Holding]


def _kap_search(fund_code: str, months_back: int = 3) -> list[dict]:
    """Belirtilen fon kodu için son N aydaki PDR bildirimleri."""
    today = dt.date.today()
    start = (today.replace(day=1) - dt.timedelta(days=31 * months_back)).replace(day=1)
    body = {
        "fromDate": start.strftime("%Y-%m-%d"),
        "toDate": today.strftime("%Y-%m-%d"),
        "year": "",
        "prd": "",
        "term": "",
        "ruleType": "",
        "bdkReview": "",
        "disclosureClass": "FR",
        "index": "",
        "market": "",
        "isLate": "",
        "subjectList": [SUBJECT_PDR],
        "mkkMemberOidList": [],
        "inactiveMkkMemberOidList": [],
        "bdkMemberOidList": [],
        "mainSector": "",
        "sector": "",
        "subSector": "",
        "memberType": "IF",  # Investment Fund
        "fromSrc": "N",
        "srcCategory": "",
        "discIndex": [],
    }
    r = requests.post(KAP_API, json=body, headers=HEADERS, timeout=30)
    r.raise_for_status()
    items = r.json() or []
    fund_code = fund_code.upper()
    matches = []
    for it in items:
        title = (it.get("summary") or it.get("title") or "")
        # KAP başlıkları genelde "TTE - ... PORTFÖY DAĞILIM RAPORU" formundadır.
        if re.search(rf"\b{re.escape(fund_code)}\b", title, re.IGNORECASE):
            matches.append(it)
    matches.sort(key=lambda x: x.get("publishDate", ""), reverse=True)
    return matches


def fetch_latest_pdr(fund_code: str) -> PdrSnapshot | None:
    """Bir fonun en güncel PDR raporunu KAP'tan getir ve parse et."""
    candidates = _kap_search(fund_code, months_back=3)
    for c in candidates:
        disclosure_id = c.get("disclosureIndex") or c.get("id") or c.get("disclosureId")
        if not disclosure_id:
            continue
        url = KAP_VIEW.format(disclosure_id=disclosure_id)
        try:
            holdings = _parse_kap_disclosure_html(url)
        except Exception as e:
            log.warning("KAP parse error %s: %s", url, e)
            continue
        if not holdings:
            continue
        period = _parse_publish_date(c.get("publishDate"))
        return PdrSnapshot(
            fund_code=fund_code.upper(),
            period=period.replace(day=1),
            source_url=url,
            holdings=holdings,
        )
    return None


def _parse_publish_date(raw: str | None) -> dt.date:
    if not raw:
        return dt.date.today()
    # "2025-04-15 18:30:00" gibi
    try:
        return dt.datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except ValueError:
        return dt.date.today()


def _parse_kap_disclosure_html(url: str) -> list[Holding]:
    """KAP bildirim HTML sayfasındaki tabloları tarayıp hisse satırlarını çıkar."""
    r = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    holdings: list[Holding] = []
    for table in soup.find_all("table"):
        header_text = " ".join((th.get_text(" ", strip=True) for th in table.find_all("th")))
        # Tipik PDR tablolarında "Hisse Senedi" veya "Pay" başlığı, "Fon Toplam Değer" ya da "Oran" sütunu olur.
        if not re.search(r"hisse|pay senedi", header_text, re.IGNORECASE):
            continue
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            # Son numerik hücreyi ağırlık (%) olarak kabul et
            weight = _last_number(cells)
            if weight is None or weight <= 0 or weight > 100:
                continue
            # İlk metin hücresinden sembol/isim çıkar
            label = cells[0].strip()
            symbol, name = _split_symbol_name(label)
            if not symbol and not name:
                continue
            holdings.append(Holding(symbol=symbol, name=name, weight=weight))

    # Aynı sembolleri konsolide et, ağırlığa göre sırala.
    merged: dict[str, Holding] = {}
    for h in holdings:
        key = h.symbol or h.name
        if key in merged:
            merged[key] = Holding(h.symbol, h.name, merged[key].weight + h.weight)
        else:
            merged[key] = h
    return sorted(merged.values(), key=lambda x: x.weight, reverse=True)


def _last_number(cells: list[str]) -> float | None:
    for c in reversed(cells):
        m = re.search(r"-?\d+[.,]?\d*", c.replace(".", "").replace(",", "."))
        if m:
            try:
                return float(m.group())
            except ValueError:
                pass
    return None


def _split_symbol_name(label: str) -> tuple[str, str]:
    # "TUPRS - Türkiye Petrol Rafinerileri" gibi formatlar
    parts = re.split(r"\s*[-–]\s*", label, maxsplit=1)
    if len(parts) == 2 and re.fullmatch(r"[A-ZÇĞİÖŞÜ0-9]{3,8}", parts[0]):
        return parts[0], parts[1]
    if re.fullmatch(r"[A-ZÇĞİÖŞÜ0-9]{3,8}", label):
        return label, label
    return "", label
