#!/bin/bash
# tiktok.pomandi.com icin Let's Encrypt cert'ini bekler;
# cert gelince DNS'i Cloudflare proxy'ye geri alir ve https'i dogrular.
set -u
cd /home/claude
set -a; source cloudflare-migration/.env 2>/dev/null; set +a
T="${CLOUDFLARE_API_TOKEN%\"}"; T="${T#\"}"
Z="${CF_ZONE_POMANDI_COM%\"}"; Z="${Z#\"}"
RID=$(cat /tmp/tiktok_rid.txt)
ORIGIN=46.224.117.155
HOST=tiktok.pomandi.com
LOG=/home/claude/tiktok-ads-api/le-monitor.log
echo "$(date -u) START monitor rid=$RID" >> "$LOG"

for i in $(seq 1 60); do   # ~60 dk
  iss=$(echo | timeout 12 openssl s_client -connect $ORIGIN:443 -servername $HOST 2>/dev/null | openssl x509 -noout -issuer 2>/dev/null)
  echo "$(date -u) iter=$i issuer=$iss" >> "$LOG"
  if echo "$iss" | grep -qiE "let's encrypt|O = Let|CN = R1|CN = E[0-9]"; then
    echo "$(date -u) LE CERT DETECTED -> re-enabling Cloudflare proxy" >> "$LOG"
    resp=$(curl -s -X PATCH "https://api.cloudflare.com/client/v4/zones/$Z/dns_records/$RID" \
      -H "Authorization: Bearer $T" -H "Content-Type: application/json" \
      --data '{"proxied":true}')
    echo "$(date -u) proxy-set: $resp" >> "$LOG"
    sleep 20
    for j in 1 2 3 4 5; do
      code=$(curl -s -m 20 -o /dev/null -w "%{http_code}" "https://$HOST/healthz")
      echo "$(date -u) verify$j https://$HOST/healthz -> $code" >> "$LOG"
      [ "$code" = "200" ] && { echo "$(date -u) SUCCESS - fully live behind Cloudflare" >> "$LOG"; exit 0; }
      sleep 15
    done
    echo "$(date -u) cert OK but proxy verify not 200 yet (CF edge cert may need a minute)" >> "$LOG"
    exit 0
  fi
  sleep 60
done
echo "$(date -u) TIMEOUT - no LE cert after ~60min (likely LE rate-limit; will need manual recheck)" >> "$LOG"
exit 1
