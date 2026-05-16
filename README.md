# AI Trading Signal Assistant

Aplikasi ini **tidak melakukan auto-trading**. Aplikasi hanya:

- menerima data/sinyal real dari TradingView Alert Webhook,
- menyimpan sinyal `BUY`, `SELL`, atau `WAIT`,
- menampilkan dashboard,
- mengirim alert ke Telegram dan/atau WhatsApp.

> Catatan: sistem ini untuk edukasi dan riset. Tidak ada sistem yang bisa menjamin profit.

## 1. Struktur Sistem

```text
TradingView Alert
        |
Webhook Receiver
        |
Signal Formatter
        |
Dashboard + Telegram / WhatsApp Alert
```

## 2. Fitur

- Sumber utama: TradingView webhook
- Pair: `EUR_USD`, `GBP_USD`, `XAU_USD`, `USD_JPY`, `BTC_USDT`
- Mode `swing`: H4 analisis, H1 eksekusi
- Mode `scalping`: M15 analisis, M5 eksekusi
- Input modal `USD` atau `USC` untuk hitung risiko dan lot
- Sinyal: `BUY`, `SELL`, `WAIT`
- Dashboard web sederhana
- Dashboard menampilkan sinyal TradingView terbaru otomatis tanpa klik refresh
- Dashboard menampilkan chart TradingView langsung sesuai pair/mode sinyal terbaru
- AI reasoning opsional dari payload TradingView, indikator, risk, dan news jika dikirim
- Kirim sinyal ke Telegram / WhatsApp
- Endpoint webhook: `/webhook/tradingview`

## 3. Install Lokal Windows

Gunakan Python 3.11 atau lebih baru.

