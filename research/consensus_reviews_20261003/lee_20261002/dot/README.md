# Lee阶段1独立复审与有限人员池探索

先阅读“独立复审与探索.md”。本包针对固定提交b1ebab888fe8ac736548897f126a8bce7292c114的新Lee人数曲线，不以旧quality研究替代本轮目标。

## 目录

- lee-audit-original：从固定提交取得的有限源码、输入及公开结果；download_proofs.json记录Git blob校验
- lee-audit-inputs：原返回ZIP及原样提取内容
- lee-audit-repro：返回包复跑、独立交并多数核验、2000批原始抽样汇总与警告记账负对照
- lee-audit-recomputed与lee-audit-recomputed-old：两套依赖组合的完整12图重放结果
- lee-audit-helper：完整来源、输出及警告核查脚本和证据；保留原警告，不含依赖安装包
- lee-audit-exploration：4554个成员子集精算、全k解析面积期望、支持分歧与误差曲线
- lee-audit-inference：独立理论检查、177个足迹的共同星形条件及解释边界
- audit-oct2-original：仅附此前固定质量交接的results.json，供210个承接对象绑定复查；不是本轮主输入

本包不含原全景图、完整3152份原始加载链或真实身份映射。完整聊天正文未取得。没有进行真人盲评、GT视觉裁决、人员重新定级或远程改动。

## 环境

当前重放：Python 3.12.14、NumPy 2.3.5、Shapely 2.1.2、GEOS 3.13.1。其他依赖及测试环境见各分项记录。旧依赖对照另隔离使用NumPy 1.26.4、Shapely 2.0.4；不等于原作者Windows环境的逐项复制。

先在自己的隔离环境准备numpy、scipy、shapely、pandas、matplotlib和pytest；精确有理数理论检查仅使用Python标准库。不要把两套numpy/shapely安装进同一个运行环境。

## 主要运行入口

从本包根目录运行，建议先复制本包到新的工作目录，保留收到的原结果用于比较：

```sh
python -B lee-audit-inference/check_inference.py
python -B lee-audit-exploration/src/explore.py --input lee-audit-exploration/inputs/fixed_input.json --out fresh_exploration --published-summary lee-audit-original/analysis_results/lee_tile_stage1_20261002/summary.csv
python -B lee-audit-repro/independent_verify.py
```

完整原算法重放：

```sh
cd lee-audit-original
python -B -m pytest tests/test_lee_tile_stage1_20261002.py tests/test_supervisor_gt_sensitivity_20260922.py tests/test_consensus_contract_20260923.py -q -p no:cacheprovider
python -B -m tools.thesis_main.analysis.lee_tile_stage1_20261002 --out ../fresh_original_replay
cd ..
```

返回包的原算法复跑与9测试见lee-audit-repro/REPRODUCE.sh。路径保持本包结构即可；脚本中的可选依赖目录可由已安装的隔离环境替代。逐来源绑定及两套原算法输出比较见lee-audit-helper/compare_audit.py，其默认读取本包保存的输出目录。warning操作数复现应在旧依赖环境执行isolate_warnings.py；独立重建检查见check_warning_overlays.py。

## 如何解读成功

- 原算法10项测试与返回包9项测试是不同范围
- 5664前缀行、354摘要行、492参考版本解析行、166精确IoU切片不是独立真人样本数
- 195份输入中177份共识候选对应24位匿名人员，18份未参与但仍保留；不擅自改资格
- 小组全枚举，大组仅列出的1、2、N−2、N−1、N为精确IoU分布；所有k的线性面积量可解析精确计算
- 期望面积之比不是期望IoU；支持场分歧不是GT后验或人员能力
- 原97警告可在旧依赖组合复现，跨栈及独立运算路径数值核查未发现超出浮点量级的差异；不能外推所有未来警告无害
- 解析与几何误差、测试及未完成项分别存档。任何新环境差异都应重新核查，不应只看进程退出0

AUDIT_PACKAGE_HASHES.json记录本交付文件大小与SHA256，不覆盖未来重跑生成的新内容。
