# 独立全景布局预览：当前可运行版本

2026-09-06：当前为显示层 v2。原 v1 包作为视觉对照保留；几何 schema 仍为 v1。

## v2 显示修正与验证

- 当前入口：[空间标本 v2](../../analysis_results/panorama_studio_20260906_v2/index.html)。先展示完整墙体、隐藏天花板；全景证据面板移到模型下方，按需展开。双模型实际画布顶部由约 559px 提前至约 310px（1512×1100 窗口）。
- 轴测、俯视使用正交相机，室内使用独立的 65° 透视相机。双窗共享观察方向、缩放和正交垂直范围；切换来源或材质保留相机，重置按钮重新构图。
- 移除按朝向逐墙隐藏，改为共享的水平剖切平面。保留高度按原始/拟合的共同竖直范围计算；绿色截交线由实际墙面三角形与平面的交点生成。原始非共面墙仍按其三角形代理展示，不伪装成正确墙面。
- 背景为独立的中性灰，去掉矩形底板与方向硬阴影；白模采用中性粗糙材质和无阴影的主光/填光。可选接触阴影是地面轮廓距离的柔化显示效果，不是物理光照模拟或几何证据。纹理模式不叠加该白模光照。
- 角点标记和鼠标拾取默认检查真实表面遮挡及剖切范围；显式打开“透视标记”才允许穿墙查看未剖掉的端点。可一键进入无装饰、无剖切的线框诊断。
- 标题和说明移到画布外，正文增大；侧栏可收起，局部图仅在选择后出现。图像失败显示原因，切换案例会清理旧状态。

```powershell
.venv/Scripts/python.exe -m tools.label_studio.panorama_studio.build --manifest analysis_results/panorama_studio_20260906_v1/input_manifest.json --out analysis_results/panorama_studio_20260906_v2
```

验证：12 项几何测试通过；浏览器遍历 75 个版本，无页面或控制台错误。新增检查覆盖正交相机、共享剖切及截交线、遮挡拾取、来源切换保留相机、8 方向纹理色块、图像解码失败后恢复、390px 无横向溢出。全部 75 份原始与拟合几何与 v1 完全相同。最终浏览器证据见 v2 `browser_qa/QA.json`；已查看白模、纹理剖切和室内截图。没有新增模型推理、标注裁决或 A line 质量结论。

下面记录 v1 的输入合同与历史实现状态；关于相机、前墙隐藏、展台和视觉待办，以本节 v2 为准。源文件沿用原目录，旧输出 HTML/JS 未覆盖。

## 打开与生成

- 历史入口：[空间标本 v1](../../analysis_results/panorama_studio_20260906_v1/index.html)。可在本地浏览器直接打开，脚本与图像均已打包，不需要网络或计算服务。
- 工具：`tools/label_studio/panorama_studio/`。几何计算、生成脚本和前端独立于原预览；仅使用已有 Three.js / OrbitControls 基础库。
- 默认展示公开数据集布局，不按拟合成功与否选择展示版本。来源下拉框可切换历史人工导出、工人标注、HoHoNet 离线结果及 Bi 两头。

```powershell
.venv/Scripts/python.exe -m tools.label_studio.panorama_studio.build --demo --out analysis_results/panorama_studio_20260906_v1
.venv/Scripts/python.exe -m tools.label_studio.panorama_studio.build --manifest MY_MANIFEST.json --out analysis_results/MY_STUDIO
.venv/Scripts/python.exe -m pytest tests/test_panorama_studio.py -q
```

自定义 manifest 的最小格式如下，路径按运行时工作目录解析：

```json
{
  "cases": [{
    "image_id": "example",
    "title": "我的房间",
    "image": "D:/images/example.png",
    "variants": [{"name": "原始标注", "path": "D:/layouts/example.txt", "width": 1024, "height": 512}]
  }]
}
```

TXT 为交替排列的上、下端点像素坐标，每行 `x y`。JSON 布局必须包含 `width`、`height`、`coordinate_mode`（`pixels` 或 `ls_percent`）、`ordered_pairs`；每对包含 `top:{x,y}`、`bottom:{x,y}`，可带唯一的 `source_pair_id`。不猜测坐标单位、不重排原始点序。

