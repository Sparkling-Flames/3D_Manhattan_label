# 复现与恢复说明

## 1. 固定输入与目录

本研究的数据基线为 https://github.com/Sparkling-Flames/3D_Manhattan_label 的 main 提交 `51b519f943b2dd3a4fb2f0198133ac5dd17209ab`。复现时先取得该提交，再将交付包中的本研究目录放入 `research/workers/personnel_global_composition_20261021/`。旧输入按仓库路径引用，不重复放进便携包。`INPUT_REFERENCES.csv` 列出所引用核心输入及本次取得文件的 SHA256；各子研究冻结回执另保留更具体的训练及运行输入。

最终报告为 `report/REPORT_ZH.md`，同名主题的 PDF 和独立 HTML 均由该文件生成。HTML 内嵌所需图片，离线打开即可阅读。各主题的代码、标签、构成实验和机制图分别在自己的目录中；同房研究没有合并进本包。

## 2. 本次环境与冻结合同

本次 Python 3.12.14，NumPy 2.3.5、Pandas 2.2.3、SciPy 1.17.0、scikit-learn 1.8.0、Shapely 2.2.0、Matplotlib 3.10.8、Pillow 12.3.0、ReportLab 4.4.9、fontTools 4.61.1。运行使用最多六个原生融合进程，每个进程的 BLAS/OMP/MKL 线程设为一；程序自身设置这些限制。`requirements_research.txt` 记录本次版本，不包含虚拟环境。

评分、参考资格、原答环序、人员及任务筛除、原生观察对应、MV50投票、定位和连接都使用上述提交中的原函数。主评分为 B8L2，D10 作敏感性。融合内部 `WORKING_GAP=7.5`，投票门槛 `ceil(n/2)`；整份原答的 9°/12° 分簇不是这个参数。本研究新增的距离、边界范围与高度代理仅作诊断，不回写融合或评分。

## 3. 标签与旧研究覆盖

从仓库根目录运行：

```bash
python research/workers/personnel_global_composition_20261021/coverage/build_coverage.py
python research/workers/personnel_global_composition_20261021/multivariate/build_multivariate.py
python research/workers/personnel_global_composition_20261021/multivariate/same_source_sensitivity.py
python research/workers/personnel_global_composition_20261021/multivariate/export_readable_labels.py
```

`multivariate/FREEZE.json`、`SAME_SOURCE_FREEZE.json`、`CLASSIFICATION_FITS.json` 和域缩放表保存机会门槛、域权重、训练折、人员、参数和输入哈希。目标建筑评价使用其楼外标签；全数据展示标签另表保存。Rnew2/F01沿用原10楼训练、另12楼目标身份，不重拟合为22楼LOBO。`integration/` 把独立方法接入同一个字段接口，并没有创造统一人员类型树。

## 4. 精确团队请求与原生融合恢复

正式复现消费已经交付的最终请求，不重新抽成员：

```bash
python research/workers/personnel_global_composition_20261021/composition/global_study.py inventory
python research/workers/personnel_global_composition_20261021/composition/recover_historical_keys.py
python research/workers/personnel_global_composition_20261021/composition/run_endpoints.py --jobs 6
python research/workers/personnel_global_composition_20261021/composition/geometry_events.py
python research/workers/personnel_global_composition_20261021/composition/build_coverage.py
python research/workers/personnel_global_composition_20261021/composition/finalize_hash_index.py
```

`ENDPOINT_REQUESTS.json.gz` 保存最终每个实际成员集合；`CONFIG_MEMBERSHIP.csv.gz` 保存人数向量与成员集合的连接；`ABC_EVENTS.csv.gz` 保存共同背景S、移出X、同构成Y、改构成Z、三队键及每条边真实换人数。三个表角色不同，不能用配置计数冒充成员覆盖。

