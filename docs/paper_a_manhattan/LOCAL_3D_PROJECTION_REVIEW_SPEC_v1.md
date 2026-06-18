# M15.19 Local 3D Projection Review Spec v1

## 1. 定位与边界

M15.19 是 Paper A Manhattan 线的 expert-side / offline / local-only 几何审查基座。它把当前 `tools/label_studio/vis_3d.html` 的 2D→3D 投影公式镜像为 Python，可为 original 与最多 3 个 M15.18.3 candidate 生成 3D 坐标、几何指标、Markdown 报告和本地只读 HTML。

本工具：

- 不连接云服务器，不访问 Label Studio API；
- 不读取 Three.js 场景作为算法输入；
- 不修改标注，不生成 annotation patch；
- 不自动优化、重排、合并或删除 corner；
- 不修改 official / worker-facing userscript；
- 不生成 routing、worker score、formal `g_t` 或 `P1/C1/C2/T1/V1` artifact；
- 不把 metric 最优解释为 correctness 或 GT。

## 2. 坐标合同

official userscript 当前的真实链路为：

1. Label Studio keypoint 提供 0–100 的 `x/y`；
2. userscript 执行 `px = x * W / 100`、`py = y * H / 100`；
3. 上下点配对后以两点 x 均值形成单一 column `x`；
4. `vis_3d.html` 接收 W/H 像素坐标。

`normalize_layout_coordinates` 支持：

- `ls_percent`：显式把 top/bottom x/y 从 0–100 转成 W/H 像素；
- `vis_pixels`：不重复缩放；
- `auto`：所有值位于 0–100 时优先按 LS/result/report 语义判为 `ls_percent`，同时写入 ambiguity warning；出现超过 100 且仍落在 W/H 范围内的值时判为 `vis_pixels`。

输出必须记录 requested/effective coordinate mode、推断理由、warning、W、H 和 `CAM_H`。top/bottom x 均值用于投影，原始垂直 x residual 另行保留。

## 3. 投影公式

Python 公式逐项镜像 `vis_3d.html::renderGeometry`：

```text
u = (x / W) * 2π - π
v_floor = (y_floor / H - 0.5) * π
v_ceiling = (y_ceiling / H - 0.5) * π
safe_floor = clamp(v_floor, 0.01, 1.5)
dist = CAM_H / tan(safe_floor)
floor_3d = (dist * sin(u), -CAM_H, -dist * cos(u))
safe_ceiling = clamp(v_ceiling, -1.5, -0.01)
ceiling_y = -dist * tan(safe_ceiling)
ceiling_3d = (dist * sin(u), ceiling_y, -dist * cos(u))
```

每个 pair 保留 raw/safe angle、floor/ceiling clamp flag、3D 坐标、wall height、vertical x residual、effective pair index 和 source preview order index。

## 4. 几何指标

- Floorprint：每面墙的 floor vector、长度、方向、最近 90°世界轴及角度 residual；同时报告 ceiling length、length ratio、短墙和 self-intersection。
- Corner turn：前后墙夹角及相对 90° residual；超过 15°只作为 review warning。
- Height：per-pair wall height、全局 median、signed/absolute residual、局部窗口 residual。异常阈值取 `max(0.25 m, 2.5 × MAD)`。
- Dense pair：center-x separation、3D floor separation、radial floor-distance delta、邻接短墙关系。分类词汇和阈值与 M15.15 保持兼容：`dense_but_distinct_3d_corner`、`unresolved_dense_corner`、`true_duplicate_2d_3d`。

墙方向以 viewer 世界坐标的固定 0/90°轴为参考；这些 residual 是 projection-space plausibility diagnostic，不是 image evidence 或 correctness。

## 5. Candidate variant

提供 M15.18.3 JSON 时，仅接收：

- `recommendation_eligible=true`；
- `probe_mode=align_then_translate_column`；
- 带有单一 effective target pair 和 after coordinates 的 row。

最多生成 `candidate_1..candidate_3`。每个 variant 从 original 深拷贝，只替换目标 pair 坐标，不改变顺序和其他 pair，并重新计算全部指标及 before/after delta。若只有 Markdown report，可从 `Human Action Summary` 做 best-effort fallback；JSON 仍是优先来源。

## 6. 本地图片与 provenance

解析优先级：

1. `--image-path`；
2. `--image-root / URL basename`；
3. 在 image-root 下递归按 basename 查找。

