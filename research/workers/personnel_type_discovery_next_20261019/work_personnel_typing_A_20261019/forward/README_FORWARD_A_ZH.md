# Part A：正向多变量人员分型交付

本目录完成了从已审计逐份历史证据到多变量画像、有限人员分区、训练侧嵌套选择、逐事件预测及解释稳定性诊断的实算。没有修改原始标注、既定评分、融合函数、参考或 GitHub main。主要效果评价由根任务在两条路线共用的替换事件上独立重聚合；本目录不以训练侧分型结果代替建筑外验收。

## 建议先读

1. `RESULTS_FORWARD_A_ZH.md`：结果与采用限制。
2. `FORWARD_SUMMARY_NUMBERS.json`、`FULL_FORWARD_CLASSES.json`：适合展示页读取的精简结果。
3. `full_selected_worker_portraits.csv.gz`：60 人完整画像、FULL 候选类、支持量、缺失、时间阈值敏感性及同类伙伴稳定性。
4. `CLASS_EXPORT_COMPLETE.json`、`FINAL_EXPORT_COMPLETE.json`、`EXPLANATION_AND_PROFILE_EXPORT_COMPLETE.json`：完整读取、行数、唯一键和概率核对收据。

FULL 是全量历史描述。真正建筑外评价必须使用该目标建筑对应的折，不能以 FULL 类别代替。

## 交换接口

| 文件 | 粒度与用途 |
|---|---|
| `selected_classes_by_fold.csv.gz` | 22,080 行；23 个情境（FULL＋22 外折）、14 个方法别名；`method_id/fold_id/heldout_building/worker_id/difficulty/class_id`。`difficulty=all` 表示全局类；条件类分别为 easy/medium/hard；`unknown` 为支持不足。|
| `selected_methods.csv` | 23 行；仅训练内选择的主候选及 K。|
| `event_predictions.csv.gz` | 4,013,324 行＝286,666 共用事件×14 方法别名；`event_id/method_id/probability`，保留折、面板、人数、难度和预测 within/between/unknown。|
| `FROZEN_CALIBRATORS.json` | 每个训练折、方法的 k×难度基线及类内/类间概率；可直接重建预测。|
| `worker_features_by_training_set.csv.gz` | 69 个唯一训练建筑子集×60 人＝4,140 行；包括全部内折历史画像。|
| `fold_features.csv.gz` | FULL＋22 外折×60 人＝1,380 行。保留连续 β、各难度 θ、绝对 Q、来源时间与相对 logT。|
| `candidate_labels_by_training_set.csv.gz` | 149,040 行；全部 28 候选及内外层训练子集；并未只保存最优类。|
| `candidate_classes_by_fold.csv.gz` | 49,680 行；全部 28 候选的 FULL/外折人员类。|
| `historical_feature_pair_relations.csv.gz` | 705,240 行；训练画像人员对距离及共同可观察域，不能当成目标图几何距离。|
| `inner_validation_building_scores.csv.gz`、`candidate_selection_process.csv` | 完整候选×训练内验证建筑的选择过程及 1SE 决策。|
| `selected_classes_by_fold_D10.csv.gz` | 固定 B8 已选 family/K，只改 D10 历史画像后重分区；方法别名与 B8 相同，新增 `B8_frozen_class_id/history_quality_metric`。没有 D10 再选 K。|
| `selected_metric_sensitivity.csv` | 固定候选/K 的 B8–D10 共类关系与支持变化；避免类编号置换问题。|

别名 `forward_selected` 是主选择。`forward_full`、`forward_minus_difficulty`、`forward_minus_semi`、`forward_minus_scope`、`forward_minus_structure`、`forward_QT_only`、`forward_base_plus_difficulty` 各自在训练内选 K。六个 `*_mainK` 固定主选择 K 做特征消融。本次它们均选 K=4，所以部分别名数值完全重复；这些副本不是独立样本。`QT_only` 是本轮同一聚类算法下的 Q 分布＋相对 T 域，不是历史固定阈值 QT 标签。

## 冻结设计

`REGISTRATION.json`、`DESIGN_DRAFT_ZH.md` 与 `FEATURE_DOMAINS.json` 保存有限候选范围。六个域是 Q、T、难度、结构历史、Semi 与 scope。核心支持门为至少 8 个普通 Manual 历史任务和 3 栋建筑；其它域各有机会门，缺失保留。

每个训练集从逐份记录重新拟合：同图、条件、参考下的 Q 人员效应；既定 strength=20 的难度部分汇聚效应；按新旧来源分别拟合的同任务 logT 效应；同任务结构与行为倾向。训练人员的中位数/IQR（退化时 MAD、SD）标准化，截断 ±3。域内各观察特征均方差、域间等权；只用双方共同可观察特征，缺域重新归一权重，缺失不设为零或能力失败。不同人员对可用域不同，这一点保留在距离表中。

