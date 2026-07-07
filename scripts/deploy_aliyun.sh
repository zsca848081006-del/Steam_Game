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
# env 文件承载：访问统计令牌 + 站长兜底 Steam Key（站长知情同意，供网页留空时使用）。
ENV_CONTENT=""
if [[ -f "$CONFIG_FILE" ]]; then
  ENV_CONTENT="$(python3 - "$CONFIG_FILE" <<'PY'
import re
import sys
text = open(sys.argv[1], encoding="utf-8").read()
stats = re.search(r"stats_token[：:]\s*([A-Za-z0-9_-]+)", text)
steam = re.search(r"steamapi[：:]\s*([A-Za-z0-9]+)", text)
lines = []
if stats:
    lines.append(f"STEAMREC_STATS_TOKEN={stats.group(1)}")
if steam:
    lines.append(f"STEAMREC_FALLBACK_STEAM_KEY={steam.group(1)}")
print("\n".join(lines))
PY
)"
fi
if [[ -n "$ENV_CONTENT" ]]; then
  printf '%s\n' "$ENV_CONTENT" | ssh "$SERVER" "cat > /etc/steam-group-rec.env && chmod 600 /etc/steam-group-rec.env"
else
  ssh "$SERVER" "rm -f /etc/steam-group-rec.env"
fi
ssh "$SERVER" "cp '$REMOTE_DIR/deploy/steam-group-rec.service' /etc/systemd/system/steam-group-rec.service && systemctl daemon-reload && systemctl enable steam-group-rec && systemctl restart steam-group-rec"
ssh "$SERVER" "cp '$REMOTE_DIR/deploy/nginx-kaluli.conf' /etc/nginx/sites-available/kaluli && ln -sf /etc/nginx/sites-available/kaluli /etc/nginx/sites-enabled/kaluli && nginx -t && systemctl reload nginx"
