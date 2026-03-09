# COS 上传与 Label Studio 导入（中文说明）

## 先回答你的关键问题

### 1）腾讯云 COS 桶里应该上传什么？

上传 **图片文件**（`png/jpg/webp`），不是 `label_studio_import*.json`。

- COS 用来托管图片资源，供标注页加载。
- `label_studio_import*.json` 是给 Label Studio 后台导入任务用的，通常保存在本地项目目录并通过 UI 导入。

---

## 推荐流程（先 COS，暂不 CDN）

1. 批量上传图片到 COS（保持原命名格式）
2. 用 `prepare_labelstudio_docker.py` 生成导入 JSON（`data.image` 指向 COS URL）
3. 在 Label Studio 项目里导入 JSON

---

## 命令示例

### A. 上传图片到 COS

```bash
set AWS_ACCESS_KEY_ID=你的SecretId
set AWS_SECRET_ACCESS_KEY=你的SecretKey

d:/Work/HOHONET/.venv/Scripts/python.exe tools/upload_mp3d_test_to_cos.py --bucket label-images-1389474327 --region ap-guangzhou --source-dir data/mp3d_layout/test/img --key-prefix data/mp3d_layout/test/img --manifest-path analysis_results/cos_upload_manifest_prod.json
```

### B. 生成 Label Studio 导入 JSON（图片 URL 指向 COS）

```bash
d:/Work/HOHONET/.venv/Scripts/python.exe tools/prepare_labelstudio_docker.py --image-base-url https://label-images-1389474327.cos.ap-guangzhou.myqcloud.com/data/mp3d_layout/test/img --disable-vis3d --output-json label_studio_import_docker.json
```

> 如果需要保留 3D 预览，不要加 `--disable-vis3d`，并确保 `--vis-base-url` 对应你的 3D 服务地址。

---

## 关键脚本（已备份与改造）

- 旧版备份：
  - `tools/legacy_server/prepare_labelstudio_docker_old_server.py`
  - `tools/legacy_server/ls_userscript_old_server.js`
  - `tools/legacy_server/vis_3d_old_server.html`
  - `tools/legacy_server/README_before_cos_update.md`

- 当前使用：
  - `tools/upload_mp3d_test_to_cos.py`（批量上传 COS）
  - `tools/prepare_labelstudio_docker.py`（生成导入 JSON）
  - `tools/official/ls_userscript_annotator.js`（正式标注员篡改猴脚本）
  - `tools/official/ls_userscript_debug.js`（调试/巡检脚本，默认不计时）
  - `tools/vis_3d.html`（3D 查看器）

---

## 篡改猴配置（新服务器）

在浏览器控制台执行一次：

```javascript
localStorage.setItem("HOHONET_HELPER_BASE_URL", "http://175.178.71.217:8000");
```

如果你做了同源反代，也可以：

```javascript
localStorage.setItem("HOHONET_HELPER_BASE_URL", location.origin);
```

如果只想让 3D viewer 走同源，而保留 `/log_time` 继续走独立 helper，也可以：

```javascript
localStorage.setItem("HOHONET_VIEWER_BASE_URL", location.origin);
```
