# 人员类别组合研究：精简包复现说明

本包把**代表案例直接重放、全部请求重建、完整冻结实验重算**分为三个入口。`analysis/reproduce.py` 根据自身位置确定包根目录；可从任意工作目录调用，`--restored` 可以指向包外的恢复目录。默认输出在包根的 `replay/`，也可用 `--out` 指定独立位置。

本入口不从原始导出重新整理坐标、删点或环序，不重新选择参考，也不修改 GitHub。原始证据与冻结科学代码从公开仓库恢复；本轮的小规格、标签、精确案例和核验凭据随包保留。完整输入、逐队缓存、距离矩阵和虚拟环境不属于精简交付。

| 入口 | 实际执行内容 | 所需大输入 | 默认是否做融合 |
|---|---|---|---|
| `quick` | 用案例内完整 `frozen_record`、参考和参数重算 21 个展示团队；核验分数、最终几何、结构诊断、共同背景与机制 | 只需要恢复后的冻结代码和测量引擎；数值模式不读完整快照或原图 | 是，只算所选案例 |
| `requests` | 物理重建 13 个主请求文件，检查完整 SHA、逐请求成员签名、类别计数、楼隔离和覆盖；再重建 `FINAL` 拼接 | 冻结 `INPUT_SNAPSHOT.json.gz`；包内标签和规格 | 否 |
| `full` | 生成按顺序可执行的融合、汇总和分层命令；保存 JSON 计划和 Bash 脚本 | 实际执行脚本前须恢复冻结输入和代码 | 本命令只写计划；运行生成脚本才开始全量融合 |

## 1. 固定版本与环境

本轮读取的 main 固定为 `e572eb73bedc4fe9056df838e458bab83c3fa423`。被沿用的融合与评分科学源固定为 `82c6164b0d4630de5316199c92aa405930973168`。两个提交的作用不同；后续移动的 main 不能替换这些冻结字节。[本轮输入审计](composition/INPUT_AUDIT.json) 保存原输入路径、大小与 SHA；[验证冻结记录](composition/VALIDATION_FREEZE.json) 保存标签、规格和关键代码的 SHA。

实际核验运行环境为 Python **3.12.14**，依赖如下，已写入 `analysis/requirements.txt`：

| 依赖 | 版本 |
|---|---|
| numpy | 2.3.5 |
| pandas | 2.2.3 |
| scipy | 1.17.0 |
| scikit-learn | 1.8.0 |
| shapely | 2.1.2 |
| threadpoolctl | 3.6.0 |
| matplotlib | 3.10.8 |
| Pillow | 12.3.0 |

在包根安装。虚拟环境可以放在包外，不需要另行归档：

```bash
python3.12 -m venv /tmp/personnel-composition-env
/tmp/personnel-composition-env/bin/python -m pip install -r analysis/requirements.txt
```

下文的 `python` 指这个环境里的 Python。入口核对直接依赖版本，并固定 `OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1`。原实现的浮点运算、排序和聚类依赖这些版本；案例的分数容差默认为 `1e-9`，最终几何则做精确序列比较。输出中会保留实际解释器、包版本和源码 SHA。

## 2. 从公开仓库恢复最小科学输入

已有恢复区时直接使用，不必再恢复上一轮 Part A 的全部归档。`--restored` 应指向**包含 `work_personnel_typing_A_20261019` 的父目录**，不要指向它下面的 `recovered`。

| 相对 `--restored` 的路径 | 用途 |
|---|---|
| `work_personnel_typing_A_20261019/recovered/repo_main_20261019/` | 原科学源快照 |
| `work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/fusion_engine.py` | 原生融合与测量入口 |
| 同一 `fusion/` 下的 `pool_io.py`、`INPUT_SNAPSHOT.json.gz` | 原布局与全部冻结池；`quick` 不读取快照 |
| `work_personnel_typing_A_20261019/recovered/work_v2_20261019/` 中测量引擎及归档小输入 | 官方 bootstrap 按 manifest 恢复 |

