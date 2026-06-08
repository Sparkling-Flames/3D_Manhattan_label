#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)

# Optional: load sensitive configuration from a private env file on the server.
# Example file: /home/ubuntu/hohonet_env.sh with chmod 600.
#   export HOHONET_LOG_TOKEN='...'
#   export CORS_SERVER_PORT=8001
#   export ACTIVE_LOG_DIR='active_logs/new_server'
ENV_FILE=${ENV_FILE:-/home/ubuntu/hohonet_env.sh}
if [ -f "$ENV_FILE" ]; then
	# shellcheck disable=SC1090
	source "$ENV_FILE"
fi

# Compatibility defaults. Prefer setting these in the env file above.
export HOHONET_LOG_TOKEN=${HOHONET_LOG_TOKEN:-'hoho-20260228-zjw200408250904!'}
export CORS_SERVER_PORT=${CORS_SERVER_PORT:-8001}

# Stop old server process if present.
pkill -f "tools/label_studio/cors_server.py" || true

echo "Starting HoHoNet Log Server with Token..."
nohup python3 "$REPO_ROOT/tools/label_studio/cors_server.py" > /home/ubuntu/cors_server.log 2>&1 &
echo "Server started in background. Check /home/ubuntu/cors_server.log for details."
