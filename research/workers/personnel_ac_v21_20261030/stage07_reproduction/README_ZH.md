# HOHONET v2.1 直接 AC 与整类替换复现说明

## 本包复现什么

本轮使用提交 `ec0973ad46fcfa64d3cdbedfeeef1fee180c4cff` 的 v2.1 原主目标与其它准入目标快照。
分类、楼外历史、原答资格、排除、目标归属、参考、正式难度和融合规则均冻结。
没有重做严格 ABC 九人或十人实验，没有重跑自然人数曲线，没有新增房间或人员。

`minimum_source/repo` 含 142 项实际所需源码与输入，总计 21,563,317 字节。
每项都已核对为上述提交的准确 Git blob；无需下载整个仓库才能复现一支团队。
原工作树和旧交付没有被覆盖。完整名单、抽样种子与精确队伍见容量和冻结设计包。

## 文件放置

将各阶段 ZIP 解压到同一个研究目录，保留包内的相对目录结构。
四个原生端点分包合起来恢复 `stage03_endpoints/pools`，其中每个池都有全部
`part_*.jsonl.gz`、`POOL_INPUT.json`、`CHECKS.json` 和重放一致性记录。
不同池代表不同图片、条件和合法目标，不能仅按图片名合并。

报告与分析使用原生分片，不依赖一份额外拼接的全量几何副本。
完整几何分片中的每条记录同时保存分数、状态、精确成员和原答 object ID。
运行目录曾生成 `stage03_endpoints/ENDPOINT_SCALARS.csv.gz` 便于筛选；交付不再重复打包这个可由分片重建的标量总拼接。
逐事件指标由两个分包恢复 `stage04_metrics/metric_shards`，258份逐池分片为正式完整来源。
不需要额外的 `EVENT_METRICS.csv.gz` 总拼接；原生几何分片同时保留端点标量、状态与身份。

## 运行环境

本次实际环境为 Python 3.12.14，NumPy 2.3.5、SciPy 1.17.0、Pandas 2.2.3、
Shapely 2.2.0、GEOS 3.14.1、Pillow 12.3.0。完整观察到的依赖版本见
`requirements-exact-observed.txt` 与 `ENGINE_AND_INPUT_CONTRACT.json`。
这是一份实际运行记录；不同软件版本下应重新检查数值一致性。

冻结模块内部仍有较早的 v2 与旧提交文字，它们是被当前入口继续调用的历史模块身份。
本轮入口明确使用当前 v2.1 池、参考与原答，并保存当前数据与提交身份；不要调用旧的
默认建池函数来替代本轮快照。

## 复现一支已经保存的团队

在研究目录运行以下命令，使用自己的 Python 环境和上述依赖。

```bash
python code/reproduce_one_team.py --team-key 已保存的team_key
```

不传 `--team-key` 时，程序选择字典序最早完成池中的首个可评分端点，仅用于检验
源码、评分和几何能否在独立导出树中运行，不作为新增研究样本。
本轮已实际完成这项验证：23 个数值字段、输出状态和完整几何均与保存端点一致，
最大数值差为 0。具体身份与结果见 `verification/REPRODUCTION_PARITY.json`。

## 在新目录重做冻结团队请求

原计划保留运行时的绝对路径。先复制计划并只调整路径：

```bash
python code/relocate_frozen_plan.py
```

脚本不覆盖原计划。它核对所有源码、池和请求字节，保持成员、参考、运行版本、
复用状态及 engine digest 不变，只调整研究目录中的四个路径字段。

随后可以把输出指向一个新的目录，重做原先登记的请求：

```bash
python stage02_engine/code/ac_endpoint_runtime.py run \
  --repo stage07_reproduction/minimum_source/repo \
  --plan stage07_reproduction/relocated_plan \
  --output reproduced_endpoints --jobs 7
```

已经登记为完整复用的端点由计划中的 `reused_full` 恢复；已有标量而缺几何的团队
会重放并核对原数值；其余团队按相同冻结规则计算。三种来源状态分别保存。
输出可中断续算，每个池的精确身份和输入哈希必须一致。

## 重新测量和汇总

测量无需再融合。使用完整端点目录、两份快照和冻结事件表运行：

```bash
python stage02_engine/code/ac_measure_events.py \
  --repo stage07_reproduction/minimum_source/repo \
  --events stage01_registered/AC_EVENTS.csv.gz \
  --endpoints stage03_endpoints \
  --pools stage07_reproduction/minimum_source/repo/research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json \
          stage07_reproduction/minimum_source/repo/research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json \
  --target-conditions stage07_reproduction/minimum_source/repo/research/workers/personnel_v21_reselection_20261029/targets/POOL_TARGET_CONDITIONS.csv \
  --out reproduced_metrics --shards-only
```

`code/summarize_ac_effects.py` 从逐池事件指标计算主效应；
`stage05_sensitivity/code` 计算成员、背景、扩块、整类分解与完整联盟；
`stage05_funnel_bridge/code` 保存容量漏斗、输出状态以及与旧严格 ABC 的共同条件对照。
分析的完整命令和输入记录分别保存在各阶段代码与回执中。

## 读数时的必要区分

质量差使用 C 减 A；正值对 B8L2 与 D10 表示上升，但结构、面积、高度、劳动的正值
只表示数值增加。平均绝对变化来自逐事件绝对值，不能以平均有符号变化的绝对值替代。
缺失 Q 不填 0；未形成完整输出、未形成可用点序列、无有效底面、测量异常及参考限制分别保留。
legacy `no_connection` 可能源于完整来源环缺失或入选节点位置未决，不能仅凭该状态名解释为纯连接失败；具体案例使用完整状态判断。

底面 BEV 距离是 `1 − IoU`，无量纲。质心距离单位为相机高度 h，面积为 h²，角度为度。
劳动量是原有标注记录，比较时控制记录来源；它不是本次程序运行耗时。

方法事件、设计链接、无向物理端点对和独立团队数是不同计数。反向展示不是第二次实验。
没有 B 队的直接 AC 不能直接估计“跨类比同类更大”；旧严格 ABC 的同类 B、原方向和
互斥关系独立保存。共同 n/m 的对照仍需检查实际成员和共同背景是否相同。

## 存储与恢复记录

本轮曾发现新生成 CSV 的 gzip 尾部不完整，并在执行闸门前修复、重新全量读取验证；
这些不是科学规则变更。还曾因 Git 未完成临时传输文件占满磁盘而初始化中断，
确认临时包无索引、无进程或文件句柄占用后，只删除该可再生临时文件并原路径续算。
当时没有新增原生融合结果，该资源错误不计入融合失败。
具体记录见设计阶段的可读性回执与 `stage02_engine/DISK_RECOVERY_RECEIPT.json`。

全部交付 ZIP 均逐文件读取验证；gzip 数据同时读到尾部并核对 CRC，CSV 检查完整行宽，
JSON/JSONL 完整解析。每个包的 SHA-256 与内部文件清单随包保存。