采用 complete linkage 切成 K=4/6/8/10，不以简单连通性把 A≈B、B≈C 自动合成大类。另有“基础类＋难度”候选：只在已有基础类内部、该难度支持充分、正负两侧各至少 2 人且训练效应均值相差至少 3 分时细分。它不使用验证图实际作答。

外层为 22 次留建筑；内层使用 `../reverse/FROZEN_BUILDING_SPLITS.json` 的三组哈希划分，每个内层子集重新做全部特征、标准化和类别。内层选择仅用 `Pro_exact_fixed_background_v1` 的 270,370 个事件。新增 `A_nested_even_v1` 的 16,296 个事件只作冻结后的额外背景评价。

选择目标与反向线相同：事件联合稳定的 Brier，先图等权，再建筑等权；k×难度内按类内/类间校准，向本单元基线收缩 2 个等效建筑。unknown 得到基线。1SE 内优先更少类及预先冻结的简单域方案。这是回顾性建筑外验证设计，不是新外部盲测。

## 输入与来源

数据来自 `../recovered/repo_main_20261019/research/statistics/v2_evidence_audit_20261019/records.json.gz`；原函数来自 `../recovered/work_v2_20261019/profiles/run_profiles.py`。复用的是 `load_inputs`、`fit_fe`、`fit_joint` 等已有函数，实际人员特征重新计算，没有把归档的全量人员效应复制为内折画像。

冻结数据 SHA256：`46ee9890a1a56264c8955538f47c650cbe893662e7cefc21e360a3e00eca9251`。

原人员拟合代码 SHA256：`808deba4d7ae2e395175511fad0e566eb3aa24ba27cc71306f7ca3f373ac5bdc`。

共用折 SHA256：`ec5a004db1c868e9802a3729af549ac959b29bd43772b53c0af18f4d32c7f9b4`。

共用选择函数 SHA256：`2f92d7d92ed698d7994e9a520edde39399fc1306a11525a6936ba900261e3873`。

这是对已审计输入的独立统计重放，不是从原始采集日志独立复现整个采集和审核流程。冻结记录已包含预处理几何；本模块未做原图视觉审查。

## 复现入口

先按主交付的 bootstrap 恢复 `../recovered/`，准备共用 `../events/common_events.csv.gz`。从任意目录运行以下各命令（把前缀替换为本目录实际绝对路径即可）：

```bash
python build_features.py --metric B8L2
python build_features.py --metric D10
python discover_forward.py --stage partition --metric B8L2
python discover_forward.py --stage partition --metric D10
python check_forward_contract.py
python discover_forward.py --stage select --implementation original
python explain_and_audit.py --stage stability
python explain_and_audit.py --stage explain
python metric_sensitivity.py
python final_profile_sensitivities.py
python summarize_forward.py
python verify_final_exports.py
```

命令应顺序执行，避免多进程写同一路径；`build_features.py` 已隔离新旧计量的中间 flatten 目录。特征缓存重用验证源数据 SHA、原函数 SHA、特征函数 SHA、训练建筑清单及人员数。`CACHE_METADATA_AUDIT.json` 如实注明本轮给已有完整缓存补充身份元数据的时间属性，数值未改。

`selection_fast.py` 是等价聚合侧车，保留原共用科学定义。`FAST_SELECTION_PARITY.json`/CSV 对 FULL 与一个外折、全部 28 候选×3 内折共 168 个上下文逐概率、逐建筑 Brier、支持和所选候选核对，误差小于 1e-12。可先运行 `check_fast_selection.py`，再选择 `--implementation fast`。最终正式预测来自成功完成的原实现；不要把失败的 fast 临时导出当作正式结果。

## 运行证据与修复

`FORWARD_BOUNDARY_CHECKS.json` 保存 69 训练集支持数量与“毒化被排除建筑”的不泄漏检查：把排除建筑所有候选数值改成极大值，训练特征和类别不变。全量重拟合与归档 β 最大差 4.32e-13、θ 最大差 3.55e-15。

本轮曾发现两个 gzip 导出不完整，并保留于 `export_recovery/`。它们已从完整、冻结的人员特征缓存重建；可解码旧前缀逐字段完全一致。数值模型没有因此调整。原实现和 fast 进程曾有重叠写入阶段；最终原实现成功发布的 4,013,324 行预测被独立完整读取，概率与冻结校准器最大差 1.11e-16，所有 event×method 唯一键完整。fast 的独有临时 `.writing` 文件未通过 gzip 尾部检查，未替换正式预测。其文件损坏原因没有被确定，不将工程导出问题解释为科学分歧。

`atomic_exports.py` 对主要导出先写唯一临时文件、完整读取核对行数/CRC，再原子替换。所有交付的正式小表和大表都有独立完成收据。失败缓存可不放入精简交付包，但应保留故障台账和精确重建代码。
