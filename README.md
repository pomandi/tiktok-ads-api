# Pomandi TikTok Ads — OAuth + API servisi

TikTok Marketing API ile programatik reklam yonetimi icin OAuth callback servisi.

## Bilesenler
- `app.py` — FastAPI OAuth servisi (callback + token saklama)
- `tiktok_client.py` — kampanya/ad group/ad olusturma helper'i
- `Dockerfile` — Coolify deploy icin

## Kurulum sirasi

### 1. Developer app'i olustur (portal/apps)
Form degerleri:
- **App name:** FirstTik
- **App description:** (Ingilizce) Automated TikTok ad campaign management for Pomandi…
- **Advertiser redirect URL:** `https://tiktok.pomandi.com/oauth/callback`
- **Scopes:** Ad Account Management, Ads Management, Creative Management,
  Reporting, Pixel Management, Measurement, (Audience Management)

App olusunca **App ID** ve **Secret** verilir.

### 2. DNS + Coolify
1. Cloudflare'de `tiktok.pomandi.com` -> sunucu (proxied)
2. Coolify'da yeni app: bu repo (Dockerfile build pack)
3. Domain: `tiktok.pomandi.com`, port 8000
4. Persistent volume: `/data`
5. Env degiskenleri (`.env.example`'a bak):
   - `TIKTOK_APP_ID`, `TIKTOK_APP_SECRET` (1. adimdan)
   - `TIKTOK_REDIRECT_URI=https://tiktok.pomandi.com/oauth/callback`
   - `START_SECRET=<rastgele uzun string>`
   - `DATA_DIR=/data`

### 3. Hesabi bagla
Tarayicida ac:
```
https://tiktok.pomandi.com/oauth/start?key=<START_SECRET>
```
TikTok yetkilendirme ekrani -> onayla -> token otomatik kaydedilir.
Token'i okumak icin: `https://tiktok.pomandi.com/token?key=<START_SECRET>`

### 4. Reklam yayinla
```bash
export TIKTOK_ACCESS_TOKEN=...   # /token cikisindan
export TIKTOK_ADVERTISER_ID=...  # bagli reklam hesabi
python tiktok_client.py
```

## Notlar
- Marketing API access token'lari uzun omurlu (suresi dolmaz, revoke edilene kadar).
- `location_ids` (BE/NL) icin `/tool/region/` API'sinden numeric id'ler cekilmeli.
- Video reklam icin once `/file/video/ad/upload/`, sonra `/ad/create/`.
- Yeni app'ler bazi scope'lar icin TikTok review'undan gecer (genelde 1-3 gun).
