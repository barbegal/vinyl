#!/usr/bin/env bash
# Add keys from .env.example that are missing in .env (never overwrites existing values).
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV="$APP_DIR/.env"
EXAMPLE="$APP_DIR/.env.example"

if [[ ! -f "$EXAMPLE" ]]; then
  echo "Missing $EXAMPLE"
  exit 1
fi

if [[ ! -f "$ENV" ]]; then
  cp "$EXAMPLE" "$ENV"
  echo "Created .env from .env.example"
  exit 0
fi

added=0
# Ensure .env ends with a newline before appending keys (avoids merging with CAST_KNOWN_HOSTS=)
if [[ -s "$ENV" ]] && [[ -n "$(tail -c1 "$ENV" | tr -d '\n')" ]]; then
  printf '\n' >>"$ENV"
fi
while IFS= read -r line || [[ -n "$line" ]]; do
  case "$line" in
    ''|'#'*) continue ;;
    [A-Za-z_]*=*)
      key="${line%%=*}"
      if ! grep -qE "^${key}=" "$ENV" 2>/dev/null; then
        printf '%s\n' "$line" >>"$ENV"
        echo "  added ${key}"
        added=$((added + 1))
      fi
      ;;
  esac
done <"$EXAMPLE"

if [[ "$added" -eq 0 ]]; then
  echo ".env already has all keys from .env.example"
else
  echo "  appended ${added} key(s) — review .env before reboot"
fi