首次从 GitHub 开始，可在独立目录取稀疏检出。科学源提交必须能由 Git 读取，官方 bootstrap 在当前字节不匹配时会执行 `git show 82c6164b…:路径`：

```bash
git clone --filter=blob:none --no-checkout https://github.com/Sparkling-Flames/3D_Manhattan_label.git /tmp/personnel-source
git -C /tmp/personnel-source sparse-checkout init --no-cone
git -C /tmp/personnel-source sparse-checkout set --no-cone '/research/workers/pro_personnel_v2_archive_20261019/' '/research/workers/personnel_composition_handoff_20261019/' '/research/workers/pro_personnel_v2_20261019/IMAGE_INDEX.csv'
git -C /tmp/personnel-source checkout e572eb73bedc4fe9056df838e458bab83c3fa423
git -C /tmp/personnel-source fetch origin 82c6164b0d4630de5316199c92aa405930973168
python /tmp/personnel-source/research/workers/pro_personnel_v2_archive_20261019/bootstrap.py --repository /tmp/personnel-source --workspace /tmp/personnel-restored/work_personnel_typing_A_20261019/recovered --smoke
```

最后的 `--workspace` 目标须不存在；bootstrap 会先验证归档与源文件 SHA，再建立新目录。部分克隆的 Git 可能为读取历史源对象补取内容。原图不在这个恢复步骤中。

**这一步是恢复冻结输入与代码，不是本轮科学重跑。** 默认 bootstrap 的 `science_executed` 为 false；`--smoke` 只核对冻结画像输入，不拟合本轮人员类型、不生成本轮团队、不重算本轮融合。不要把官方旧研究的 `--stage all --execute` 当作本轮入口。[官方 bootstrap 源码](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/e572eb73bedc4fe9056df838e458bab83c3fa423/research/workers/pro_personnel_v2_archive_20261019/bootstrap.py) 中明确区分了这两步。

冻结融合快照的 SHA 必须是：

```text
83179b9842d06916b105d80ff181918c223e4fee2073f425f9825db124ec11d7
```

该快照有 229 池，其中普通 Manual 177、门洞 Manual 17、普通 Semi 32、特殊 Manual 2、特殊 Semi 1。`requests` 会验证快照和本轮冻结依赖，不会因路径改变而重加工输入。

## 3. 快速重放全部代表案例

恢复后执行：

```bash
python analysis/reproduce.py quick --restored /tmp/personnel-restored --out /tmp/personnel-quick
```

默认按 `composition/CASE_SELECTION.json` 中冻结的案例顺序读取 `representative_cases/cases/` 下的导出 JSON。也可只核验指定文件：

```bash
python analysis/reproduce.py quick --restored /tmp/personnel-restored --case analysis/representative_cases/cases/C05_matched_block_improvement.json --out /tmp/personnel-one-case
```

`--case` 可重复。`--selection` 也接受相对其文件位置的路径列表、含 `case_json` 的列表，或本包以 `case_id` 索引导出案例的选择规格。

每个案例携带精确 worker ID、object ID、类别、全部冻结成员记录、固定参考点和参考平面、自动融合参数以及最终几何。重放直接调用原生 `fuse(..., gap=7.5)['automatic']` 和固定测量引擎，保留绑定、环序与坐标。主分数是 B8L2；D10 只把原模型方向尺度从 8° 改为 10°，没有修改匹配阈值、参考或融合。N1 未接入。

输出包括 `REPLAY_SUMMARY.json` 和每例一个 `.replay.json`。检查 `all_passed`，以及各臂 `B8L2_delta`、`D10_delta`、`geometry_exact`；分数和完整性失败保留原状态/null，不补零。单独的墙段覆盖与真实转角诊断也重算，不混入 B8L2。带机制的案例还核对固定成员链、原生 `transition`、支持票数和失选身份组；带 A/B/C 的案例核对相同共同背景、相同实际换人人数与来源构成。

