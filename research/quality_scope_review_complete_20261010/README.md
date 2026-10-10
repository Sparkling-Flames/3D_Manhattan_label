# 空间范围指定批次最终回执与研究交付（2026-10-10）

## 最新结论

**以本目录的35图最终确认层为准，旧16图/5图资料仅作历史。**

- 回执261行，35图地面确认：此前16图原样保留＋本轮19图；28图修改地面，7图沿用当前显示GT地面。35个确认空间均为primary，替代候选0。
- 本轮优先19视角、指定批次23个可编辑视角均已确认；自动策略确认0。另226行仍未确认。
- 35确认中33图在259图研究基集内，共429份正式作答（380 manual、49 semi），417份有效、12份不可算。另q9-21/25仅参考视角，各0份正式作答，不扩分母。
- 旧16图134份三参考指标逐值保持相同。人工范围包括扩大、缩小及混合增删，不能一概称为缩小。
- **此次仅地面/BEV，顶界仍待定，reference_ready=false；GT和资格未改，新范围完整3D Q、集合Q、融合、人员排序和人数曲线未重算。**
- 122条来源图片线索与30个未完整载入或只读关联视图没有全部经人工范围裁决；本次指定批次完成不等于全库问题已解决。

正式输入固定：`24360ad8544d76d8aba18a8e641f784a76ca0d42`。对应已发布工作台v3.4.2源码：`e44b52969f0d18a352773a83c4b9575f720bc5a7`。

## 可直接阅读的核心资料

| 内容 | 入口 |
|---|---|
| 最终机器摘要 | [SUMMARY_FINAL.json](SUMMARY_FINAL.json) |
| 回执中文报告、字段说明 | [最终回执核验](reports/RECEIPT_REPORT.md)、[字段说明](reports/RECEIPT_SCHEMA.md) |
| BEV研究接入报告 | [最终地面研究报告](reports/BEV_REPORT.md) |
| 35图规范确认层 | [normalized_confirmation_overlay.json](data/normalized_confirmation_overlay.json) |
| 用户原始回执（字节原样） | [raw_scope_receipt.json](data/raw_scope_receipt.json) |
| 35空间参考与来源 | [reference_registry.json](data/reference_registry.json)、[source_bindings.json](data/source_bindings.json) |
| 429作答三参考结果 | [record_metrics.csv](data/record_metrics.csv)、[JSON](data/record_metrics.json) |
| 逐图结果、条件/门槛分层 | [image_summary.csv](data/image_summary.csv)、[condition_gate_summary.csv](data/condition_gate_summary.csv) |
| 地面改动类型与12条不可算原因 | [floor_geometry_changes.csv](data/floor_geometry_changes.csv)、[noncalculable_12_records.csv](data/noncalculable_12_records.csv) |
| 35图与本轮19/23视角核对 | [35图几何变化](data/receipt_confirmed_35_geometry_deltas.csv)、[优先19](data/receipt_priority_19_completion.csv)、[指定23](data/receipt_assigned_23_completion.csv) |
| 未确认226图 | [unconfirmed_226_image_codes.json](data/unconfirmed_226_image_codes.json) |
| 实跑测试与来源 | [封包验证](reports/RELEASE_VALIDATION.json)、[BEV来源](reports/bev_source_provenance.json)、[搬迁复算](reports/bev_portability_validation.json) |
| 可审阅源码 | [回执代码](code/receipt/)、[BEV代码](code/bev/) |

实际仓库入口是本统一目录。恢复完整包后，两个最新子包分别位于 `final_scope_receipt_validation/` 与 `final_scope_reference_integration/`；子包原说明中的独立上传建议路径不是本次实际仓库目录。

这些是便于GitHub阅读的精简副本。代码所需完整inputs、测试fixtures、照片、历史资料和正确目录布局在下方完整包内；请恢复完整包再运行复算。

## 完整便携包：恢复与校验

完整ZIP共 **65.80 MiB**，分为 **17个二进制分卷**（每卷至多4MiB），恢复后 **1337个文件**。分卷只是单一标准ZIP的连续字节，不是彼此独立ZIP。

先下载本目录所有文件（包括 `archive_parts/`）。保留路径，不要以GitHub网页HTML代替原文件。Python 3标准库即可校验及恢复：

```sh
python verify_release.py
python restore_bundle.py --verify-only
python restore_bundle.py
```

默认恢复至 `restored/quality_scope_review_complete_20261010/`。脚本先核每卷SHA256、合并ZIP总SHA256及CRC，拒绝危险路径或覆盖不同内容。也可指定 `--output-dir /your/path`；加 `--keep-zip` 可保留合成ZIP。

```sh
python restored/quality_scope_review_complete_20261010/verify_delivery.py
```

读恢复目录的README，按对应requirements配置Python依赖，再复算。分卷列表与ZIP哈希见 [ARCHIVE_PARTS.json](ARCHIVE_PARTS.json)，完整包逐文件哈希见 [BUNDLE_FILE_MANIFEST.json](BUNDLE_FILE_MANIFEST.json)。本目录校验清单见 [CHECKSUMS_SHA256.txt](CHECKSUMS_SHA256.txt)。实际分卷恢复、文件校验及篡改反例结果见 [PACKAGING_VALIDATION.json](PACKAGING_VALIDATION.json)。

## 包内保留了什么

- 最终回执核验和最终35图地面研究层，含冻结输入、规范层、全部结果、脚本、测试与日志
- 完整工作台v3.4.2：12个fixtures、282份逐图records、266个assets和完整dist；保留原始测试断言
- 此前未提交main的full_scope_inventory全部86个文件，以及全部历史阶段资料591文件，逐字节保留
- 本地69条来源增量、123份原件对账、完整库存、扩展及补漏证据、旧16图研究结果、yq-07三份改序固定GT质量诊断

历史资料均在完整包 `history/prior_stage_contents/`，旧“等待回执”、16图/5图状态或过时顶层清单不能覆盖最新35图结果。新增材料没有删除或覆盖仓库已有资料。

## 实际测试边界

本次工作台原版8套检查26,977项通过；full_scope_inventory保存结果418,908项通过；yq-07主复算60项、14项测试通过，6个核心输出逐字节相同。最终回执Node 60,989项、独立Python 3,103项及10个拒绝反例通过。BEV 1,060项断言、31项pytest通过，18个核心结果搬迁逐字节相同。

**真实浏览器视觉与实际交互尚未验收。** Site发布、数据/几何/模拟DOM通过不代表浏览器验收。工作台完整静态数据与照片已提供，可本地查看；其内置16确认是导出前快照，最新35确认在最终回执中。
