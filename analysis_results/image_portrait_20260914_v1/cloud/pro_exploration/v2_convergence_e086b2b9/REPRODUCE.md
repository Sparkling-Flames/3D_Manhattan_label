# 复算与交付说明

## 直接阅读

解压ZIP后，从根目录的`START_HERE.html`进入，或打开本目录`REPORT_ZH.html`。报告的数值图已嵌入HTML；逐例CSV/CSV.GZ、JSON、脚本保留目录。`review/LOCAL_REVIEW.html`不需要网络，可选择留在自己电脑的原图；图像不会上传。它不是自动语义裁决器。

## 两种交付包

完整包包含全部本轮输出（包括计算用NPZ缓存）、恢复的旧结果、旧分析模块及必要源代码和非视觉工作包。轻量包保留同样的代码、全部结果表、报告和图，仅省略数值NPZ缓存；因此轻量包可读，但完全复算请使用完整包。

上一轮没有自动留存的中间文件不可声称已恢复：见`audit/unavailable_preceding_intermediates.csv`。其原代码、已恢复汇总和逐例结果保持原样。额外模型原始导出数值仍来自固定输入提交；本轮复算不需要原图、模型权重或视觉推理。

## 环境

本次Python3.13执行环境的实际包版本记录在`requirements_runtime.txt`与`EXECUTION_MANIFEST.json`。从完整包的`repo/`目录运行。推荐创建独立环境后安装：

```bash
python -m pip install -r analysis_results/image_portrait_20260914_v1/cloud/pro_exploration/v2_convergence_e086b2b9/requirements_runtime.txt
python -m tools.thesis_main.analysis.image_portrait.convergence_v2_run --verify
```

## 实际计算命令

```bash
python -m tools.thesis_main.analysis.image_portrait.convergence_v2_run --stage all
```

逐阶段运行例：

```bash
python -m tools.thesis_main.analysis.image_portrait.convergence_v2_run --stage process
python -m tools.thesis_main.analysis.image_portrait.convergence_v2_run --stage subgroups
python -m tools.thesis_main.analysis.image_portrait.convergence_v2_run --stage prediction
python -m tools.thesis_main.analysis.image_portrait.convergence_v2_run --stage combinations
python -m tools.thesis_main.analysis.image_portrait.convergence_v2_run --stage partition_audit
```

Runner将BLAS线程数固定为1，并保存本轮执行日志。已有预测缓存不会无提示重复拟合；要从头复算预测，可在**解压出的独立复算副本**中，将`prediction/cold`和`strict_cold/prediction/cold`改名备份，再运行相应阶段。不要删除原始输入或v1结果。新v2结果可由同输入确定性重新生成；随机种子和per-image哈希种子在代码中固定。

`prepare`复用完整包的`foundation/`与`prediction/portrait_matrices/`。它只在缓存缺失时读取已有的数值模型导出；若希望清空全部缓存，从输入提交/先前的数值artifact恢复`repo`同级`numerics/`，不能重新执行视觉模型代替本轮冻结数据。

## 关键定义

每图保留实际观察n；Manual/Semi按条件分开。点数不同不并簇；支持须至少2名真实不同人员；单人模式与无效记录保留。P/D/G为探索定义，不是正式停止规则。随机顺序不是日历时间，也不是新增样本。严格图片预测不含目标有效人数；已知窗口与前k人分析明确条件于评价窗口。固定分区精确占位和逐前缀重新聚类是不同计算，均保留。

## 测试与审计

`tests/execution_first.log`保留首次23通过、1项因严格冷预测仍在执行而暂跳过的结果；`tests/execution_final.log`是完整执行后的结果。`audit/explicit_corrections.json`记录分母/缺失/命名纠正，`audit/strictcold_output_path_correction.json`记录严格图片结果目录纠正及数值精度核对。每个失败与支持不足有独立表，不将无法判断强行标为持续不收敛。

## 远端状态

本轮未向GitHub提交。`PENDING_GITHUB_RETURN.csv`列出本轮新增文件和哈希。ZIP交付与远端版本状态是两个不同事实；不得据本地入口误称GitHub main已更新。
