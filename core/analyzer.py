"""Fon analizi: en güncel PDR + bir önceki PDR arasındaki ağırlık değişimleri."""
from __future__ import annotations

from dataclasses import dataclass

from . import kap, storage


@dataclass
class HoldingDiff:
    symbol: str
    name: str
    weight: float            # güncel %
    prev_weight: float | None
    delta: float | None      # güncel - önceki

    @property
    def trend(self) -> str:
        if self.delta is None:
            return "🆕"
        if self.delta > 0.05:
            return "🔼"
        if self.delta < -0.05:
            return "🔽"
        return "▪️"


@dataclass
class FundAnalysis:
    fund_code: str
    period: str
    source_url: str
    top: list[HoldingDiff]


def analyze_fund(code: str, top_n: int = 5, refresh: bool = True) -> FundAnalysis | None:
    code = code.upper()

    # 1) Refresh isteniyorsa KAP'tan yeni snapshot çek ve kaydet.
    if refresh:
        try:
            snap = kap.fetch_latest_pdr(code)
            if snap:
                storage.save_pdr(snap)
        except Exception:
            # Çevrim dışı / KAP erişilemiyor olabilir; DB'ye düşeriz.
            pass

    rows = storage.latest_pdrs(code, limit=2)
    if not rows:
        return None
    cur = rows[0]
    prev = rows[1] if len(rows) > 1 else None

    cur_holdings = cur.get("holdings") or []
    prev_map = {
        (h.get("symbol") or h.get("name")): float(h.get("weight") or 0)
        for h in (prev.get("holdings") if prev else []) or []
    }

    sorted_cur = sorted(cur_holdings, key=lambda h: float(h.get("weight") or 0), reverse=True)[:top_n]
    diffs = []
    for h in sorted_cur:
        key = h.get("symbol") or h.get("name")
        w = float(h.get("weight") or 0)
        pw = prev_map.get(key)
        diffs.append(
            HoldingDiff(
                symbol=h.get("symbol") or "",
                name=h.get("name") or "",
                weight=w,
                prev_weight=pw,
                delta=(w - pw) if pw is not None else None,
            )
        )

    return FundAnalysis(
        fund_code=code,
        period=str(cur.get("period")),
        source_url=cur.get("source_url") or "",
        top=diffs,
    )


def format_analysis(a: FundAnalysis) -> str:
    """Telegram için MarkdownV2-uyumsuz, sade metin tablo."""
    if not a.top:
        return f"`{a.fund_code}` için PDR bulunamadı."

    lines = [
        f"📊 *{a.fund_code}* — Portföy Dağılım Raporu ({a.period})",
        "",
        "```",
        f"{'#':<2} {'Sembol':<8} {'Ağırlık':>8}  {'Δ':>7}",
        "-" * 32,
    ]
    for i, h in enumerate(a.top, 1):
        delta_s = f"{h.delta:+.2f}" if h.delta is not None else "  yeni"
        sym = h.symbol or h.name[:8]
        lines.append(f"{i:<2} {sym:<8} {h.weight:>7.2f}%  {delta_s:>7} {h.trend}")
    lines.append("```")
    if a.source_url:
        lines.append(f"\n[Kaynak: KAP]({a.source_url})")
    return "\n".join(lines)
