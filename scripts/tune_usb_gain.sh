#!/usr/bin/env bash
# Calibrate USB capture + cast gain (writes ~/.vinyl/calibration.json).
# Run while playing a record: bash scripts/tune_usb_gain.sh 3
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

SECS="${1:-2}"
FORCE=""
if [[ "${2:-}" == "--force" ]]; then
  FORCE="--force"
fi

if [[ ! -x "$APP_DIR/.venv/bin/python" ]]; then
  echo "Missing venv — run: python3 -m venv .venv && pip install -r requirements.txt"
  exit 1
fi

# shellcheck source=/dev/null
source "$APP_DIR/.venv/bin/activate"

if [[ -f "$APP_DIR/.env" ]]; then
  set -a
  # shellcheck source=load_env.sh
  VINYL_ENV_FILE="$APP_DIR/.env" source "$APP_DIR/scripts/load_env.sh"
  set +a
fi

exec python -m src.audio.gain_calibration "$SECS" $FORCE
