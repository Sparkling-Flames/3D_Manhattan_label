# 导师回复前数据全量审计（2026-09-05）

## 结论先行

1. 本次源底座实跑与旧底座在剔除 workbook 元数据后语义等价（布尔格式归一、数值容差 1e-12）；historical/manual 最终目录明确复用旧冻结包，其 QA 与本会话先前完整复跑一致，不把复用伪称为本次再次重算。旧 42 张高密度图共 1055 条记录，其中严格几何 1013；旧独立性标签为 independent=840、confirmed=88、suspected=115、unknown=12；旧 reference-quality eligibility 为 770。unknown 没有被补成零或独立。
2. 工人粗分只够作候选描述，不支持固定人群类型。当前授权版 H/L/U=3/2/15；跨 building 与两版本中，任意折内标签完全稳定为 6 人（H: W1；L: W34/W37；U: W11/W30/W33），但能稳定归入实质 H/L 的只有 3 人。稳定 U 仍是“未分类”，不是第三种人群。
3. `7/8/7` 未在指定机器可读产物、报告或导师草稿中找到可追溯来源，不能作为人数分母或结论。
4. 214 张历史图均找到 HoHoNet 和 BiLayout enclosed/extended 文件；严格人类几何 2427 条，覆盖 214 图/22 building。按本次所选 reference/readiness 口径，GT 几何可描述比较 180 图；180 不表示其余图物理 GT 文件缺失，也不是新研究准入门槛。公共 GT 不自动视为正确，且未审 scope 与已裁定 reference 分开保留。
5. 没有证据支持把 full-roster 自恢复当作质量上限，也没有检验出“平台期”。full-roster self-recovery 是同一有限 roster 的构造性目标，不是新工人总体保证。

## 来源全量盘点

扫描 `export_label/`、`import_json/`、`active_logs/`，并登记 GT、HoHoNet 与 BiLayout 外部预测。文件分类计数：{"active_log_metadata": 6, "development_export": 15, "development_or_unlaunched_import": 30, "duplicate_active_log": 97, "duplicate_or_revision_export": 9, "formal_active_log": 39, "formal_experiment_export": 18, "formal_planned_import": 19, "legacy_active_log": 12, "legacy_import": 12, "package_manifest": 1, "reference_export": 12, "reference_import": 5, "unresolved_active_log": 97, "unresolved_import": 23}。共展开 10956 个按来源出现的 annotation snapshot：formal=2513、reference=5512、development=779、duplicate/revision=2152；这是源角色与快照计数，不代表额外的独立标注。`unresolved_records.csv` 的 120 项实际为 23 个 unresolved import 文件和 97 个 unresolved active-log 文件（可含 README/XML 等支持文件），不是 120 条丢失的人类标注。2501 条 canonical 是已建立身份映射的历史实验底座；其他参考、开发与修订资料均已登记，未因旧 eligibility 判为不可用，但尚未作为额外独立响应并入。重复快照、revision、reference、development 与 formal source 分开，详见 `source_inventory.csv`、`export_annotation_version_inventory.csv` 和 `unresolved_records.csv`。

## 独立性敏感性与 k

新研究的主普查不使用旧 eligibility 过滤，覆盖全部实际 canonical 与版本：

- C1 / manual：87 图单元、87 context、674 canonical、680 raw version、raw geometry 可计算 668；观察到≥20人/strict 支持 k20 的图分别为 12/12。
- C1 / semi：25 图单元、25 context、106 canonical、108 raw version、raw geometry 可计算 105；观察到≥20人/strict 支持 k20 的图分别为 0/0。
- C2-A-RP / manual：42 图单元、55 context、80 canonical、80 raw version、raw geometry 可计算 79；观察到≥20人/strict 支持 k20 的图分别为 0/0。
- C2-B / manual：46 图单元、46 context、160 canonical、160 raw version、raw geometry 可计算 160；观察到≥20人/strict 支持 k20 的图分别为 4/1。
- P1 / manual：30 图单元、30 context、779 canonical、782 raw version、raw geometry 可计算 741；观察到≥20人/strict 支持 k20 的图分别为 30/30。
- P1 / oos：9 图单元、9 context、234 canonical、234 raw version、raw geometry 可计算 221；观察到≥20人/strict 支持 k20 的图分别为 9/9。
- P1 / semi：18 图单元、18 context、468 canonical、469 raw version、raw geometry 可计算 464；观察到≥20人/strict 支持 k20 的图分别为 18/18。

