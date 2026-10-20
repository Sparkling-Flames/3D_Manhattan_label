# HOHONET 人员类别与融合不确定性：20261020 接续研究

先读 `REPORT_ZH.pdf` 或同内容的 `REPORT_ZH.md`。本包保留实际检验的积极方向和失败，主研究单位为完整类别人数向量、总人数与任务条件。C01/C02 等编号只在各自分类方法内有意义。

## 从哪里看

| 需要 | 入口 |
|---|---|
| 主结论、适用范围、反例与选人价值 | `REPORT_ZH.pdf`，正文第 4—10 节 |
| 少量图像确认 | `interchangeability_20261020/figures/cases/` 的 S07/S10、S06、S03/S04，其他案例在报告第 9 节 |
| 类别的精确成员 | 正向 `forward/worker_labels.csv.gz`；反向 `reverse/mixed_fit/worker_labels.csv.gz` 与 `reverse/legacy_fit/worker_labels.csv.gz`；均在研究目录下 |
| 简要搜索台账 | 根目录 `SEARCH_LEDGER.csv`；细项的候选、容量、失败见报告证据索引 |
| 核心数值与逐成员请求 | `interchangeability_20261020/core_replay/`；完整固定评估请求另在 `assessment/` |
| 配比与必要几何 | 反向 `nested_new2/full_vectors/`，混类 `both_effects/` 全部冻结单元，以及 `cases/S*.json` |
| 实际交付验收 | `verification/FINAL_VERIFICATION.json` 及对应真实运行回执 |
| 全部文件完整性 | `FILES_SHA256.json`，ZIP 的 CRC 与大小审计另见 `ZIP_CONTENTS_REVIEW.json` |

路径省略前缀时，`forward/`、`reverse/`、`assessment/` 等均在 `interchangeability_20261020/` 下。保持解压后的布局：根目录的 `analysis/` 与 `interchangeability_20261020/` 同级；不要仅复制某一脚本到新位置。

## 环境与输入

本次实际验证使用 Python 3.12.14。科学依赖与绘图、报告依赖都固定在 `requirements.txt`。例如在自己的工作目录执行：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

本包不重复保存冻结输入全集、旧报告缓存或虚拟环境。读取的最新任务 main 为 `445686f8f3cf6039c4ce1f60016cad1d26829044`；沿用的归档输入版本为 `e572eb73bedc4fe9056df838e458bab83c3fa423`；融合科学代码版本为 `82c6164b0d4630de5316199c92aa405930973168`。逐文件 SHA 比目录名更优先。

外部恢复的入口和准确参数见 `interchangeability_20261020/reproduction/RECOVERY_QUICKSTART_ZH.md`。优先复用已有恢复目录；无需从原始导出重做坐标、删点、环序或参考。主快照 SHA256 为：

```text
83179b9842d06916b105d80ff181918c223e4fee2073f425f9825db124ec11d7
```

将恢复目录传给 `--restored /path/to/restored`，其中应存在 `work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/`。快速案例重放只使用包内嵌入的成员和参考，加外部冻结科学代码；核心面板再读取冻结快照。完整正向画像与反向重训另需要说明中列明的历史证据。

## 最少操作：直接重放主结论

以下命令从解压目录运行。各次 `--work` 使用新的输出目录，以便区分原生重新计算与旧结果读取；大输出不必放回本包。

```bash
python reproduce.py hashes
python reproduce.py cases --restored /path/to/restored --work /tmp/personnel_cases
python reproduce.py core --restored /path/to/restored --work /tmp/personnel_core --jobs 3
```

- `cases` 原生重算 10 个代表案例、39 个不同池×团队，核精确人员、共同背景、类别向量、参考、最终几何、B8L2/D10 和相近判据。程序禁止读取完整库存快照和旧团队结果缓存。
- `core` 原生重算 17,726 个固定核心任务、46 图、7 楼、59 人。含 F01/F04/F05、Rnew2 n13 四格、旧 G/R 新背景锚点、高 Q n7 完整配比、五比例全部评估、P05 单图全部 3,752 队、W132 同支持机制检查。每队核 32 个最终字段和精确几何指纹，重算 1,819 个配对事件、分层汇总与全部相关配比均值。
- `EXPECTED_FINAL_FIELDS.json.gz` 保存必要最终数值与几何指纹；只有代表案例保存完整最终几何。它不包含全部团队流程状态，不能当作整个搜索的结果缓存。

