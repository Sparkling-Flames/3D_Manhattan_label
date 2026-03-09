**HoHoNet Active Time 收集说明**

本文件说明如何在现有 HoHoNet 工程中：

- 精确采集标注者在 Label Studio 中的“活跃时间（Active Time）”，
- 日志如何存放、滚动与归档，
- 如何用 `tools/lead_time_stats.py` 将 Label Studio 导出的 `lead_time` 与实测 `active` 时间对齐比较。

**概览**

- 组件：
  - `tools/official/ls_userscript_annotator.js`：正式标注员脚本。默认记录 active time，不提供本地停计时开关。
  - `tools/official/ls_userscript_debug.js`：调试/巡检脚本。默认不记录 active time，只有显式设置 `HOHONET_ENABLE_DEBUG_ACTIVE_TIME=1` 才会开始上报。
  - `tools/cors_server.py`：接收 POST `/log_time` 请求，将日志按天写入 `ACTIVE_LOG_DIR` 指定目录；若未设置，则默认写入项目根目录下的 `active_logs/active_times_YYYY-MM-DD.jsonl`。
  - `tools/lead_time_stats.py`：统计脚本，支持读取 Label Studio 导出文件和 `active_logs/` 目录，提供 `--project` 过滤与 `--detail` 输出。
  - Nginx（在 Docker 容器中）：将浏览器发向 `http://<server>:8000/log_time` 的请求代理到宿主机 Python 服务（容器内通过 `172.17.0.1:8001` 访问宿主）。

**为什么这样设计**

- 使用 Userscript 可以在不改动 Label Studio 后端的前提下采集精确活动数据，安全且低侵入。
- 把日志按天写入目录，便于压缩、归档和按项目分离，避免单个巨大的日志文件。

**启用流程（小白友好）**

1. 浏览器端（Tampermonkey）

  - 正式标注员：安装 `tools/official/ls_userscript_annotator.js`。
  - 调试/巡检人员：安装 `tools/official/ls_userscript_debug.js`。
   - **（重要）在浏览器控制台一次性设置两个参数**（会保存在 `localStorage`，除非你手动清理浏览器数据，否则长期有效）：

     ```js
     // 1) HoHoNet Helper 基址（你的 Nginx 对外端口）
     localStorage.setItem("HOHONET_HELPER_BASE_URL", "http://<server>:8000");

     // 2) /log_time 鉴权 token（可选，但推荐；与服务器端 HOHONET_LOG_TOKEN 保持一致）
     localStorage.setItem("HOHONET_LOG_TOKEN", "<your-secret>");
     ```

    - 如果你已把 `/tools/vis_3d.html` 反代到 Label Studio 同源，建议额外设置：

     ```js
     localStorage.setItem("HOHONET_VIEWER_BASE_URL", location.origin);
     ```

     这样 3D viewer 走同源 iframe，可减少浏览器扩展里常见的 report-only CSP 提示。

   - 如果 3D 视图“几何有但图片纹理没有”，通常是 **WebGL 纹理加载的 CORS 限制**。推荐按下面的 Nginx 配置开启 `/ls/` 同源代理，脚本会自动把 Label Studio(8080) 的图片 URL 改写为 `http://<server>:8000/ls/...`，从而 **不需要** 在云服务器放 `assets/` 目录。
   - debug 脚本默认不计时。如需在 debug 脚本下临时开启计时：

     ```js
     localStorage.setItem("HOHONET_ENABLE_DEBUG_ACTIVE_TIME", "1");
     ```

   - 若要强制关闭 debug 计时：

     ```js
     localStorage.setItem("HOHONET_DISABLE_ACTIVE_TIME", "1");
     ```

2. 服务器端：运行日志接收服务

   - 默认行为：脚本会写入 `<repo_root>/active_logs/active_times_YYYY-MM-DD.jsonl`。
   - 如果服务器环境文件中已设置：
     ```bash
     export ACTIVE_LOG_DIR='active_logs/new_server'
     ```
     那么新服务器的实际写入路径会变成：
     ```bash
     /home/ubuntu/workspace/HoHoNet/active_logs/new_server/active_times_YYYY-MM-DD.jsonl
     ```
   - 启动服务（项目根）：
     ```bash
     cd /home/ubuntu/workspace/HoHoNet
     nohup python3 tools/cors_server.py > server.log 2>&1 &
     ```
   - 如果想把目录名改成 `logs`：
     ```bash
     export ACTIVE_LOG_DIR=logs
     nohup python3 tools/cors_server.py > server.log 2>&1 &
     ```
  - 双服务器推荐（防混淆）：给每台服务器设置不同目录。
     ```bash
     # 旧服务器 106.53.106.49
     export ACTIVE_LOG_DIR=active_logs/old_server

     # 新服务器 175.178.71.217
     export ACTIVE_LOG_DIR=active_logs/new_server
     ```
    说明：当前主要依赖目录分流区分新旧服务器；如果后续需要把服务器标识写入每条日志，需要再单独扩展字段。