程序按池原子写入检查点，每500个新增终点落盘，重启复用既有键。`ENDPOINT_SHARD_INDEX.csv` 保存逐池输入哈希、原生输出语义哈希、标量哈希和恢复路径。便携包不包含全部原生几何大缓存；缺失时按精确请求和原函数恢复。`TEAMS_SCALARS.csv.gz` 已包含全部最终标量，通常的汇总和读表不需要重算融合。

旧13个大请求依原生成器恢复，恢复请求文件的压缩SHA256与旧审计一致。恢复请求身份本身不运行融合。旧集合已算过但完整几何无法取得的情况标记为恢复，不能算成新的独立集合发现。历史大请求、历史重复缓存及本轮 `runtime/` 不放进便携包。

设计生成代码供核对使用。不要在完成计算的输出目录直接重跑 `prepare_design.py` 覆盖最终请求；如需验证抽样生成过程，使用隔离副本，依次核对原预算、V2最大容量补全和V3机会补全的阶段哈希。正式研究复现无需再次执行设计搜索。

## 5. 不重算融合的分析

```bash
python research/workers/personnel_global_composition_20261021/analysis/check_new_expression.py
python research/workers/personnel_global_composition_20261021/analysis/analyze_global.py --part all
python research/workers/personnel_global_composition_20261021/analysis/last_two_paths.py
python research/workers/personnel_global_composition_20261021/analysis/team_continuous_check.py --deletions 1 2
python research/workers/personnel_global_composition_20261021/analysis/summarize_team_continuous_check.py
```

原答检查、ABC/配置结果、近全员成员层、跨楼连续对照和末两步顺序分别输出，避免把不同问题合成一个成功率。`team_continuous_check.py` 默认读最终合并标量，只取精确N−1/N−2层；本次运行读取的不可变阶段快照哈希写入其合同。后续附加的配置与ABC集合不会改变该层。

类内、类间全部近全员配对矩使用有限集合的精确求和公式，并按实际m=1/2分开，不需要显式保存所有二次方配对。大块ABC严格对齐共同背景、n、m；两者是不同证据。细层增量有两项独立分析：在同一目标图持出实际成员集合，以及在外部目标建筑检查相对团队响应。后者不是未知图片绝对质量预测。

缺失Q不填零，类别未知不伪造一个自然类，失败不从分母删除。团队时间仅在全员有同口径时间时合计；报告来源秒数之和、理想并行活动代理、实际墙钟工期并非同一个量。目标图或建筑外的类成员选择不得使用该目标图质量。

## 6. 案例与原图

`evidence/README_ZH.md` 给出五例的精确图像ID、Release成员索引、原答和融合点、票账、成员、叠图及复现命令。三张原图由Release按ZIP成员索引抽取，文件长度、CRC和SHA256均记录。案例是结果后选取的解释材料，不代替全部尝试的成功/失败分母。

便携包保留这三张原图和五例必要几何，未打包原图全集。已取得案例的重新渲染不需要再运行融合；需要恢复完整票账时，只重放明确列出的已知集合，并核对冻结分数。`evidence/OBSERVATION_TRANSITIONS.csv` 分清门槛变化、共同观察重新分组与新增/移出观察。

## 7. 报告、摘要图与文件校验

```bash
python research/workers/personnel_global_composition_20261021/report/build_summary_figures.py
python research/workers/personnel_global_composition_20261021/report/render_report.py
```

字体是官方Noto Sans CJK的必要字符子集，附许可证及来源哈希；PDF中已嵌入，HTML使用系统中文字体。字体原始全集、环境、截图检查缓存不属于交付。

`DELIVERY_MANIFEST.csv` 给出交付路径、字节数和SHA256。ZIP内保留各阶段冻结身份、必要代码与结果；根报告、Manual/Semi逐人标签、26域覆盖、主要结果及逐事件小表另外提供独立文件。完整成员/顺序宇宙的未计算范围由 `composition/UNIVERSE_FINAL_COVERAGE.csv.gz` 逐行列明。本轮完成的有限层及注册事件均可独立复查，不把未展开的全空间写成已经完成。
