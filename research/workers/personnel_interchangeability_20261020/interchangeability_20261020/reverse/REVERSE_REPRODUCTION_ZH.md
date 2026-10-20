# 反向路线的最小复现依赖与恢复入口

这份说明供精简成果包整合使用。主结论重放应使用**已冻结人员标签和精确请求**；重新学习类别是另外一个复现层级。不同数值库引起边界标签差异时，不能静默换掉本轮主类别再把结果称为同一实验。

## 一、版本与数据恢复

当前任务文档 main 为 `445686f8f3cf6039c4ce1f60016cad1d26829044`；冻结融合科学源为 `82c6164b0d4630de5316199c92aa405930973168`。本工作区实际核验旧 A 档案的仓库提交为 `e572eb73bedc4fe9056df838e458bab83c3fa423`，档案逐文件哈希列在 `REVERSE_RECOVERY_INPUTS.json`。三者用途分开，不能只标一个“main”代替全部来源。

固定仓库是 `Sparkling-Flames/3D_Manhattan_label`。恢复入口：

- `research/workers/personnel_type_discovery_next_20261019/bootstrap.py`
- 同目录 `ARCHIVE_FILE_MAP.json`、`PAYLOAD_BUNDLES.json` 及所列内容分片。
- 复用的上轮档案：`research/workers/pro_personnel_v2_archive_20261019/`。

在包含该固定档案和科学提交对象的克隆中，工作区结构保持为交付说明中的根目录，运行：

```bash
python repo/research/workers/personnel_type_discovery_next_20261019/bootstrap.py \
  --repository repo \
  --output restored
```

`restored` 必须是新目录或空目录。该入口恢复并核对原档案成员，不联网、不运行科学计算、不覆写已有恢复目录。完整恢复会产生约 1.56GB 的临时工作数据；它不是本次 ZIP 的内容，也不是每次查看主结果都必需的步骤。若按文件清单做定向恢复，必须验证每个保留文件的 SHA，不能把定向恢复称为整个历史 ZIP 的逐字节校验。

**真正用于反向训练的是 79 个历史逐池 `events/comparisons/<pool>/events.csv.gz`**，不是 95MB `common_events.csv.gz` 总表。逐池数据同时含旧固定背景与 A_nested；学习函数明确只取 `Pro_exact_fixed_background_v1`（122,082 次历史真实替换），把 7,272 次 A_nested 留作冻结后的历史压力检查。另需 `events/DESIGN.json`、`FIELD_CONTRACT.json`、`EVENT_VERIFICATION_RECEIPT.json`。精确 79 条路径和 SHA 已附于恢复索引。

共享冻结快照为：

`restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz`

其 SHA256 为 `83179b9842d06916b105d80ff181918c223e4fee2073f425f9825db124ec11d7`。不得改从未经继承处理的原始导出重建坐标、环序、参考或 OOS 资格。

## 二、新历史面板和 35 万配对如何重建

精简包应保留 `history_panel/HISTORY_PANEL_REGISTRATION.json`、`history_anchors.json.gz`（约 0.57MB）及精确 `history_requests.json.gz`（约 0.64MB），或保留经过成员一致性审计的生成器与原样 spec。选择只读取历史池元数据、ID 与种子 `2026102001`，不读取目标质量或类别。

```bash
python analysis/composition/fusion_runner.py \
  --restored restored \
  --requests interchangeability_20261020/history_panel/history_requests.json.gz \
  --out interchangeability_20261020/history_panel/native_runs \
  --jobs 2

python interchangeability_20261020/reverse/extract_native_history.py \
  --root . \
  --out interchangeability_20261020/reverse \
  --jobs 2
```

共 81 个历史普通 Manual 池、31,539 支实际团队、1,576 个固定共同背景，得到 359,916 个不同实际人员对替换。生成的 `reverse/native_history_events.csv.gz` 约 37.9MB，SHA 为 `44c8752ee5822617f3ec19ff8f6de190d6301368b4abff7f71feacd816cfa3a0`。这个派生大表、逐池 chunks、全部 native 状态都可不打包。

抽取代码的实际依赖是 `analysis/composition/summarize_grid.py` 中的 `pair_metrics` 和 `signature`，以及旧 `analysis/forward/results/features_train.csv.gz` 的 `worker_id/person_origin`。保留目录层级；不要把这些位置替换为完整画像 FULL 或目标楼评价。

