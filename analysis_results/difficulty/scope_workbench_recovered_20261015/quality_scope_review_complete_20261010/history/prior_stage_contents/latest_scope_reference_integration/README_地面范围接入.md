# 最新确认地面范围：增量研究层与 BEV 复算

## 本次落实了什么

接收用户在 2026-10-10 11:52:40 UTC 导出的编辑器 v3.2 回执，以及其后明确确认“旧五张已修改范围”和“此前确为五张”的两条说明。原回执逐字节保存；确认依据由独立回执验证包规范化，本包只消费最终确认层。

**有效确认共16图：此前5图的最新地面＋新批11图。其中13图有人工地面替代候选，3图为沿用现有已选GT地面，不新增3份几何。没有推测第六张旧图。**

本包是一层新增的研究输入与地面诊断结果。建议原样放到仓库 `research/latest_scope_reference_integration_20261010/`，由明确选择此层的研究脚本读取。它不改写 `load_current_bundle()`、合同或正式GT，不自动解除质量hold，也不把候选变成正式质量可评对象。

## 当前结果

- 正式输入来源：`24360ad8544d76d8aba18a8e641f784a76ca0d42` 的当前 `load_current_bundle()` / `load_current_input()`，两入口数据相同。
- 16图共134份正式作答全量保留：120份manual、14份semi，不混充134个独立人员。
- 132份有有效底面并计算指标；2份输出空指标及失败原因，不修复、不当零分。其中 pa4otMbVnkk-14/R00596 为相机不在底面内部，uNb9QFRL6hY-68/R01879 为点对不可用，二者原本均为excluded。
- 原质量门槛保持：92份 `candidate_pending_geometry`、38份 `hold_scene_or_reference`、4份 `excluded`。候选不等于通过正式质量评估。
- 逐记录同时保留“历史原GT”“当前已选GT”“本次确认地面”三组指标；没有挑最优参考、自动推断历史意图或计算集合分。
- 21个正式输入、合同和代码文件已与该提交的blob或LFS内容SHA256及长度核对；3441个正式对象保留整体及受保护字段指纹。

### 逐图范围

下表“新地面/已选GT面积”是几何比值，不是质量得分。所有单位为相机高度h及h²，不是米。

| 图片 | 本次处理 | 作答数 | 新地面/已选GT面积 |
|---|---|---:|---:|
| S9hNv5qa7GM-04 | full_gt，沿用现有地面 | 1 | 1.000000 |
| b8cTxDM8gDG-18 | 更新此前人工地面 | 6 | 0.410968 |
| e9zR4mvMWw7-09 | 更新此前人工地面 | 6 | 0.384160 |
| e9zR4mvMWw7-17 | 更新此前人工地面 | 6 | 0.812202 |
| pRbA3pwrgk9-02 | 更新此前人工地面 | 6 | 0.117485 |
| pa4otMbVnkk-14 | full_gt，沿用现有地面 | 6 | 1.000000 |
| q9vSo1VnCiC-11 | 新人工地面 | 5 | 0.887877 |
| q9vSo1VnCiC-12 | 新人工地面 | 10 | 0.885219 |
| q9vSo1VnCiC-29 | 更新此前人工地面 | 5 | 0.224804 |
| uNb9QFRL6hY-44 | 新人工地面 | 10 | 0.892870 |
| uNb9QFRL6hY-55 | 新人工地面 | 15 | 0.883437 |
| uNb9QFRL6hY-68 | 新人工地面 | 20 | 0.887922 |
| uNb9QFRL6hY-81 | 新人工地面 | 15 | 0.926776 |
| wc2JMjhGNzB-22 | 新人工地面 | 8 | 0.882947 |
| wc2JMjhGNzB-26 | full_gt，沿用已选人工修订GT | 6 | 1.000000 |
| wc2JMjhGNzB-29 | 新人工地面 | 9 | 0.875183 |

特别注意：wc2JMjhGNzB-26 的已选GT是 `gt_manual_revision`，不是历史 `gt_original`。其已选地面与历史原GT的BEV IoU约0.936269；因此这两个版本分别保留，不能将full_gt解释成改回历史原GT。

## 可算与仍待确认的边界

本次只算地面面积、周长、相机到地面边界距离，以及作答底面A相对于每个固定地面R的：

- 面积比：|A|/|R|
- BEV IoU：|A∩R|/|A∪R|
- 参考覆盖率：|A∩R|/|R|
- 参考遗漏率：|R\A|/|R|
- 作答越界率：|A\R|/|A|
- 超出面积/参考面积：|A\R|/|R|
- 对称差D：|A△R|/|R|，等于遗漏率＋超出面积/参考面积，不等于1−IoU

条件、质量门槛、融合门槛、清洗及独立资格分层保留D≥0.2/0.3/0.4的诊断计数；不合并成人员投票、不更新图片难度。

