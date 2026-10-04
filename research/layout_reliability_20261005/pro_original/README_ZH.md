# 全员布局共识可靠性：四图机制研究，2026-10-05

先读 `REPORT_ZH.html`，再打开 `EVIDENCE_VIEWER_ZH.html`。本包不需要连接GitHub或取得整个仓库才能复算。HOHONET是本地工作区名；云端来源是Sparkling-Flames/3D_Manhattan_label，读取main时为017f3056a9d5bf889c257378403783bf023b3a70。

核心结论：精确投票和编辑近似必须分开。两张完整名单可构造全员精确弧；另外两张整池域外，人员全部保留。新增锁底压缩能保持Lee范围，但不是普遍的质量或人员支持保证。新增固定经度误差及距离三角不等式审计，可以界定压缩对质量/成员变化的污染幅度。

## 运行

Python 3.10+；本次实际Python 3.13.5，依赖见environment.json。核心仅需numpy、scipy、pandas、shapely。不需要GPU、SimpleITK、浏览器或原图。

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python run_research.py --out /path/to/NEW_output
```

`--out`必须是不存在的新目录。脚本不覆盖本包或仓库旧结果。默认BLAS线程过多在本环境使一次执行达到200秒限制；Linux建议：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python run_research.py --out /path/to/NEW_output
```

PowerShell可先设置`$env:OPENBLAS_NUM_THREADS='1'; $env:OMP_NUM_THREADS='1'`。本次以单线程BLAS完整重算成功，86个结果文件逐字节一致；失败尝试和最终成功日志分别保留。

只运行一个完整当前名单、不读取GT：

```bash
python run_one.py inputs/7y3sRwLe3Va-04.json --out /path/to/NEW_result.json
python run_one.py inputs/2t7WUuJeko7-06.json --edit-policy bottom_locked --epsilon 0.5 --out /path/to/NEW_editor.json
python run_one.py inputs/rPc6DW4iMge-06.json --out /path/to/NEW_failure.json
```

`bottom_locked`的单图入口采用必要底边转折起点；论文结果中对应`bottom_locked_mandatory_anchor`。`pixel_only`是原固定起点压缩。默认只构造精确结果。点数超过声明预算时，编辑步骤返回not_run，精确结果保留；该参数仅限制编辑压缩，不承诺一般大输入的构造运行时间。

浏览器打开`EVIDENCE_VIEWER_ZH.html`即可离线查看。可选再生成页面：`python src/make_viewer.py`；需要完整研究结果已生成，核心复算不依赖页面。浏览器验收脚本`src/check_viewer.py`需另装playwright及Chromium，不是核心依赖。本环境file导航被策略阻止，验收通过读取本地生成HTML到浏览器内容完成，没有加载任何原图。

## 数据与证据边界

四张图是机制开发面板，不是随机样本、未见图片或新盲测。inputs含66份当前独立作答、24名不同人员；各图人数3/24/24/15。其四文件与当前交接完全一致。完整名单见results/complete_roster.csv。

本包完整取得四份原始版本GT；此四图交接没有人工修订GT，不代表全库没有。evaluation不参与构造/压缩。context只保留本轮读取的审核摘要和原有五份未选中记录台账，不是完整审核数据库。main不包含全部未提交本地消费者，本轮没有声称重新执行load_current_bundle完整源绑定。

长度单位h=共同相机高度1，非米。相机以上的派生顶部高度是Y_top，完整局部墙高为Y_top+1。没有新视觉GT裁决；没有屋顶内部或真实实体体积。

## 结果索引

- `results/input_and_domain_checks.json`：66份字段/四图构造/Lee等价性及整池失败。
- `results/construction/`：全部当前人员的精确输出、Lee区域及逐记录诊断。失败池无成功子集替代。
- `results/compression/*_losses.csv`：三种压缩政策×四预算×两适用图的24条损失。
- `*_anchor_sensitivity.csv`：364个相同精确环的循环起点试验；不是364张图。
- `mandatory_anchor_invariance.csv`：160个必要起点状态的保留节点检查。
- `results/domain_locations/`：复杂确认环的多分支经度区间及源边。
- `results/metrics/reference_metrics.csv`：66原作答＋28输出＝94条固定原参考评价；不是94独立样本。
- `compression_score_certificates.csv`：72项GT-free压缩距离界及随后评价核查。
- `metric_order_*`、`refined_discordances.json`：真实分项指标排序与两处细步长核查。
- `witness_relaxation_samples.csv`：65,536经度显示严格包含损失的幅度，抽样诊断而非精确极值证书。
- `results/reproduction_checks.json`、`results/viewer_checks.json`和logs：本轮执行核验。

## 新增与复用

复用并保持原字节：src/arc_consensus.py、simplify.py、quality.py、baseline_points.py；来源为当前handoff/external/dot/source/layout_foundations_20261004_v2/src，散列见vendor_source_receipt.json。这里的点方法是数值步骤对照，不是整个当前global_pair模块及所有诊断的逐字复现。

新增：continuous_metrics.py、compression_study.py、mandatory_anchor.py、localize_failures.py、metric_study.py、witness_relaxation.py、refine_metrics.py、两个运行入口及24项测试。REPORT给出证明范围与不保证性质。

没有提交到GitHub；没有修改源标注、GT、人员资格、人工环或方法合同。请将后续本地修改保存为新版本，不用新结果覆盖本包证据。
