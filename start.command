#!/bin/bash
cd "$(dirname "$0")"
echo "Starting STEN-F Application..."

# Launch browser in the background after 8 seconds
(sleep 8 && open http://localhost:3000) &

uv run reflex run
