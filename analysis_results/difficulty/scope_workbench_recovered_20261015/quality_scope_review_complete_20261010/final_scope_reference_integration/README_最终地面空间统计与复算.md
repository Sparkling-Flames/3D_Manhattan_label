# 最终确认地面空间接入与 BEV 范围复算

## 一、这次接入了什么

用户于 2026-10-10 13:16:29.431 UTC 导出编辑器 v3.4.2 回执，并在 13:17 UTC 交回，要求统计后统一上传 GitHub main。本目录是新增、独立、可复算的研究诊断层；不覆盖前一轮包、旧实验、正式 GT 或正式 loader。

- 回执有 **261图**；明确确认 **35图、35个 primary 空间**，其中28份修改后地面，7份沿用当时显示的编辑GT地面。
- 此前16图逐点几何保持一致；本轮新增确认19图（15份修改、4份 full_gt）。此前16图对应的134份作答，原GT/已选GT/确认地面的三组指标逐值完全相同。
- 35图中的33图有正式研究作答，合计 **429份作答**：380份 manual、49份 semi，涉及26个不同匿名 worker ID。作答数不等于独立人数。
- **417份底面可算，12份不可算**。全部429份保留，不能只报告有效行，也不能将不可算置零。
- q9vSo1VnCiC-21、q9vSo1VnCiC-25 是外部恢复视角，**零研究作答**，仅登记来源、确认范围与几何变化，不加入259图研究分母。
- 23图同房间批次全部已有明确确认；“无操作沿用原GT”自动确认数量为0。其它226张未确认回执记录不被本包批量确认。
- 本次回执没有任何替代空间；程序和测试支持同图多个已确认空间，并逐空间独立输出。primary 身份来自回执 region_id，不通过比较GT或作答分数选择。

本目录建议新增到仓库 `research/final_scope_reference_integration_20261010/`，由研究脚本显式选择读取。`load_current_bundle()` / `load_current_input()` 未改写；现有清洗、独立资格、质量门槛和融合门槛全部保持。后续上传动作由统一交付处理，不由本包执行。

## 二、正式作答及可算范围

正式源提交为 `24360ad8544d76d8aba18a8e641f784a76ca0d42`。两个正式加载入口数据一致；3441个正式对象保留整体指纹及受保护字段指纹；24个源文件逐一验证同提交blob或LFS内容SHA256和长度。

该正式loader的图片注册表有261项，其中259研究图、2既有参考-only项。本次补回的 q9-21/25 不属于这259研究图，也没有被偷偷加成研究标注。这个计数与编辑器261张可编辑图片的计数口径不同。

本批429份记录的既有质量门槛：

| 状态 | 记录数 | 本次处理 |
|---|---:|---|
| candidate_pending_geometry | 367 | 仍是待几何评估候选，不等于通过 |
| hold_scene_or_reference | 38 | 保留hold |
| hold_individual_review | 2 | 保留hold |
| excluded | 22 | 保留排除 |

不可算原因：10份点对不可用，1份相机不在底面内部，1份坐标超出1024×512画布。具体ID、条件、原门槛在 `results/unavailable_records.csv/.json`。

特别保留：rPc6DW4iMge-22 / R01424 的坐标出画布，但既有门槛是 `candidate_pending_geometry`；本包只输出空指标和失败原因，不擅自将它改为排除或可算。其余11份不可算记录原本均为excluded。

## 三、计算哪些指标

沿用仓库连续ERP底面投影，按来源环顺序使用成对点中的地面点。相机高度归一为h；面积单位h²，长度单位h，均不是米。可算多边形必须有效、面积大于0，并严格包含相机原点。

对作答底面A及每个固定地面参考R，独立计算：

- 面积、交集面积、并集面积、遗漏面积和越界面积
- 面积比 |A|/|R|
- BEV IoU = |A∩R|/|A∪R|
- 参考覆盖率 = |A∩R|/|R|
- 参考遗漏率 = |R\A|/|R|
- 作答越界率 = |A\R|/|A|
- 超出面积/参考面积 = |A\R|/|R|
- 对称差D = |A△R|/|R| = 遗漏率 + 超出面积/参考面积；D不是1−IoU

每份作答同时保留历史原GT、当前已选编辑GT、每个确认空间的结果。原GT与已选GT不能混称：例如 wc2JMjhGNzB-26 沿用的仍是既有 `gt_manual_revision`。

逐图、逐条件、逐门槛的均值和D≥0.2/0.3/0.4计数只是记录级范围诊断；不解释成人员投票、完整质量Q、难度或资格放行。不对多个空间取最优分，不合并/求并集，不建立“允许目标集合”的完整评分协议。

## 四、28个修改地面：新增与移除分别判断

