#!/bin/bash
set -euo pipefail

# 可选：从单独的 env 文件读取敏感配置（推荐，避免把 token 写进脚本/仓库）
# 例如在服务器上创建：/home/ubuntu/hohonet_env.sh（chmod 600），内容：
#   export HOHONET_LOG_TOKEN='...'
#   export CORS_SERVER_PORT=8001
ENV_FILE=${ENV_FILE:-/home/ubuntu/hohonet_env.sh}
if [ -f "$ENV_FILE" ]; then
	# shellcheck disable=SC1090
	source "$ENV_FILE"
fi

# 旧服务器默认 token（历史备份）
export HOHONET_LOG_TOKEN=${HOHONET_LOG_TOKEN:-'hoho-20251222-zjw200408251734!'}
export CORS_SERVER_PORT=${CORS_SERVER_PORT:-8001}

# 杀掉旧进程（如果不存在，不要让脚本失败）
pkill -f "tools/cors_server.py" || true

# 启动服务
echo "Starting HoHoNet Log Server with Token..."
nohup python3 tools/cors_server.py > /home/ubuntu/cors_server.log 2>&1 &
echo "Server started in background. Check /home/ubuntu/cors_server.log for details."
