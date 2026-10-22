# 旧 n20 失败净差：独立复算与本地修复

日期：2026-10-23。范围仅为 `exchanges/compare_legacy_n20.py` 及其旧 n20 六份结果表；无新增融合、评分或分类拟合。

## 问题与正确口径

原脚本将 `net_failure_difference` 与 Q、几何等指标一起按 `all_scored` 筛选。失败事件因此被置空，剩余事件三队均未失败，导致条件汇总失败净差被错误写成零。

原事件生成器 `event_kernel.py` 将每队失败定义为 `not complete_evaluable`。本次沿用保存的 A/B/C 布尔失败列，逐事件计算 `C_failure − B_failure`，不重新解释失败原因，也不把无效事件删除。汇总层次为：条件内事件按图片取均值，图片按建筑取均值，建筑等权取条件均值。分项 `m/r` 表沿用其原来的更细分组。

该指标单位为比例；乘 100 后为百分点。负值表示 C 的失败率低于 B，正值表示更高。它与三队 Q 共同可评分分母分开；时间仍使用原本的完整、同来源时间分母。

## 实际变化

- 完整事件 **271,331** 行，其中 **266,373** 行三队 Q 均可评分，**4,958** 行不能共同评分。
- 原失败净差缺失的 4,958 行全部恢复；其中 **2,489** 行实际为非零差值。A/B/C 失败次数分别为 **2,532 / 1,705 / 1,506**。
- 76 个父类固定×实际 m 条件中，**36 个**失败净差由错误的 0 修正为非零，18 个正向、18 个负向。其余 40 个仍为 0。
- Semi `SP_scale` 粗类 n20/m12：**−5.555556 个百分点**（43 事件、4 图、2 楼）。
- Semi `SP_scale` 粗类 n20/m9：**+4.000000 个百分点**（51 事件、4 图、2 楼）。
- 全部 76 个条件前后值见 [LEGACY_FAILURE_CONDITION_CHANGES.csv](LEGACY_FAILURE_CONDITION_CHANGES.csv)。

| 结果表 | 总行数 | 失败净差发生变化的行数 |
|---|---:|---:|
| EVENT_OUTCOMES | 271,331 | 4,958 |
| IMAGE_M_R_COMPARISON | 12,131 | 388 |
| BUILDING_M_R_COMPARISON | 4,668 | 359 |
| PARENT_FIXED_M_RESPONSE | 76 | 36 |
| IMAGE_PARENT_FIXED_M_RESPONSE | 2,500 | 93 |
| BUILDING_PARENT_FIXED_M_RESPONSE | 721 | 82 |

## 修复与验证

1. 原脚本、六份受影响数据表及原 README 已按原目录结构保存在 `original/exchanges/`；源 ZIP 没有修改。交付 manifest 继续描述原始交付，本修复记录描述本地后续变化。
2. 根因修复：Q 等指标继续使用原掩码，失败净差从全部事件的 C/B 失败列重建。
3. 新增 `--rebuild-delivered`，复用 `EXACT_EVENT_LINKS.csv.gz` 和 `EVENT_OUTCOMES.csv.gz`，通过同一汇总函数重建六表；不依赖未展开的历史宽表。使用浮点数 round-trip 读取，保留原记录中接近零的带符号均值。
4. 全六表逐列与备份比较：除失败净差外，Q、时间、几何、正向数量、支持分母及关联均保留。五表其它数值完全一致；76 条件表只有最多 **1.78×10⁻¹⁵** 的浮点差异，所有计数完全一致。
5. 另从布尔失败列独立按图片、建筑汇总，与全部 76 个修正条件一致；每张汇总表也满足 `net_failure_difference = C_failure − B_failure`，误差小于 10⁻¹²。
6. 两项定向测试通过：失败事件不得因 Q 无效而退出失败分母；事件量不等时仍按图片、建筑等权。完整检查数值见 [LEGACY_FAILURE_FIX_CHECKS.json](LEGACY_FAILURE_FIX_CHECKS.json)。

复现命令（仓库根目录）：

```text
.venv/Scripts/python.exe -X utf8 research/workers/personnel_mixture_comparison_20261022/exchanges/compare_legacy_n20.py --rebuild-delivered
.venv/Scripts/python.exe -m pytest tests/test_personnel_mixture_legacy_failure_20261023.py -q
```

本次没有重跑融合、原始几何评分、分类拟合或历史宽分片读取；核验对象为本轮实际交付的完整窄事件与关联。数据字段和协议均未改变，新增测试与本地修复记录由统筹线程一并登记；本修复不单独修改主报告、资料目录或项目地图。