本表比较确认地面T和当时编辑GT G，分别计算新增 |T\G| 与移除 |G\T|。**不以净面积增减判定纯扩展或纯缩小。**

分类容差（仅用于文字类别）：`ε = 1e-9 h² + 1e-8 × max(|T|, |G|)`。

- 新增和移除均大于ε：混合增减
- 仅新增大于ε：扩大（容差内）
- 仅移除大于ε：缩小（容差内）
- 两者均不大于ε：等价（容差内）

得到 **7缩小、6扩大、15混合增减**。若干混合项目的GT外新增条带很小，表中保留实际数值，不能因此称其为纯缩小。ε不用于回剪、吸附、修复、归零或改动坐标；机器表保留全精度。

uNb9QFRL6hY-88 是明确补入GT外面积：新增约 **0.8338373346 h²**、移除约 **5.1×10⁻¹⁷ h²**；作为容差内纯扩展完整保留，未剪回GT。

| 图片 | 范围变化 | 新面积/编辑GT面积 | 新增GT外面积 h² | 从GT移除面积 h² |
|---|---|---:|---:|---:|
| b8cTxDM8gDG-18 | 混合增减 | 0.410968 | 4.85522032e-05 | 5.96090794 |
| e9zR4mvMWw7-09 | 混合增减 | 0.384160 | 0.302738669 | 12.3886659 |
| e9zR4mvMWw7-17 | 混合增减 | 0.812202 | 0.000333425169 | 3.00939652 |
| pRbA3pwrgk9-02 | 混合增减 | 0.117485 | 4.40392559e-06 | 4.71242606 |
| q9vSo1VnCiC-11 | 混合增减 | 0.887877 | 8.11165398e-05 | 1.43716908 |
| q9vSo1VnCiC-12 | 混合增减 | 0.885219 | 7.33822599e-05 | 1.28033639 |
| q9vSo1VnCiC-16 | 混合增减 | 0.882252 | 0.000159604745 | 1.51906261 |
| q9vSo1VnCiC-25 | 缩小（容差内） | 0.922292 | 0 | 0.905834242 |
| q9vSo1VnCiC-29 | 混合增减 | 0.224804 | 6.77078442e-06 | 3.55577925 |
| rPc6DW4iMge-05 | 缩小（容差内） | 0.737632 | 4.28499492e-17 | 1.67767325 |
| rPc6DW4iMge-06 | 缩小（容差内） | 0.561391 | 1.1810111e-16 | 3.13279495 |
| rPc6DW4iMge-22 | 缩小（容差内） | 0.709032 | 1.47986185e-17 | 1.94771201 |
| uNb9QFRL6hY-18 | 扩大（容差内） | 1.095818 | 0.86481064 | 1.66853207e-11 |
| uNb9QFRL6hY-26 | 扩大（容差内） | 1.085544 | 0.768347704 | 0 |
| uNb9QFRL6hY-41 | 扩大（容差内） | 1.098136 | 0.878962924 | 0 |
| uNb9QFRL6hY-44 | 混合增减 | 0.892870 | 8.80834087e-05 | 0.799714297 |
| uNb9QFRL6hY-55 | 混合增减 | 0.883437 | 0.000157577696 | 0.948402002 |
| uNb9QFRL6hY-59 | 扩大（容差内） | 1.095599 | 0.775804602 | 4.31891427e-16 |
| uNb9QFRL6hY-66 | 扩大（容差内） | 1.089755 | 0.748348453 | 0 |
| uNb9QFRL6hY-67 | 混合增减 | 0.121521 | 0.0316514762 | 7.61527025 |
| uNb9QFRL6hY-68 | 混合增减 | 0.887922 | 0.000129780133 | 0.840514822 |
| uNb9QFRL6hY-81 | 混合增减 | 0.926776 | 0.000115336063 | 0.592625062 |
| uNb9QFRL6hY-88 | 扩大（容差内） | 1.082165 | 0.833837335 | 5.12517528e-17 |
| wc2JMjhGNzB-03 | 缩小（容差内） | 0.891841 | 0 | 0.94658373 |
| wc2JMjhGNzB-22 | 混合增减 | 0.882947 | 0.000138608709 | 1.00950286 |
| wc2JMjhGNzB-29 | 混合增减 | 0.875183 | 8.70136426e-05 | 1.1652782 |
| wc2JMjhGNzB-54 | 缩小（容差内） | 0.883004 | 0 | 1.0661398 |
| wc2JMjhGNzB-61 | 缩小（容差内） | 0.957523 | 0 | 0.384389499 |

q9-25 出现在上表仅说明其参考地面本身的几何变化；该图没有作答指标，也不进入研究汇总。

## 五、逐图记录覆盖

