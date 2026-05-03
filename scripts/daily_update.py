"""Günlük cron — TEFAS fon listesini ve takip edilen fonların PDR'larını günceller."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import kap, storage, tefas

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
log = logging.getLogger("daily")


def main() -> int:
    # 1) TEFAS Menkul Kıymet Yatırım Fonu listesini upsert et.
    rows = tefas.list_investment_funds()
    n = storage.upsert_funds(rows)
    log.info("TEFAS funds upserted: %d", n)

    # 2) En az bir kullanıcının takip ettiği veya en likit ilk N fonun PDR'sini tazele.
    #    (Free tier rate-limit'i koruyalım: ilk 25 fon)
    target_codes = [r.code for r in rows[:25] if r.code]
    log.info("Refreshing PDR for %d funds", len(target_codes))
    ok = 0
    for code in target_codes:
        try:
            snap = kap.fetch_latest_pdr(code)
            if snap:
                storage.save_pdr(snap)
                ok += 1
                log.info("✓ PDR saved: %s (%s) %d holdings", code, snap.period, len(snap.holdings))
        except Exception as e:
            log.warning("PDR fail %s: %s", code, e)
    log.info("Done. PDR refreshed for %d/%d funds", ok, len(target_codes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