输出的 `input_manifest.json` 保留输入来源，`geometry_audit.json` 保留逐版本原始坐标、重建结果、拟合状态、偏差和失败原因；`data.js` 为浏览器数据副本，`image_*.js` 为图像包。几何 schema 为 `panorama_studio_v1`，不改变仓库正式 schema。

## 当前能力与假设

- 白模、纹理、线框；双窗同步旋转、缩放和平移；俯视、轴测、相机原点观察；天花板、前墙、编号、展台显隐；单窗放大与全景图折叠。
- 点击墙面或角点可联动全景图、三维视窗和跨接缝局部图。不同来源的相同显示编号不自动视为同一语义角点，切换来源会清除选中状态。
- 相机为原点，Y 轴向上，离地高度为 1 个相对单位；没有真实尺度依据时不报告米。
- 原始上端点采用其自身射线及对应地面点的水平距离。这是明确的重建代理，不能解释成观测到的天花板深度。
- 约束结果固定角点数量、顺序与基线主方向，使用 SciPy SLSQP 最小化各端点等权的球面角距离平方均值。相邻边允许共线，优化不生成新的角点对应关系。
- 0.5° 近地平线检查、40° 墙向归属检查属于当前工程保护设置，不是人员质量阈值或正式研究协议。自交、退化、可见性或方向归属未解决时不强行拟合。
- 三角化仅用于有效多边形；异常输入保留可解析线框。原始与拟合使用相同相机、尺度和展示设置。

## 与 A line 的关系

复查了「a线8」、`manhattan_3d_projection.py`、`run_manhattan_worker_gt_calibration.py` 及既有 12 图 / 312 标注校准摘要。

旧流程会对角点对按横坐标排序，部分路径平均上下横坐标、截断近地平线角度，并使用 1.6 的相机高度。当前实现保留输入顺序、上下各自射线，不做该截断，默认相对高度为 1。正常、上下对齐且远离地平线的点使用相同球面坐标约定，但整体尺度及诊断定义需要区分，不能直接混合数值。

示例中的历史精标导出按原始顺序展示，不冒充旧流程整理后的参考。既有审计 CSV 仅用于定位真实导出身份、保留旧诊断数值；标注坐标重新读取 `export_label/`。HoHoNet / Bi 为已有离线推理产物，不当作实际历史初始化。

保留了既有反例对应的实际人员记录：task 625 的 ann3285 和 ann4744 等。旧面板中，最低墙向残差仅在 2/12 图命中最佳 `q_boundary`，在 0/12 图命中最佳 `q_wallwall`；这些是历史审计结果，本轮不声称重新计算该质量面板。更规整、更漂亮不代表更正确。

## 验证与本次收口

- 几何测试：12 项通过，覆盖矩形、凹形、共线点、投影往返、相对尺度、身份保留、错误顺序、上下横坐标不一致、地平线、重复/退化、TXT/百分比 JSON 和非有限坐标。
- 示例：12 图、75 个版本，61 个拟合成功、14 个保留阻断原因、0 个输入解析失败。样本是工程验证集，不具有研究代表性。
- 实际 Chromium / WebGL 检查通过：全部 75 个版本载入，局部选择、双窗相机、纹理、前墙隐藏、单窗放大、全景折叠、390px 窄屏无横向溢出；浏览器无报错。展示开关前后的几何 JSON 完全一致。
- 验证脚本：`tests/panorama_studio_browser.cjs`；用 Node 执行，必要时通过 `PLAYWRIGHT_MODULE` 指向本地 Playwright 模块。截图及最终结果见示例包 `browser_qa/QA.json` 与 `01_clay.png`、`02_texture.png` 等。`failure.png` 为首次测试遇到默认历史精标点序异常时的中间截图，不是最终结果。
- 已人工查看白模、纹理和室内视角截图。当前展台阴影仍偏硬、色温偏暖；按用户要求停在当前版本，未继续做接触阴影和灯光精修。
- 仍未完成：独立的 A line 数值差异回归测试、模拟资源缺失的自动化检查及更细的视觉调优。本轮不把代码/材料检查冒充这些验证。

原预览、A line 源码、人工记录、运行时数据及正式协议均未修改。新增入口已在仓库索引与地图登记；未创建提交。
