"""
TikTok Content Posting API — Direct Post (dosya yukleme).

Kullanim:
    export TIKTOK_USER_TOKEN=...     # /token?kind=account cikisindan
    python content_posting.py video.mp4 "Acilis kampanyasi #takimelbise"

Akis:
  1. creator_info/query  -> izinli privacy seviyelerini ogren
  2. video/init (FILE_UPLOAD) -> upload_url al
  3. PUT ile video baytlarini yukle
  4. status/fetch -> yayin durumu

NOT: App audit'ten gecmeden privacy_level sadece SELF_ONLY (gizli) olabilir.
Audit sonrasi PUBLIC_TO_EVERYONE kullanilabilir.
"""
import os
import sys
import time

import httpx

BASE = "https://open.tiktokapis.com/v2"
TOKEN = os.environ["TIKTOK_USER_TOKEN"]
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json; charset=UTF-8"}


def creator_info() -> dict:
    r = httpx.post(f"{BASE}/post/publish/creator_info/query/", headers=H, timeout=30)
    d = r.json()
    print("creator_info:", d.get("data", d))
    return d.get("data", {})


def direct_post(video_path: str, title: str, privacy: str = "SELF_ONLY") -> str:
    size = os.path.getsize(video_path)
    init_body = {
        "post_info": {
            "title": title,
            "privacy_level": privacy,
            "disable_comment": False,
            "disable_duet": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": size,
            "chunk_size": size,          # tek parca (kucuk videolar icin)
            "total_chunk_count": 1,
        },
    }
    r = httpx.post(f"{BASE}/post/publish/video/init/", headers=H, json=init_body, timeout=60)
    d = r.json()
    if d.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(f"init hata: {d}")
    publish_id = d["data"]["publish_id"]
    upload_url = d["data"]["upload_url"]
    print("publish_id:", publish_id)

    with open(video_path, "rb") as f:
        data = f.read()
    put = httpx.put(
        upload_url,
        headers={
            "Content-Type": "video/mp4",
            "Content-Length": str(size),
            "Content-Range": f"bytes 0-{size-1}/{size}",
        },
        content=data,
        timeout=300,
    )
    print("upload status:", put.status_code)

    for _ in range(20):
        s = httpx.post(
            f"{BASE}/post/publish/status/fetch/",
            headers=H, json={"publish_id": publish_id}, timeout=30,
        ).json()
        st = s.get("data", {}).get("status")
        print("status:", st)
        if st in ("PUBLISH_COMPLETE", "FAILED"):
            print(s.get("data"))
            break
        time.sleep(5)
    return publish_id


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("kullanim: python content_posting.py <video.mp4> <baslik> [privacy]")
        sys.exit(1)
    privacy = sys.argv[3] if len(sys.argv) > 3 else "SELF_ONLY"
    info = creator_info()
    print("izinli privacy:", info.get("privacy_level_options"))
    direct_post(sys.argv[1], sys.argv[2], privacy)
