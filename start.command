#!/bin/bash
cd "$(dirname "$0")"
echo "STEN-F 起動準備中..."

# 別プロセスとして7秒待機後にブラウザを起動させる
(sleep 7 && open http://localhost:3000) &

uv run reflex run