```bash
python --version
cd ai-trading-signal-app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Jalankan aplikasi:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Buka dashboard:

```text
http://localhost:8000
```

## 4. Konfigurasi TradingView

Di `.env`, gunakan:

```env
DATA_PROVIDER="tradingview"
```

TradingView tidak diambil dengan pull API dari aplikasi. TradingView mengirim data ke aplikasi lewat alert webhook. Jadi analisis/sinyal dibuat di TradingView, lalu aplikasi menerima payload webhook dan meneruskannya ke Telegram.

Untuk rekomendasi otomatis `BUY`, `SELL`, atau `WAIT`, gunakan Pine Script:

```text
tradingview/auto_signal_webhook.pine
```

Cara pakai:

1. Buka TradingView.
2. Buka Pine Editor.
3. Copy isi file `tradingview/auto_signal_webhook.pine`.
4. Add to chart.
5. Atur input script:
   - `Mode`: `swing` atau `scalping`
   - `Account Type`: `USD` atau `USC`
   - `Balance`: modal
   - `Risk Percent`: risiko per sinyal
   - `Send WAIT Alerts`: default aktif untuk test webhook
6. Buat alert.
7. Pada condition, pilih script `AI Trading Signal Webhook`, lalu pilih `Any alert() function call`.
8. Isi Webhook URL ke endpoint aplikasi.

Endpoint lokal:

```text
POST http://localhost:8000/webhook/tradingview
```

Untuk menerima webhook dari internet, server harus punya URL publik HTTPS:

```text
https://domain-anda.com/webhook/tradingview
```

Jika tidak memakai Pine Script otomatis, contoh body alert manual:

```json
{
  "pair": "XAU_USD",
  "mode": "swing",
  "analysis_timeframe": "H4",
  "execution_timeframe": "H1",
  "ticker": "{{ticker}}",
  "exchange": "{{exchange}}",
  "timeframe": "{{interval}}",
  "time": "{{time}}",
  "signal": "AUTO",
  "analysis_bias": "BULLISH",
  "execution_confirmation": "BULLISH_CONFIRMATION",
  "price": "{{close}}",
  "stop_loss": "",
  "tp1": "",
  "tp2": "",
  "tp3": "",
  "balance": 1000,
  "account_type": "USD",
  "risk_percent": 1,
  "note": "TradingView alert"
}
```

Mode yang didukung:

- `swing`: H4 untuk analisis, H1 untuk eksekusi
- `scalping`: M15 untuk analisis, M5 untuk eksekusi

Pair yang didukung:

- `EUR_USD`
- `GBP_USD`
- `XAU_USD`
- `USD_JPY`
- `BTC_USDT`

Untuk akun cent, gunakan:

```json
{
  "account_type": "USC",
  "balance": 100000,
  "risk_percent": 1
}
```

Jika payload berisi `price` dan `stop_loss`, aplikasi akan menghitung `risk_amount_usd` dan rekomendasi lot.
Untuk `BTC_USDT`, nilai `lot_size` dibaca sebagai estimasi quantity BTC, bukan lot forex.

Jika `signal` berisi `AUTO`, aplikasi akan menyimpulkan:

- `BUY` jika bias analisis bullish dan konfirmasi eksekusi bullish
- `SELL` jika bias analisis bearish dan konfirmasi eksekusi bearish
- `WAIT` jika kondisi belum selaras

Contoh untuk strategy alert:

```json
{
  "pair": "XAU_USD",
  "mode": "scalping",
  "ticker": "{{ticker}}",
  "timeframe": "{{interval}}",
  "action": "{{strategy.order.action}}",
  "price": "{{strategy.order.price}}",
  "stop_loss": "",
  "tp1": "",
  "tp2": "",
  "tp3": "",
  "balance": 1000,
  "account_type": "USD",
  "risk_percent": 1,
  "note": "{{strategy.order.comment}}"
}
```

Field yang didukung antara lain: `pair`, `symbol`, `ticker`, `tickerid`, `mode`, `signal`, `action`, `side`, `price`, `close`, `entry_price`, `stop_loss`, `sl`, `tp1`, `tp2`, `tp3`, `balance`, `modal`, `account_type`, `risk_percent`, `note`, `message`, `timeframe`, `interval`, `time`, dan `exchange`.

## 5. AI Reasoning Opsional

Sinyal utama tetap dibuat oleh TradingView/Pine Script. AI dipakai sebagai lapisan tambahan untuk membaca payload sinyal, indikator, risk, dan `news` jika dikirim, lalu memberi reasoning tambahan di dashboard dan Telegram.

Aktifkan di `.env`:

```env
ENABLE_AI_REASONING=true
OPENAI_API_KEY="ISI_API_KEY_ANDA"
OPENAI_MODEL="gpt-5.2"
OPENAI_BASE_URL="https://api.openai.com/v1"
```

Jika AI gagal, webhook tetap diterima dan Telegram tetap dikirim dengan reasoning TradingView biasa.

Contoh menambahkan news di payload manual:

```json
{
  "pair": "XAU_USD",
  "mode": "swing",
  "signal": "AUTO",
  "analysis_bias": "BULLISH",
  "execution_confirmation": "BULLISH_CONFIRMATION",
  "price": "{{close}}",
  "stop_loss": "",
  "balance": 1000,
  "account_type": "USD",
  "risk_percent": 1,
  "news": "FOMC malam ini, spread XAU berpotensi melebar"
}
```

Opsional untuk keamanan, isi `.env`:

```env
TRADINGVIEW_WEBHOOK_SECRET="secret-kamu"
```

Lalu tambahkan field yang sama di alert TradingView:

```json
{
  "secret": "secret-kamu",
  "ticker": "{{ticker}}",
  "signal": "BUY",
  "price": "{{close}}"
}
```

## 6. Telegram Setup

1. Buka Telegram.
2. Cari `@BotFather`.
3. Buat bot baru dengan `/newbot`.
4. Copy token bot ke `.env`:

```env
TELEGRAM_BOT_TOKEN="123456:ABC..."
```

5. Kirim `/start` ke bot Anda.
6. Dapatkan chat ID:

```text
https://api.telegram.org/bot<TOKEN_ANDA>/getUpdates
```

7. Isi `.env`:

```env
TELEGRAM_CHAT_ID="123456789"
```

8. Restart server.

## 7. WhatsApp Setup

WhatsApp memakai Meta WhatsApp Business Cloud API.

```env
WHATSAPP_ACCESS_TOKEN="EAAG..."
WHATSAPP_PHONE_NUMBER_ID="1234567890"
WHATSAPP_TO_NUMBER="628xxxxxxxxxx"
WHATSAPP_API_VERSION="v23.0"
```

Untuk pesan bisnis/proaktif di luar window 24 jam, biasanya wajib memakai template yang disetujui Meta.

## 8. Endpoint API

```text
GET  /
GET  /api/health
GET  /api/markets
GET  /api/signals
DELETE /api/signals
POST /api/send-alert/{signal_id}
POST /webhook/tradingview
```

Mode `tradingview` tidak menjalankan scan/analisis lokal. Data masuk hanya dari alert webhook TradingView.

Dashboard otomatis mengecek sinyal terbaru setiap 5 detik. Saat TradingView mengirim webhook baru, kartu sinyal terakhir dan riwayat akan diperbarui otomatis.

Dashboard juga memuat chart TradingView langsung. Chart mengikuti sinyal terbaru:

- `swing`: chart eksekusi H1
- `scalping`: chart eksekusi M5
- symbol mengikuti payload TradingView jika ada `exchange/ticker`, atau fallback ke pair yang didukung

## 9. Deployment Singkat

```bash
git clone <repo-anda>
cd ai-trading-signal-app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Untuk produksi, jalankan di balik Nginx + HTTPS dan pakai `systemd` atau Docker.

