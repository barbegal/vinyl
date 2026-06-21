#!/usr/bin/env bash
# Load KEY=VALUE lines from .env without executing stray content (git diff headers, etc.).
# Usage: source scripts/load_env.sh [path-to-.env]
set -euo pipefail

ENV_FILE="${1:-}"
if [[ -z "$ENV_FILE" ]]; then
  APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  ENV_FILE="$APP_DIR/.env"
fi

if [[ ! -f "$ENV_FILE" ]]; then
  return 0 2>/dev/null || exit 0
fi

while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line#"${line%%[![:space:]]*}"}"
  [[ -z "$line" || "$line" =~ ^# ]] && continue
  [[ "$line" =~ ^@ ]] && continue
  if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
    export "$line"
  fi
done <"$ENV_FILE"
