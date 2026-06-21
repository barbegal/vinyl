#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

# shellcheck source=boot_milestone.sh
. "$APP_DIR/scripts/boot_milestone.sh"
boot_milestone "start_app.sh"

if [[ ! -f "$APP_DIR/.venv/bin/python" ]]; then
  echo "Missing venv at $APP_DIR/.venv — run: python3 -m venv .venv && pip install -r requirements.txt"
  exit 1
fi

# shellcheck source=/dev/null
source "$APP_DIR/.venv/bin/activate"

if [[ -f "$APP_DIR/.env" ]]; then
  set -a
  # shellcheck source=load_env.sh
  source "$APP_DIR/scripts/load_env.sh"
  set +a
fi

export DISPLAY="${DISPLAY:-:0}"
export PYTHONUNBUFFERED=1

exec python -m src.main
