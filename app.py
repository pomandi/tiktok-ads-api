"""
Pomandi TikTok Ads — OAuth callback + token saklama servisi.

Akış:
  1. /oauth/start      -> advertiser'i TikTok yetkilendirme ekranina yonlendirir
  2. /oauth/callback   -> TikTok auth_code ile geri doner, biz token'a ceviririz
  3. token /data/tiktok_tokens.json icine guvenli kaydedilir (Coolify volume)

Marketing API v1.3
"""
import os
import json
import time
import secrets
import pathlib

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

APP_ID = os.environ.get("TIKTOK_APP_ID", "")
APP_SECRET = os.environ.get("TIKTOK_APP_SECRET", "")
REDIRECT_URI = os.environ.get(
    "TIKTOK_REDIRECT_URI", "https://tiktok.pomandi.com/oauth/callback"
)
# Basit koruma: /oauth/start'i sadece bu anahtari bilen tetikleyebilsin
START_SECRET = os.environ.get("START_SECRET", "")

DATA_DIR = pathlib.Path(os.environ.get("DATA_DIR", "/data"))
TOKEN_FILE = DATA_DIR / "tiktok_tokens.json"
BASE = "https://business-api.tiktok.com"

app = FastAPI(title="Pomandi TikTok Ads OAuth")

# Tek instance icin yeterli; coklu replica'da Redis'e tasinir
_state_store: set[str] = set()


@app.get("/healthz")
def health():
    return {"ok": True, "configured": bool(APP_ID and APP_SECRET)}


@app.get("/oauth/start")
def start(key: str = ""):
    """Advertiser'i yetkilendirme ekranina yonlendirir."""
    if not APP_ID:
        raise HTTPException(500, "TIKTOK_APP_ID configured degil")
    if START_SECRET and key != START_SECRET:
        raise HTTPException(403, "Gecersiz key")

    state = secrets.token_urlsafe(16)
    _state_store.add(state)
    auth_url = (
        f"{BASE}/portal/auth"
        f"?app_id={APP_ID}"
        f"&state={state}"
        f"&redirect_uri={REDIRECT_URI}"
    )
    return RedirectResponse(auth_url)


@app.get("/oauth/callback")
async def callback(request: Request):
    """TikTok auth_code ile geri doner -> access_token'a ceviririz."""
    params = dict(request.query_params)
    auth_code = params.get("auth_code") or params.get("code")
    state = params.get("state")

    if not auth_code:
        raise HTTPException(400, f"auth_code yok. Gelen parametreler: {params}")

    # state dogrulama (varsa)
    if state and _state_store:
        if state not in _state_store:
            raise HTTPException(400, "Gecersiz state (CSRF korumasi)")
        _state_store.discard(state)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE}/open_api/v1.3/oauth2/access_token/",
            json={
                "app_id": APP_ID,
                "secret": APP_SECRET,
                "auth_code": auth_code,
            },
        )

    payload = r.json()
    if payload.get("code") != 0:
        raise HTTPException(400, f"Token degisimi basarisiz: {payload}")

    data = payload["data"]
    record = {
        "access_token": data.get("access_token"),
        "advertiser_ids": data.get("advertiser_ids"),
        "scope": data.get("scope"),
        "obtained_at": int(time.time()),
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(record, indent=2))

    adv = ", ".join(record.get("advertiser_ids") or [])
    return HTMLResponse(
        "<html><body style='font-family:sans-serif;max-width:600px;margin:40px auto'>"
        "<h2>✅ TikTok hesabi baglandi</h2>"
        f"<p><b>Advertiser IDs:</b> {adv or '—'}</p>"
        f"<p><b>Scope:</b> {', '.join(record.get('scope') or [])}</p>"
        "<p>Access token guvenli sekilde kaydedildi. Bu pencereyi kapatabilirsin.</p>"
        "</body></html>"
    )


@app.get("/token")
def get_token(key: str = ""):
    """Kaydedilmis token'i okur (sadece START_SECRET bilen erisebilir)."""
    if not START_SECRET or key != START_SECRET:
        raise HTTPException(403, "Gecersiz key")
    if not TOKEN_FILE.exists():
        raise HTTPException(404, "Henuz token yok. Once /oauth/start ile baglan.")
    return JSONResponse(json.loads(TOKEN_FILE.read_text()))
