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
if [[ -f "$CONFIG_FILE" ]]; then
  DEEPSEEK_API_KEY="$(python3 - "$CONFIG_FILE" <<'PY'
import re
import sys
text = open(sys.argv[1], encoding="utf-8").read()
match = re.search(r'"deepseek_api_key"\s*:\s*"([^"]+)"', text)
print(match.group(1) if match else "")
PY
)"
  if [[ -n "$DEEPSEEK_API_KEY" ]]; then
    printf 'DEEPSEEK_API_KEY=%q\n' "$DEEPSEEK_API_KEY" | ssh "$SERVER" "cat > /etc/steam-group-rec.env && chmod 600 /etc/steam-group-rec.env"
  fi
fi
ssh "$SERVER" "cp '$REMOTE_DIR/deploy/steam-group-rec.service' /etc/systemd/system/steam-group-rec.service && systemctl daemon-reload && systemctl enable steam-group-rec && systemctl restart steam-group-rec"
