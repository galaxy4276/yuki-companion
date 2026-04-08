#!/usr/bin/env python3
"""
Claude Code hooks 연동 스크립트.
Claude Code settings.json 의 hooks 섹션에 등록해서 사용.

등록 예시 (PreToolUse / PostToolUse / Stop 모두):
{
  "hooks": {
    "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "python3 /home/deveungu/vtuber-companion/hooks/claude_hook.py"}]}],
    "PreToolUse": [...],
    "PostToolUse": [...]
  }
}
"""
import json
import sys
import urllib.request

VTUBER_URL = "http://localhost:8002/hooks/claude"

def main():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    hook_type = payload.get("hook_name") or payload.get("type") or "Stop"
    tool_name  = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    body = json.dumps({
        "hook_type": hook_type,
        "tool_name": tool_name,
        "tool_input": tool_input,
        "session_id": "default",
    }).encode()

    req = urllib.request.Request(
        VTUBER_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=3):
            pass
    except Exception:
        pass  # 서버 미기동 시 조용히 무시

if __name__ == "__main__":
    main()
