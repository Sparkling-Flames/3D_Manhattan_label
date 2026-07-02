# C1 v3.1 smoke import drafts

- `*_zh.json` 只用于 175.178/http 中文入口，`vis_3d` 使用 `http://175.178.71.217:8000`。
- `*_foreign_https.json` 只用于 https 海外入口，`vis_3d` 使用 `https://label.sparkle0825.top`。
- 不要把 `foreign_https` 文件导入 175.178/http 项目；Label Studio 会在前端 fetch `$vis_3d`，scheme/CORS 不匹配时会报 `TypeError: Failed to fetch`。
- 这些文件只用于 smoke test 草案，未调用 Label Studio API，不能视为 launch。
