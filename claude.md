# TEFAS & KAP Financial Intelligence Bot

> Vibe Coding modu — kullanıcı kod yazmaz. Tüm teknik işler bu repoda otomatize edildi.
> Bu dosya projenin **ana dökümantasyonu** ve **agent hafızası**dır. Her ilerleme buraya not edilir.

---

## 1. Amaç
TEFAS'taki **Menkul Kıymet Yatırım Fonları**nın gerçek içeriğini (KAP'tan gelen aylık **Portföy Dağılım Raporu / PDR** verileriyle) Telegram üzerinden 7/24 ve **sıfır maliyetle** takip etmek.

## 2. Mimari (Zero Cost Architecture)

| Katman | Teknoloji | Amaç |
|---|---|---|
| Engine | Python 3.11 | Tüm iş mantığı |
| Veri Kaynağı 1 | TEFAS public endpoint (`fundturkey.com.tr/api/DB/BindHistoryInfo`) | Fon listesi & fiyatları |
| Veri Kaynağı 2 | KAP (`kap.org.tr`) açık verileri | PDR (portföy dağılım) raporları |
| DB | Supabase (Free Tier) | Fonlar + PDR snapshotları |
| Bot | Telegram Bot API | Kullanıcı arayüzü |
| Hosting | Vercel Serverless (Python runtime) | `/api/webhook` |
| Cron | GitHub Actions | Her sabah 09:00 TR veri güncelleme |

## 3. Klasör Yapısı

```
fon/
├── api/
│   └── webhook.py            # Vercel serverless entrypoint (Telegram webhook)
├── core/
│   ├── __init__.py
│   ├── config.py             # ENV yönetimi
│   ├── tefas.py              # TEFAS fon listesi & fiyat çekici
│   ├── kap.py                # KAP PDR bulucu & parser
│   ├── analyzer.py           # Fon analizi (top 5 hisse, değişim)
│   ├── storage.py            # Supabase katmanı
│   └── telegram_bot.py       # Komut yönlendirme (/start, /analiz, /takip)
├── scripts/
│   ├── daily_update.py       # GitHub Actions tarafından çağrılır
│   └── set_webhook.py        # Telegram webhook URL'sini Vercel'e bağlar
├── .github/workflows/
│   └── daily.yml             # Cron job
├── requirements.txt
├── vercel.json
├── .env.example
├── .gitignore
├── README.md
└── claude.md                 # Bu dosya
```

## 4. Telegram Komutları

- `/start` — Karşılama mesajı ve komut listesi.
- `/analiz <FON_KODU>` — Örn: `/analiz TTE`. Fonun en güncel PDR'ından **en büyük 5 hisse**, ağırlıkları ve son aya göre **değişim** tablosu.
- `/takip <FON_KODU>` — Fonu kullanıcının takip listesine ekler.
- `/listem` — Takip edilen fonlar.
- `/sil <FON_KODU>` — Takipten çıkar.

## 5. Veri Modeli (Supabase)

```sql
-- Fonlar
create table funds (
  code text primary key,
  title text,
  type text,
  updated_at timestamptz default now()
);

-- PDR snapshotları (ay bazında)
create table pdr_snapshots (
  id bigserial primary key,
  fund_code text references funds(code),
  period date,                   -- raporun ait olduğu ay (ilk gün)
  holdings jsonb,                -- [{symbol, name, weight}, ...]
  source_url text,
  created_at timestamptz default now(),
  unique(fund_code, period)
);

-- Telegram kullanıcı takipleri
create table watchlist (
  chat_id bigint,
  fund_code text,
  created_at timestamptz default now(),
  primary key (chat_id, fund_code)
);
```

## 6. Kurulum Adımları (Kullanıcı için özet)

> Detaylı sürüm `README.md`'de.

1. Supabase'te yeni proje aç → SQL Editor'a yukarıdaki tabloları yapıştır.
2. `@BotFather`'dan Telegram bot tokenı al.
3. GitHub'a bu repoyu push et.
4. Vercel'e bağla (Python runtime otomatik algılanır).
5. Vercel + GitHub Actions environment variable'larını `.env.example`'a göre doldur.
6. `python scripts/set_webhook.py` çalıştır → bot Telegram'da canlı.

## 7. İlerleme Günlüğü

- [x] Repo iskeleti ve dökümantasyon
- [x] Phase 1: requirements + env + config
- [x] Phase 2: TEFAS + KAP modülleri
- [x] Storage katmanı (Supabase)
- [x] Phase 3: Telegram webhook (Vercel)
- [x] Phase 4: GitHub Actions cron
- [x] README + kullanıcı talimatları

## 8. Sıradaki İyileştirmeler (Backlog)
- KAP PDR PDF parsing (şu an Excel/HTML öncelikli).
- `/karsilastir FON1 FON2` komutu.
- Hisse bazlı alarm: "X hissesi 5 farklı fon tarafından alındı" bildirimleri.
- TEFAS getiri grafikleri (matplotlib → Telegram photo).