| 图片 | 地面决定 | 正式作答 | 可算作答 | 人数ID数 | 说明 |
|---|---|---:|---:|---:|---|
| S9hNv5qa7GM-04 | full_gt | 1 | 1 | 1 | 研究图 |
| b8cTxDM8gDG-18 | allow | 6 | 6 | 6 | 研究图 |
| e9zR4mvMWw7-09 | allow | 6 | 6 | 6 | 研究图 |
| e9zR4mvMWw7-17 | allow | 6 | 6 | 6 | 研究图 |
| pRbA3pwrgk9-02 | allow | 6 | 6 | 6 | 研究图 |
| pa4otMbVnkk-14 | full_gt | 6 | 5 | 6 | 研究图 |
| q9vSo1VnCiC-11 | allow | 5 | 5 | 5 | 研究图 |
| q9vSo1VnCiC-12 | allow | 10 | 10 | 10 | 研究图 |
| q9vSo1VnCiC-15 | full_gt | 26 | 24 | 26 | 研究图 |
| q9vSo1VnCiC-16 | allow | 10 | 8 | 10 | 研究图 |
| q9vSo1VnCiC-21 | full_gt | 0 | 0 | 0 | 恢复参考-only；不加入研究分母 |
| q9vSo1VnCiC-25 | allow | 0 | 0 | 0 | 恢复参考-only；不加入研究分母 |
| q9vSo1VnCiC-29 | allow | 5 | 5 | 5 | 研究图 |
| rPc6DW4iMge-05 | allow | 5 | 5 | 5 | 研究图 |
| rPc6DW4iMge-06 | allow | 26 | 24 | 26 | 研究图 |
| rPc6DW4iMge-22 | allow | 26 | 23 | 26 | 研究图 |
| uNb9QFRL6hY-18 | allow | 19 | 19 | 19 | 研究图 |
| uNb9QFRL6hY-26 | allow | 19 | 19 | 19 | 研究图 |
| uNb9QFRL6hY-41 | allow | 19 | 19 | 19 | 研究图 |
| uNb9QFRL6hY-44 | allow | 10 | 10 | 10 | 研究图 |
| uNb9QFRL6hY-50 | full_gt | 23 | 23 | 23 | 研究图 |
| uNb9QFRL6hY-55 | allow | 15 | 15 | 15 | 研究图 |
| uNb9QFRL6hY-59 | allow | 19 | 18 | 19 | 研究图 |
| uNb9QFRL6hY-60 | full_gt | 23 | 23 | 23 | 研究图 |
| uNb9QFRL6hY-66 | allow | 22 | 22 | 21 | 研究图 |
| uNb9QFRL6hY-67 | allow | 16 | 16 | 16 | 研究图 |
| uNb9QFRL6hY-68 | allow | 20 | 19 | 20 | 研究图 |
| uNb9QFRL6hY-81 | allow | 15 | 15 | 15 | 研究图 |
| uNb9QFRL6hY-88 | allow | 20 | 20 | 19 | 研究图 |
| wc2JMjhGNzB-03 | allow | 5 | 5 | 5 | 研究图 |
| wc2JMjhGNzB-22 | allow | 8 | 8 | 8 | 研究图 |
| wc2JMjhGNzB-26 | full_gt | 6 | 6 | 6 | 研究图 |
| wc2JMjhGNzB-29 | allow | 9 | 9 | 8 | 研究图 |
| wc2JMjhGNzB-54 | allow | 9 | 9 | 9 | 研究图 |
| wc2JMjhGNzB-61 | allow | 8 | 8 | 8 | 研究图 |

## 六、未由本次确认产生的结果

35条确认均保留 `top_boundary_pending=true`、`reference_ready=false`。本次只有地面确认，没有新顶点高度，没有继承或猜测顶高；因此不生成新参考的完整3D Q、3D IoU、顶界/高度误差、集合Q、人员排序、融合结果、难度或人数曲线。

原环序、全部正式坐标和门槛不变；不按x排序、不用buffer(0)修复、不裁回GT、不根据作答优化参考。不可算输出null，不生成零分替代。

旧三图完整Q实验仍对应自己的冻结旧地面；本次地面与其冻结几何不同。旧实验可复现其原条件，但不能改标为本次地面的完整Q、路由或图表。`historical_artifact_applicability.json` 保存适用性边界。此前16图范围层仍保留，本包只新增，未覆盖历史。

恢复的q9-21/25来自已审计的原始等价精标快照，和独立import文件的原环序坐标一致，审计标记roundtrip_only。本包独立验证了同提交源文件及抽取记录，但**没有获得原label_cor文本字节**；不能把等价快照称作已取得原始txt。来源及这一限制写入reference registry和source bindings。

