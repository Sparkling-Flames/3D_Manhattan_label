# 数值复算说明：主空间分层与历史收敛粗分类

## 0. 版本与数据身份

本轮读取和结束核对的分支头均为 `9d19e4e7de5d49025f8844d1a02889a90e21b4b3`。
数值工作包绑定 `a36e307724a127b7c110b4e5039f2d62a121091b`；后两次提交仅新增传输工作流，没有修改该工作包。实际取回任务 run=34867369471。

实际下载并校验的是106张有主观标签图的五模型数值输出（含新增DINO），以及648图元数据/状态、历史人工输入。2178个文件通过转运SHA核验；28个继承人工/评价输入通过最新Git blob核验。不能把648图运行状态记录写成已经取得648图全部特征。完整648转运run34865295736取消，工件为空。

原图、模型权重不在压缩包内。任何步骤都不调用视觉模型或解码原图。

## 1. 阅读包与完整包

解压后打开根目录 `START_HERE.html`，主要报告已经内嵌六张数值图。

- `mainspace_history_readable.zip`：全部本轮代码、统计结果、折外预测、内部参数网格、报告、审图队列、源记录；不包含 `cache/*.npy` 高维特征矩阵。
- `mainspace_history_full.zip`：另包含准确数值汇聚缓存，支持从特征矩阵重新拟合。不再次附带原始五模型NPZ的重复副本。
- 已恢复的旧v1/v2报告及表保留为历史材料，不等于其所有旧中间输入均已恢复。

不要将阅读包声称为完全重拟合包。其独立测试可运行，但完整重新拟合需要完整包。

## 2. 环境

实测环境见 `audit/environment.json`。建议在独立Python环境（本次Python 3.13.5）安装 `requirements-mainspace.txt`。项目路径含中文时使用UTF-8。

```bash
cd repo
python -m pip install -r requirements-mainspace.txt
python -m tools.thesis_main.analysis.image_portrait.difficulty_stratified_reproduce --tests-only
```

这是新研究的23项针对性测试，不代表整个历史仓库的所有业务/采集测试通过。另执行工作包 `build_bundle --check`；不重建人工数据。

## 3. 从已保存拟合网格复算统计和报告

请在完整包的一个工作副本中运行：

```bash
cd repo
python -m tools.thesis_main.analysis.image_portrait.difficulty_stratified_reproduce
```

重新进行所有训练内部选层/组合、配对增量、类别内对照、同房标签迁移、历史粗分类网格和后缀/尾段敏感性、来源审计及报告生成。历史轨迹来源是上一轮已经执行并按SHA保留的逐顺序轨迹；此命令不会冒称重新进行从原始角点到全部历史轨迹的计算。

## 4. 从准确数值特征重新拟合

```bash
cd repo
python -m tools.thesis_main.analysis.image_portrait.difficulty_stratified_reproduce --refit --workers 2
```

`--refit`将当前 `cv/`移入带时间戳的 `reproduction_backups/`，不删除原拟合记录；随后重新执行全部候选的内外层留楼、三个分层方案。内层标准化/PCA/选层不读取外层标签。机器资源有限时使用 `--workers 1`。重复重拟合不会变成新独立验证。

整个分析可以只在CPU运行。内存取决于并行数及最高147456维的六面96区域矩阵；不需要GPU。不同BLAS/软件版本可能有浮点末位差别；不用字节不同误判为科学结论不同。

## 5. 重新从仓库中的模型输出生成数值汇聚

只有需要核对本轮准确汇聚缓存时，才把冻结工作包中对应106个image_id的已有NPZ放回 `analysis_results/image_portrait_20260914_v1/models/`。清单和每个原文件SHA见 `audit/TRANSPORT_MANIFEST.json`、`audit/loaded_model_files.csv`。

```bash
python -m tools.thesis_main.analysis.image_portrait.difficulty_stratified_reproduce --refresh-pooling --refit --workers 2
```

这个选项只读取已有模型数值NPZ，不读原图，不下载权重，不推理。完整ZIP不重复附原NPZ，因此没有这些文件时该选项应报缺件，而不能用零数组替代。

## 6. 分步命令

```bash
python -m tools.thesis_main.analysis.image_portrait.difficulty_stratified_cv --workers 2
python -m tools.thesis_main.analysis.image_portrait.difficulty_stratified_cv --within --workers 2
python -m tools.thesis_main.analysis.image_portrait.difficulty_stratified_cv --within --stratum main --workers 2
python -m tools.thesis_main.analysis.image_portrait.difficulty_stratified_results
python -m tools.thesis_main.analysis.image_portrait.difficulty_stratified_contrasts
python -m tools.thesis_main.analysis.image_portrait.difficulty_stratified_legacy
python -m tools.thesis_main.analysis.image_portrait.difficulty_stratified_rooms
python -m tools.thesis_main.analysis.image_portrait.difficulty_history_bridge
python -m tools.thesis_main.analysis.image_portrait.difficulty_history_confirmation
python -m tools.thesis_main.analysis.image_portrait.difficulty_stratified_controls
python -m tools.thesis_main.analysis.image_portrait.difficulty_stratified_audit
python -m tools.thesis_main.analysis.image_portrait.difficulty_stratified_figures
python -m tools.thesis_main.analysis.image_portrait.difficulty_stratified_report
python -m pytest tests/test_difficulty_stratified_followup.py -q
```

已有CV缓存时分步CV命令复用它；需要重新拟合使用上面的 `--refit` 总入口。零协变量Ridge对照单列 `controls/`，不列入视觉候选族；零特征kNN的任意并列近邻不作为无信息基线解释。

## 7. 核验与回传

根目录运行：

```bash
python verify_archive.py .
```

会逐文件SHA-256核验该包实际清单。数据修改/重新运行后，旧发布清单失配是正常的，应为新研究运行生成新版本，不能改原清单掩盖差别。

本轮未提交GitHub。`PENDING_GITHUB_RETURN.csv`只列本轮新增代码、结果与入口，含建议回传目录；不要把原图、权重或ZIP提交到仓库。本地可将新增目录与代码复制到研究分支核查，正式合同和原始数据不修改。

## 8. 目标与证据边界

106主观难易标签不是205张历史人工过程的替代真值；二者只重叠35图。主空间功能来自明确的首分句关键词派生，AI来源与11张人工focus分开。早期阈值k=2至7全部保留；历史派生类允许无法判断、其他轨迹和稳定多簇，不把“观察内碎片化”写成“永不收敛”。