**16条回执的 `top_boundary_pending=true` 和 `reference_ready=false` 均保留。没有新建顶点高度，也没有继承/猜测中位顶高来扩充本次批准。** 这不改变既有GT自身的历史使用状态；只是本次地面确认不产生额外的顶界批准。

因此，本批不生成新参考的完整3D质量Q、顶边/高度误差、3D IoU、集合Q、人员排序、融合结果、难度或人数曲线。之后若要采用人工替代参考的完整Q，需要确定相应顶界；若要将多个允许目标作为正式评分集合，还需明确集合评分协议。此处不代替任何既有清洗和分析资格判断。

地面坐标一字不改：不回剪到GT、不按x重排、不再次吸附、不使用buffer(0)修复、不按作答优化参考。e9zR4mvMWw7-09仍有约4.0155%的人工地面位于已选GT外，这是确认范围的一部分。其它极小越界也按原坐标保留，不强制归零。

## 旧五图及旧三图实验

旧确认快照保存在规范化确认层的 `previous_confirmation_history` 中，原件仍保留。`previous_confirmed_floor_delta.json` 明确新旧坐标哈希与地面变化，只有新的当前地面诊断采用此次坐标。

此前三图完整Q实验位于 `research/quality_scope_comparison_20261010/`。这三图的新地面坐标均与旧实验冻结坐标不同；旧输出仍可用于复现当时的条件实验，但不能改标成新地面的Q、集合Q、路由或图表。三图变化的对称差相对旧底面分别约0.0029%、0.0093%、0.0054%，没有据此宣称质量变化很大，也没有重算完整Q。

`historical_artifact_applicability.json` 保存逐图对应关系。历史目录和文件不删除、不覆盖。

## 复算与验证

便携复算只需要Python 3和Shapely；不需要仓库、照片、浏览器或网络：

```bash
python recompute_bev.py
python -m pytest -q tests
python verify_replay.py
```

只读重新提取当前正式输入（需相同提交及仓库已有依赖）：

```bash
python extract_formal_input.py --repo /path/to/3D_Manhattan_label
python recompute_bev.py
```

提取会核对提交与回执、加载正式增量、校验原/选GT身份及坐标；缺失于稀疏工作区的普通CSV仅从同一提交blob只读获取，不写回仓库；缺失LFS正文直接失败。已物化LFS可能在稀疏Git状态里显示M，但这里按已提交LFS哈希和长度核验，不把该状态误判为坐标改动。

本批验证：526项复算断言通过；21项便携测试通过；与仓库既有numpy投影的最大坐标差为4.44e−16 h。搬迁独立复算的10个核心输出逐字节一致，结果见 `results/portability_validation.json`。测试包括非嵌套范围、明确分母、无效几何不修复、原环序保留、只变顶高不影响底面、输入及门槛篡改失败关闭、全部资格字段保存和离线结果重放。

## 文件入口

- `inputs/raw_scope_return.json`：原回执，逐字节保存。
- `inputs/normalized_confirmation_overlay.json`：回执验证包的最终确认层，SHA256为 `f840b070f984170aac5324957ee241f176757f114c095311855edf678fc38b5b`。
- `inputs/current_formal_subset.json`：当前正式16图快照、原/选GT、134份记录及全正式输入指纹。
- `inputs/input_manifest.json`：输入内容哈希；改动即停止复算。
- `results/reference_registry.json`：13个新底面候选＋3个现有GT地面决策，所有顶界待定状态。
- `results/record_metrics.json/.csv`：134行三参考对照，空值及失败原因显式保留。
- `results/image_summary.json/.csv`：逐图来源、人数、地面范围和门槛计数。
- `results/condition_gate_summary.json/.csv`：保持条件与资格分层的诊断计数。
- `results/previous_confirmed_floor_delta.json`：旧五图新旧地面的变化。
- `results/historical_artifact_applicability.json`：旧三图条件Q实验的适用性边界。
- `results/source_provenance.json`：21个提交源文件、正式加载器和独立投影验证。
- `results/validation.json`、`pytest.log`、`portability_validation.json`：检查结果。
- `MANIFEST_SHA256.txt`：整个交付目录的文件哈希，可在目录内运行 `sha256sum -c MANIFEST_SHA256.txt`。

### 方法来源

- [正式输入合同](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/24360ad8544d76d8aba18a8e641f784a76ca0d42/docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json)：当前loader、既有资格与“candidate不是最终可评价”的边界。
- [既有范围诊断](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/24360ad8544d76d8aba18a8e641f784a76ca0d42/analysis_results/image_difficulty_full_review_20261010/build_scope_review.py)：连续ERP底面投影、相机内部检验和面积对称差。
- [旧三图实验说明](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/24360ad8544d76d8aba18a8e641f784a76ca0d42/research/quality_scope_comparison_20261010/README_%E4%B8%89%E5%9B%BE%E5%AF%B9%E7%85%A7.md)：地面批准不代替顶界批准、原GT/小目标并存、完整Q仍是当时冻结输入下的条件实验。

本包只准备新增研究交付；未修改Site、未提交或推送GitHub。
