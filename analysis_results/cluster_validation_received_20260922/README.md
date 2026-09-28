# 2026-09-22 分簇核验返回接收

先读[独立复核与采用意见](独立复核与采用意见.md)。主要数值可复现，纳入探索证据；当前算法、原始点、资格、采集计划及正式合同不变。

- `Pro原始返回.zip`：下载目录的原件归档，含冻结输入、原代码、结果、报告和图。
- `Pro原报告.md`、`Pro对话返回原文.txt`：便于直接阅读的原文。
- `本地复算.zip`：本次全新00—09阶段运行的代码、结果、日志和比较记录，省略可再生成图片和重复冻结源。
- `audit/INDEPENDENT_CHECK.json`：2444份有效点核对、53份结果差异解释、小图穷举、新候选x扰动、单人簇下界及重放抽样误差。
- `audit/diameter_partition_singleton_lower_bound.csv`：110图的孤立作答与达90%重复支持覆盖的必要条件。
- `audit/candidate_shared_x_sensitivity.csv`：新候选全240图的同样x扰动探针。
- `audit/replay_monte_carlo_intervals.csv`：80次重放的逐图Wilson区间，只是固定人群下的模拟误差。

本轮新增维护代码为`tools/thesis_main/analysis/audit_cluster_validation_return_20260922.py`，最小检查为`tests/test_audit_cluster_validation_return_20260922.py`。收到的原代码保留为证据，不升格为正式默认算法。

## 复现

在仓库根目录，将原包解压到较短且尚不存在的`.cv22`；Windows须保持UTF-8，避免深目录超过系统路径长度。依赖沿用原包requirements；本次没有安装或修改全局依赖。

```powershell
python -m zipfile -e analysis_results/cluster_validation_received_20260922/Pro原始返回.zip .cv22
$env:PYTHONUTF8='1'
python -X utf8 -B .cv22/code/run_all.py --fresh --output .cv22run --jobs 3
python -X utf8 -B -m tools.thesis_main.analysis.audit_cluster_validation_return_20260922 --package .cv22 --recomputed .cv22run
python -X utf8 -B -m pytest tests/test_audit_cluster_validation_return_20260922.py -q
```

第一轮本地全阶段均成功、20项原测试通过，原比较器因5份JSON差异返回非零：4份只有最大约5.69×10⁻¹⁴的浮点尾差，1份只有Node版本不同。独立检查显式记录差异，没有把原`all_pass=false`改为true；离散结果一致。新增1项检查通过。当前机环境见`audit/ENVIRONMENT.json`。

所有临时重算图片及工作目录在证据归档后清理；没有改下载原件或源数据。没有重做全库视觉语义验收、运行线上运营或训练测试，也没有派发或推送。