其中旧 42 图只是 P1 Manual 30 + C1 Manual 12 的历史高密度子集；新增高支持层还包括 P1 Semi、P1 OOS 与 C2-B。P1 OOS 保留为独立层，不能因旧 scope 排除；C1 Semi 即使旧 eligibility 不准入，也仍进入全量普查与同图描述。低支持单元不伪造 k15。

全量 strict 支持≥15 单元的分层嵌套回放：

- C1 / manual，固定 k20 支持集，k=15：12 图/5 building，status=0.700/0.717，partition=0.820/0.847（task-equal/building-equal）。
- C1 / manual，固定 k20 支持集，k=16：12 图/5 building，status=0.736/0.755，partition=0.840/0.865（task-equal/building-equal）。
- C1 / manual，固定 k20 支持集，k=17：12 图/5 building，status=0.770/0.791，partition=0.858/0.882（task-equal/building-equal）。
- C1 / manual，固定 k20 支持集，k=18：12 图/5 building，status=0.800/0.821，partition=0.873/0.895（task-equal/building-equal）。
- C1 / manual，固定 k20 支持集，k=19：12 图/5 building，status=0.836/0.855，partition=0.892/0.912（task-equal/building-equal）。
- C1 / manual，固定 k20 支持集，k=20：12 图/5 building，status=0.874/0.890，partition=0.914/0.928（task-equal/building-equal）。
- C2-B / manual，固定 k20 支持集，k=15：1 图/1 building，status=1.000/1.000，partition=1.000/1.000（task-equal/building-equal）。
- C2-B / manual，固定 k20 支持集，k=16：1 图/1 building，status=1.000/1.000，partition=1.000/1.000（task-equal/building-equal）。
- C2-B / manual，固定 k20 支持集，k=17：1 图/1 building，status=1.000/1.000，partition=1.000/1.000（task-equal/building-equal）。
- C2-B / manual，固定 k20 支持集，k=18：1 图/1 building，status=1.000/1.000，partition=1.000/1.000（task-equal/building-equal）。
- C2-B / manual，固定 k20 支持集，k=19：1 图/1 building，status=1.000/1.000，partition=1.000/1.000（task-equal/building-equal）。
- C2-B / manual，固定 k20 支持集，k=20：1 图/1 building，status=1.000/1.000，partition=1.000/1.000（task-equal/building-equal）。
- P1 / manual，固定 k20 支持集，k=15：30 图/12 building，status=0.747/0.725，partition=0.943/0.924（task-equal/building-equal）。
- P1 / manual，固定 k20 支持集，k=16：30 图/12 building，status=0.774/0.750，partition=0.945/0.929（task-equal/building-equal）。
- P1 / manual，固定 k20 支持集，k=17：30 图/12 building，status=0.795/0.773，partition=0.949/0.933（task-equal/building-equal）。
- P1 / manual，固定 k20 支持集，k=18：30 图/12 building，status=0.823/0.804，partition=0.952/0.937（task-equal/building-equal）。
- P1 / manual，固定 k20 支持集，k=19：30 图/12 building，status=0.847/0.832，partition=0.957/0.943（task-equal/building-equal）。
- P1 / manual，固定 k20 支持集，k=20：30 图/12 building，status=0.874/0.859，partition=0.966/0.953（task-equal/building-equal）。
- P1 / oos，固定 k20 支持集，k=15：9 图/6 building，status=0.833/0.832，partition=0.908/0.954（task-equal/building-equal）。
- P1 / oos，固定 k20 支持集，k=16：9 图/6 building，status=0.863/0.864，partition=0.918/0.959（task-equal/building-equal）。
- P1 / oos，固定 k20 支持集，k=17：9 图/6 building，status=0.884/0.891，partition=0.919/0.960（task-equal/building-equal）。
- P1 / oos，固定 k20 支持集，k=18：9 图/6 building，status=0.901/0.913，partition=0.926/0.963（task-equal/building-equal）。
- P1 / oos，固定 k20 支持集，k=19：9 图/6 building，status=0.913/0.928，partition=0.930/0.965（task-equal/building-equal）。
- P1 / oos，固定 k20 支持集，k=20：9 图/6 building，status=0.930/0.947，partition=0.938/0.969（task-equal/building-equal）。
- P1 / semi，固定 k20 支持集，k=15：18 图/10 building，status=0.752/0.655，partition=0.916/0.849（task-equal/building-equal）。
- P1 / semi，固定 k20 支持集，k=16：18 图/10 building，status=0.783/0.691，partition=0.922/0.860（task-equal/building-equal）。
- P1 / semi，固定 k20 支持集，k=17：18 图/10 building，status=0.808/0.721，partition=0.929/0.871（task-equal/building-equal）。
- P1 / semi，固定 k20 支持集，k=18：18 图/10 building，status=0.839/0.762，partition=0.936/0.885（task-equal/building-equal）。
- P1 / semi，固定 k20 支持集，k=19：18 图/10 building，status=0.858/0.788，partition=0.939/0.891（task-equal/building-equal）。
- P1 / semi，固定 k20 支持集，k=20：18 图/10 building，status=0.884/0.824，partition=0.947/0.904（task-equal/building-equal）。

