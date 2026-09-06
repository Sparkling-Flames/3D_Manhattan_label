# 交付故障修复与复现约束

## 已确认的上次故障

旧bottleneck分析run 33977472903在解码SOURCE_ZLIB_BASE64时失败：编码长度9469不合法，分析计算未在该远端run运行。随后旧发布run 33978100559未能取得相应产物。旧发布命令已使用git add -f，不能把本次根因归为.gitignore。旧sandbox链接也没有建立可恢复的完整持久包，因此本次是从原始来源重新构建，而不是声称恢复了逐字节相同的旧ZIP。

本次改为普通UTF-8源码，基础计算run 34007364589已经成功，包括计算、验证、artifact上传和main结果提交。其EXECUTION_RECEIPT.json记录60个基础结果文件；后续总清单DELIVERY_MANIFEST.json另外覆盖案例、图、报告和代码副本，二者有各自范围，不能混淆文件计数。

## 本包的证据层

原始坐标和选定导出SHA重新验证；规范化引擎复用仓库实现。Bi差异为带来源SHA的归档结果，未重新推理。时间采用归档来源完整性字段，未宣称新工时算法已经正确。实际图片、标注和参考组成案例，解释为AI初查；没有新增真人数据或人工裁决。

本包重建了上次核心精度、尾部比较、资源网格和渐近形状敏感性，并新增五项前置研究。它不包含一个被声称为完整经验验证的疲劳模拟器，也没有执行正式三臂实验。

## 复现

先在本仓库根目录运行，保留对应原始数据和依赖目录。ZIP中的code/是本轮源码副本，不是包含所有历史原始数据的独立软件发行包。SOURCE与DELIVERY清单分别固定输入及输出SHA；source_commit为本次打包入口代码提交，不自动等于每条历史数据首次产生的提交。

```bash
python -m pip install numpy==2.3.5 pandas==2.2.3 scipy==1.17.0 scikit-learn==1.8.0 shapely==2.1.2 pillow==12.3.0 matplotlib==3.10.8
python -m tools.thesis_main.analysis.preflight_statistics_20260906
python -m tools.thesis_main.analysis.preflight_panels_20260906
python -m tools.thesis_main.analysis.preflight_deliver_20260906
python -m tools.thesis_main.analysis.preflight_plots_20260906
```

建议OPENBLAS_NUM_THREADS=1和OMP_NUM_THREADS=1。`early_prediction_all_draws.csv.gz`保留全部逐次预测；可直接用pandas.read_csv读取，不必解压出巨大明文文件。

## 后续分析的交付门

不能只提交workflow或运行入口就宣布交付。以后必须同时满足：报告和表实际存在；要求的输出非空；逐文件SHA清单；ZIP CRC和成员SHA验证；显式git add -f仅限所选结果目录；发布前先上传artifact；写入main后从origin/main逐文件读回验证；最终提供实际存在的附件和可浏览仓库路径。

本轮提供通用验证器tools/thesis_main/analysis/verify_analysis_delivery.py。新分析可复用并指定root、minimum-files及require文件。不能仅靠这一文档假定所有未来代码已自动遵守；每次新任务仍需实跑并出示验证结果。

```bash
python -m tools.thesis_main.analysis.verify_analysis_delivery \
  --root analysis_results/preflight_20260906_v2 \
  --archive analysis_results/preflight_20260906_v2/preflight_analysis_20260906.zip \
  --git-ref origin/main
```

归档外的.zip.sha256验证整个ZIP；归档内DELIVERY_MANIFEST.json验证每个成员。清单不递归包含ZIP本身或其SHA侧车。普通结果文件和完整ZIP均写入main；不能只依赖会过期的Actions artifact。
