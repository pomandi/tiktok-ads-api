"""
TikTok Marketing API v1.3 — kampanya yayinlama helper'i.

Kullanim:
    export TIKTOK_ACCESS_TOKEN=...      # /token endpoint'inden veya tokens.json'dan
    export TIKTOK_ADVERTISER_ID=...     # bagladigin reklam hesabi
    python tiktok_client.py

Reklam hiyerarsisi:
    Campaign (hedef + butce stratejisi)
      └── Ad Group (hedef kitle + butce + teklif + yerlestirme)
            └── Ad (creative: video/gorsel + metin + CTA)
"""
import os
import json
import httpx

BASE = "https://business-api.tiktok.com/open_api/v1.3"
TOKEN = os.environ["TIKTOK_ACCESS_TOKEN"]
ADV_ID = os.environ["TIKTOK_ADVERTISER_ID"]

HEADERS = {"Access-Token": TOKEN, "Content-Type": "application/json"}


def _post(path: str, body: dict) -> dict:
    body = {"advertiser_id": ADV_ID, **body}
    r = httpx.post(f"{BASE}{path}", headers=HEADERS, json=body, timeout=60)
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"{path} hata: {data}")
    return data["data"]


def create_campaign(name: str, objective: str = "TRAFFIC") -> str:
    """
    objective ornekleri: TRAFFIC, REACH, VIDEO_VIEWS, WEB_CONVERSIONS,
    LEAD_GENERATION, PRODUCT_SALES
    Takim elbise icin tipik: WEB_CONVERSIONS (pixel ile) veya TRAFFIC (test icin)
    """
    data = _post(
        "/campaign/create/",
        {
            "campaign_name": name,
            "objective_type": objective,
            "budget_mode": "BUDGET_MODE_INFINITE",  # butceyi ad group'ta yonet
        },
    )
    print("Campaign:", data["campaign_id"])
    return data["campaign_id"]


def create_adgroup(
    campaign_id: str,
    name: str,
    daily_budget: float = 20.0,
    pixel_id: str | None = None,
    optimization_event: str = "ON_WEB_ORDER",
) -> str:
    """
    Gunluk butce, hedef kitle ve teklif. Asagidaki ornek:
    - Placement: otomatik (TikTok)
    - Lokasyon: Belcika + Hollanda (BE, NL)  -> location_ids gercekte numeric;
      asagida ulke kodu yerine TikTok'un location_ids'i gerekir (region API'den cek)
    """
    body = {
        "campaign_id": campaign_id,
        "adgroup_name": name,
        "placement_type": "PLACEMENT_TYPE_AUTOMATIC",
        "budget_mode": "BUDGET_MODE_DAY",
        "budget": daily_budget,
        "schedule_type": "SCHEDULE_FROM_NOW",
        "billing_event": "OCPM",
        "optimization_goal": "CONVERT" if pixel_id else "CLICK",
        "bid_type": "BID_TYPE_NO_BID",  # lowest cost
        # Hedef kitle ornegi — gerekirse genislet:
        "location_ids": [],  # region/list/ ile BE+NL location_id'lerini doldur
        "gender": "GENDER_UNLIMITED",
        "age_groups": ["AGE_25_34", "AGE_35_44", "AGE_45_54"],
    }
    if pixel_id:
        body["pixel_id"] = pixel_id
        body["optimization_event"] = optimization_event
    data = _post("/adgroup/create/", body)
    print("Ad Group:", data["adgroup_id"])
    return data["adgroup_id"]


def create_ad(
    adgroup_id: str,
    ad_name: str,
    video_id: str,
    text: str,
    landing_url: str,
    cta: str = "SHOP_NOW",
    identity_id: str | None = None,
) -> str:
    """
    video_id: once /file/video/ad/upload/ ile video yuklenir, donen video_id buraya.
    identity_id: TikTok hesabi kimligi (/identity/get/ ile alinir).
    """
    creative = {
        "ad_name": ad_name,
        "ad_format": "SINGLE_VIDEO",
        "video_id": video_id,
        "ad_text": text,
        "call_to_action": cta,
        "landing_page_url": landing_url,
    }
    if identity_id:
        creative["identity_id"] = identity_id
        creative["identity_type"] = "CUSTOMIZED_USER"
    data = _post("/ad/create/", {"adgroup_id": adgroup_id, "creatives": [creative]})
    print("Ad:", data["ad_ids"])
    return data["ad_ids"][0]


if __name__ == "__main__":
    # ORNEK akis (gercek video_id ve pixel_id koymadan calismaz):
    cid = create_campaign("Pomandi - Takim Elbise TEST", objective="TRAFFIC")
    agid = create_adgroup(cid, "BE+NL 25-54", daily_budget=20.0)
    print("\nKampanya iskeleti hazir. Simdi creative yukleyip ad/create yap.")
    print("Detaylar: https://business-api.tiktok.com/portal/docs")
