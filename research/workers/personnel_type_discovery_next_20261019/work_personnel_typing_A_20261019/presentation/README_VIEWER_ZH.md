# Part A 人员类型与同背景替换离线展示

交付入口为 `personnel_types_part_a.html`。它是单个自包含 HTML，压缩数据、少量案例原图、字体和绘图代码均在文件内；不连接网站、不修改数据、不运行新的分类或融合。解压交付包后，用支持 `DecompressionStream` 的现代浏览器打开即可。`personnel_types_part_a_preview.html` 是开发时的旧标签骨架，不能替代正式入口。

## 可以查看什么

- **人员类别与解释**：60 人按人员 ID 展示；选择正向、反向、旧 QT/QTD 或明确保留的诊断方案。默认使用排除当前图所在建筑的训练标签和历史画像，另有明确标识的全量描述模式。困难／中等／简单条件类别优先匹配当前图的冻结难度，然后才使用基础类别。编号跨折不自动对应，未知类别保留。
- **整图标法簇**：177 个普通 Manual 合格池、5,719 份真实冻结作答，均提供 9°／12°全局亲近度与同距离完整链接对照。整簇和逐人开关使用真实成员；不同点对数不合簇。可以按当图局部簇、当前人员类或人员 ID 着色。局部 C01 等编号仅在该图有效。
- **同背景 A/B 与反例**：只载入主研究者按保存规则选定的有限事件。两队人员及共同背景、参考、完整状态、时间覆盖和失败均可追溯。质量变化、范围变化、上／下端点、节点、连接和联合容差分别列出。本次嵌入的 7 例均为主面板 k16，不拼接成完整曲线。读取器也支持同一新背景链的 8/12/16/24 已算节点，但本次有限案例没有选入该链，不能称已在本页展示新链过程。
- **联动显示**：人员表可跳到该类在当前图上的所有已作答成员；案例可跳到两位换入人员各自整簇的并集。ERP、BEV 与逐角高度 3D 共用选中成员。两队 A/B 的 BEV 和 3D 使用同一坐标范围，3D 可拖动、滚轮缩放或方向键旋转。

类别标签仅代表已保存的候选／训练选择；方案出现于下拉框不等于已经建议正式采用。采集前预测类别与目标作答后的局部簇分别显示，后者不能冒充事前人员类型。

## 输入与计算来源

页面使用 `assessment/ALL_SELECTED_AND_BASELINE_LABELS.csv.gz` 的冻结合并标签，使用 `forward/fold_features.csv.gz` 的全量及外层训练画像。几何、资格、参考及四种局部分区来自恢复后的 Pro `fusion/INPUT_SNAPSHOT.json.gz` 与 `clusters/CLUSTER_API.json.gz`。本页不回到原始导出覆盖点位、平均 x、删点或绑定环序。

案例团队来自本轮原生融合重放的 `events/native_runs/pools/`，事件数值来自 `events/common_events.csv.gz`。全共同面板为 270,370 个原精确背景事件及 16,296 个新增固定身份、嵌套背景事件；58,882 端点请求对应 58,679 个不同实际团队。旧省略状态缓存没有被声称完整读取。本轮重放的数量、输入摘要和原输出子集数值复核见 `events/FULL_RUN_RECEIPT.json` 与 `events/EVENT_VERIFICATION_RECEIPT.json`。

ERP、BEV、3D 的几何投影函数从恢复后的 Pro `presentation/viewer_template.html` 按固定代码块提取。显示层增加了原图未嵌入的网格说明、嵌入字体和当前结果的数据绑定；密集线框中将参考最后绘制以保证可见。球面距离、投票、连接、融合结果和评分均未修改。B8L2 为主线，D10 保留方向尺度敏感性；N1 未接入。

## 原图与有限视觉材料

`CASE_SELECTION.json` 保存主研究者给出的精确案例、用途、规则和筛选分母。`fetch_case_images.py` 只取得这些案例所涉及的既有公开 Release 档案，再只提取指定图像；完整档案与逐图 SHA256 均核对。`CASE_IMAGE_RECEIPT.json` 记录实际获取范围，不把下载称为视觉审查。

本页普通 Manual 的 177 图中，175 图有可用原图；为控制离线体积，嵌入其中 7 张案例的 JPEG 预览，其余 168 图明示“本页未嵌入”，不表示原图不存在。`2t7WUuJeko7-02`、`2t7WUuJeko7-03` 仍只使用仓库已有预览，不声称完成原图视觉核验。页面的几何浏览不依赖原图是否嵌入。

## 复建与检查

在交付根目录、完成恢复输入和主分析后运行：

```bash
python presentation/fetch_case_images.py --cases presentation/CASE_SELECTION.json
python presentation/build_part_a_viewer.py --cases presentation/CASE_SELECTION.json
node presentation/qa_part_a_viewer.cjs personnel_types_part_a.html
```

第一条需要访问用户指定的公开 Release；后两条读取现有结果，不增加统计试验。构建依赖 Python 3.12、numpy 2.3.5、pandas 2.2.3、Pillow 12.3.0、fontTools 4.61.1；绘图字体是随恢复输入保留的 Noto CJK，子集及原版权依 SIL Open Font License 1.1 随文件提供。

QA 使用 Node 的 `jsdom@30.1.3` 与运行环境已有的 `@napi-rs/canvas`。如果本地没有 jsdom，可按 `qa_runtime/package-lock.json` 恢复；`CODEX_PRIMARY_RUNTIME_NODE_MODULES` 可指定已有原生 canvas 依赖路径。QA 校验全部分区、真实成员、冻结标签、案例两端共同背景和嵌套顺序，并触发控件及生成实际 canvas PNG。

**检查边界**：本轮尝试下载 Chromium 时，公开下载地址返回了 `Site Unavailable` HTML，未能取得浏览器；日志保留于 `events/chromium_install.log`。因此本轮只完成 jsdom 的 DOM／交互和 native canvas 渲染检查，没有真实浏览器整页布局截图验证。生成 canvas PNG 与人工打开 PNG 的范围分别记录，不声称已经视觉审查所有作答或原图。

`VIEWER_BUILD_RECEIPT.json`、`VIEWER_INPUT_CASE_MANIFEST.json`、`CASE_IMAGE_RECEIPT.json`、`qa/VIEWER_QA.json` 记录本次正式文件摘要、覆盖和检查结果。最终文件通过 230 项 DOM／原生 canvas 检查，14 个真实团队与 7 个同背景事件完整追溯；这些是显示和数据完整性检查，不是新的统计验证。`VISUAL_REVIEW.json` 逐项记录助理实际打开的 13 张最终画布、对应 5 个案例图的缩放 ERP 上下文及几何视图；另外 2 个案例原图仅完成获取和渲染，不计入本助理的视觉判读。没有进行原图全分辨率审查、人工金标裁定或 177 图全面视觉审查。若案例或标签尚未提供，预览模式会显式标识这一状态，不用历史展示伪装本轮完成结果。

## 有限证据包与体积

`CASE_EVIDENCE_FULL.json.gz` 约 170 KB，保留 7 例的整池作答、精确两端请求、结果和完整 native 状态；其中事件字段明确保留原 CSV 文本类型，团队结果和状态使用原 JSON 类型。正式 HTML 约 5.4 MB，可独立打开。发布交付时可省略 `release_cache/`、`qa_runtime/node_modules/` 与开发预览，它们有公开来源、锁文件及精确重建入口；不应把省略的下载缓存误称未取得案例图。
