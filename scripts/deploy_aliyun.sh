#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVER="${STEAMREC_SERVER:-root@8.131.69.97}"
REMOTE_DIR="${STEAMREC_REMOTE_DIR:-/opt/steam-group-rec}"
CONFIG_FILE="${STEAMREC_CONFIG_FILE:-$ROOT/配置.md}"

rsync -az --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude 'data' \
  --exclude '配置.md' \
  "$ROOT/" "$SERVER:$REMOTE_DIR/"

ssh "$SERVER" "cd '$REMOTE_DIR' && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
# DeepSeek key 已改为用户网页填写、随请求转发，服务器不保存任何 AI key。
# env 文件只承载访问统计令牌（低敏感，不产生费用）。
STATS_TOKEN=""
if [[ -f "$CONFIG_FILE" ]]; then
  STATS_TOKEN="$(python3 - "$CONFIG_FILE" <<'PY'
import re
import sys
text = open(sys.argv[1], encoding="utf-8").read()
match = re.search(r"stats_token[：:]\s*([A-Za-z0-9_-]+)", text)
print(match.group(1) if match else "")
PY
)"
fi
if [[ -n "$STATS_TOKEN" ]]; then
  printf 'STEAMREC_STATS_TOKEN=%s\n' "$STATS_TOKEN" | ssh "$SERVER" "cat > /etc/steam-group-rec.env && chmod 600 /etc/steam-group-rec.env"
else
  ssh "$SERVER" "rm -f /etc/steam-group-rec.env"
fi
ssh "$SERVER" "cp '$REMOTE_DIR/deploy/steam-group-rec.service' /etc/systemd/system/steam-group-rec.service && systemctl daemon-reload && systemctl enable steam-group-rec && systemctl restart steam-group-rec"
ssh "$SERVER" "cp '$REMOTE_DIR/deploy/nginx-kaluli.conf' /etc/nginx/sites-available/kaluli && ln -sf /etc/nginx/sites-available/kaluli /etc/nginx/sites-enabled/kaluli && nginx -t && systemctl reload nginx"