3. Nginx（Docker 中）

   - 在 Nginx 配置里添加代理段（容器内代理到宿主 172.17.0.1:8001）：

     ```nginx
     location /log_time {
         proxy_pass http://172.17.0.1:8001;
         add_header 'Access-Control-Allow-Origin' '*' always;
         add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS' always;
         add_header 'Access-Control-Allow-Headers' 'Content-Type' always;
         if ($request_method = 'OPTIONS') {
             add_header 'Access-Control-Allow-Origin' '*';
             add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS';
             add_header 'Access-Control-Allow-Headers' 'Content-Type';
             add_header 'Content-Length' 0;
             return 204;
         }
     }
     ```

   - （推荐）增加 **Label Studio 图片同源代理**，用于 3D Viewer 纹理加载（避免 CORS；也就不需要 `assets/`）：

     ```nginx
     location /ls/ {
         proxy_pass http://172.17.0.1:8080/;
         proxy_set_header Host $host;
         proxy_set_header X-Real-IP $remote_addr;
         proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
         proxy_set_header X-Forwarded-Proto $scheme;
     }
     ```

   - 把修改过的宿主机 `nginx.conf` 挂载到容器中（或修改对应绑定的文件），并 `nginx -s reload`。确保 `curl -I -X OPTIONS http://localhost:8000/log_time` 返回 `204` 且包含 `Access-Control-Allow-Origin`。

4. 验证
  - 正式标注员脚本：在 Label Studio 的任务页面随便活动（鼠标、键盘），等待约 10 秒。
  - debug 脚本：默认不应出现 `log_time` 请求；只有显式开启 `HOHONET_ENABLE_DEBUG_ACTIVE_TIME=1` 后才应上报。
   - 在服务器上检查：
     ```bash
    ls -lh active_logs/new_server
    tail -n 5 active_logs/new_server/active_times_$(date +%F).jsonl
     ```
   - 日志行示例：
     ```json
     {
       "task_id": "463",
       "project_id": "15",
       "project_name": "manual_test",
       "active_seconds": 12,
       "timestamp": 1700000000000
     }
     ```

**把日志搬到本地（若需要）**

- 单文件下载（Windows PowerShell）：
  ```powershell
  scp ubuntu@<host>:/home/ubuntu/workspace/HoHoNet/active_logs/active_times_2025-12-03.jsonl C:\Users\you\Downloads\
  ```
- 多文件：先在服务器打包再下载：
  ```bash
  cd /home/ubuntu/workspace/HoHoNet
  tar -czf /tmp/active_times_logs.tar.gz active_logs/active_times_*.jsonl
  # 然后 scp 下载 /tmp/active_times_logs.tar.gz
  ```

**用 `lead_time_stats.py` 做对比分析**

- 在本地或服务器上运行：
  ```bash
  # 假设 export.json 是 Label Studio 导出的文件
  # 如果 logs 在项目根 active_logs/ 下：
  python3 tools/lead_time_stats.py export.json --active-log active_logs --project 15 --detail
  ```
- 参数说明：
  - `--active-log`：可以是单个文件路径或目录（脚本会扫描 `active_times_*.jsonl`）。
  - `--project`：可选，指定 `project_id` 来只统计该项目的数据。
  - `--detail`：输出中位数、最小、最大、标准差等。

**日志管理（避免占满磁盘）**

1. 每日压缩（示例 crontab，每天 01:05 压缩前一天日志并保留最近 30 天）：

   ```bash
   # 先在服务器上创建脚本 /home/ubuntu/workspace/HoHoNet/scripts/rotate_logs.sh
   # 内容示例：
   #!/bin/bash
   cd /home/ubuntu/workspace/HoHoNet/active_logs
   # 压缩昨天日志
   y=$(date -d "yesterday" +%F)
   if [ -f active_times_${y}.jsonl ]; then
     gzip -9 active_times_${y}.jsonl
   fi
   # 删除 30 天前的压缩文件
   find . -type f -name 'active_times_*.jsonl.gz' -mtime +30 -delete
   ```

   然后用 crontab 调度：

   ```cron
   5 1 * * * /bin/bash /home/ubuntu/workspace/HoHoNet/scripts/rotate_logs.sh
   ```

2. 若日志量极大，建议把压缩文件周期性上传到对象存储（S3/OSS），服务器只保留最近 N 天。

**如何在正式开始标注时启用/停用**

- 正式标注：启用 `tools/official/ls_userscript_annotator.js`。
- 调试巡检：启用 `tools/official/ls_userscript_debug.js`；默认不记录 active time。
- 若 debug 侧确需临时记录，再显式设置 `HOHONET_ENABLE_DEBUG_ACTIVE_TIME=1`。

**常见问题排查**

- 浏览器报 CORS：确认 Nginx 返回的预检响应（OPTIONS）包含 `Access-Control-Allow-Origin`。在宿主机运行：
  ```bash
  curl -I -X OPTIONS -H "Origin: http://<host>:8080" http://localhost:8000/log_time
  ```
- POST 返回 404：说明 Nginx 未代理 `/log_time`，检查容器内 `/etc/nginx/conf.d/default.conf` 与挂载的宿主文件是否一致，`nginx -T` 输出是否包含 `location /log_time`。
- 日志为空或未写入：确认 `cors_server.py` 正在运行，查看 `server.log`（启动时 `nohup` 的输出），并根据当前 `ACTIVE_LOG_DIR` 检查对应目录；例如新服务器可用 `tail -f active_logs/new_server/active_times_$(date +%F).jsonl` 监控。

**示例一键命令（在服务器上运行统计并下载结果）**

```bash
# 在服务器上运行统计并输出到临时文件
python3 tools/lead_time_stats.py /home/ubuntu/export.json --active-log /home/ubuntu/workspace/HoHoNet/active_logs --project 15 --detail > /tmp/stats_project15.txt
# 然后在本地下载
scp ubuntu@<host>:/tmp/stats_project15.txt ./
```
