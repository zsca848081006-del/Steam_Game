#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export STEAMREC_PORT="${STEAMREC_PORT:-8673}"
exec .venv/bin/python app.py