历史全 roster 分三种独立性处置：全部严格几何；仅旧标签 independent；仅排除 confirmed（suspected/unknown 仍显式包含）。用户确认的当前可用 20 人（W1/W2/W6/W8/W10/W11/W12/W13/W15/W17/W28–W37）另做 all-strict 与 independent-only 的 k=15–20。每个 scenario×task 使用同一组随机排列，各 k=3/5/8/12/13/15/16/17/18/19/20 取嵌套前缀并记录相邻 k 配对变化；每图每 k 做 200 次有限 roster 无放回重放。15–20 是资源敏感性范围，不证明 20 是质量上限，也不外推未来招募。

- current_available20__all_strict_geometry|fixed_common_support_k20，k=15：36 图/12 building/20 人；full-status task-equal/building-equal=0.847/0.860，partition=0.944/0.929。
- current_available20__all_strict_geometry|fixed_common_support_k20，k=16：36 图/12 building/20 人；full-status task-equal/building-equal=0.877/0.890，partition=0.955/0.945。
- current_available20__all_strict_geometry|fixed_common_support_k20，k=17：36 图/12 building/20 人；full-status task-equal/building-equal=0.907/0.915，partition=0.965/0.955。
- current_available20__all_strict_geometry|fixed_common_support_k20，k=18：36 图/12 building/20 人；full-status task-equal/building-equal=0.940/0.945，partition=0.976/0.971。
- current_available20__all_strict_geometry|fixed_common_support_k20，k=19：36 图/12 building/20 人；full-status task-equal/building-equal=0.969/0.974，partition=0.988/0.987。
- current_available20__all_strict_geometry|fixed_common_support_k20，k=20：36 图/12 building/20 人；full-status task-equal/building-equal=1.000/1.000，partition=1.000/1.000。
- current_available20__all_strict_geometry|scenario_k_specific，k=15：42 图/12 building/20 人；full-status task-equal/building-equal=0.845/0.856，partition=0.933/0.920。
- current_available20__all_strict_geometry|scenario_k_specific，k=16：42 图/12 building/20 人；full-status task-equal/building-equal=0.875/0.886，partition=0.946/0.937。
- current_available20__all_strict_geometry|scenario_k_specific，k=17：42 图/12 building/20 人；full-status task-equal/building-equal=0.907/0.913，partition=0.958/0.950。
- current_available20__all_strict_geometry|scenario_k_specific，k=18：42 图/12 building/20 人；full-status task-equal/building-equal=0.941/0.946，partition=0.973/0.969。
- current_available20__all_strict_geometry|scenario_k_specific，k=19：41 图/12 building/20 人；full-status task-equal/building-equal=0.973/0.977，partition=0.990/0.988。
- current_available20__all_strict_geometry|scenario_k_specific，k=20：36 图/12 building/20 人；full-status task-equal/building-equal=1.000/1.000，partition=1.000/1.000。
- current_available20__legacy_independent_only|fixed_common_support_k20，k=15：12 图/5 building/20 人；full-status task-equal/building-equal=0.792/0.784，partition=0.885/0.886。
- current_available20__legacy_independent_only|fixed_common_support_k20，k=16：12 图/5 building/20 人；full-status task-equal/building-equal=0.834/0.830，partition=0.908/0.910。
- current_available20__legacy_independent_only|fixed_common_support_k20，k=17：12 图/5 building/20 人；full-status task-equal/building-equal=0.878/0.876，partition=0.933/0.935。
- current_available20__legacy_independent_only|fixed_common_support_k20，k=18：12 图/5 building/20 人；full-status task-equal/building-equal=0.916/0.913，partition=0.954/0.954。
- current_available20__legacy_independent_only|fixed_common_support_k20，k=19：12 图/5 building/20 人；full-status task-equal/building-equal=0.955/0.955，partition=0.973/0.974。
- current_available20__legacy_independent_only|fixed_common_support_k20，k=20：12 图/5 building/20 人；full-status task-equal/building-equal=1.000/1.000，partition=1.000/1.000。
- current_available20__legacy_independent_only|scenario_k_specific，k=15：38 图/11 building/20 人；full-status task-equal/building-equal=0.898/0.904，partition=0.939/0.935。
- current_available20__legacy_independent_only|scenario_k_specific，k=16：35 图/11 building/20 人；full-status task-equal/building-equal=0.926/0.936，partition=0.953/0.955。
- current_available20__legacy_independent_only|scenario_k_specific，k=17：19 图/8 building/20 人；full-status task-equal/building-equal=0.917/0.931，partition=0.952/0.957。
- current_available20__legacy_independent_only|scenario_k_specific，k=18：14 图/7 building/20 人；full-status task-equal/building-equal=0.928/0.938，partition=0.960/0.967。
- current_available20__legacy_independent_only|scenario_k_specific，k=19：12 图/5 building/20 人；full-status task-equal/building-equal=0.955/0.955，partition=0.973/0.974。
- current_available20__legacy_independent_only|scenario_k_specific，k=20：12 图/5 building/20 人；full-status task-equal/building-equal=1.000/1.000，partition=1.000/1.000。
- historical_all__all_strict_geometry|fixed_common_support_k20，k=3：42 图/12 building/26 人；full-status task-equal/building-equal=0.174/0.204，partition=0.863/0.850。
- historical_all__all_strict_geometry|fixed_common_support_k20，k=5：42 图/12 building/26 人；full-status task-equal/building-equal=0.260/0.288，partition=0.863/0.849。
- historical_all__all_strict_geometry|fixed_common_support_k20，k=8：42 图/12 building/26 人；full-status task-equal/building-equal=0.468/0.460，partition=0.871/0.857。
- historical_all__all_strict_geometry|fixed_common_support_k20，k=12：42 图/12 building/26 人；full-status task-equal/building-equal=0.640/0.618，partition=0.885/0.871。
- historical_all__all_strict_geometry|fixed_common_support_k20，k=13：42 图/12 building/26 人；full-status task-equal/building-equal=0.676/0.649，partition=0.890/0.877。
- historical_all__all_strict_geometry|fixed_common_support_k20，k=15：42 图/12 building/26 人；full-status task-equal/building-equal=0.743/0.710，partition=0.909/0.893。
- historical_all__all_strict_geometry|fixed_common_support_k20，k=16：42 图/12 building/26 人；full-status task-equal/building-equal=0.768/0.736，partition=0.915/0.901。
- historical_all__all_strict_geometry|fixed_common_support_k20，k=17：42 图/12 building/26 人；full-status task-equal/building-equal=0.795/0.761，partition=0.924/0.909。
- historical_all__all_strict_geometry|fixed_common_support_k20，k=18：42 图/12 building/26 人；full-status task-equal/building-equal=0.822/0.791，partition=0.934/0.919。
- historical_all__all_strict_geometry|fixed_common_support_k20，k=19：42 图/12 building/26 人；full-status task-equal/building-equal=0.849/0.819，partition=0.943/0.928。
- historical_all__all_strict_geometry|fixed_common_support_k20，k=20：42 图/12 building/26 人；full-status task-equal/building-equal=0.878/0.852，partition=0.956/0.942。
- historical_all__all_strict_geometry|scenario_k_specific，k=3：42 图/12 building/26 人；full-status task-equal/building-equal=0.174/0.204，partition=0.863/0.850。
- historical_all__all_strict_geometry|scenario_k_specific，k=5：42 图/12 building/26 人；full-status task-equal/building-equal=0.260/0.288，partition=0.863/0.849。
- historical_all__all_strict_geometry|scenario_k_specific，k=8：42 图/12 building/26 人；full-status task-equal/building-equal=0.468/0.460，partition=0.871/0.857。
- historical_all__all_strict_geometry|scenario_k_specific，k=12：42 图/12 building/26 人；full-status task-equal/building-equal=0.640/0.618，partition=0.885/0.871。
- historical_all__all_strict_geometry|scenario_k_specific，k=13：42 图/12 building/26 人；full-status task-equal/building-equal=0.676/0.649，partition=0.890/0.877。
- historical_all__all_strict_geometry|scenario_k_specific，k=15：42 图/12 building/26 人；full-status task-equal/building-equal=0.743/0.710，partition=0.909/0.893。
- historical_all__all_strict_geometry|scenario_k_specific，k=16：42 图/12 building/26 人；full-status task-equal/building-equal=0.768/0.736，partition=0.915/0.901。
- historical_all__all_strict_geometry|scenario_k_specific，k=17：42 图/12 building/26 人；full-status task-equal/building-equal=0.795/0.761，partition=0.924/0.909。
- historical_all__all_strict_geometry|scenario_k_specific，k=18：42 图/12 building/26 人；full-status task-equal/building-equal=0.822/0.791，partition=0.934/0.919。
- historical_all__all_strict_geometry|scenario_k_specific，k=19：42 图/12 building/26 人；full-status task-equal/building-equal=0.849/0.819，partition=0.943/0.928。
- historical_all__all_strict_geometry|scenario_k_specific，k=20：42 图/12 building/26 人；full-status task-equal/building-equal=0.878/0.852，partition=0.956/0.942。
- historical_all__exclude_confirmed_only|fixed_common_support_k20，k=3：41 图/12 building/26 人；full-status task-equal/building-equal=0.196/0.231，partition=0.862/0.849。
- historical_all__exclude_confirmed_only|fixed_common_support_k20，k=5：41 图/12 building/26 人；full-status task-equal/building-equal=0.286/0.335，partition=0.862/0.852。
- historical_all__exclude_confirmed_only|fixed_common_support_k20，k=8：41 图/12 building/26 人；full-status task-equal/building-equal=0.510/0.528，partition=0.874/0.862。
- historical_all__exclude_confirmed_only|fixed_common_support_k20，k=12：41 图/12 building/26 人；full-status task-equal/building-equal=0.689/0.681，partition=0.889/0.879。
- historical_all__exclude_confirmed_only|fixed_common_support_k20，k=13：41 图/12 building/26 人；full-status task-equal/building-equal=0.721/0.713，partition=0.893/0.885。
- historical_all__exclude_confirmed_only|fixed_common_support_k20，k=15：41 图/12 building/26 人；full-status task-equal/building-equal=0.786/0.776，partition=0.909/0.901。
- historical_all__exclude_confirmed_only|fixed_common_support_k20，k=16：41 图/12 building/26 人；full-status task-equal/building-equal=0.813/0.803，partition=0.916/0.909。
- historical_all__exclude_confirmed_only|fixed_common_support_k20，k=17：41 图/12 building/26 人；full-status task-equal/building-equal=0.842/0.835，partition=0.925/0.918。
- historical_all__exclude_confirmed_only|fixed_common_support_k20，k=18：41 图/12 building/26 人；full-status task-equal/building-equal=0.869/0.860，partition=0.934/0.925。
- historical_all__exclude_confirmed_only|fixed_common_support_k20，k=19：41 图/12 building/26 人；full-status task-equal/building-equal=0.902/0.897，partition=0.946/0.939。
- historical_all__exclude_confirmed_only|fixed_common_support_k20，k=20：41 图/12 building/26 人；full-status task-equal/building-equal=0.931/0.929，partition=0.959/0.951。
- historical_all__exclude_confirmed_only|scenario_k_specific，k=3：42 图/12 building/26 人；full-status task-equal/building-equal=0.201/0.233，partition=0.866/0.850。
- historical_all__exclude_confirmed_only|scenario_k_specific，k=5：42 图/12 building/26 人；full-status task-equal/building-equal=0.294/0.338，partition=0.865/0.853。
- historical_all__exclude_confirmed_only|scenario_k_specific，k=8：42 图/12 building/26 人；full-status task-equal/building-equal=0.518/0.530，partition=0.877/0.864。
- historical_all__exclude_confirmed_only|scenario_k_specific，k=12：42 图/12 building/26 人；full-status task-equal/building-equal=0.696/0.682，partition=0.892/0.880。
- historical_all__exclude_confirmed_only|scenario_k_specific，k=13：42 图/12 building/26 人；full-status task-equal/building-equal=0.728/0.714，partition=0.895/0.886。
- historical_all__exclude_confirmed_only|scenario_k_specific，k=15：42 图/12 building/26 人；full-status task-equal/building-equal=0.791/0.777，partition=0.911/0.901。
- historical_all__exclude_confirmed_only|scenario_k_specific，k=16：42 图/12 building/26 人；full-status task-equal/building-equal=0.818/0.805，partition=0.918/0.910。
- historical_all__exclude_confirmed_only|scenario_k_specific，k=17：42 图/12 building/26 人；full-status task-equal/building-equal=0.846/0.836，partition=0.927/0.919。
- historical_all__exclude_confirmed_only|scenario_k_specific，k=18：42 图/12 building/26 人；full-status task-equal/building-equal=0.872/0.860，partition=0.936/0.926。
- historical_all__exclude_confirmed_only|scenario_k_specific，k=19：42 图/12 building/26 人；full-status task-equal/building-equal=0.904/0.898，partition=0.948/0.939。
- historical_all__exclude_confirmed_only|scenario_k_specific，k=20：41 图/12 building/26 人；full-status task-equal/building-equal=0.931/0.929，partition=0.959/0.951。
- historical_all__legacy_independent_only|fixed_common_support_k20，k=3：15 图/7 building/24 人；full-status task-equal/building-equal=0.231/0.319，partition=0.628/0.573。
- historical_all__legacy_independent_only|fixed_common_support_k20，k=5：15 图/7 building/24 人；full-status task-equal/building-equal=0.220/0.267，partition=0.641/0.581。
- historical_all__legacy_independent_only|fixed_common_support_k20，k=8：15 图/7 building/24 人；full-status task-equal/building-equal=0.418/0.381，partition=0.673/0.610。
- historical_all__legacy_independent_only|fixed_common_support_k20，k=12：15 图/7 building/24 人；full-status task-equal/building-equal=0.598/0.558，partition=0.736/0.687。
- historical_all__legacy_independent_only|fixed_common_support_k20，k=13：15 图/7 building/24 人；full-status task-equal/building-equal=0.630/0.592，partition=0.753/0.706。
- historical_all__legacy_independent_only|fixed_common_support_k20，k=15：15 图/7 building/24 人；full-status task-equal/building-equal=0.704/0.673，partition=0.800/0.763。
- historical_all__legacy_independent_only|fixed_common_support_k20，k=16：15 图/7 building/24 人；full-status task-equal/building-equal=0.743/0.719，partition=0.824/0.793。
- historical_all__legacy_independent_only|fixed_common_support_k20，k=17：15 图/7 building/24 人；full-status task-equal/building-equal=0.784/0.765，partition=0.851/0.828。
- historical_all__legacy_independent_only|fixed_common_support_k20，k=18：15 图/7 building/24 人；full-status task-equal/building-equal=0.836/0.831，partition=0.885/0.877。
- historical_all__legacy_independent_only|fixed_common_support_k20，k=19：15 图/7 building/24 人；full-status task-equal/building-equal=0.878/0.881，partition=0.913/0.914。
- historical_all__legacy_independent_only|fixed_common_support_k20，k=20：15 图/7 building/24 人；full-status task-equal/building-equal=0.924/0.933，partition=0.948/0.956。
- historical_all__legacy_independent_only|scenario_k_specific，k=3：42 图/12 building/24 人；full-status task-equal/building-equal=0.207/0.250，partition=0.864/0.851。
- historical_all__legacy_independent_only|scenario_k_specific，k=5：42 图/12 building/24 人；full-status task-equal/building-equal=0.294/0.345，partition=0.869/0.856。
- historical_all__legacy_independent_only|scenario_k_specific，k=8：42 图/12 building/24 人；full-status task-equal/building-equal=0.519/0.537，partition=0.877/0.866。
- historical_all__legacy_independent_only|scenario_k_specific，k=12：42 图/12 building/24 人；full-status task-equal/building-equal=0.719/0.720，partition=0.894/0.886。
- historical_all__legacy_independent_only|scenario_k_specific，k=13：42 图/12 building/24 人；full-status task-equal/building-equal=0.757/0.756，partition=0.900/0.893。
- historical_all__legacy_independent_only|scenario_k_specific，k=15：42 图/12 building/24 人；full-status task-equal/building-equal=0.835/0.837，partition=0.918/0.912。
- historical_all__legacy_independent_only|scenario_k_specific，k=16：41 图/12 building/24 人；full-status task-equal/building-equal=0.867/0.877，partition=0.927/0.924。
- historical_all__legacy_independent_only|scenario_k_specific，k=17：39 图/11 building/24 人；full-status task-equal/building-equal=0.897/0.901，partition=0.936/0.930。
- historical_all__legacy_independent_only|scenario_k_specific，k=18：30 图/10 building/24 人；full-status task-equal/building-equal=0.906/0.919，partition=0.938/0.940。
- historical_all__legacy_independent_only|scenario_k_specific，k=19：23 图/9 building/24 人；full-status task-equal/building-equal=0.921/0.928，partition=0.943/0.942。
- historical_all__legacy_independent_only|scenario_k_specific，k=20：15 图/7 building/24 人；full-status task-equal/building-equal=0.924/0.933，partition=0.948/0.956。