这两项的失败不补零。原生结果中的 `complete_conditional` 沿用冻结环序／参考资格，不能改称新增人工确认。单图穷举、W132 探针和交付重放都不增加独立图片或外部验证。

## 重建设计、历史特征与分类

```bash
python reproduce.py designs --restored /path/to/restored --work /tmp/personnel_designs
python reproduce.py forward --restored /path/to/restored --work /tmp/personnel_forward
```

`designs` 核验 18 个命名流：16 个从冻结规则、种子与人员容量重新生成；P05 与 W132 两个小请求精确保留并核验。三份条件全表／分表属于同一设计链，不能把 18 个流说成 18 个独立原生批次。全部请求多重集、去重成员、事件、类别计数、实际换人规模、嵌套路径和台账指纹均核查。

`forward` 从历史十楼冻结记录重建 60×328 画像、188 个候选、11,280 行逐人标签及成员容量表；它与“仅从已算画像重跑分类”不同。所有缺失位置、数值和标签分别核验。具体输入的来源与 SHA 见 `FORWARD_FEATURE_INPUTS.json`。

完整反向学习的输入恢复、风险构造、四类算法、所有 K 和逐楼选择见 `interchangeability_20261020/reverse/REVERSE_REPRODUCTION_ZH.md`。反向历史关系大表、距离矩阵、模型缓存由代码重建，不在 ZIP 内；本次交付阶段没有再次重训全部 1,808 个反向候选。共同面板统计重算还需其两阶段原生结果；`reproduction/prepare_common_analysis.py` 搭建带 SHA 约束的隔离目录，具体命令见同目录 README。

全宽搜可先运行 `designs` 再将重建的某一请求送入冻结入口：

```bash
python analysis/composition/fusion_runner.py --restored /path/to/restored \
  --requests /path/to/rebuilt_requests.json.gz --out /tmp/personnel_native --jobs 3
```

再调用该分支既有分析脚本。宽搜全部重放比核心重放更大；本次交付验收没有把全宽搜第二次全部重算，实算边界写在回执中。

## 原图、图表与报告

九张代表图已从既有 Release 获取并用于本包 PNG，对应 10 个案例。原图不重复装入 ZIP。`ORIGINALS_MANIFEST.json` 给出精确 Release ZIP、内部路径、尺寸、CRC 和实际原图 SHA；Release 索引没有逐图发布者 SHA 时明确标注。

```bash
python reproduce.py fetch-originals
python reproduce.py render-cases --work /tmp/personnel_case_figures
python reproduce.py report --work /tmp/personnel_report
```

`fetch-originals` 只按 HTTP Range 提取九个条目并核验本次记录的 SHA，不下载全部原图 ZIP。先获取原图再绘制才能重建带照片的 ERP。数值重放无需原图。独立 PNG 是无损分享版本，PDF 为阅读用压缩预览。人数／配比曲线的源 CSV 和绘图脚本随对应分支保留；报告排版不会训练分类或重选比较规则。

中文字体为 Noto Sans SC 的本报告字符子集，约 0.54 MB，附 SIL Open Font License。字体来源和 SHA 在 `analysis/fonts/FONT_PROVENANCE.json`，`analysis/prepare_fonts.py` 可生成更大字符集；修改报告加入新字时应重建子集。

## 实验边界

本轮 17 个正式批次跨批去重后实际覆盖 569,529 个池×精确团队、181 张真实图片、22 楼、60 人；大量团队是同图重复观测。普通 Manual 177 池全部覆盖，Semi 尝试 14 池而只有 12 池有完整评分，门洞 4 池；特殊条件没有本轮新实验。全部未覆盖池、失败、机会不足和未入选结果均有小表或可重建台账。

这些仍是反复探索过的 v2 内部数据。质量方向、成员可互换性、范围结构和来源效率分别解释；未修改不等于盲信、scope 倾向不等于审核正确率，缺初始几何不估净纠错。B8L2、D10 和固定参考未改变，N1 未接入。