### Deployment ke Vercel

Aplikasi ini bisa dideploy ke Vercel sebagai FastAPI serverless app. Vercel akan memakai entrypoint:

```text
app/index.py
```

Vercel memberi URL HTTPS publik yang bisa dipakai untuk TradingView webhook:

```text
https://nama-project.vercel.app/webhook/tradingview
```

Checklist sebelum deploy:

1. Push project ke GitHub, GitLab, atau Bitbucket.
2. Pastikan `.env` tidak ikut commit atau upload. File `.vercelignore` sudah mengecualikan `.env`, `.venv`, dan `signals.db`.
3. Buat database Supabase untuk production, lalu isi `DATABASE_URL` di Vercel.
4. Set environment variables di Vercel dari daftar di bawah.
5. Deploy, lalu tes `https://nama-project.vercel.app/api/health`.

Deploy dari dashboard Vercel:

1. Buka Vercel.
2. Pilih **Add New Project**.
3. Import repository.
4. Framework preset bisa dibiarkan otomatis.
5. Tambahkan environment variables.
6. Klik **Deploy**.

Deploy dari CLI:

```bash
npm i -g vercel
vercel login
vercel
vercel --prod
```

Set environment variables di dashboard Vercel:

```env
APP_ENV=production
DATA_PROVIDER=tradingview
ENABLE_SCHEDULER=false
ENABLE_AI_REASONING=false
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.2
OPENAI_BASE_URL=https://api.openai.com/v1
TELEGRAM_BOT_TOKEN=isi_token_bot
TELEGRAM_CHAT_ID=isi_chat_id
TRADINGVIEW_WEBHOOK_SECRET=secret-kamu
DATABASE_URL=postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres?sslmode=require
```

Untuk riwayat sinyal permanen, gunakan Supabase Postgres.

Langkah Supabase:

1. Buat project di Supabase.
2. Buka **Connect**.
3. Pilih **Transaction pooler** karena Vercel adalah serverless.
4. Copy connection string.
5. Pastikan memakai `sslmode=require`.
6. Set `DATABASE_URL` di Vercel.

```env
DATABASE_URL=postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres?sslmode=require
```

Tabel akan dibuat otomatis saat aplikasi start lewat `init_db()`. Untuk membuat tabel manual dari lokal, isi `DATABASE_URL` dengan connection string Supabase lalu jalankan:

```bash
python scripts/init_supabase_db.py
```

Alternatif manual: buka Supabase SQL Editor lalu jalankan file:

```text
supabase/schema.sql
```

SQLite lokal `signals.db` cocok untuk development, tetapi tidak cocok untuk Vercel karena filesystem Vercel Functions bersifat read-only dan hanya `/tmp` yang writable sementara.

Jika `DATABASE_URL` belum diisi saat berjalan di Vercel, aplikasi akan memakai SQLite sementara di `/tmp/signals.db` supaya smoke test bisa berjalan. Data tersebut tidak permanen, jadi tetap gunakan Supabase untuk production.

## 10. Batasan

- Sinyal ini bukan nasihat keuangan.
- Jangan gunakan tanpa backtest dan forward test.
- Aplikasi tidak membuka posisi/order sendiri.
- TradingView webhook membutuhkan URL publik HTTPS jika dipakai dari internet.
- WhatsApp Cloud API memiliki aturan template dan window pesan.