全程无网络请求。找不到图片时仍输出 geometry-only 报告和 HTML warning。JSON 记录 image basename/相对路径、存在性、SHA-256、mtime、可用时的分辨率；不记录本机绝对路径。input/candidate 同样记录 basename 与 SHA-256。

## 7. CLI 与输出

```powershell
python tools/paper_a_manhattan/run_local_3d_projection_review.py `
  --input <latest_gt_or_single_image_input_json> `
  --image-root data/mp3d_layout/img_v `
  --candidate-json <m15_18_3_output_json> `
  --out-dir analysis_results/paper_a_manhattan/local_3d_projection/<case_name> `
  --coordinate-mode ls_percent `
  --local-server-root .
```

固定输出：

- `projection_metrics.json`
- `projection_review_report.md`
- `local_3d_review.html`

HTML 复用 `tools/label_studio/vis_3d.html` iframe，通过 `postMessage(type=update_layout)` 发送只读 variant，支持 original/candidate 切换、side-by-side 和 show/hide labels。若 `file://` 阻止纹理加载，在共同 root 运行 `python -m http.server` 后用 localhost 打开。

## 8. 审查口径

报告必须先给出 `Input Provenance`、`Human Review Summary` 和 `Candidate Metric Summary`。人工决策同时检查：

- affected local walls/corners 是否改善；
- target pair height 是否异常；
- dense pair 是否仍保持分离；
- 后续邻接窗口是否仍有较大 residual；
- 本地纹理与 3D 形状是否一致。

任何“更 Manhattan”的 metric 变化都不能单独授权采用 candidate。

## 9. M15.19.1 Local Texture URL Hardening

M15.19.1 将两个 URL 的解析基准明确分离：

- `viewer_url_for_wrapper` 由外层 `local_3d_review.html` 消费；无 server root 时相对 output directory 生成。
- `image_url_for_viewer` 由 iframe 内的 `vis_3d.html` 消费；无 server root 时必须相对 `vis_3d.html` 所在目录生成。
- 提供 `--local-server-root` 时，两者统一生成同源 root-relative URL，例如 `/tools/label_studio/vis_3d.html` 与 `/data/mp3d_layout/img_v/<image>.jpg`。

`vis_3d.html` 必须向 parent 回传 `hohonet_texture_status`，至少区分 `loading / loaded / failed / unavailable`。wrapper provenance 显示 `image_exists`、`image_sha256`、`image_url_for_viewer`、`viewer_url`、`texture_expected` 和实时 `texture_load_status`。若本地图存在但 iframe 回报失败，页面顶部必须给出阻断告警，不能把纯色回退静默解释为贴图验证通过。

对于已知 Label Studio 0–100 输入，正式 review 命令应显式使用 `--coordinate-mode ls_percent`。若仍使用 `auto` 且出现 0–100 ambiguity warning，HTML 顶部必须显著提示该建议。

## 10. M15.19.2 Local 3D Inspection Workbench

M15.19.2 在不改变投影公式、指标语义和只读边界的前提下，把本地 HTML 扩展为双启动模式的专业检查界面：

- 直接打开 `local_3d_review.html` 时，iframe 使用相对 `vis_3d.html` 路径，本地 panorama 以 data URL 嵌入 HTML；嵌入只用于本地显示，不写入 `projection_metrics.json`。
- localhost 模式继续使用 repository-root URL；每个仓库内输出目录生成可双击的 `open_local_3d_review.cmd`，由 `serve_local_3d_projection_review.py` 在 `127.0.0.1` 提供只读静态服务。
- wrapper 必须等待 `hohonet_viewer_ready` 后才发送 layout，并分别报告 viewer load 与 texture load 状态，避免把 iframe 本身未加载误报为贴图失败。
- 点击 floor/ceiling 角点时显示 pair、source order、输入/归一化坐标、权威 Python 3D 坐标、高度与 turn residual；点击墙面时显示方向、最近 Manhattan 轴、角度 residual、长度、短墙状态和两端相邻 corner 夹角。
- 检查工具包括 residual heatmap、candidate/original ghost overlay、两角点 3D 测量、top/isometric/inside/reset camera preset 和按严重度排序的 issue navigation。
- 所有交互只选择、观察和测量；不允许拖动角点、保存坐标、生成 patch、写回 annotation 或自动接受 candidate。

Heatmap 颜色合同：`≤5°` 为绿色，`>5° 且 ≤15°` 为橙色，`>15°` 为红色，short wall 优先显示紫色。它们仅表示 projection-space review priority，不表示 correctness。
