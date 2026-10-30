#!/usr/bin/env bash
# 门洞交界 · 空间审核：本地启动脚本（HTTP/1.1 keep-alive，避免首访偶发连接重置）
# 用法：./serve.sh [端口]（默认 8787）
set -euo pipefail
PORT="${1:-8787}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$DIR/serve.py" "$PORT"
