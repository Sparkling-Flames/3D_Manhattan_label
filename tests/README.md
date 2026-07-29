# Test suite classification

`pytest.ini` 将正式 pytest 收集根限定为本目录。仓库根目录的
`test_depth.py`、`test_layout.py`、`test_sem.py` 是模型运行脚本，
不属于合同测试，也不应因缺少 Torch/natsort 阻断方法链 CI。

`tests/` 保持扁平布局，以兼容 `AGENTS.md`、CI 和本地定向 `pytest` 命令；分类通过文件名前缀和本索引完成，不为整理目录而移动仍在使用的测试。

## Categories

- `test_c1_*`, `test_geometry_*`, `test_compute_dt_score.py`: C1 calibration、variable-k、peer/LOO、active-time 与 worker profile 合同。
- `test_c2_*`, `test_c2b_*`, `test_*risk_rule*`: C2-A-RP、C2-B、risk-rule 与 final-gold 合同。
- `test_global_*`, `test_materialize_frozen_routing_profiles.py`, `test_materialize_full_policy.py`, `test_v1_policy.py`: Stage 3、Strong Global、Full/T1/V1 routing 合同。
- `test_label_studio_*`, `test_*assignment*`, `test_*registry*`: Label Studio、assignment、registry 与导入/导出链路。
- `test_paper_b_*`, `test_b0_*`, `test_b1_*`, `test_b2_*`: Paper B 独立研究线。
- 其余 `test_materialize_*`, `test_build_*`, `test_run_*`: 对应工具的 materializer、builder 或 workflow 集成测试。

## Retention rules

- 正式协议、字段合同和 freeze gate 的失败关闭测试必须保留。
- 当前正式入口必须至少有一组成功路径和关键缺失字段/哈希不匹配的失败路径。
- 仅验证已被后续版本完整替代、且无正式入口或文档引用的历史脚本测试可以与旧脚本一起删除。
- 不因测试失败而降低断言、默认补字段或改成 fail-open。
- 新增测试优先沿用上述前缀；只有形成稳定且独立的测试域时才考虑建立子目录。

## Retired version chains

- `revise_semi_selection_v7`, `v8`, `v9` 已由正式的 `revise_semi_selection_v10` 取代；旧脚本及其自引用测试不再参与当前仓库合同。
