# 接续本轮所需的小输入

这里保存实际数据文件，避免轻量成果包只剩来源索引。23 个输入文件约 4.13 MB；不复制原图、完整端点缓存或重复仓库。

准确来源、SHA256、大小、行数和身份见 [`SOURCE_MANIFEST.csv`](SOURCE_MANIFEST.csv)。复制来源均为读取的 main `ef148c82df18582228b2d23837faa2659e79eba7` 已有文件，或本轮由其标签整理的逐折定义；底层真人数据为 v2。

| 目录 | 内容与用途 |
|---|---|
| `four_main/` | 四套重点方法的 ALL 描述标签、逐人中文解释、成员与历史中心；5,456 行楼外标签及本轮使用的逐折成员/中心 |
| `legacy/` | 旧 M、SP、A2、Rnew2、F01、多域等的原 ALL 成员与目标映射；26 域子集的原覆盖记录 |
| `cross_condition/` | 已完成的 XCOND_GEOM、XCOND_GEOM_QT、XCOND_PAIRED 的 ALL/楼外标签、中心、定义与原采用矩阵 |
| `references/` | 入场时的 11 家族采用登记，保留原研究阶段 |

ALL 用于整体描述。评价目标建筑时，四主类用相应 `heldout_building` 的标签；双条件标签同时排除目标建筑两种条件的历史，再分别评价 Manual/Semi。旧方法沿各行 `label_fit_scope` 和原阶段，尤其 F01 的冻结历史域不能重写成每折重新拟合。未知/机会不足不填成零或常规类。

大部分文件与来源字节完全一致。两份跨条件楼外 CSV 仅作 gzip 封装，解压内容与来源字节完全一致；清单同时保存源文件与输出文件哈希。这里没有重拟合、重新对齐类号、修改成员或改变资格。

`four_main/FOLD_CLASS_DEFINITIONS.csv` 为本轮配比分析的逐折定义，不能按类编号直接连接 ALL 名称；请使用同一方法、条件、楼外折、层级及对应历史中心。其来源文件位于已完成的 `configurations/`，来源身份在清单单列。

运行相邻 `integration/build_method_registry.py` 可按清单重建这些副本。团队成员、背景及端点关联沿本轮 `configurations/`、`exchanges/` 和 `direct_ac/`，此处不重复存几何。
