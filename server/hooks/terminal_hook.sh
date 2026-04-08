#!/usr/bin/env zsh
# MacOS ~/.zshrc 에 아래 줄을 추가하세요:
#   source /path/to/terminal_hook.sh
#
# 또는 내용을 직접 ~/.zshrc 하단에 붙여넣기

VTUBER_SERVER="http://125.242.221.180:8002"
_CMD_START_TIME=0
_LAST_CMD=""

# 명령어 실행 직전
_vtuber_preexec() {
  _CMD_START_TIME=$(date +%s%3N)  # 밀리초
  _LAST_CMD="$1"
}

# 명령어 실행 직후 (프롬프트 표시 전)
_vtuber_precmd() {
  local exit_code=$?
  local now=$(date +%s%3N)
  local duration=$(( now - _CMD_START_TIME ))
  local cwd="$PWD"

  # 빈 명령어는 무시
  [[ -z "$_LAST_CMD" ]] && return

  # 서버에 비동기 전송 (백그라운드, 터미널 차단 없음)
  curl -s -X POST "$VTUBER_SERVER/hooks/terminal" \
    -H "Content-Type: application/json" \
    -d "{\"command\":\"$_LAST_CMD\",\"exit_code\":$exit_code,\"duration_ms\":$duration,\"cwd\":\"$cwd\"}" \
    --max-time 2 > /dev/null 2>&1 &

  _LAST_CMD=""
}

autoload -Uz add-zsh-hook
add-zsh-hook preexec _vtuber_preexec
add-zsh-hook precmd  _vtuber_precmd
