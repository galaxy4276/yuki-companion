#!/usr/bin/env zsh
VTUBER_SERVER="http://125.242.221.180:8002"
_CMD_START_TIME=0
_LAST_CMD=""

_vtuber_preexec() {
  _CMD_START_TIME=$(date +%s%3N)
  _LAST_CMD="$1"
}

_vtuber_precmd() {
  local exit_code=$?
  local now=$(date +%s%3N)
  local duration=$(( now - _CMD_START_TIME ))
  local cwd="$PWD"
  [[ -z "$_LAST_CMD" ]] && return

  local body
  body=$(python3 -c "
import json, sys
print(json.dumps({
    'command': sys.argv[1],
    'exit_code': int(sys.argv[2]),
    'duration_ms': int(sys.argv[3]),
    'cwd': sys.argv[4],
}))
" "$_LAST_CMD" "$exit_code" "$duration" "$cwd" 2>/dev/null) || return

  curl -s -X POST "$VTUBER_SERVER/hooks/terminal" \
    -H "Content-Type: application/json" \
    -d "$body" --max-time 2 > /dev/null 2>&1 &

  _LAST_CMD=""
}

autoload -Uz add-zsh-hook
add-zsh-hook preexec _vtuber_preexec
add-zsh-hook precmd  _vtuber_precmd