## 七、复算与检查

最小回放只需Python 3及Shapely；pytest用于测试，不需要仓库、照片、浏览器或网络。依赖安装可使用：

```bash
python -m pip install -r requirements.txt
python recompute_bev.py
python -m pytest -q tests
python verify_replay.py --report results/portability_validation.json
sha256sum -c MANIFEST_SHA256.txt
```

若需要从正式提交重新提取（应使用该提交的checkout及仓库既有numpy/matplotlib依赖）：

```bash
python extract_formal_input.py --repo /path/to/3D_Manhattan_label
python recompute_bev.py
```

重新提取核对HEAD、原/选GT绑定、各源文件及LFS正文。稀疏checkout缺失的普通CSV/JSON可从同提交blob只读取得；缺失LFS正文直接失败。提取不写回正式仓库。

本次实际运行结果：

- 1060项复算断言通过。
- 31项pytest测试通过。
- 18个核心结果在独立临时目录回放后逐字节一致，涵盖新summary、几何变化、逐空间记录、source bindings和不可算清单。
- 24个提交文件验证通过，3441个正式对象保持指纹。
- 与仓库既有numpy投影最大坐标差4.44e-16 h。

测试覆盖：非嵌套集合、明确分母、有效与无效底面、相机边界、原环序、只变顶高不变底面、输入/门槛哈希篡改失败关闭、429记录及全部资格字段保留、两个恢复视角不进入研究分母、旧16/134完全一致、GT外扩展保留、面积净零但混合增减、多空间逐一输出且不择优、未确认替代空间拒绝、重复(image_code,region_id)拒绝、全部核心输出离线搬迁回放。

运行环境为Python 3.12.14、Shapely 2.1.2、pytest 9.1.1；正式提取另使用numpy 2.3.5及matplotlib 3.10.8。逐字节回放是在相同依赖环境下验证；不同库版本可能有极小浮点差异。本环境使用已存在的依赖目录，没有下载或安装新软件。

## 八、文件入口

- `inputs/raw_scope_return.json`：用户最终原回执，逐字节保存。
- `inputs/normalized_confirmation_overlay.json`：独立回执核验得到的35条确认层。
- `inputs/current_formal_subset.json`：35图研究/参考登记、33图429作答、当前正式输入全对象指纹及24个源文件绑定。
- `inputs/prior_confirmation_overlay.json`、`prior_reference_registry.json`、`prior_record_metrics.json`：此前16/134的冻结对照。
- `inputs/recovered/`：两个恢复视角的来源描述及精标快照记录。
- `inputs/input_manifest.json`：递归输入哈希；缺失、多出或变化均停止复算。
- `results/summary.json`：核心统计。
- `results/reference_registry.json`：逐确认空间登记、原环序地面、参考ID与顶界待定状态。
- `results/source_bindings.json`：逐空间回执JSON pointer、精确几何哈希、原/选GT身份和恢复来源。
- `results/record_metrics.json/.csv`：429个唯一作答行；每行包含完整逐空间结果。
- `results/space_record_metrics.json/.csv`：按(作答,空间)展开的易分析长表。本次429行，未来多空间时可多于作答数。
- `results/image_summary.json/.csv`：35图覆盖及primary范围诊断；参考-only图作答数为0。
- `results/condition_gate_summary.json/.csv`：条件和资格分层诊断，避免把held/excluded混成正式可评。
- `results/floor_geometry_changes.json/.csv`：35地面的新增、移除、净变化与明确分类容差；28修改的分类用于上表。
- `results/unavailable_records.json/.csv`：12份不可算的精确原因及未改动门槛。
- `results/previous_confirmed_floor_delta.json`：旧16地面完全不变证据。
- `results/historical_artifact_applicability.json`：旧三图完整Q实验的适用性说明。
- `results/source_provenance.json`、`validation.json`、`pytest.log`、`portability_validation.json`：提取、计算、测试与便携回放证据。
- `MANIFEST_SHA256.txt`：交付目录文件SHA256。

### 方法与源依据

- [正式输入合同](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/24360ad8544d76d8aba18a8e641f784a76ca0d42/docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json)
- [当前正式输入加载器](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/24360ad8544d76d8aba18a8e641f784a76ca0d42/tools/thesis_main/data_prep/consolidate_research_input.py)
- [既有范围投影及诊断](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/24360ad8544d76d8aba18a8e641f784a76ca0d42/analysis_results/image_difficulty_full_review_20261010/build_scope_review.py)
- [历史三图条件实验说明](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/24360ad8544d76d8aba18a8e641f784a76ca0d42/research/quality_scope_comparison_20261010/README_%E4%B8%89%E5%9B%BE%E5%AF%B9%E7%85%A7.md)
