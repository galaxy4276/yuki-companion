#!/usr/bin/env bash
# llama.cpp Gemma 4 기동 래퍼. 유저 로컬 경로 맞춰 조정 필요.
set -euo pipefail

LLAMA_BIN="${LLAMA_BIN:-/opt/llama.cpp/server}"
MODEL_PATH="${MODEL_PATH:-/models/gemma-4-26b-a4b.gguf}"
API_KEY="${GEMMA_API_KEY:-w7PhLd603vZQ8Om-Ys7wHeK6CZyzK4ngp1lwsYh2oyQ}"
PORT="${LLAMA_PORT:-8001}"
CTX_SIZE="${LLAMA_CTX:-8192}"

exec "$LLAMA_BIN" \
  -m "$MODEL_PATH" \
  --host 127.0.0.1 --port "$PORT" \
  --api-key "$API_KEY" \
  -ngl 999 -c "$CTX_SIZE"
