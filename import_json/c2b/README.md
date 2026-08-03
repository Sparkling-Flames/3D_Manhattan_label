# C2-B D8 Batch A formal import JSON

- `c2b_D8_batch_a_import_zh.json` 和 `c2b_D8_batch_a_import_foreign_https.json` 是不可覆盖的历史 v17 import。
- v17→v18 迁移生成 `c2b_D8_batch_a_import_zh_v18.json` 和 `c2b_D8_batch_a_import_foreign_https_v18.json`；两份文件都保留冻结的 46 条完整任务池，语言分组由冻结的 worker language/deployment manifest 和 private assignment list 约束。
- 保留 `vis_3d` 访问路由，不写入 Label Studio `predictions`，也不调用 Label Studio API。
- runtime binder 按 deployment/project 内容身份识别 export，不依赖文件名；静态 `launch_ready` 不等于 `formal_ready`，必须产生 `c2b_v17_to_v18_runtime_evidence_v1.json` 后才可进入正式 closeout。