这不是 population plateau 分析；支持不足的图保持不可评估，另报告固定 k20 common-support 集，真实 image/building/worker 分母逐行报告。当前 20 人子集同时报告“恢复该子集 filtered full target”和“恢复同独立性处置下 historical-all target”两个 estimand，不混用；若某图恰有 20 人完整支持，k20 对前者的自恢复机械为 1。不同独立性场景会改变 filtered full-roster 目标，因此场景差不是“同一目标上的独立性因果效应”。少数结构只表示数据支持的几何模式；既不自动正确，也不等同 GT；same-second 同时给 all-task 分母和 full-second 支持≥2 的条件分母。逐 building 的 15–20 固定支持集见 `independence_sensitivity_building_k15_20.csv`。

## 参考质量敏感性

- historical_all__all_strict_geometry：770 条/41 图/11 building/24 人；task-equal mean=0.8909。
- historical_all__legacy_independent_only：770 条/41 图/11 building/24 人；task-equal mean=0.8909。
- historical_all__exclude_confirmed_only：770 条/41 图/11 building/24 人；task-equal mean=0.8909。
- current_available20__all_strict_geometry：692 条/41 图/11 building/20 人；task-equal mean=0.8885。
- current_available20__legacy_independent_only：692 条/41 图/11 building/20 人；task-equal mean=0.8885。

