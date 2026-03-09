本目录用于归档 active_time 日志。

服务端实际写入位置：
- 默认是仓库根目录下的 active_logs，即 /home/ubuntu/workspace/HoHoNet/active_logs
- 对应逻辑见 tools/cors_server.py：默认写入 repo_root/active_logs/active_times_YYYY-MM-DD.jsonl
- 只有显式设置环境变量 ACTIVE_LOG_DIR 时，服务端才会改写到别的目录

本地归档建议：
- old_server/ 仅用于从旧服务器拉回历史日志快照
- new_server/ 仅用于从新服务器拉回历史日志快照
- 这两个子目录是本地整理用途，不是服务端自动分流目录

常用拉取命令：

scp -r ubuntu@106.53.106.49:/home/ubuntu/workspace/HoHoNet/active_logs "D:\Work\HOHONET\active_logs\old_server"

scp -r ubuntu@175.178.71.217:/home/ubuntu/workspace/HoHoNet/active_logs "D:\Work\HOHONET\active_logs\new_server"

如果需要让新服务器直接写入独立目录，例如 active_logs/new_server，需要在服务器环境变量中设置：

export ACTIVE_LOG_DIR="active_logs/new_server"

然后重新启动 cors_server。

你当前新服务器如果已经在 `/home/ubuntu/hohonet_env.sh` 中这样设置了，那么服务端日志就会直接落到 `active_logs/new_server/`，这与本地归档目录命名是一致的。