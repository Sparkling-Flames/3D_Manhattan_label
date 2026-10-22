# 本轮独立增量：结构、局部墙高和整体高度的处罚

先读 [REPORT_ZH.md](REPORT_ZH.md)。本目录只保存本轮新增研究，**没有替换旧方法、原始标注、参考、人工回执、资格或共识输出**。

## 两个交付如何恢复

1. 先将 `quality_top_structure_research_20261012_repaired_v1.zip` 解压到一个新目录。
2. 将本轮 `quality_structure_height_extension_20261012_v1.zip` 解压到同一个位置。它只包含 `quality_top_structure_research_20261012/structure_height_preference_20261012/`，不会覆盖旧研究文件。
3. 进入共同根 `quality_top_structure_research_20261012`。此处原有的 `FILE_MANIFEST_SHA256.json` 是上轮清单；本轮清单在新增目录内，二者不要混用。

修复包的大小为 **42,665,801字节**，SHA256：

```text
08b752a63cb8fb557fd32bce5c633539629f9eb847858d29bef1f027786e0bdd
```

修复包包含387个完整文件，与上一轮完整研究清单一致。旧41,211,515字节文件没有完整尾部，不要拿它作为数值复现根。`quality_top_structure_repair_verification_20261012.zip` 含实际回下载后的校验、原截断审计、完整成员清单及校验脚本。

本轮ZIP自己的大小、SHA256、逐文件清单、CRC和实际交付副本验证在独立交付完整性说明中；ZIP无法可靠包含自身完整哈希，整包哈希以该外部记录为准。

## 复现

从共同根运行：

```bash
python -m pip install -r structure_height_preference_20261012/requirements.txt
python structure_height_preference_20261012/run_reproduction.py
```

第一条仅在本机缺少依赖时需要；已具备依赖时，研究代码本身不需要网络。默认复现显式资格规则、43个结构控制、39条候选、65个新高度控制、907条高度诊断、922条当前输入诊断、旧与新比较、模型失败控制、固定融合新评分和汇总图表。代码检查26个核心输出文件中的数值、ID、标签、资格与表结构，并在开始和结束核对上轮386文件加其清单的全部字节。

包括原图对照和四组新匿名材料的重建：

```bash
python structure_height_preference_20261012/run_reproduction.py --with-review
```

各图可以使用本轮随包原图，不依赖工作环境的旧绝对图库路径。每对图共享物理坐标范围；展示的是原冻结共享后重建，不是平均前凭空新建的非垂直墙体。当前共享前点位仅按其真实表示叠线。

复现只写本轮目录的计算输出；建议在新解压目录运行，以保留一份交付原样。运行后的耗时、路径、日志摘要可能变化，不能将这类元数据字节变化说成研究分数变化。数值容差绝对1e-7、相对1e-8；记录ID、标签、资格、行序精确比较。程序发现旧研究文件变化、缺失输入或结果不一致即停止。

本轮实际从**新交付修复包的回下载副本**另建目录执行了复现，结果见 `verification/fresh_reproduction_report.json`：14个入口全部成功，26个核心输出文件的182,335个数值单元最大差为0，记录／标签／资格／结构精确一致，旧387个文件前后全部保持原字节。新ZIP在关闭后做完整CRC、全新目录解压、逐成员SHA，再进行实际交付副本核查；最终结果以外部交付完整性记录为准。

## 阅读顺序

| 需要查看 | 文件／目录 |
|---|---|
| 全部中文结论、边界和下一步 | [REPORT_ZH.md](REPORT_ZH.md) |
| D真实定义、凹角/共线/尖角/遗漏反例 | [structure/REPORT_ZH.md](structure/REPORT_ZH.md) |
| 高度、顶部、有限候选与控制 | `height/REPORT_ZH.md`、`height/candidate_functions.py`、`height/candidate_config*.json` |
| 资格、主观敏感性、公平比较、模型与冻结融合 | [evidence/EVIDENCE_REPORT_ZH.md](evidence/EVIDENCE_REPORT_ZH.md) |
| 39条候选精确分数 | `height/results/candidate_scores_39.json`、`.csv` |
| 汇总对照、关键真实例、T20分母 | `analysis/results/` |
| 原始输入版本及周期残差 | `representation/results/` |
| 新四对用户材料 | [structure/review_pairs/review_pairs_blind_user.html](structure/review_pairs/review_pairs_blind_user.html) |
| 新四对研究说明及原图/三层坐标 | `structure/review_pairs/` |
| 本轮main及对话澄清、原图访问清单 | `inputs/` |

旧七例复核材料位于上轮 `top_structure_20261012/review/`，修复中未改。新四对只补充能区分本轮机制的对照。**现在不要求用户作答，先由dot核验完整性和关键数值。**

## 实际材料与保留规则

本轮实际读取 main `a7ff459e992769c944541800dbe3be6e4b83ae4b` 并逐字节保存八个优先入口文件。14条原留出和四个暴露组显式屏蔽，剩余五组103条不认证为干净验证集。W019不恢复人员资格；未勾选全部未审查；犹豫不改档；错误GT、OOS、门洞/范围hold沿用；未确认顶部和不可靠配对不生成完整分数。

六个历史输入包本轮实际完整读取并CRC/hash验证；261原图均实际解码，报告只对选定图作视觉判读。修复包及增量包不是完整原图库。数值复现和本轮所交图片不需要重新取得四个大包；若要从头复核261原图清单或自行拓展新图，需要原三图包与相应图片索引。第四扩展包并非第四份原图库。

## 结果性质

本轮有工程复现、机制合成控制和有条件开发比较。没有新人工标签，没有独立验证，没有总体准确率、严重率或误报率。分数组合建议不自动进入正式算法。模型预测概率不代表用户置信度，邻档情景频数不是概率，题对数不是独立样本量。