同人数案例的 15 个成对诊断由重放后的最终几何和测量重建。主联合稳定同时要求完整、`|ΔQ|≤2`、平面 `1−IoU≤0.05`、相同节点数、绑定循环角距离≤3°。**质量分数接近不能代替整体稳定。** 例如 C05 的 A/B 分差约 0.339，但节点数不同、平面差约 0.0926；C06 的 A/B 分差约 0.213，但平面差约 0.0719；两者主联合稳定均为 false。

最终 7 例共 21 个不同实际团队，覆盖 6 图、6 池、4 楼、52 名实际入队人员。为成员叠图与完整加入链嵌入了 55 名不同人员的记录；55 不是 21 个展示团队的入队人数。完整快照独立审查与案例内记录重放分别记录在 `independent/REPRESENTATIVE_CASE_PARITY.json`、`independent/PORTABLE_REPLAY_READ_AUDIT.json`。后者实测禁止了完整快照、证据 records、请求文件和旧融合缓存的读取。

`quick` 不读取完整池，因此不声称从案例的成员子集重建完整 `pool_digest`；它把该摘要保留作原池来源标识。案例与原快照的逐字段一致性由单独的完整快照审查确认。

## 4. 重建全部请求并核对成员

```bash
python analysis/reproduce.py requests --restored /tmp/personnel-restored --out /tmp/personnel-requests
```

入口依次运行原生成器，先查冻结依赖，再检查每个 `request_id → (pool_id, k, sorted worker_ids, counts, team_key)` 的 SHA；同时重新计数池成员、类别、phase/建筑资格、来源条件与台账。完整文件 SHA 与成员签名来自首次独立重建的 `independent/REPRODUCTION_AUDIT.json`；不要求包内保留原始大请求文件。

| 主请求文件 | 请求行数 | 覆盖含义 |
|---|---:|---|
| `SCREEN_REQUESTS.json.gz` | 14,187 | 发现侧无类别条件的具体团队抽样 |
| `DISCOVERY_GRID_REQUESTS.json.gz` | 139,322 | 发现侧宽覆盖构成搜索 |
| `DISCOVERY_BLOCK_REQUESTS.json.gz` | 77,232 | 25,744 个 A/B/C 共同背景事件 |
| `VALIDATION_BLOCK_REQUESTS.json.gz` | 67,020 | 22,340 个建筑留出 A/B/C 事件 |
| `DISCOVERY_CURVE_REQUESTS.json.gz` | 123,267 | 发现侧冻结人数/整数配比曲线 |
| `VALIDATION_CURVE_REQUESTS.json.gz` | 100,810 | 对应建筑留出曲线 |
| `DISCOVERY_CONFIRM_REQUESTS.json.gz` | 25,798 | 发现侧冻结构成的新成员抽样复查 |
| `VALIDATION_CONFIRM_REQUESTS.json.gz` | 21,134 | 建筑留出的成员复查 |
| `DISCOVERY_NESTED_REQUESTS.json.gz` | 5,872 | 发现侧精确逐人加入链 |
| `VALIDATION_NESTED_REQUESTS.json.gz` | 4,290 | 建筑留出加入链 |
| `DISCOVERY_CONDITION_REQUESTS.json.gz` | 5,758 | 门洞、Semi 自身条件资格的发现侧搜索 |
| `VALIDATION_CONDITION_REQUESTS.json.gz` | 5,117 | 对应条件的建筑留出搜索 |
| `SPECIAL_REQUESTS.json.gz` | 183 | 3 个有资格特殊池的描述性融合 |

13 文件合计 **589,990 请求行、583,261 个不同实际团队、126 池、106 图、12 楼、59 人**；重复行 6,729 不另算不同团队。输出 `REQUEST_REBUILD_RECEIPT.json` 保存逐文件 SHA、成员签名、支持量、覆盖和遗漏。此处是请求支持量；真实评分可用分母还须看融合完成后的 `study_coverage`。

