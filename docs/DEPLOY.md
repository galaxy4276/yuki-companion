# Yuki Companion 배포 가이드

## 서버 (GPU 호스트)

SSH: `ssh -p 22022 deveungu@125.242.221.180`

### 포트
- `22022` SSH
- `8001` llama.cpp (localhost 전용)
- `8002` orchestrator (외부 공개)
- `8880` Qwen3-TTS (localhost 전용)
- `3301` sometime-central MCP (Phase 6, localhost 전용)

### 방화벽 (ufw)
```bash
sudo ufw allow 22022/tcp
sudo ufw allow 8002/tcp
sudo ufw enable
```

### systemd 등록
```bash
sudo cp deploy/yuki-*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now yuki-llm yuki-orchestrator
sudo journalctl -u yuki-orchestrator -f
```

### 로그
- `server/logs/yuki.log` (rotation 10MB x 7)
- systemd: `journalctl -u yuki-orchestrator --since '10 min ago'`

## 클라이언트

```bash
cd client && npm install && npm start
# 빌드
npm run build:mac
```

## MCP 통합 (sometime-central)

### 전제
- MCP 서버는 **smartnewbie macmini** (`macmini.tail6899df.ts.net`)에 기배포됨
- 공개 엔드포인트: `https://mcp.sometime-central.com/mcp` (Cloudflare + Tailscale Funnel)
- 내부 Tailscale 경로: `https://macmini.tail6899df.ts.net/mcp`
- 추가 배포 불필요

### 접근 옵션

**Option A (권장): 공개 HTTPS**
- yuki 서버(GPU)가 인터넷 outbound만 있으면 작동
- `MCP_BASE_URL=https://mcp.sometime-central.com/mcp`
- Bearer token 필요

**Option B: Tailscale 참여**
- yuki 서버에 Tailscale 설치 → tailnet 가입
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --authkey=<smartnewbie tailnet authkey>
```
- `MCP_BASE_URL=https://macmini.tail6899df.ts.net/mcp`
- 동일 tailnet 내이므로 Cloudflare bypass

### Bearer token 획득
macmini 측 관리자로부터 `MCP_HTTP_BEARER_TOKEN` 발급:
```bash
ssh smartnewbie_macmini@macmini.tail6899df.ts.net
# .secrets/mcp-bearer-token.txt 또는 launchd plist env 확인
```

### yuki orchestrator에 주입
```bash
sudo systemctl edit yuki-orchestrator
# 에디터에 추가:
[Service]
Environment=MCP_BASE_URL=https://mcp.sometime-central.com/mcp
Environment=MCP_BEARER_TOKEN=<발급받은 토큰>
# 저장 후
sudo systemctl restart yuki-orchestrator
```

### 동작 확인
```bash
curl -X POST "$MCP_BASE_URL" \
  -H "Authorization: Bearer $MCP_BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | jq '.result.tools | length'
# → 숫자 출력 (허용된 tool 개수)
```

### 실패 시 폴백
- `MCP_BEARER_TOKEN` 미주입 시 `MCP_ENABLED=False` → tool-loop 자동 스킵
- `tools/list` 실패 로그 `[MCP] tools/list 실패` → MCP 비필수
