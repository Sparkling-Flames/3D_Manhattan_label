# 版本身份与采用顺序

## 已核实的版本

本轮开始时的 GitHub 最新 `main` 是 **48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b**，提交标题为 “Integrate manual-order acceptance and research index”。该提交与第 08–12 批冻结来源相同。完整提交记录见 [SOURCE_HEAD.json](inputs/SOURCE_HEAD.json)，九个核心输入与引擎文件的实际 Git blob 一致性见 [PINNED_CORE_INPUTS.csv](inputs/PINNED_CORE_INPUTS.csv)。

[GitHub 固定提交](https://github.com/Sparkling-Flames/3D_Manhattan_label/commit/48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b)

第 08–12 批的类别解释、K4 图册、混合规律、进入过程和 C1↔C3 严格半队补充是这个提交之后已交付的增量成果。它们在当前工作副本中存在，不声称已被上述 main 提交收录。`CURRENT_RESEARCH_BASIS.md` 因包含这些已交付段落而与 main 版不同，两版快照分别保存：

- [main 中的研究口径](inputs/CURRENT_RESEARCH_BASIS_GITHUB_MAIN.txt)
- [第 12 批完成后的研究口径](inputs/CURRENT_RESEARCH_BASIS_ACCEPTED_BATCH12.txt)

这种文档增量没有改变当前楼外标签、有效原答、参考、正式融合或评分输入。

## 当前标签与历史 TARGET

本轮的当前 DSTRUCT K3 来自：

`research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/classification/LABELS_ALL_LOBO.csv.gz`

按目标图片所属建筑选择 LOBO 折。历史 AC 自带 `FINAL_LABELS_FOR_AC_ALL_LOBO.csv.gz` 保留其旧身份。两者 1,426 个“人员×折”行（62 人×23 折，含 ALL）中，有 **34 个目标建筑 LOBO 行变类**；ALL 描述折变类 0 行，known 资格变化 0 行。详见 [逐行交叉表](audit/LABEL_CROSSWALK_ALL_LOBO.csv.gz)、[34 行变更](audit/CHANGED_WORKER_FOLDS.csv)。

合法性必须落实到事件的具体 X/Z/D 成员，不能因为旧方法名称含 TARGET 就将整库改称当前 DSTRUCT，也不能因为 34 行变化就废弃所有历史团队。旧事件转为另一当前合法方向时保留原 event_id、设计和方向，同时登记映射。背景 D 的当前构成单列，通用 AC 不要求 D 纯类。

## 实际采用顺序

1. 本轮用户明确限定的直接 AC 问题及当前类别定义。
2. 固定 main 的当前标签、有效预处理、真实候选池、参考和正式融合/评分代码。
3. 第 08–12 批经过验收的增量研究，保持各自来源和方法身份；本轮只引用联盟、配比、曲线及 ABC 的已有估计。
4. 历史 AC 逐成员通过当前定义后复用；不合法者保存旧身份和原因。筛选后的存量结果不是按当前类重新均匀抽样。
5. 本轮 22 个容量缺口条件格的冻结补充，单独标为 `current_capacity_gap_supplement`。

原自动版和已批准的固定坐标人工连接版分别保存。原共同 Q、辅助新增共同 Q、辅助完整共同 Q 分别计算；坐标候选不进入本轮。未覆盖的新无连接端点保持无输出，既不填零，也不自动接入人工连接。

## 本地核验

```bash
python research/workers/current_dstruct_ac_final_20261104/check_input_versions.py
```

脚本只读取并比对冻结清单，不覆盖本地文件。若缺少某个原始源文件，可按来源清单恢复固定提交的原文件；若本地文件已改变，应先判断具体变更与本研究的关系，不能静默回退到历史版本后继续沿用当前标签名称。