`FINAL_REQUESTS.json.gz` 是其中 7 个后续阶段的有序拼接，共 230,041 行；不能再次加到上述总量。原文件的 `component_manifests.path` 保存了最初机器上的绝对路径文本。为逐字重建完整 SHA，入口保留这些**来源字符串**；实际读取使用新 `--out` 中的文件。它们不是机器路径依赖。条件生成器同样保留原来的逻辑 `source_spec=analysis/forward/condition_experiment_spec.json`。

需要检查局部或已有重建时：

```bash
python analysis/reproduce.py requests --restored /tmp/personnel-restored --out /tmp/personnel-requests --only SCREEN_REQUESTS.json.gz
python analysis/reproduce.py requests --restored /tmp/personnel-restored --out /tmp/personnel-requests --check-existing
```

`--check-existing` 仅核验已有重建，不再执行生成器。只有全部 13 主文件通过时才生成派生 FINAL。

搜索覆盖的具体边界见小 receipt：能穷举的是有容量条件的计数向量或小有限成员集合；宽搜索、区块与具体人员组合采用有种子的系统抽样。曲线穷举指定线上的可行整数位置，不等于所有类别比例；区块候选 frame 还有混合向量、core 向量及事件配额上限。一次成员抽样后 core 容量失败不代表数学不可行。改 seed 得到的新请求也可能重复原团队，入口按实际成员重新去重。

## 5. 只恢复 6 张展示原图，再画 ERP／BEV／3D

数值 `quick` 不需要原图。需要画图时，在包根按精确 Release 索引提取这些图片：

```bash
python analysis/visual_sources/range_zip.py extract --metadata analysis/visual_sources/release_metadata.json --directories analysis/visual_sources/zip_directories.json --index analysis/visual_sources/release_IMAGE_INDEX.csv --image-id yqstnuAEVhm-27 --image-id yqstnuAEVhm-25 --image-id UwV83HsGsw3-22 --image-id X7HyMhZNoso-07 --image-id UwV83HsGsw3-09 --image-id q9vSo1VnCiC-03 --out analysis/selected_originals
python analysis/reproduce.py quick --restored /tmp/personnel-restored --out /tmp/personnel-quick-with-figures --render --font /path/to/NotoSansSC-Regular.ttf
```

原图源是公开 [quality-original-images-20261015 Release](https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/tag/quality-original-images-20261015)。`release_IMAGE_INDEX.csv` 用 image code/ID 定位 ZIP asset 和内部 `archive_path`。本包另保留研究使用的 v2 `IMAGE_INDEX` 和来源核验；二者用途不同，不按相似文件名猜图。

提取脚本只读取 ZIP 中央目录、选定成员的 local header 和数据 Range；已核验该 Release 返回 HTTP 206。它不会在不支持 Range 时静默下载完整 ZIP。提取验证尺寸和 CRC，绘图前再验证案例记录的逐图 SHA。Release 未提供逐张图的发布者 SHA 时，案例 SHA 是本轮提取后记录的值；部分下载不等于验证完整 ZIP 的 SHA。原图读取不到会跳过该例画图，数值和最终几何仍保留，并在 receipt 明示视觉缺口。

如包内附有用于本报告的中文子集字体，默认位置为 `analysis/fonts/NotoSansSC-Regular.ttf`，可以省略 `--font`。也可用自己的完整中文字体。需要从 Noto 的可变字体建立静态 400/700 字重时，可使用 本研究实际使用的官方 Noto CJK NotoSansSC 源文件及 `fontTools`：

