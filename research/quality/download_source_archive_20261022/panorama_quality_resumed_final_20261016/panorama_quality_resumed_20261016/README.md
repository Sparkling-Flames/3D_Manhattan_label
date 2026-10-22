# 本轮完整交付入口

先读[结论与完整报告](REPORT.zh.md)，再看[24例原图派生对照](review.html)、[数学合同](MATHEMATICS.md)和[主比较逐例891行](results/SCORES_891.csv)。

本轮不是上一轮未交付实验的转述：已实际恢复原始loader、重算891固定参考作答、比较15个B版本和完整EBC候选，并在独立目录离线重跑。11个关键CSV字节一致，45项测试通过。覆盖与缺口见[运行总览](RUN_SUMMARY.json)和[失败边界](FAILURES_AND_LIMITS.json)。

推荐：原B8L2维持主线；D10作温和参数敏感性；EBC2-L2作完整竞争研究版本。没有宣布新模型全面优于基线，也没有把更高均分、难度排序或测试通过当作效度证明。

固定输入891份是已获准集合在v6下重新核验的结果，不是全部3152作答，也不包含2个尚未获准的新空间。32份条件门洞压力结果保持hold，不进入正式分母。没有更改原始作答、GT或main评分。

## 复现

```bash
python -m pip install -r requirements.txt
python reproduce.py --output /path/to/NEW_REPLAY
# 包装命令中断后，只在源文件/输入一致时允许接续
python reproduce.py --output /path/to/NEW_REPLAY --resume
```

数值复现使用完整、显式、带来源和哈希的派生几何清单，无需图片或网络。原始loader的实际执行验证见results/input_audit.json；从原始仓库重建输入需按src/prepare.py恢复同提交依赖和审核增量，不能只用preprocessed_source.json。

面向新增批次的逐行评分入口：src/score_manifest.py；固定目标/几何比较入口：src/compare_versions.py。复现目录与面向新清单的评分/比较入口拒绝覆盖已存在结果；内部阶段脚本应通过复现入口在新目录运行。算法参数与代码身份见MODEL_REGISTRY.json，包内文件哈希见FILE_HASHES.json。

## 主要目录

inputs：固定作答/参考、v6难度、原始评论、外部控制及参数设计。

src、vendor：本轮实现与冻结的真实基线代码，历史GQS实现单独标记。

results：逐例、全部候选、分层、控制、数值性质、资格、参考和重跑记录。

figures：原图派生叠线及BEV板；原图ZIP不再打包。

tests：45项实现与数据合同检查；不是人工有效性验证。

尚未完成：正式门洞细调、新两空间完整参考准入、独立新增数据验证和下游人员/融合/同房重放。
