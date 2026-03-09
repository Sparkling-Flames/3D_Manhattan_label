#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)

# 可选：从单独的 env 文件读取敏感配置（推荐，避免把 token 写进脚本/仓库）
# 例如在服务器上创建：/home/ubuntu/hohonet_env.sh（chmod 600），内容：
#   export HOHONET_LOG_TOKEN='...'
#   export CORS_SERVER_PORT=8001
ENV_FILE=${ENV_FILE:-/home/ubuntu/hohonet_env.sh}
if [ -f "$ENV_FILE" ]; then
	# shellcheck disable=SC1090
	source "$ENV_FILE"
fi

# 兼容：如果没有 env 文件/外部注入，则使用脚本内默认值（你可以按需改掉这一行）
export HOHONET_LOG_TOKEN=${HOHONET_LOG_TOKEN:-'hoho-20260228-zjw200408250904!'}
export CORS_SERVER_PORT=${CORS_SERVER_PORT:-8001}

# 杀掉旧进程（如果不存在，不要让脚本失败）
pkill -f "cors_server.py" || true

# 启动服务
echo "Starting HoHoNet Log Server with Token..."
nohup python3 "$REPO_ROOT/tools/cors_server.py" > /home/ubuntu/cors_server.log 2>&1 &
echo "Server started in background. Check /home/ubuntu/cors_server.log for details."
