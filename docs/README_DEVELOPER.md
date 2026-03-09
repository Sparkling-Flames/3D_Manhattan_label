# HoHoNet 开发者与部署指南 (Developer Guide)

本指南面向项目管理员与开发者，涵盖云端部署、安全配置、数据准备及系统维护。

## 1. 系统架构概览

系统由三个核心组件组成：

1.  **Label Studio (Port 8080)**: 核心标注平台。
2.  **Nginx (Port 8000)**: 静态资源服务器 + 反向代理。负责提供 3D 查看器、图片数据，并代理日志接口。
3.  **Log Server (Port 8001)**: Python 编写的轻量级服务，用于接收并记录标注者的活跃时间。

---

## 2. 部署与配置

### 2.1 Nginx 配置 (Port 8000)

Nginx 是系统的入口，必须正确配置以支持跨域 (CORS) 和同源代理。

- **配置文件**: `nginx.conf` (容器内路径 `/etc/nginx/conf.d/default.conf`)
- **核心逻辑**:
  - `/`: 提供 `tools/vis_3d.html` 等静态工具。
  - `/data/`: 映射宿主机 `data/` 目录，提供标注图片。
  - `/log_time`: 代理到宿主机 8001 端口，并注入 CORS 头。
  - `/ls/` (可选): 代理到 Label Studio (8080)，用于解决 WebGL 纹理跨域问题。

**应用配置命令**:

```bash
docker cp nginx.conf nginx-static:/etc/nginx/conf.d/default.conf
docker exec nginx-static nginx -s reload
```

### 2.2 安全 Token 配置

为了防止日志接口被滥用，系统使用 `X-HOHONET-TOKEN` 进行校验。

1.  **服务端**: 在 `start_log_server.sh` 读取的环境文件中设置 `HOHONET_LOG_TOKEN`；默认环境文件路径是 `/home/ubuntu/hohonet_env.sh`。
2.  **客户端**: 标注员需在浏览器控制台设置相同的 Token：
    ```javascript
    localStorage.setItem("HOHONET_LOG_TOKEN", "你的密钥");
    ```

### 2.3 启动日志服务

```bash
chmod +x start_log_server.sh
./start_log_server.sh
```

> 建议把 token 放到宿主机的私有 env 文件中（默认路径：`/home/ubuntu/hohonet_env.sh`，权限 `chmod 600`），
> 然后直接运行 `./start_log_server.sh`。脚本会优先读取该 env 文件；若没有，才回退到脚本内默认值。
> 如果还设置了 `ACTIVE_LOG_DIR=active_logs/new_server`，那么日志会写入 `/home/ubuntu/workspace/HoHoNet/active_logs/new_server/`，而不是根目录的 `active_logs/`。

日志会按天保存在 `ACTIVE_LOG_DIR` 指定目录中，格式为 `.jsonl`；如果未设置该变量，才默认写入 `active_logs/`。

---

## 3. 数据准备与分析流程 (Data Preparation & Analysis)

### 3.1 导入 Label Studio

1.  准备图片目录：`data/mp3d_layout/test/img/`。
2.  使用 `tools/prepare_labelstudio_docker.py` 生成导入 JSON。
3.  在 Label Studio 界面通过 "Import" 上传生成的 JSON。

> 注意：Label Studio 导出时会写入 choices 的"显示文本"（`Choice value`），而不是 `alias`。
> 因此 `tools/analyze_quality.py` 的 `--quality_mode v2` 解析是按关键词匹配显示文本完成的。
> 当前 v2 配置为三字段：`scope`（单选，决定是否进入主指标）+ `difficulty`（多选）+ `model_issue`（仅半自动，多选）。
> 其中 `scope` 的多个 OOS 子类（几何假设不成立/边界不可判定/错层多平面/证据不足）会按 OOS 处理：主 layout 指标默认剔除，但会单列计数与 gate reason。

### 3.2 质量分析工作流（单数据集 → 汇总）

**阶段 1：试运行（单数据集，3-5 人）**
```bash
# 从 Label Studio 导出 JSON
python tools/analyze_quality.py export_pilot.json --output_dir analysis_results_pilot
```
输出：`quality_report_YYYYMMDD.csv`（包含 per-annotation 指标、IAA、r_u）

**阶段 2：正式标注（5 个数据集并行）**
- `main_manual`：100 样本，纯人工
- `main_semi`：100 样本，半自动
- `calibration_manual`：30 样本，多人标注（用于 Scheme A 的 r_u 估计）
- `validation_manual/semi`：各 60 样本（用于分配策略验证）

分别分析：
```bash
python tools/analyze_quality.py export_main_manual.json --output_dir analysis_results
python tools/analyze_quality.py export_main_semi.json --output_dir analysis_results
# ... 其余 3 个数据集
```

**阶段 3：汇总分析（跨数据集对比）**
```bash
python tools/aggregate_analysis.py --csv main_manual:analysis_results/quality_report_manual.csv main_semi:analysis_results/quality_report_semi.csv calibration_manual:analysis_results/quality_report_calib.csv validation_manual:analysis_results/quality_report_valman.csv validation_semi:analysis_results/quality_report_valsemi.csv --output-dir analysis_results --output-prefix aggregate_final
```

输出：
- 合并 CSV（带 dataset/condition/subset 列）
- 汇总统计 JSON（分组 mean/std/median）
- 对比表格 Markdown（Manual vs Semi）

### 3.2 路径映射说明

确保 Docker 启动时挂载了正确的路径：

```bash
docker run -d --name nginx-static -p 8000:80 -v /home/ubuntu/workspace/HoHoNet:/usr/share/nginx/html:ro nginx:1.29.3
```

---

## 4. 维护与排障

- **图片 404**: 检查 `nginx-static` 容器挂载路径，确保容器内 `/usr/share/nginx/html/data` 存在文件。
- **3D 纹理黑屏**: 确保 Nginx 返回了 `Access-Control-Allow-Origin: *` 头，或引导用户通过 `8000/ls/` 访问。
- **日志未记录**: 检查 `server.log` 以及当前 `ACTIVE_LOG_DIR` 指向的目录权限，确保 Python 进程有写入权限；如果你在新服务器环境文件里设置了 `ACTIVE_LOG_DIR=active_logs/new_server`，就不要只盯着根目录 `active_logs/`。
