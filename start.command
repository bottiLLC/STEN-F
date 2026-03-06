#!/bin/bash
cd "$(dirname "$0")"
echo "STEN-F 起動準備中..."

# バックグラウンドで6秒待機してからブラウザを開く
(sleep 6 && open "http://localhost:3000") &

uv run reflex run