## 三、人员类别学习与历史控制

数值依赖已固定在 `requirements_reverse.txt`：Python 3.12；numpy 2.3.5、pandas 2.2.3、scipy 1.17.0、scikit-learn 1.8.0、shapely 2.1.2。绘图另用 matplotlib 3.10.8、Pillow 12.3.0。冻结融合链所需的其余共享依赖由成果包主复现入口管理。

在交付根目录执行，输出到新的重建目录，避免覆写冻结主标签：

```bash
python interchangeability_20261020/reverse/learn_swap_types.py \
  --root . \
  --domains ordinary hard small_n large_n \
  --out interchangeability_20261020/reverse/legacy_rebuild

python interchangeability_20261020/reverse/learn_swap_types.py \
  --root . \
  --supplemental-events interchangeability_20261020/reverse/native_history_events.csv.gz \
  --input-tag mixed_history_v1 \
  --minimum-class-pair-coverage .75 \
  --out interchangeability_20261020/reverse/mixed_rebuild
```

合并版默认七域、四种风险表达、四算法，每个训练图支持人数允许的全部整数 K，seed `2026102003`；最小类 4 人。五个历史内折每次仅八栋训练、两栋留出。`--pilot` 是未用于本轮主结果的便捷试跑，不可拿 pilot 产物代替已冻结 1,040 个合并候选及 768 个旧版候选。

历史解释与审计的可运行入口已列于 `README_REVERSE_ZH.md`：

- `audit_explain_types.py`：类画像、删楼、机会收缩、非传递性。
- `audit_inner_baselines.py`：仅来源与来源内保持容量的随机基线。
- `audit_inner_q_baselines.py`：每折重新构造八楼 Q，比较同 K Q 类及 Q×来源容量随机。它还依赖当前 `forward/audit_and_features.py`、旧前向特征构建代码和历史 records，不能仅提供一张全十楼 Q 表就宣称无泄漏重建了内层基线。
- `stress_nested_history.py`：不参与选类的旧 A_nested 背景压力。
- `summarize_training_audits.py`：各表的可读对照；并非重新拟合。

### 必须直接保留的历史小证据

`legacy_fit`、`mixed_fit` 的精确 `worker_labels.csv.gz`、`METHOD_MANIFEST.json`、`REGISTRATION.json`、`INPUT_AUDIT.json`、`RUN_RECEIPT.json`，以及全部候选的 `candidate_fold_ledger.csv.gz`、`candidate_cv_summary.csv`；两份冻结短名单和 `review_tables/all_candidate_catalog.csv.gz`、搜索台账不能只剩获胜者。

本轮 15 路线的原始逐折／楼小表已提取为 **`review_tables/selected_inner_cv_building.csv.gz`，138 行**。它保留所选路线全部实际支持，不把完整数千行逐候选缓存打包。Q 控制至少保留 `inner_q_baselines/REGISTRATION.json`、`Q_BASELINE_RECEIPT.json`、`paired_summary.csv`、`paired_draw_summary.csv`、`support_ledger.csv`、`eight_building_Q_features.csv.gz`。来源基线与删楼、收缩、实际非传递的核心小表也列在清单中。

完整 `inner_cv_building.csv.gz`、所有 `historical_pair_relations.csv.gz`、随机基线的全部楼×draw 大表可生成，不是主案例重放必需输入。无需模型权重或每折序列化模型缓存：当前方法是由历史关系确定的分区和固定人员标签。

## 四、主评估和 W132 机制检查

主设计入口是 `code/design_nested_new2.py`；它固定块后展开 core 前缀，不是每个 n 重新抽人员。原始 spec、freeze、seed、容量账和精确请求应按主目录复现说明保存或重建并校验实际成员哈希。