```bash
curl --fail --location 'https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/Variable/TTF/Subset/NotoSansSC-VF.ttf' --output /tmp/NotoSansSC-VF.ttf
python - <<'PY'
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
for weight, name in [(400, 'Regular'), (700, 'Bold')]:
    font = TTFont('/tmp/NotoSansSC-VF.ttf')
    instantiateVariableFont(font, {'wght': weight}, inplace=True)
    font.save('/tmp/NotoSansSC-' + name + '.ttf')
PY
```

本次静态化使用 fonttools 4.61.1；它只影响排版，不影响几何与评分。`--font /tmp/NotoSansSC-Regular.ttf` 即可使用。字体来源及授权应随需要的字体文件保留；不必把两份完整 CJK 字体打进数值成果包。

BEV 与 3D 使用同一固定几何轴域；3D 高度按原射线与单位相机高度展示，不宣称真实米制深度。粉色未覆盖参考墙段与局部放大用于人工检查特定结构，不能据此把所有参考节点称为语义必要节点。

## 6. 完整冻结实验：先生成精确命令，再执行

```bash
python analysis/reproduce.py full --restored /tmp/personnel-restored --out /tmp/personnel-full --jobs 5
```

这一步仅写 `FULL_REPLAY_PLAN.json`、`FULL_REPLAY_COMMANDS.sh` 和重定位的阶段索引。确认路径后运行：

```bash
bash /tmp/personnel-full/FULL_REPLAY_COMMANDS.sh
```

命令顺序包括全部请求重建、原生冻结融合、7 个构成网格汇总、发现/留出的匹配区块及具体类别对分析、成员敏感性、加入链、冻结 H1–H11 比较、固定构成内波动、真实支持与跨缓存重复团队输出一致性检查，以及追加的房间类型分层。`--render` 还会把概要曲线绘制命令加入计划。

运行生成的大缓存和成对小表留在指定输出目录，不写回冻结标签或规格。融合按原阶段使用 `runs`、`runs_blocks`、`runs_curves`、`runs_final`、`runs_special`；缓存接续只接受相同计算 context。汇总默认要求计算齐全，缺少计算与已算失败明确分开，不把未计算标记成低质量。

完整计划**重放已经冻结的类别和比较规则**，不重做报告撰写时的候选筛选、标题选择或图例编辑。已有 v2 多轮探索背景下的建筑留出也保持原解释，不被改称新的外部盲测。包内研究代码仍包含完整候选发现、筛选和失败台账，便于检查这些选择从哪里来。

需要独立重新拟合历史类别，可在固定 main 的源码检出具备所列文件时运行下列入口，输出到独立目录，再按 `worker_id/method_id/domain/class_id/known` 及分区摘要与冻结标签比较。CSV gzip 的时间头不属于类别科学差异；不要把重拟合后的新压缩文件直接覆盖验证冻结标签。

```bash
python analysis/forward/build_forward.py --repo /tmp/personnel-source --split analysis/composition/SPLIT.json --metric B8L2 --out /tmp/personnel-refit-forward
python analysis/reverse/discover_reverse_composition.py --records /tmp/personnel-restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/clusters/records_geometry.csv.gz --assignments /tmp/personnel-restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/clusters/assignments.csv.gz --split analysis/composition/SPLIT.json --output /tmp/personnel-refit-reverse
```

正向入口使用 main 的三个冻结相对路径：`research/statistics/v2_evidence_audit_20261019/records.json.gz`、`research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/profiles/run_profiles.py`、`research/workers/personnel_type_discovery_next_20261019/work_personnel_typing_A_20261019/forward/build_features.py`。若使用前述最小稀疏检出，须另行把缺失文件纳入检出；不需要恢复上一轮全部大型状态。这些源码和证据的 SHA 可对照 `forward/results/feature_fit_receipt.json` 与本轮输入审计。

正、反向拟合仅使用 `SPLIT.json` 的 10 栋 history 建筑；发现和留出各 6 栋。同一已知人员在不同建筑重复出现，因此建筑留出检验不是新人员外推。完整 `FULL` 画像没有进入这些验证标签。