这里沿用旧 eligibility，目的是审计旧结论；GT 只是测量参考，不是无条件真值。reference readiness、scope、independence 与 missingness 是四个分开的字段。

## 人—人、人—模型、模型—模型

- `human_human_different_worker_same_stage`：21892 对，191 图，22 building，D_mask 中位数 0.0774。
- `human_human_cross_stage`：76 对，18 图，7 building，D_mask 中位数 0.0816。
- `human_gt`：2104 对，180 图，22 building，D_mask 中位数 0.0697。
- `human_hohonet`：2427 对，214 图，22 building，D_mask 中位数 0.0942。
- `human_bilayout_enclosed`：2403 对，213 图，22 building，D_mask 中位数 0.0831。
- `human_bilayout_extended`：2419 对，213 图，22 building，D_mask 中位数 0.0912。
- `hohonet_bilayout_enclosed`：213 对，213 图，22 building，D_mask 中位数 0.0576。
- `hohonet_bilayout_extended`：213 对，213 图，22 building，D_mask 中位数 0.0562。

`D_mask = 1 - IoU` 使用 1024×512 周期横向、线性插值的图像平面 mask proxy，与仓库既有 `quality_core` 实现逐点等价检查通过；它不是球面几何距离。全量高支持聚类已传递 pointwise correspondence compatibility；42 个旧 P1/C1 Manual 图在 full support、structure status、cluster count、second support 和按 worker 规范化的完整分区上与旧原生引擎 42/42 一致。enclosed/extended 分开报告，不挑选更有利的一支。building 证据见 `building_evidence.csv`，所有 comparison 明细见 `geometry_comparisons.csv`。

