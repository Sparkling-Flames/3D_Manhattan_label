# active_logs 说明

`active_logs/` 是原始 `active_time` 日志真源。云服务器端的日志存储位置不需要随 `tools/` 源码迁移而改变。

## 云服务器存储逻辑

云服务器仓库根目录示例：

```text
/home/ubuntu/workspace/HoHoNet/
```

当前日志目录仍应位于仓库根下：

```text
/home/ubuntu/workspace/HoHoNet/active_logs/
```

如果云端启动时设置：

```bash
ACTIVE_LOG_DIR="active_logs/new_server"
```

则新日志应写入：

```text
/home/ubuntu/workspace/HoHoNet/active_logs/new_server/
```

这和源码文件是否从 `tools/cors_server.py` 迁移到 `tools/label_studio/cors_server.py` 是两件事。迁移后的 `cors_server.py` 需要继续以仓库根目录解析相对 `ACTIVE_LOG_DIR`，避免误写到 `tools/active_logs/`。

## 本地归档建议

- 老服务器日志可归档到 `active_logs/old_server/`。
- 新服务器日志可归档到 `active_logs/new_server/`。
- 本地归档目录仍是原始日志层，不是分析输出层。

常用拉取命令：

```bash
scp -r ubuntu@106.53.106.49:/home/ubuntu/workspace/HoHoNet/active_logs "D:\Work\HOHONET\active_logs\old_server"

scp -r ubuntu@175.178.71.217:/home/ubuntu/workspace/HoHoNet/active_logs/new_server/. "D:\Work\HOHONET\active_logs\new_server"
```

如果要先清空本地旧内容再覆盖：

```powershell
Remove-Item -Recurse -Force "D:\Work\HOHONET\active_logs\new_server\*"
```

然后再执行上面的 `scp` 命令。

如果需要让新服务器直接写入独立目录，例如 `active_logs/new_server`，需要在服务器环境变量中设置：

```bash
export ACTIVE_LOG_DIR="active_logs/new_server"
```

然后重新启动 `cors_server`。

你当前新服务器如果已经在 `/home/ubuntu/hohonet_env.sh` 中这样设置了，那么服务端日志就会直接落到 `active_logs/new_server/`，这与本地归档目录命名是一致的。

## 边界

- 不把 active log 写入 `export_label/`。
- 不把云端日志目录改到 `tools/` 下。
- 不把 `analysis_results/` 当作 active log 输入真源。
- 不因源码路径迁移改变 active-time schema 或统计口径。
