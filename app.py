"""
Pomandi TikTok — OAuth callback + token saklama servisi.

Iki ayri akis:
  A) ADVERTISER (Marketing API / reklam)
     /oauth/start    -> business-api portal/auth -> /oauth/callback (auth_code)
     token: tiktok_tokens.json
  B) ACCOUNT HOLDER (icerik paylasimi / Spark Ads)
     /oauth/account/start -> www.tiktok.com/v2/auth -> /oauth/callback (code)
     token: tiktok_user_tokens.json  (open_id, access_token, refresh_token)

Callback tek URL; auth_code varsa A, sadece code varsa B olarak ayrilir.
"""
import os
import json
import time
import secrets
import pathlib
import urllib.parse

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

APP_ID = os.environ.get("TIKTOK_APP_ID", "")
APP_SECRET = os.environ.get("TIKTOK_APP_SECRET", "")
REDIRECT_URI = os.environ.get(
    "TIKTOK_REDIRECT_URI", "https://tiktok.pomandi.com/oauth/callback"
)
START_SECRET = os.environ.get("START_SECRET", "")

# Account-holder (icerik) icin istenecek scope'lar
ACCOUNT_SCOPES = os.environ.get(
    "TIKTOK_ACCOUNT_SCOPES",
    "user.info.basic,user.info.profile,user.info.stats,video.list,"
    "video.publish,video.upload,biz.spark.auth,biz.creator.info",
)

DATA_DIR = pathlib.Path(os.environ.get("DATA_DIR", "/data"))
TOKEN_FILE = DATA_DIR / "tiktok_tokens.json"
USER_TOKEN_FILE = DATA_DIR / "tiktok_user_tokens.json"

BIZ_BASE = "https://business-api.tiktok.com"
TT_BASE = "https://open.tiktokapis.com"

app = FastAPI(title="Pomandi TikTok OAuth")
_state_store: set[str] = set()


@app.get("/healthz")
def health():
    return {
        "ok": True,
        "configured": bool(APP_ID and APP_SECRET),
        "advertiser_linked": TOKEN_FILE.exists(),
        "account_linked": USER_TOKEN_FILE.exists(),
    }


# ---------------------------------------------------------------- ADVERTISER
@app.get("/oauth/start")
def start(key: str = ""):
    if not APP_ID:
        raise HTTPException(500, "TIKTOK_APP_ID configured degil")
    if START_SECRET and key != START_SECRET:
        raise HTTPException(403, "Gecersiz key")
    state = secrets.token_urlsafe(16)
    _state_store.add(state)
    url = (
        f"{BIZ_BASE}/portal/auth?app_id={APP_ID}"
        f"&state={state}&redirect_uri={REDIRECT_URI}"
    )
    return RedirectResponse(url)


# ------------------------------------------------------------ ACCOUNT HOLDER
@app.get("/oauth/account/start")
def account_start(key: str = ""):
    if not APP_ID:
        raise HTTPException(500, "TIKTOK_APP_ID configured degil")
    if START_SECRET and key != START_SECRET:
        raise HTTPException(403, "Gecersiz key")
    state = secrets.token_urlsafe(16)
    _state_store.add(state)
    params = {
        "client_key": APP_ID,
        "scope": ACCOUNT_SCOPES,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "state": state,
    }
    url = "https://www.tiktok.com/v2/auth/authorize?" + urllib.parse.urlencode(params)
    return RedirectResponse(url)


# --------------------------------------------------------------- CALLBACK
@app.get("/oauth/callback")
async def callback(request: Request):
    params = dict(request.query_params)
    state = params.get("state")
    if state and _state_store:
        _state_store.discard(state)  # tek kullanimlik; eksikse de devam

    # A) ADVERTISER akisi: auth_code var
    if params.get("auth_code"):
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                f"{BIZ_BASE}/open_api/v1.3/oauth2/access_token/",
                json={"app_id": APP_ID, "secret": APP_SECRET,
                      "auth_code": params["auth_code"]},
            )
        p = r.json()
        if p.get("code") != 0:
            raise HTTPException(400, f"Advertiser token degisimi basarisiz: {p}")
        d = p["data"]
        rec = {
            "access_token": d.get("access_token"),
            "advertiser_ids": d.get("advertiser_ids"),
            "scope": d.get("scope"),
            "obtained_at": int(time.time()),
        }
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(json.dumps(rec, indent=2))
        adv = ", ".join(rec.get("advertiser_ids") or [])
        return _ok_page("Advertiser (reklam) baglandi", f"Advertiser IDs: {adv}")

    # B) ACCOUNT HOLDER akisi: sadece code var
    if params.get("code"):
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                f"{TT_BASE}/v2/oauth/token/",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "client_key": APP_ID,
                    "client_secret": APP_SECRET,
                    "code": params["code"],
                    "grant_type": "authorization_code",
                    "redirect_uri": REDIRECT_URI,
                },
            )
        p = r.json()
        if "access_token" not in p:
            raise HTTPException(400, f"Account token degisimi basarisiz: {p}")
        rec = {
            "access_token": p.get("access_token"),
            "refresh_token": p.get("refresh_token"),
            "open_id": p.get("open_id"),
            "scope": p.get("scope"),
            "expires_in": p.get("expires_in"),
            "refresh_expires_in": p.get("refresh_expires_in"),
            "obtained_at": int(time.time()),
        }
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        USER_TOKEN_FILE.write_text(json.dumps(rec, indent=2))
        return _ok_page("TikTok hesabi (icerik) baglandi",
                        f"open_id: {rec.get('open_id')}<br>scope: {rec.get('scope')}")

    raise HTTPException(400, f"auth_code/code yok. Gelen: {params}")


@app.get("/token")
def get_token(key: str = "", kind: str = "advertiser"):
    if not START_SECRET or key != START_SECRET:
        raise HTTPException(403, "Gecersiz key")
    f = USER_TOKEN_FILE if kind == "account" else TOKEN_FILE
    if not f.exists():
        raise HTTPException(404, f"{kind} token yok.")
    return JSONResponse(json.loads(f.read_text()))


def _ok_page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        "<html><body style='font-family:sans-serif;max-width:600px;margin:40px auto'>"
        f"<h2>✅ {title}</h2><p>{body}</p>"
        "<p>Token guvenli kaydedildi. Bu pencereyi kapatabilirsin.</p></body></html>"
    )
