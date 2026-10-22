# 顶部与结构惩罚质量研究：离线交付入口

研究轮次标识为 `20261012`；实际读取、研究与本次工程复现在 **2026-10-11 UTC** 完成。最新审核文件实际 main 为 `38e259c043fed0817307dbc3d21c6dba06bd6662`。本包没有替换正式质量方法、修改原始点、回执、GT、资格或重新融合。

## 阅读顺序

1. [中文完整报告](top_structure_20261012/quality_top_structure_report_20261012.html)：结论、数值、定义、反例、候选取舍、冻结条件及原论文来源；HTML 自包含图像。
2. [用户盲审版](top_structure_20261012/review/review_blind_user_20261012.html)：7 份作答、6 原图、5 组问题，末组可选，所有答案为空。隐藏方法、分数和题号映射。
3. [研究复核版](top_structure_20261012/review/review_researcher_20261012.html)：显示选例原因、映射与回答影响。建议完成盲审后再打开。
4. [完整复现说明](REPRODUCE_ZH.md)：源文件角色、范围、复现命令、结果比较及限制。

## 当前可用的研究结论

旧顶部 S 在 T20 的分母贡献为 4.1965，H* 为 0.2188，底部 S 为 0.0194；D/F 只扣约 0.29 分。简单取 max 没有解决其严罚。降低顶部项主导作用有支持，但去顶部后的旧 24 判断排序改善主要跨图，T09/T22 的同图反例仍在。

最简重建候选为去顶部 S，专项候选为全局高度与中心化局部残差分开控制；后者的 0.25 仍是研究尺度。原始输入的周期 x 残差与处理后重建质量分开报告，精确高度幅度/影响周长作为诊断。不冻结唯一公式、8°残差处罚、分阶段转折或质量等级阈值。

本轮实际数值对照为旧 24＋9 条条件可算严重＋6 条待定，共 39 份、30 张图、14 栋楼。另有 907 条无标签描述池、70 项有效合成控制及 1 项不可算控制。79 份未勾选仍全部未审查；所有缺失几何为空值。原 14 条留出暴露及其分组污染记录保留，没有认证新干净测试集。

## 一条命令复现

环境先具备 `requirements.txt` 中的 NumPy、SciPy、Shapely、Pillow 和 Matplotlib。复现入口本身不联网、不自动安装、不改包内文件。

```bash
python run_reproduction.py --with-figures
```

默认在包外建立带实际 UTC 时间的新目录，执行固定 22 步，含数值链及选定原图重绘。若只需数值，可不加 `--with-figures`，执行 17 步。也可指定一个尚不存在、位于包外的新目录：

```bash
python run_reproduction.py --with-figures --output-root ../reproduction_top_structure_fresh --workers 2
```

仅核验来源：

```bash
python top_structure_20261012/delivery_tools/prepare_and_reproduce.py verify --package-root .
```

入口拒绝已有输出目录。所有重算在新副本中进行，保留交付期望结果用于比较；出现差异立即停止并保留日志。它不是对未来任意数据自动授予资格的生产评分入口。

## 已实际通过的工程复现

在 2026-10-11 14:59 UTC 的全新目录中运行了含绘图的 22 步。104 个 JSON/CSV 文件、65,359 个数值比较全部一致，最大数值差为 0；源文件未改。见 `top_structure_20261012/delivery_tools/reproduction_evidence/`。这是固定开发研究的可复现性证明，不是质量定义、人类阈值或新独立样本的验证。

## 核心代码与结果

| 文件或目录 | 用途 |
|---|---|
| `top_structure_20261012/analysis/candidate_functions.py` | 最小候选评分，不接收人员 ID 或人工标签 |
| `top_structure_20261012/analysis/protocol_*.json` | 有限候选协议；追加 stage13 明确为适应性开发探查 |
| `top_structure_20261012/analysis/results/candidate_scores_39.csv` | 39 份的完整分量、旧分数和新候选分数 |
| `top_structure_20261012/analysis/fair_comparison/` | 15 方法相同切点预算、11 栋楼的开发检验 |
| `top_structure_20261012/analysis/sensitivity/` | 全 24 可变的邻档情景、按图/组移除及有限参数交叉 |
| `top_structure_20261012/mechanisms/` | 精确高度定义、71 项控制、39 真实、Hcenter 及核验 |
| `top_structure_20261012/representation/results/` | 原导出/当前编辑/共享后版本审计、周期残差及原始边界 |
| `top_structure_20261012/evidence/results/` | 115 资格台账、留出暴露、67 成员与固定融合端点 |
| `top_structure_20261012/exploration/` | 精确高度幅度及周长支持：109 有效剖面、327 不变性与36解析式检查 |
| `top_structure_20261012/inputs/main_snapshot/` | 原 main 回执和覆盖，原文未改 |
| `top_structure_20261012/inputs/USER_CLARIFICATIONS_THIS_TURN.txt` | 最新对话澄清独立层 |
| `top_structure_20261012/CONCLUSIONS_MACHINE_READABLE.json` | 主要结论、边界与状态的机器可读摘要 |
| `provenance/`、`FILE_MANIFEST_SHA256.json` | 复制角色、输入版本、实际范围及最终字节清单 |

旧 `study_*` 与 `previous_research/` 下的分数和证据明确为历史输入；本轮输出统一在 `top_structure_20261012/` 中。候选分数中的 `null` 不得改成 0，也不能将未审查记录当负例。

## 图片与完整档案边界

六个指定 ZIP 的实际字节/清单/CRC 已在本轮原恢复环境核验；前三份原图库含 261 张不同的 2048×1024 原图，扩展包不是第四原图库。包内只带本轮6张原图、必要数值链与元数据，不重复附 261 全图库、旧24图册或外部ZIP。

`inputs/verify_sources.py` 保留完整档案核验入口，但须另行持有原两研究ZIP及四基础ZIP；不在最小离线复现中冒称重新读取它们。主报告中的“本轮实际读取”与此次“封包离线复现”是两个有不同输入范围的执行阶段。

任何重新选例、改阈值、改变参考、加入新融合输出或新人工标签都应另存为下一轮输入和结果。原排除、hold、OOS、门洞交界、W019人员资格和未知顶界状态继续有效。