```bash
python interchangeability_20261020/code/design_nested_new2.py

python analysis/composition/fusion_runner.py \
  --restored restored \
  --requests interchangeability_20261020/assessment/nested_new2_requests.json.gz \
  --out interchangeability_20261020/assessment/native_nested_new2 --jobs 2

python interchangeability_20261020/code/summarize_blocks.py \
  --snapshot restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz \
  --requests interchangeability_20261020/assessment/nested_new2_requests.json.gz \
  --native interchangeability_20261020/assessment/native_nested_new2 \
  --features interchangeability_20261020/forward/features_train.csv.gz \
  --out interchangeability_20261020/assessment/nested_new2_metrics \
  --jobs 1 --stream --events-only

python interchangeability_20261020/reverse/assessment_interpretation/analyze_nested_new2.py
python interchangeability_20261020/reverse/assessment_interpretation/supplement_new2_primary.py
python interchangeability_20261020/reverse/assessment_interpretation/summarize_full_vectors.py
python interchangeability_20261020/reverse/assessment_interpretation/plot_nested_chinese.py
```

绘图默认字体为 `analysis/fonts/NotoSansSC-Regular.ttf`，可用 `--font` 指向别的中文 TTF。仅从已给的小表重绘两张曲线不需要历史大配对表、原图集或重新融合。

`summarize_full_vectors.py` 只重新汇总已冻结 n13/m5 双方向 116 个事件，以 A/B 与 C 的完整类别人数向量为单位，生成 `nested_new2/full_vectors/` 中的全部 10 个向量、逐图/逐楼表和精确成员链接。它是事后构成分层，不触发新融合，也不改变分类或评估方向。跨向量的图片支持不同，不能把跨行均分变化解释为纯配比效应。

六个固定反向细类方向用 `analyze_fixed_directions.py`，它读取主生成器产生的 `assessment/direction_requests.json.gz` 与正式完成 receipt。代码只提取六个已冻结方向，并检查当前标签 SHA 与 freeze 相符；不会从尚未完成的 pool 把缺队算成失败。

**W132 事后检查只有 82,828 字节精确请求，建议直接保留。** 同时保留 `assessment_interpretation/w132_probe/REGISTER.json`、设计 receipt、容量／精确 links 及 `design_w132_probe.py`。其命令顺序与主面板相同：生成器→冻结 runner（requests=`assessment/w132_probe_requests.json.gz`，out=`assessment/native_w132_probe`）→`summarize_blocks.py`（out=`assessment/w132_probe_metrics`）→`analyze_w132_probe.py`→`plot_w132_probe.py`。生成器已有 REGISTER 时沿用原登记时间和 hash；不要新生成时间后据此认定成员设计不同。

W132 代码只读取旧 n13/m5 双向 116 事件、当前池可用人员与冻结 C02 标签，其他类别与 n/m 不扩展。235 个替代只在原 ABC 并集外枚举，同一替代者在 W132 的全部位置一致替换。原／新有限质量支持、A-only 的 B/C 不变断言、全部无容量均可重建。

## 五、成果包清单与边界

机器可读建议清单是 `REVERSE_MINIMAL_REPRODUCTION.json`，逐项列文件大小、SHA、用途及可重建大表。所列共享文件只应装一次。最终精简建议文件压缩前约 11.9MB，其中已包括图、标签、候选证据、完整配比小表和共享设计；精确数量以机器清单为准，父成果包可按必要性合并重复路径、去掉替代格式图像。

`PRUNE_REBUILDABLE.json` 明确列出可从初包移出的 14 个派生文件及重建入口：两版全候选宽画像、历史基线的建筑×draw 明细、非主张的发现分层、嵌套相邻人数步骤明细、旧 A_nested 的类别对×楼展开。它们不包含冻结标签、全部候选台账、主评估逐图/逐楼、成员/建筑剔除、完整配比、精确请求或最终几何。历史来源与 Q 基线的每 draw 小汇总仍保留；全部 15 路线的 86 类和 743 条逐人解释也保留。剔除清单只是包装政策，不执行删除研究源文件。

`assessment_interpretation/EXPORT_S07_AND_COUNTER_SELECTION.json` 可直接供主 `export_cases.py` 使用；最终精确成员、参考及几何由主导出器嵌入病例文件。S07 原图已缓存，S10 如需全景原图按精确 `image_id` 从既有 Release 索引提取。原图全集和逐队全流程状态不应装入精简包。

不应省略：精确冻结标签、全候选失败台账、实际支持小表、主曲线 source 小表、W132 的事后注册和原／新精确 links、少数最终病例几何及重放证明。可以省略：35 万新配对大表、全体距离图、每折模型缓存、重复仓库副本、原图全集、native 缓存和大量日志。恢复原档案、重训所有候选、重放主比较是不同层级，应分别记录是否实际执行。
