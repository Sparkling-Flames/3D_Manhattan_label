# 当前标签 AC 容量缺口：有限补充

本目录实际补算普通 Manual 原目标的 7 张图、4 栋建筑，共 22 个既有核心预算条件格：14/7 与 20/7 下合计 11 个 pool×类别对。范围由当前标签、逐成员合法性和真实容量确定，未按 Q、时间、GT 几何或想要的效果选图选人。

## 设计与身份

- 固定随机种子 **202611041301**，见 [DESIGN.json](DESIGN.json)。每格 32 个不同物理 AC 对；最多 16 组不同 X/Z，剩余人员中均匀抽共同背景 D。
- 某格只有 8 种 X/Z 时采用全部 8 种、每种 4 个 D；只有 1 种时使用该固定替换块的 32 个不同 D。没有重复人员去凑不存在的替换块。
- 共 **704 个 AC 对、1,408 支唯一团队**。反向显示是同一物理对调，不另外生成团队，也不算第二次独立验证。
- 新补充是缺口条件上的当前标签抽样；旧存量仍是筛选后的条件分析。合并图片范围不等同于全体图片重新均匀抽样。

原生评分、有效 shared-x 预处理、坐标、参考和分类均保持。端点中 `full_state` 保存全部原生身份组、成员观察、节点支持、已选节点和连接诊断。固定 n 的名义支持阈值为 ceil(n/2)，即 n14 为 7、n20 为 10。

## 实际执行

冻结团队在 18 个既有登记/端点来源、739,534 条登记键中精确查询，未找到已有端点；其中包括旧完整 AC 登记、当前 focused 缓存、相关既有选队登记、第 12 批、这七张图的自然路径以及 57 个批准人工辅助端点。查询明细见 [缓存清单](audit/CACHE_SOURCES.csv)。本轮没有为新增失败端点推断人工顺序。

1,408 个团队中 **1,388 个有正式 Q，20 个无连接**。它们全部保留；缺失 Q 不填零。实际计数、身份、几何和公式核验见 [最终验收](audit/FINAL_VALIDATION.json)。完整统计由上一级 `analysis/` 接续，本目录保存原始执行结果而不进行择优删样。

## 复现

在已有 HOHONET 仓库根目录安装本批覆盖文件，使用 Python 3.10+ 和项目原有依赖（numpy、pandas、scipy、shapely 等）。

```bash
python research/workers/current_dstruct_ac_final_20261104/supplement/validate_results.py
python research/workers/current_dstruct_ac_final_20261104/supplement/run_native.py --jobs 3
```

第一条只核验现存结果，不运行融合。第二条使用冻结请求和已有逐池检查点恢复执行，不重新选择团队；现有完整端点会被保留。脚本启动时查缓存、核验历史端点运行一致性，再仅运行缺失请求。如果重新替换来源后出现精确缓存命中，脚本要求先恢复该保存端点，防止静默重复计算。

`design.py` 是设计生成代码，但交付中已附冻结设计，默认拒绝覆盖 `DESIGN.json`。若需要独立重建，应复制本研究目录到另一个隔离目录，保留全部原始输入后移走**该副本**的设计与结果；不得在已采用目录中边看结果边重选。

关键文件：[事件](EVENTS.csv.gz)、[团队](REQUESTS.csv.gz)、[替换块与背景数](BLOCKS.csv.gz)、[缺口容量](MISSING_CAPACITY_CELLS.csv)、[完整池输入](inputs/SELECTED_POOLS.json.gz)、[端点分项](endpoints/ENDPOINT_SCALARS.csv.gz)、[完整几何](endpoints/ENDPOINT_GEOMETRY.csv.gz)、逐池完整原生端点 `endpoints/pools/`。
