# 当前 DSTRUCT AC 机制交付目录

先打开 **[中文机制报告](REPORT_ZH.md)** 或 **[离线交互图册](CURRENT_DSTRUCT_AC_ATLAS.html)**。图册单文件包含12个当前AC案例、12张不变原图（其中1张仅供既有ABC附录）、全部相关人员完整原答、当前楼外标签、合法记录劳动、原生对应组/票账/来源环、D观察跨队映射与参考。无需联网。原图和机器可读数据也单独保留，方便审计和进一步分析。

本模块对应 `Sparkling-Flames/3D_Manhattan_label` main `48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b`。解压时保留目录 `research/workers/current_dstruct_ac_final_20261104/mechanisms/`，可放入 `D:/Work/HOHONET`。不依赖本次临时工作路径或本机全仓库树索引。

## 文件用途

| 文件/目录 | 内容 |
| --- | --- |
| `DIAGNOSTIC_SAMPLE_PROTOCOL.json` / `DIAGNOSTIC_SAMPLE.csv.gz` | 不看效果的248对冻结选择协议、清单和哈希 |
| `DIAGNOSTIC_PAIR_RESULTS.csv.gz` | 每物理对全部机制、几何与状态诊断 |
| `D_OBSERVATION_ANCHOR_LINKS.csv.gz` | 原答ID+角点索引的稳定/歧义跨队映射 |
| `MECHANISM_QUALITY_ASSOCIATIONS.csv` | 图内先汇总、图片等权的机制关联，含图片/建筑/物理对分母 |
| `MECHANISM_DIFFICULTY_ASSOCIATIONS.csv` | 按难度、类别对分层，含≥5/≥10分支持和建筑聚类区间 |
| `ANCHOR_MAPPING_COVERAGE.csv` | 无法稳定映射的节点/端点/物理对数量 |
| `CASE_SELECTION_PROTOCOL.md` / `CASE_SELECTION.csv` | 后验例证覆盖规则和12例冻结选择 |
| `CASE_METRIC_EVIDENCE.csv` / `CASE_NATIVE_MECHANISMS.csv` | 每例完整主要分项及原生机制 |
| `CASE_APPROVED_MANUAL_ORDER_MATCH.csv` | 24端点对57批准人工端点的精确身份交集，均未命中 |
| `cases/AC01.json.gz` … `AC12.json.gz` | 每例全数据；A/C核心几何和评分仍为原保存值 |
| `cases/APPENDIX_EXISTING_ABC.json.gz` | 第12批既有ABC的原保存几何与GS来源；不计入本轮样本 |
| `tables/` | 全部候选组、每一支持者、来源顺序、边/环、D观察链接等扁平表 |
| `trace_endpoints/` | 508个历史既有端点及经过一致性验收的原生full_state |
| `source/SAVED_LEGACY_ENDPOINTS.jsonl.gz` | 508个未附诊断的原保存科学端点 |
| `source/SAVED_LEGACY_ENDPOINT_ORIGINS.csv` | 每端点原repo分片路径、行号、Git blob及SHA256 |
| `source/DIAGNOSTIC_POOLS.json.gz` | 相关冻结输入池、完整预处理原答和精确参考 |
| `source/RECOVERY_SOURCE_PART_INDEX.json` | 所需池的有界源树索引；可从固定提交恢复分片 |
| `originals/` | 原尺寸PNG字节，按Release成员CRC核验 |
| `figures/` | 12例完整原图/底面板、机制/难度关联、局部投影图和既有ABC图 |
| `*_RECEIPT.json` / `*_CHECKS.json` | 样本、来源、重放、原图、图册与最终验收记录 |

## 安装

建议使用 Python 3.11 或 3.12；绘图与从保存诊断重新汇总的依赖可安装为：

```powershell
cd D:/Work/HOHONET
python -m pip install numpy pandas scipy shapely matplotlib pillow fonttools
```

原生重放使用仓库既有引擎，需保留该 main 提交的对应代码与其原有依赖/资料。**只重新汇总、检查数据、查看图册和绘图，不必调用原生融合引擎。** 所有路径以代码所在仓库根自动解析，不依赖当前命令行工作目录；示例为了易读从仓库根运行。

## 从已交付诊断数据重新汇总

