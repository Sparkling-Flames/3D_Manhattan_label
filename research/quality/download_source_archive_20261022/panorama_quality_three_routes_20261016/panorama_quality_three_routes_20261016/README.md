# 全景布局质量：三条独立研究路线（GQS-20261016-v2）

建议先读`REPORT.zh.md`，公式见`MATHEMATICS.md`。QA为对应夹角+弱结构辅助，QB为转角函数形状，QC为连续边界距离/法向。推荐QA进入下一轮工作试验，QB保留实质竞争；当前QC不作主分。未覆盖正式账本，未声称新总分整体击败B8L2。

## 实际材料边界

当前891份与历史1145份的旧公式分别复核。新几何重算244份/34图/22人，全部Manual；固定当前参考及来源池至少3人规则。此处244只是当前891中的可恢复几何子集，不是新增完整891结果。

未取得GitHub release原图和LFS真实文件；未成功重跑当前统一loader；无新原图视觉裁决。`frozen_repo`保留附件内必要真实快照和账本，不含虚构补全；`geometry_gallery.html`展示显式几何重建，不是原图。原始/新任务参考仍按冻结规则排除，缺失不补零。N01/N11参考身份别名单列，不混入严格20例人工比较。

## 阅读与运行

Python及依赖见`ENVIRONMENT.json`/`requirements.txt`。已在新目录完整重跑，244份及93控制的QA/QB/QC与交付分数最大误差0。35项单元/合同测试通过；这些只证明有限数值性质，不证明人类测量有效性。

```
python -m pip install -r requirements.txt
python reproduce.py --out /tmp/gqs_replay --full
```

输出目录必须不存在；脚本复制输入，在新目录恢复当前244份、跑三方案/控制/消融/测试/敏感性，不覆盖交付结果。路径及身份遵循所附快照；重跑不需要网络、GPU、原图或当前loader，但也不能据此声称完成loader端到端核验。

直接对冻结授权清单打分：

```
python src/score_manifest.py --manifest RUN_MANIFEST.json --out my_scores.csv
python src/compare_versions.py --left my_scores.csv --right another_version.csv --out comparison.csv
```

更换参数须同时创建新config、更新清单config哈希并命名新版本。增加人或图须用新的资格/参考目录与清单，不把当前244自动扩为其他记录。比较器只对作答、参考、目标、几何及资格身份一致的行给差分；改参考/改资格单列。它不按分数匹配参考，也不因为两个参考几何接近就自动视为同一目标。

`results/current244_scores.csv`包含新三分与WQ/A10/B8L2/同参考旧棱柱IoU对照；`results/component_ablation244.csv`分解夹角、结构、高度及重新添加冻结Sb的响应；`results/synthetic_scores.csv`是机制控制；`results/ordinal_descriptive.csv`是曝光粗档的描述性反序；`results/ROBUSTNESS_SUMMARY.json`和`REPLAY_SUMMARY.json`记录实际执行范围。

`src/geomscore_seed_v1.py`及seed结果保留探索前版本；`legacy/`为上一轮RCS/旧分对照，不是本轮推荐实现。完整信源及核验边界见`REFERENCES.md`。