## 纯手工 / 纯机器 / 机标人校的现有覆盖

- C1 / manual：674 条，87 图，历史实际 proposal 图 25，HoHo/Bi 双头文件覆盖 87/87。
- C1 / semi：106 条，25 图，历史实际 proposal 图 25，HoHo/Bi 双头文件覆盖 25/25。
- C2-A-RP / manual：80 条，42 图，历史实际 proposal 图 0，HoHo/Bi 双头文件覆盖 42/42。
- C2-B / manual：160 条，46 图，历史实际 proposal 图 0，HoHo/Bi 双头文件覆盖 46/46。
- P1 / manual：779 条，30 图，历史实际 proposal 图 0，HoHo/Bi 双头文件覆盖 30/30。
- P1 / semi：468 条，18 图，历史实际 proposal 图 18，HoHo/Bi 双头文件覆盖 18/18。
- ALL / manual：1693 条，187 图，历史实际 proposal 图 25，HoHo/Bi 双头文件覆盖 187/187。
- ALL / semi：574 条，43 图，历史实际 proposal 图 43，HoHo/Bi 双头文件覆盖 43/43。

- C1 Manual∩Semi：25 图/9 building；同 worker×同 image 跨条件配对 2 条、2 图。
- C2-A-RP Manual∩Semi：0 图/0 building；同 worker×同 image 跨条件配对 0 条、0 图。
- C2-B Manual∩Semi：0 图/0 building；同 worker×同 image 跨条件配对 0 条、0 图。
- P1 Manual∩Semi：0 图/0 building；同 worker×同 image 跨条件配对 0 条、0 图。

