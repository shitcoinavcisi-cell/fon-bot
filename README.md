# TEFAS & KAP Fon İstihbarat Botu

TEFAS'taki **Menkul Kıymet Yatırım Fonları**nın gerçek içeriğini KAP Portföy Dağılım Raporları (PDR) ile birleştirip Telegram üzerinden 7/24 sunan, **sıfır maliyetli** bir bot.

> Mimari özet ve klasör yapısı için bkz. `claude.md`.

## ✨ Özellikler
- `/analiz <FON_KODU>` → Fonun en büyük 5 hissesi + bir önceki PDR'a göre değişim.
- `/takip`, `/listem`, `/sil` → Kişisel watchlist.
- TEFAS public endpoint'inden günlük fiyat & fon listesi.
- KAP açık disclosure API'sinden PDR otomatik çekimi (HTML parser).
- Supabase'te kalıcı saklama, GitHub Actions cron ile günlük tazeleme.

## Sıfırdan Kurulum (5 adım)

### 1) Supabase
1. https://supabase.com → yeni proje aç.
2. Settings → API → **Project URL** ve **service_role key**'i kopyala.
3. SQL Editor'a aşağıyı yapıştırıp çalıştır:

```sql
create table if not exists funds (
  code text primary key,
  title text,
  type text,
  updated_at timestamptz default now()
);

create table if not exists pdr_snapshots (
  id bigserial primary key,
  fund_code text references funds(code),
  period date,
  holdings jsonb,
  source_url text,
  created_at timestamptz default now(),
  unique(fund_code, period)
);

create table if not exists watchlist (
  chat_id bigint,
  fund_code text,
  created_at timestamptz default now(),
  primary key (chat_id, fund_code)
);
```

### 2) Telegram botu
1. Telegram'da `@BotFather` → `/newbot` → tokenı kopyala.

2. (Opsiyonel) `/setcommands` ile şu listeyi yapıştır:
   ```
   start - Yardım
   analiz - Bir fonun PDR analizi
   takip - Fonu takibe al
   listem - Takip listem
   sil - Takipten çıkar
   ```

### 3) Vercel deploy
1. Bu repoyu GitHub'a push et.
2. https://vercel.com → "Add New → Project" → repoyu seç → **Framework: Other**.
3. Settings → Environment Variables: `.env.example`'daki **6 değişkeni** ekle.
   - `PUBLIC_BASE_URL` ilk deploy'dan **sonra** güncellenir; önce bir placeholder bırakıp deploy yap, sonra Vercel'in verdiği `https://xxx.vercel.app`'i bu değere yaz ve **redeploy** et.

### 4) Webhook'u bağla
Yerelde:
```bash
pip install -r requirements.txt
cp .env.example .env   # değerleri doldur
python scripts/set_webhook.py
```
Çıktıda `{"ok": true, ...}` görmelisin.

### 5) Cron'u aç
GitHub repo → Settings → Secrets and variables → Actions:
`.env.example`'daki tüm anahtarları **Repository secret** olarak ekle.
`Actions` sekmesine git → **Daily TEFAS+KAP refresh** workflow'unu enable et.

İlk dolum için bir kez `Run workflow` → `daily_update.py` Supabase'i hazırlasın.

## 🧪 Yerel Test

```bash
pip install -r requirements.txt
python -c "from core.tefas import list_investment_funds; print(len(list_investment_funds()))"
python -c "from core.kap import fetch_latest_pdr; print(fetch_latest_pdr('TTE'))"
```

## ⚠️ Notlar
- KAP HTML şeması zaman zaman değişir; parser tabloyu bulamazsa `core/kap.py:_parse_kap_disclosure_html` içindeki regex'leri güncellemeniz gerekebilir.
- Vercel free planı serverless fonksiyon başına 10sn timeout uygular. KAP yavaşsa `/analiz` ilk seferde "PDR bulunamadı" diyebilir; ikinci denemede DB'den anlık döner.
- Bu yazılım yatırım tavsiyesi değildir.
