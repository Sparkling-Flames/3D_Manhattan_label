# 自然进入顺序的几何波动与抽样精度

## 估计对象

固定一张图的正式人员池、人数 k，随机均匀抽取两个相互独立的 k 人团队。几何主量是两次有效完整底面输出之间的 `1−IoU` 的期望，记 V；它刻画换成员时底面输出的波动，不是与 GT 的误差。另保留质心距离、平均高度差、实际转折数差及节点数差。距离、完整底面资格和高度/转折量沿用已保存的冻结结果。

随机路径在给定 k 处诱导均匀的 k 人子集。R 条路径的 V 使用所有不同路径对的均值；两条路径偶然选择同一成员集时保留两条路径权重，距离贡献0。排除的仅是同一条路径与自身配对。不能先把出现过的团队去重后对团队等权，否则改变自然抽样分布。

若实际枚举了全部 M 个合法团队，精确有限总体的独立双抽样分母是 M²，包含同队自配的0距离；不能以 M(M−1)把目标变为“强制选择两个不同团队”。这一精确枚举分支与随机路径 U 统计分别标识。旧小池全排列的历史汇总仍保留原定义。

## 抽样误差

程序对每条完整进入路径做一次删除，重新计算该图所有人数处的 V。由这些删除值计算 jackknife 蒙特卡洛标准误。区间变化使用同一条路径在两个 k 处的删除值之差，因此保留进入过程的配对关系，不把前后端独立重抽。这个标准误衡量固定图片与固定人员池中的随机顺序抽样误差。

原答/端点失败不会被填为0距离。每个指标保留全部尝试路径、有效路径、有效配对数；删除无有效底面的路径时，条件有效底面的均值不变。不到2条有效路径时 V 缺失；只有2条时不能估计删除一条后的 jackknife 标准误，即使观察到的距离为0，标准误也保持缺失。缺失新增端点另存 `GEOMETRY_UNCOMPUTED_LINKS.csv.gz`，不作为融合失败。

图片等权总体均值的蒙特卡洛方差，是各图标准误平方之和除以图片数平方；这依赖各池独立的随机种子。输出同时保留图间标准差、建筑均值标准差和建筑等权估计。后两者是场景差异，不能与路径抽样误差混为同一置信区间。展示的 `1.96×MCSE` 是局部近似半宽，不是新建筑预测区间。

满员处全部顺序使用同一个成员集合：若该完整底面有效，V及其顺序抽样误差均为0；若满员失败，V缺失。这个零表示该有限池已经没有可换成员的空间，不表示对参考正确。

## 原 24 重新汇总：保留阶段 01 的基线记录

本节保留追加计算前的原 24 诊断，方便核对。本轮 194 池新增顺序已全部完成，最终实测判断及旧、新共同支持比较见 `GEOMETRY_FINDINGS_ZH.md`；本节不再代表尚未完成的工作状态。

程序已实际计算普通177图与门洞17图全部已有自然前缀：30,480个图×人数×指标结果。与保存的旧几何表回连，30,390个共同有效值最大绝对差 `8.88e−16`，缺失状态完全相同。没有调用融合、评分或分类。

固定 N≥30 的普通 Manual 157图，V_floor 在 k3/k20/k30 为 0.12215/0.03652/0.01601；相应总体蒙特卡洛95%近似半宽为0.00283/0.00161/0.00098。原来关于总体成员波动随人数降低的主要发现，量级远大于这类抽样误差。

同一固定157图中，3→6、6→10、10→20、20→30 的 V 平均变化分别为 −0.04307、−0.01890、−0.02366、−0.02050；配对近似半宽分别为0.00302、0.00197、0.00215、0.00190。下降图数分别157/157、155/157、155/157、156/157。这些数字只取原顺序；独立新 24 和合并 48 的实测结果已另存 `results/GEOMETRY_FIXED157_INTERVAL_MAIN.csv`，主要判断保持。

单图精度差异更大。困难27图在 k3 的单图MCSE中位为0.02210、P90为0.05443；门洞17图在 k3 的单图MCSE中位为0.05730。门洞总体 k3 V 为0.43456，总体近似半宽0.02866。24条支持总体大幅缩波，但对具体困难/门洞图片的细小几何变化，仍有增加独立顺序的价值。