## 7. 必须保留的解释边界

低尾、失败、缺少评分和容量不足都保留原分母。总体分类效用、来源匹配、历史 Q 相近子集、逐人移除敏感性分别输出，不把所有类别对或组合压成唯一类内/类间均值，也不把分类变量全部控制掉后替代总体结论。

`scene` 是沿用的 OOS/门洞状态；卧室、通行空间等实际房间类型来自 `independent/POOL_IMAGE_CONDITIONS.csv`。该表保留全部 229 池的原始类型、未知和来源，没有根据融合结果重分组。对冻结规律追加的房间类型分层是事后探索性解释。多数既有难度等级含参考几何与非盲全景复核；依赖难度的选人规则以预先已有可比难度判断和相同目标范围为条件。

Semi 旧错误、旧编辑、新批最终质量和可确认纠正的证据资格各自继承；缺失逐份初始几何的部分不生成净改善。节点/直接邻接、共线分点不敏感的墙段覆盖、真实转角位置召回均为相对固定参考的几何诊断，不是已验证的语义必要结构正确率，也不是 N1。

## 8. 复现凭据与精简边界

| 文件 | 核验对象 |
|---|---|
| `independent/HISTORICAL_PARITY_SUMMARY.json` | 26 个精确历史团队与旧原生结果，包括失败状态 |
| `independent/REPRODUCTION_AUDIT.json` | 13 主 manifest 与 FINAL 的独立物理重建、全部成员和实际搜索覆盖 |
| `independent/BLOCK_DESIGN_AUDIT.json`、`VALIDATION_BLOCK_DESIGN_AUDIT.json` | 两阶段全部 A/B/C 事件的人员、构成、来源与台账不变量 |
| `independent/REPRESENTATIVE_CASE_PARITY.json` | 最终 7 例与完整快照、原生几何/分数/机制的逐项一致性 |
| `independent/PORTABLE_REPLAY_READ_AUDIT.json` | 数值 quick 在禁止完整快照和旧结果读取时仍独立成功 |
| `composition/geometry_diagnostics.py` 与对应探针 receipt | 共线点、凸起/凹角缺失、自交、匹配数量优先等诊断行为 |

运行后生成的 `replay/`、`portable_requests_entry/`、`rebuilt_requests/`、原生逐队状态和旧输入恢复区都可再生成，不应放入精简 ZIP。必要的主结论小表、全部固定规则、成员可重建依据、具体案例的最终几何与反例应保留；“精简”不意味着只保留获胜图或总体均值。

## 9. 从小表重画概要与中文报告

数值研究依赖见 `analysis/requirements.txt`；重建 PDF 或字体子集时另安装 `analysis/report_requirements.txt`。这些排版依赖不影响融合分数。

```bash
python -m pip install -r analysis/report_requirements.txt
python analysis/figures_summary/make_summary_figures.py --from-sources --out analysis/figures_summary --font analysis/fonts/NotoSansSC-Regular.ttf
python analysis/composition/plot_frozen_curves.py --from-sources --source-dir analysis/figures_summary --out analysis/figures_summary --font analysis/fonts/NotoSansSC-Regular.ttf
python analysis/build_report.py
```

报告使用包内已核验的小表、案例和图。其 27 页布局与所有数字可直接审阅；全部 7 个案例图可按第5节重新取6张原图后重画。三张概要曲线可直接从随图小表重画，也可在完整重算后由 `plot_frozen_curves.py` 从网格与加入链恢复。`analysis/fonts/` 包含本报告字符集的两份静态子集、字符表、OFL及来源哈希；增加未包含的新文字时应换用完整字体。

从相同可变字体重建子集：

```bash
python analysis/prepare_fonts.py --source /tmp/NotoSansSC-VF.ttf --out /tmp/personnel-subset-fonts --subset --characters analysis/fonts/CHARACTERS.txt
```
