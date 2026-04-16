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
