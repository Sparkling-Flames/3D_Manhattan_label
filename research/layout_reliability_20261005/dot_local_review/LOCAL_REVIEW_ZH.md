# 全景布局课题本地只读复核

审查日期：2026-10-05（本地环境 UTC）  
仓库：`D:\Work\HOHONET`，remote `https://github.com/Sparkling-Flames/3D_Manhattan_label.git`  
HEAD：`61ad4c61564572793f76e1872d307b688bdad4ab`，分支 `main`；`origin/main`=`017f3056a9d5bf889c257378403783bf023b3a70`，本地领先 2 个提交。

## 研究意图

[10/04 推进方案](D:/Work/HOHONET/docs/thesis_main/研究推进方案_共识可靠性与Pro深研_20261004.md#L9)的 10/05 更新保留 RQ1「完整共识与测量」优先，其后为人数过程 RQ2 和人员/场景解释 RQ3；同段明确，局部空间候选是独立探索，不改变三问题顺序或正式合同。[10/05 局部删改计划](D:/Work/HOHONET/docs/thesis_main/空间候选构造_局部删改试验_20261005.md#L1)提出从观测结构出发的有限删改账本，不宣称已实现多人并集重组。该定位与课题当前目标一致。

四份当前面板输入共 **66 份标注记录**，来自 **24 个不同 worker ID**；各图记录/独立 worker 数为 3、24、24、15（每图名单内无 worker 重复）。5 份困难记录保留用于机制检查；本试验不把算法域外当成人员错误，也不按 GT 分数选取。GT 未读取。

## 连续指标修复复核

当前代码的两个修复与此前独立复现的问题相对应，机制合理且定向复跑通过：[修复报告](D:/Work/HOHONET/analysis_results/layout_reliability_fixed_20261005/REPORT.md#L5)，实现见 [continuous_metrics.py](D:/Work/HOHONET/tools/thesis_main/analysis/layout_reliability_20261005/continuous_metrics.py#L127)。

1. **高度包络漏掉正切图表无穷点。** 原实现将交点问题化为 `tan(θ)` 多项式，只处理有限根；在 `cos(θ)=0` 的相位，真实交点会丢失，曾导致合法自包含来源出现约 0.4h 的假越界。现实现按 `π/2 + kπ` 显式切分区间后，在各有限图表区间内求交点和包络。这样避免把跨越奇点的两个分支当同一有限多项式区间处理。新增性质回归检查每个来源在自身来源包络内，并测试四个循环相位。
2. **失败区间合并错误延长来源标签。** 原合并条件只比较失败见证人列表；若相邻区间的上界或下界来源改变，整段会继承前一来源标签。现实现还要求 `top_source_curves` 和 `bottom_source_curves` 均完全相同，供者切换处因此保持为区间边界。[对应代码](D:/Work/HOHONET/tools/thesis_main/analysis/layout_reliability_20261005/continuous_metrics.py#L158) 与新增回归覆盖真实来源切换。

本次在仓库外重算 26 份诊断（2 份精确结果、24 个压缩状态），完成 57 个原子区间供者标签检查。仅 1 份 witness 区间结构变化；聚合值最大绝对差 `5.829114968491922e-12`（报告阈值 `1e-10`）；来源自包络最大越界 `3.3306690738754696e-16 h`；高度压缩结论未变。数值积分误差仍是估计，不构成严格区间证明；本次未重新跑全部 86 个工件、起点扫描、GT 指标或人数实验。

## 局部删改复算

[删改报告](D:/Work/HOHONET/analysis_results/local_structure_deletion_20261005/REPORT.md#L5)与仓库外重新运行结果一致：5 个完整原答加 51 个单点删改候选共 56 项；51 个删改中 50 个多边形有效、1 个无效但保留记录，48 个相机严格位于候选内。51 个删改都没有严格同端点边供者或完全相同整环编码。程序未读 GT、未拟合、未改原环；新候选保持未确认状态。

策略结果依赖目标与约束：方向残差优先在 5 个来源中选出 2 个删点候选；加入 0.05h 的路径预算后仅 1 个来源选择删点，其余保留原答。该预算是机制控制而非人类容差。细节保护政策因缺少逐局部图像证据仍标为 `not_run_missing_local_evidence`。因此这轮结果是操作后果账本，不证明删改提高真实布局质量，也不等于多人空间候选重组已完成。

## 未提交改动

起始和结束 Git 状态相同，未修改工作树。未提交的 panorama studio/几何消费者改动涉及保留墙顶边界分段与坐标约定；其定向 Python 测试及下述 headless Chromium smoke test 均通过。两处未提交数据准备消费者的 diff 只改生成隐私说明文字，不改坐标/投影逻辑。文字说明其依据为 10/01 授权；本次没有查看映射或自由文本评语，也没有生成或发布数据包。

## 测试和验证

- `python -B -m pytest -p no:cacheprovider tests/test_layout_reliability_20261005.py tests/test_local_structure_deletion_20261005.py -q` — **9 passed**。
- `python -B -m pytest -p no:cacheprovider tests/test_panorama_studio.py tests/test_layout_foundation_20260930.py tests/test_layout_metric_probe_20260926.py -q` — **35 passed**。
- `node tests/panorama_studio_order_browser.cjs --geometry-only --source` — **passed**。这是 Node 驱动的 Playwright + headless Chromium 浏览器 smoke test：启动 Chromium/SwiftShader、用临时合成夹具打开本地 source 服务、执行页面 JavaScript 并操作画布/角点控件。它不是纯数学单元测试；但没有人工视觉审阅、截图或真实目标图编辑验收。
- `git diff --check` — 无输出。

本轮没有运行全仓库测试、原 Pro 包 24 项兼容测试或完整数据/GT流水线；历史报告中记录的复算不计为本次执行。没有安装新软件。未发现本次检查范围内的新代码失败。

## 输出与边界

本报告、命令日志和脱敏聚合结果一并包含于 ZIP。完整本地重算 JSON 位于 `review_output/reliability/summary.json` 与 `review_output/deletion/results.json`；ZIP 不含这两份细粒度文件，只含剔除候选/人员 ID 的聚合计数，且不含原图、GT、原始身份、评论或完整数据集。

剩余研究限制是实验范围，不是运行阻塞：需继续核查局部图像语义和锚点、建立有限相容多人重组、将政策候选冻结后再做 GT 评价；没有依据宣称完成物理房间正确性或一般方法效度。
