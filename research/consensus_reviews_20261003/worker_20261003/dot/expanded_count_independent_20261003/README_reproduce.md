# A线独立核查复算

固定提交405f3041fdd76977f625d50c558c63dbf342699d。此文件夹自含本轮冻结输入、用于对照的冻结结果、独立脚本和已验证输出；不要求完整仓库或原图。全部输入保持只读，输出写入本目录的independent_results。

## 环境

Python 3.12；NumPy 2.3.5；Shapely 2.1.2。只需要numpy与shapely，不调用上游模型或外部服务。本机运行命令中的依赖路径仅为本机用法，携带到其他环境不需要该路径。

## 复算命令

在此目录运行：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python independent_verify.py --all-k
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python check_additional.py
python check_panel_contract.py
python check_old45.py
```

输出仅写independent_results。可先复制整个目录到新的位置后运行，以保留打包时的结果。没有下载原始照片，没有改变资格、共享x、环序、GT、难度或人员类型。

## 结果索引

- REPORT_zh.md：结论、范围、统计界推导和限制
- independent_results/run_summary.json：全3,438均值复算范围及环境
- independent_results/recomputed_means.csv：每个均值与原结果差值
- independent_results/endpoint_checks.csv：精确单人／全员点
- independent_results/metadata_checks.json：资格、失败整池、固定窗口、难度／建筑覆盖
- independent_results/fixed_panel_contract_checks.json：1,876行／166序列的名单、分母与汇总字段
- independent_results/area_field_checks.csv与prefix_recut_checks.csv：13,752字段和540子集检查
- independent_results/paired_contrast_summary.json：源种子诊断与新种子独立两规则计算区间
- independent_results/paired_contrast_per_image.csv与paired_mean_draws.npz：每图差与用于方差界的每次跨图平均差
- independent_results/download_git_blob_checks.json：16个冻结文件的Git blob匹配
- MANIFEST.sha256：交付文件完整性

概率区间只控制固定数据上的MC计算误差；不包含新图片、新建筑、新人员、标注错误或GT争议的不确定性。源种子只作复现诊断，新种子两规则族才是新增的定向精度核查；不声称全曲线同时改用了更窄的界。
