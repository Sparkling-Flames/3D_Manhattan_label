# 新 Pro 三路线独立复算与继续审查入口

完整中文审查：`/workspace/shared/new_pro_review.md`。本目录只保存独立审计脚本和结果，没有改正式算法、原始记录、资格或参考。

## 完成状态

- 原包35测试及`reproduce.py --full`全部通过；244真实、93控制三分逐列最大复现差0。`replay/REPLAY_SUMMARY.json`，逐命令日志在`replay/results/replay_*.log`。
- 实际current loader逐份固定参考扩展891：889新入口可评价（826 Manual+63 Semi），2 Manual相机外置NA；原891旧资格未改。全部2D点/3D几何哈希与先前完成的891原指标审计相等。`current891_extension/`包含完整显式几何、身份、低层测量、CSV和来源哈希。
- 891×5状态不变性：反向/环起点精确不变、冗余完整线性插点浮点精度不变；共同yaw最大ΔQA .00430、ΔQB .00460、ΔQC .44097。实际891未发现A角度对应有限跳变。
- 新固定6×5角反例：共同精确90°，I和H不变，QA6.71680→11.29141。独立枚举全部30最大基数环对应，位置全局最优恰有两个，成本精确3+√5+2√2；坐标规范起点+pair索引tie选择了不同物理映射。`qa_matching_tie_regression.json`。
- 少量阶梯（每侧2/3/4步）和R00751/N12原答案衍生粗化已测。它们改变真实几何，不是冗余表示；宏观墙结构偏好须同图人工裁决，不能以合成例推断普遍失败。`symmetric_stair_angle_escape.json`、`priority_angle_correspondences.json`、`real_coarsening_controls.json`、`real_shallow_detail_deletions.json`。
- B连续最小化：独立32对随机简单多边形、解析区间凹性和独立积分支持事件端点覆盖。`turning_continuous/`。
- QC最坏真实yaw例细化后大幅收敛；共享高度nearest tie合成例QB差1.864分细化20倍仍保持。旧max残差tie规则同例四姿态Hcenter精确不变，新first-argmin为稳健性退化。`boundary_refinement.json`、`height_nearest_tie_old_new.json`。
- 新local_error与旧Hcenter在同891几何上的绝对差中位2.05e-7、最大3.48e-5；旧均高早已周长积分、旧Hcenter早已中心化双向最近底面。新增贡献应准确收窄。`new_vs_old_local_height891.csv`。

## 依赖与来源

实际Python3.12.14，numpy2.3.5、pandas2.2.3、scipy1.17.0、shapely2.2.0、pytest9.1.1。numpy/pandas/scipy用系统site-packages；独立`python_deps`只提供缺失依赖，保持系统目录在前，防止目标目录的numpy覆盖。

仓库冻结锚点：d1b435ab4d7bfbb199805809be127c00e921c347。原包SHA256：c290b474c07f9579819fd58935ea6a32bc3bb84148d02324166209282253bd44。

主要来源：
- 收到原包`new_pro_return/panorama_quality_three_routes_20261016/`；config与geomscore源码未改。
- 当前实际loader `repo/tools/thesis_main/data_prep/consolidate_research_input.py::load_current_bundle`。
- `repo/research/statistics/descriptive_statistics_rescored_20261016/{quality_records.csv,space_reference_catalog.csv}`，固定参考完整精度点。
- 先前独立891几何审计 `audit_quality_baseline/current891_complete/current891_fixed_reference_geometry_replay.csv`，逐点/3D哈希对照，保留首轮855+补36序列化证明；需要时先按该目录README恢复基线。
- `check_priority_controls.py`特意用作者244输入和metadata重建对照（包括10位参考序列化），与原审计控制结果逐分精确一致；891全量另用current完整精度几何，二者来源分开。
- 未重新选择或构造GT来源，不改变source pool人数，未因分数选择最优参考。

关键文件哈希及审计脚本/结果清单在`SOURCE_HASHES.json`与`ARTIFACT_SHA256.json`。每份输入的哈希在891表/显式pairs内。

## 安全重跑命令

以下在同一scratch根运行；新输出目录不覆盖本次已完成证据。前3个扩展脚本原输出默认拒绝已存在路径，现在提供环境变量只更换输出位置，算法未变。

```bash
cd /workspace/scratch/81fa50cc64f5
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages:/workspace/scratch/81fa50cc64f5/python_deps
RUN="$(mktemp -d /workspace/scratch/81fa50cc64f5/gqs_review_replay.XXXXXX)"
python new_pro_return/panorama_quality_three_routes_20261016/reproduce.py --out "$RUN/original_replay" --full
GQS_891_OUT="$RUN/current891" python new_pro_audit/extend_current891.py
GQS_891_INPUT="$RUN/current891" GQS_INVARIANCE_OUT="$RUN/invariance891" python new_pro_audit/audit_invariance891.py
GQS_TURNING_OUT="$RUN/turning_continuous" python new_pro_audit/check_turning_continuous.py
python new_pro_audit/check_qa_matching_tie.py --out "$RUN/qa_matching_tie.json"
python new_pro_audit/check_priority_controls.py --out "$RUN/priority_controls"
GQS_STAIR_OUT="$RUN/symmetric_stairs.json" python new_pro_audit/probe_symmetric_stairs.py
python new_pro_audit/check_boundary_refinement.py --out "$RUN/boundary_refinement.json"
python new_pro_audit/check_height_nearest_tie.py --out "$RUN/height_tie_old_new.json"
python new_pro_audit/compare_local_height891.py --out "$RUN/local_height_comparison.csv"
```

`boundary_refinement`使用已存固定891几何和确定的合成控制；仅诊断步长.01/.005/.0025/.001/.0005，并提高max_samples上限容纳细化，不覆盖正式v2成绩。`compare_local_height891`读取此前已重测的旧分项及本次新分项，不谎称它本身又重复测了一轮几何。

早期`probe_*.py`与`*_probe.json`是发现轨迹；正式固定反例以`check_qa_matching_tie.py`及独立30方案枚举为准。完整原输入都在JSON，随机seed也保留。

## 明确未做

未新增盲人工标签、未独立看全量原图、未校准绝对分档；原图工作台与必要结构裁决由主审另行完成。没有证明QA/QB/QC对所有Manual、Semi、门洞或未来算法优于旧B8L2。没有为通过测试改正式源码、篡改资格或挑参考。旧目录Hm/Hc单位文档bug与新方案采用决策分列，未混入纯链接修复。