这里的 Semi 是历史“机标人校”；P1 Manual 与 Semi 若无同图交集就不能当直接对照，C1 同图重叠也只作描述。历史 actual proposal 的来源和响应由 `proposal_fact.csv` / `proposal_response.csv` 追溯；HoHoNet ep300 与 BiLayout 双头是新的离线纯机器候选，不冒充当时展示给工人的 proposal。本审计只做宏观统计，不冻结三路径实验，也不新跑训练。

## 支持与不支持

- 支持：源底座可语义重现；独立性处置会改变有效支持与恢复曲线；人—机差异必须按模型分支、图与 building 报告。
- 不支持：固定 H/L/U 人格类型、`7/8/7`、把稳定 U 当子类、把 full-roster 自恢复当质量 ceiling、把公共 GT 当绝对正确、或从这些有限 roster 曲线宣称总体平台期。历史回放含 26 名历史 worker，不能称为“当前 20 人结果”；用户已确认当前可用 20 人名单，该名单只用于明确命名的资源敏感性补充。
- 旧 Semi proposal response 只解释当时辅助提案响应；本次 HoHoNet/BiLayout 是离线对照，不能倒推历史因果效应。
- 若未来能招募新人，可预先冻结跨场景收敛验证；未来招募不确定只限制当前承诺，不等于禁止该验证。

## 审计边界

这是 audit-only 产物，不改变协议、schema、routing、SOP、raw truth 或运行时 Label Studio。C2 当前关闭状态不是本报告研究结论的一部分。输出使用实值分母，缺失与无法解析均保留，详细断言见 `QA.json`。
