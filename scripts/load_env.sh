# POSIX sh: load KEY=VALUE lines from .env, ignoring comments / stray content
# (e.g. git diff headers like "@ -0,0 ...").  Safe to source from bash or dash.
# Usage: source scripts/load_env.sh /path/to/.env
#   - Caller may set `set -a` first so values are exported.
#   - Pass the .env path explicitly; do NOT rely on BASH_SOURCE (absent in dash).

_vinyl_env_file="${1:-}"
if [ -z "$_vinyl_env_file" ]; then
  if [ -n "${VINYL_ENV_FILE:-}" ]; then
    _vinyl_env_file="$VINYL_ENV_FILE"
  fi
fi

if [ -n "$_vinyl_env_file" ] && [ -f "$_vinyl_env_file" ]; then
  while IFS= read -r _vinyl_line || [ -n "$_vinyl_line" ]; do
    case "$_vinyl_line" in
      ''|'#'*|'@'*|' '*'#'*) continue ;;
    esac
    case "$_vinyl_line" in
      [A-Za-z_]*=*)
        _vinyl_key="${_vinyl_line%%=*}"
        _vinyl_val="${_vinyl_line#*=}"
        # Strip one layer of surrounding quotes (optional in .env).
        case "$_vinyl_val" in
          \"*\") _vinyl_val="${_vinyl_val#\"}"; _vinyl_val="${_vinyl_val%\"}" ;;
          \'*\') _vinyl_val="${_vinyl_val#\'}"; _vinyl_val="${_vinyl_val%\'}" ;;
        esac
        # Do not use eval — unquoted spaces (e.g. "Living Room Speaker") break set -e boot.
        export "$_vinyl_key=$_vinyl_val"
        ;;
    esac
  done <"$_vinyl_env_file"
fi

unset _vinyl_line
unset _vinyl_key
unset _vinyl_val
unset _vinyl_env_file