```powershell
python research/workers/current_dstruct_ac_final_20261104/mechanisms/code/analyze_diagnostic_sample.py
```

该命令不进行融合或评分，只读取冻结样本、池和已验收full_state，核对D成员与观察身份，重新生成逐对表、跨队映射、图片优先汇总、难度分层与建筑聚类区间。

不要在看过结果后改样本清单或种子来替换病例。`freeze_diagnostic_sample.py` 和 `select_cases.py` 提供原选择规则，冻结清单的顺序/身份若改变会触发断言。案例是事后解释，不用于估计总体发生率。

## 重新核验原生诊断（可选、全部仍是旧团队）

交付已包含保存端点与508个原生full_state。若需独立重新运行原生代码：

```powershell
python research/workers/current_dstruct_ac_final_20261104/mechanisms/code/replay_native_traces.py --jobs 4 --force
python research/workers/current_dstruct_ac_final_20261104/mechanisms/code/replay_native_traces.py --selection research/workers/current_dstruct_ac_final_20261104/mechanisms/CASE_SELECTION.csv --jobs 4 --force
```

重放原有固定团队，不新增比较队伍。每个输出必须保持原保存评分、状态、ERP坐标、组身份及连接拓扑，随后附加诊断；正式原值仍保留。去掉 `--force` 则优先复用已验收trace缓存。仓库正式 `INPUT_SNAPSHOT.json` 存在时先核对它；否则可使用本交付中相同的冻结子集。

若压缩端点缓存丢失，可按原分片身份恢复：

```powershell
python research/workers/current_dstruct_ac_final_20261104/mechanisms/code/recover_saved_endpoints.py
python research/workers/current_dstruct_ac_final_20261104/mechanisms/code/recover_saved_endpoints.py --selection research/workers/current_dstruct_ac_final_20261104/mechanisms/CASE_SELECTION.csv
```

恢复先用交付的每端点精确来源清单，不要求临时环境的 `FILE_INDEX.json`。下载的是固定提交源分片，核验Git blob和完整team key。原请求计划预测只作为缺少精确来源的后备路径。

## 重建案例与图册

主交付的当前合法主分析表和记录劳动索引就绪后，可重新绑定案例：

```powershell
python research/workers/current_dstruct_ac_final_20261104/mechanisms/code/build_case_evidence.py
python research/workers/current_dstruct_ac_final_20261104/mechanisms/code/fetch_case_originals.py
python research/workers/current_dstruct_ac_final_20261104/mechanisms/code/render_mechanisms.py --font C:/Windows/Fonts/msyh.ttc
python research/workers/current_dstruct_ac_final_20261104/mechanisms/code/build_mechanism_atlas.py
```

`fetch_case_originals.py` 使用已交付的Release成员索引，优先检查现有完整PNG；缺失时只请求相应ZIP成员的字节区间，不下载全图库。渲染可用 `--font` 或环境变量 `HOHONET_CJK_FONT` 指向中文字体，也会寻找常见Windows/Linux字体。交付图册已嵌入Noto的中文子集字体；字体许可证见 `source/FONT_LICENSE.txt`。原始PNG字节保持不变，科学覆盖层来自冻结坐标。

图册的交互包括逐人完整原答、只显示D、只显示X/Z、原参考、所有候选组、局部D锚点放大、全票账、来源顺序和单例JSON下载。CSV.gz/JSON.gz可直接用Pandas/gzip读取。

## 检验口径

Q变化要求A和C原自动Q均存在；没有Q不填0。状态表保留失败。机制样本124对/预算，图片优先汇总；“≥10分对数”与图片数分开。D混合类别合法；跨队组只有同一非空D原答观察集合才作为稳定锚点。未检测到跨票不等于歧义部分没有机制。反方向差值取负，物理对不重复计数。

记录劳动只采用本轮主分析的合法同源记录与共同支持。它不等于人工连接劳动、融合CPU时间、完整研究成本或共识收敛时间。图册原生full_state和原端点仍保存旧时间字段供溯源，但显示/比较优先采用 `current_metrics` 与 `current_record_labor`。

本轮机制关联与12例都是原自动结果。全部24个案例端点精确核查未命中57个批准人工结果；尤其AC11不自行添加连接。另附的ABC只引用第12批，既不重跑也不加入本轮样本分母。