完整逐图表和同路径人数变化表分别为 `results/GEOMETRY_PATH_PRECISION.csv.gz` 与 `GEOMETRY_PAIRED_INTERVAL_PRECISION.csv.gz`，现已同时包含 old24、新24、合并48及重点96。固定图片及难度汇总为 `GEOMETRY_CURVE_MC_SUMMARY.csv` 与 `GEOMETRY_INTERVAL_MC_SUMMARY.csv`。独立新旧批次提供随机顺序的重复检查；它们仍使用相同图片和人员池，不是新图片或新建筑的外部验证。

## 运行

从专题 `analysis_geometry/` 运行。先按根目录 `REPRODUCE_ZH.md` 将 `HOHONET_POPULATION_ROOT` 设置为固定提交的原人口研究目录的绝对路径；不要在本轮目录内重复复制仓库。

```bash
python geometry_sampling_precision.py \
  --base "$HOHONET_POPULATION_ROOT" \
  --out results --prepare
python geometry_sampling_precision.py \
  --base "$HOHONET_POPULATION_ROOT" \
  --out results --jobs 3
python summarize_geometry_precision.py --results results \
  --source-base "$HOHONET_POPULATION_ROOT"
```

`--prepare` 生成可重建的逐池临时几何缓存；它不需要随交付重复打包。新增精确连接表可用 `--new-orders` 指向，实际新端点根目录可用重复的 `--new-endpoints-dir` 传入。该程序兼容每池 `part_*.scalars.csv.gz` 与 `part_*.geometry_state.jsonl.gz`；只读实际已落盘端点。

最终交付的轻量路线优先读取新端点目录中的 `NEW_ENDPOINT_SCALARS.csv.gz` 与 `NEW_ENDPOINT_GEOMETRY_COMPACT.jsonl.gz`，按 `team_key` 一次接合后形成可重建的逐池临时缓存。它无需下载可选的全部身份组/投票 `full_state` 分片。旧端点仍从本次固定main的标量与52.7MB几何源恢复。`old_pool_geometry_cache`、`new_compact_pool_geometry_cache`、`combined_pool_geometry_cache` 均是临时派生物，不属于需要重复交付的研究输入。

本轮完整新增数据的复算命令：

```bash
python geometry_sampling_precision.py \
  --base "$HOHONET_POPULATION_ROOT" \
  --out results --new-orders ../design/NEW_PREFIX_TEAM_LINKS.csv.gz \
  --new-endpoints-dir ../new_endpoints --jobs 3
python exact_geometry_margins.py \
  --design ../design/EXACT_MARGINAL_TEAM_DESIGN.csv.gz \
  --geometry-results results --new-endpoints-dir ../new_endpoints --jobs 3
python summarize_geometry_precision.py --results results \
  --source-base "$HOHONET_POPULATION_ROOT"
python export_geometry_main_tables.py --results results
python plot_geometry_precision.py --results results --out figures
```

原图之外的VFua机制图可仅凭小案例数据重画，无需仓库或可选大状态包：

```bash
python render_saved_vfua_case.py \
  --data case_VFua_04/VFUA_MECHANISM_GEOMETRY.json.gz \
  --out case_VFua_04/VFUA_LEAVE_ONE_OUT_BEV_redraw
```

三份有限边际小表整理及完整VFua案例重建入口均支持 `--population-root`，也支持 `HOHONET_POPULATION_ROOT`。未显式指定时，先识别最终仓库布局中本轮目录的父级人口研究目录，最后才兼容旧工作区的 `STUDY/repo/research/...` 布局；显式路径错误会直接报告，不会静默改用其它输入。

```bash
python summarize_wc2_p10_weights.py --study .. \
  --population-root "$HOHONET_POPULATION_ROOT" --out case_WC2_46_P10
python summarize_rare_success_support.py --study .. \
  --population-root "$HOHONET_POPULATION_ROOT" --out case_missed_failure
python find_missed_leave_one_out_failure.py --study .. \
  --population-root "$HOHONET_POPULATION_ROOT" --out case_missed_failure
```

`build_vfua_leave_one_out_case.py` 使用同一定位参数。它从原答/原端点与完整身份状态重建案例，需要先执行本节 `--prepare`，并取得对应P03状态；仅重画已保存案例图仍采用前述 `render_saved_vfua_case.py`，不需要这些大输入。若没有未打包的逐池处理中间表，完整重建会改读已交付的 `results/GEOMETRY_PATH_PRECISION.csv.gz` 对应池和人数行；不需要恢复逐池检查点。
