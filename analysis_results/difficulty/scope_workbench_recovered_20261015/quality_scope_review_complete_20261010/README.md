# 空间范围指定批次：最终回执、统计与完整研究资料

## 先读最新结论

本次收到的是编辑器v3.4.2于2026-10-10 13:16:29.431 UTC导出的261行回执。有效地面确认35图 = 此前16图原样保留 + 本轮19图；28图修改地面，7图沿用当前显示GT地面。35个确认空间均为primary，替代候选为0。另226行未确认，不能因用户说“完成”而自动批准。

本轮优先19视角及指定4组中23个可编辑视角均已完成确认。策略自动确认数为0，本轮19图均有按钮确认。这只完成了此次指定批次；122条来源图片线索及30个未完整载入或只读关联视图没有全部经过人工范围裁决，不能据此称全库问题已经解决。

正式研究输入固定为 `24360ad8544d76d8aba18a8e641f784a76ca0d42`。当前35确认中33图属于259图研究基集，共429份正式作答（380 manual、49 semi，涉及26名不同人员）。417份底面有效；12份不可算保留原因和空指标，不修复也不填零。另q9-21与q9-25仅作参考视角，各0份正式作答，不扩充研究基集。

所有确认仍仅限地面：顶界待定、`reference_ready=false`，没有解除质量hold或改动GT。新范围完整3D Q、集合Q、融合、人员排序和人数曲线没有重算。既有yq-07固定GT改序实验是独立诊断，保留原研究边界。

## 本包目录

- `final_scope_receipt_validation/`：最终原回执、35图规范确认层、逐行/逐空间核验、操作重放、旧16比较及未确认226清单。这里优先于历史16图/5图入口。
- `final_scope_reference_integration/`：只读提取固定正式输入后，对33图429作答计算原GT、当前选定GT、最新确认地面的BEV诊断；保留35空间参考登记、门槛分层、无效原因及来源绑定。
- `workbench_v3.4.2/`：已发布提交 `e44b52969f0d18a352773a83c4b9575f720bc5a7` 的完整静态工作台、12个fixtures、282份records、266个assets及原版回归脚本。见 `README_离线复现.md`。
- `history/prior_stage_contents/`：此前591个文件完整逐字节保留。包括此前未提交main的 `full_scope_inventory/` 全部86文件，以及来源清点、123份原件对账、旧16图研究层、扩展/补漏线索、旧工作台代码快照、yq-07改序结果。
- `verification/`：本次封包验证日志及汇总。
- `MANIFEST_SHA256.json`、`verify_delivery.py`：完整包逐文件字节数和SHA256检查。

历史资料的“待确认”“16图”“旧5图”“v3.4.1”及旧顶层MANIFEST只表示原阶段，不覆盖本次35图结果。旧工作台代码片段的缺依赖限制已由新的完整 `workbench_v3.4.2/` 补齐，但历史文件本身没有改写。

子包说明若提及建议单独上传到 `research/final_scope_reference_integration_20261010/`，那只是原子包建议；本次实际仓库统一入口是 `research/quality_scope_review_complete_20261010/`，恢复后请使用这里的 `final_scope_reference_integration/` 路径。原子包文件没有改写，其各自哈希清单保持有效。

## 复算

先检查文件完整性：

```sh
python verify_delivery.py
```

回执核验只需Node.js和Python标准库：

```sh
node final_scope_receipt_validation/validate_receipt.js
python final_scope_receipt_validation/independent_audit.py
node final_scope_receipt_validation/negative_tests.js
python final_scope_receipt_validation/build_reports.py
```

BEV复算需Python 3、Shapely 2.1.2，测试另需pytest 9.1.1；先按对应requirements配置依赖：

```sh
python final_scope_reference_integration/recompute_bev.py
python -m pytest -q final_scope_reference_integration/tests
python final_scope_reference_integration/verify_replay.py
```

完整工作台数据/几何/模拟DOM检查（无需浏览器或npm包）：

```sh
python workbench_v3.4.2/run_offline_checks.py
```

yq-07改序诊断复算（还需numpy、scipy）：

```sh
python history/prior_stage_contents/order_score_recompute/recompute.py --out order_score_replay
python -m pytest -q history/prior_stage_contents/order_score_recompute/tests
```

## 实际验证与限制

以 `verification/RELEASE_VALIDATION.json` 和两个最终子包报告为完整依据。本次工作台8套原版检查26,977项通过；full_scope_inventory保存结果418,908项通过；yq-07复算60项和14项测试通过，6个核心输出与原保存文件逐字节相同。最终回执Node 60,989项、独立Python 3,103项及10个拒绝反例通过；BEV 1,060项断言、31项pytest通过，18个核心结果搬迁逐字节相同。不将历史回执当作本次新跑结果。

工作台源码与数据643个原文件已按Git blob核对至发布提交。新的便捷检查入口和中文说明单独标明。未包含Site仓库.git、node_modules、凭证、下载辅助程序或缓存。

真实浏览器视觉与实际交互尚未验收。Site发布成功及模拟DOM检查均不代表浏览器验收。包内完整静态站点可本地启动查看；原发布工作台内置16图是导出前快照，最新35图结果保存在最终回执，可按导入功能查看。

范围几何可能同时增加与删去原GT区域，不将“修改地面”都称为缩小，不回剪到GT、不重新吸附、不改变环序、不凭照片重判。坐标单位为相机高度h及h²，不是米。
