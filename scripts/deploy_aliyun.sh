#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVER="${STEAMREC_SERVER:-root@8.131.69.97}"
REMOTE_DIR="${STEAMREC_REMOTE_DIR:-/opt/steam-group-rec}"

rsync -az --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude 'data' \
  --exclude '配置.md' \
  "$ROOT/" "$SERVER:$REMOTE_DIR/"

ssh "$SERVER" "cd '$REMOTE_DIR' && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
ssh "$SERVER" "cp '$REMOTE_DIR/deploy/steam-group-rec.service' /etc/systemd/system/steam-group-rec.service && systemctl daemon-reload && systemctl enable steam-group-rec && systemctl restart steam-group-rec"
