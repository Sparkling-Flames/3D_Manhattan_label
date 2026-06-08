# VIS 3D Geometry Compatibility Spec v1

本文档定义实验外 realtime Manhattan assistant 必须遵守的 3D preview 几何兼容性边界。目标是让 future assistant 与当前 HoHoNet / 3D preview 坐标语义一致，而不是另起一套 BEV 或 3D 解释。

## 1. 目标

Realtime Manhattan assistant 的几何逻辑必须与当前 3D preview 逻辑兼容。若同一输入在 current 3D preview 与 future assistant 中产生不同的 polygon、corner order、floor/ceiling pairing、height 或坐标轴语义，assistant 不得输出 adjustment suggestion，只能输出 `compatibility_failure`。

该 spec 只服务实验外 expert-side / lab-side prototype。它不得进入当前实验 worker-facing UI。

## 2. 当前 2D keypoints 到 3D preview 的路径

当前正式 worker-facing 路径是：

1. `tools/label_studio/label_studio_view_config.xml` 定义 2D 标注入口：
   - `<Image name="img" value="$image">`
   - `<KeyPointLabels name="kp" toName="img">`
   - 右侧 `<HyperText name="vis_3d" value="$vis_3d">`
2. `tools/label_studio/official/ls_userscript_annotator.js` 从 Label Studio selected annotation 读取 `results`。
3. Userscript 优先使用 `keypointlabels` / `keypointregion`。
4. `value.x` / `value.y` 或包装后的 `value.value.x` / `value.value.y` 被视为百分比坐标。
5. Userscript 用当前 preview 宽高将百分比坐标转为像素：
   - `px = x * W / 100`
   - `py = y * H / 100`
   - 默认 `W=1024`、`H=512`，也可从 iframe query 读取。
6. Keypoints 按像素 `x` 排序。
7. Userscript 用 `threshold = W * 0.05` 做 x-sort 后的 nearest-x greedy pairing：对每个未使用点，扫描其右侧所有未使用点，选择满足 `diff < threshold` 且 `diff` 最小的候选。阈值边界是严格小于，不包含 `diff == threshold`。
8. 每个 pair 形成：
   - `x = mean(p1.x, p2.x)`
   - `y_ceiling = min(p1.y, p2.y)`
   - `y_floor = max(p1.y, p2.y)`
   - `originalPoints = [p1, p2]`
9. Userscript 发送 `postMessage({ type: "update_layout", corners, baseCorners, width, height, imageUrl, preserveOrder, previewOrder, previewSignature })` 到 `tools/vis_3d.html`。

`tools/label_studio/ls_3d_logic.js` 也包含早期 preview 逻辑：从 `keypointlabels` 读取百分比点、转像素、按 `x` 排序、用 `W*0.05` 配对，并把 pair 渲染为 ceiling / floor lines。该旧逻辑使用 first-match greedy；当前 official userscript 使用 nearest-x greedy。未来 compatibility work 应优先以 official userscript + `vis_3d.html` 为准，同时记录与 `ls_3d_logic.js` 的差异。

## 3. `vis_3d.html` corner order 假设

`vis_3d.html` 接收的 corner item 语义为：

- `x`
- `y_ceiling`
- `y_floor`
- optional `originalPoints`

渲染时：

- 若 `preserveOrder=true`，保持 userscript 传入顺序。
- 否则按 `x` 升序排序。
- Preview order override 只改变 preview order，不应被解释为正式 annotation 修改。

Future assistant 必须以同一 ordered corner list 为输入。若需要提出 order adjustment suggestion，只能生成 preview-only candidate，不能覆盖正式标注结果。

## 4. 坐标单位与 3D 坐标轴语义

当前 pipeline 中存在三类坐标：

- Label Studio 百分比坐标：`value.x` / `value.y` in `[0,100]`。
- 像素坐标：`x * W / 100`、`y * H / 100`。
- Three.js 坐标：`vis_3d.html` 内部生成。

`vis_3d.html` 的核心投影逻辑：

- `u = (corner.x / W) * 2π - π`
- `vFloor = (corner.y_floor / H - 0.5) * π`
- `vCeil = (corner.y_ceiling / H - 0.5) * π`
- `CAM_H = 1.6`
- `safeFloor = clamp(vFloor, 0.01, 1.5)`
- `dist = CAM_H / tan(safeFloor)`
- `x3 = dist * sin(u)`
- `z3 = -dist * cos(u)`
- `yFloor = -CAM_H`
- `safeCeil = clamp(vCeil, -1.5, -0.01)`
- `yCeil = -dist * tan(safeCeil)`

因此 current preview 的 floor plane 固定为 `y=-1.6`，camera height 固定为 `1.6`。未来 assistant 的 3D compatibility check 不得使用不同 room-height 语义替代当前 preview。

## 5. Polygon closure 与 invalid layout 表现

`vis_3d.html` 对 non-empty `ceilPoints` / `floorPoints` 会把第一个点追加到末尾以闭合 loop。墙面通过相邻 ceiling/floor pair 生成两个三角形，floor 以 `(0, -CAM_H, 0)` 为 fan center。

当前 preview 没有显式 self-intersection checker。以下问题通常会表现为 3D preview “不方正”、扭曲或不稳定：

- keypoint 数量为奇数，导致一个点无法配对；
- duplicate / near-duplicate corner；
- ceiling/floor pair 的 `x` 不够接近；
- greedy nearest-x pairing 配错；
- corner order 与真实 room order 不一致；
- wraparound seam 附近的左右边界排序错误；
- open boundary 或 split-level 被误当作 normal；
- 过高或过低的 `y_floor` / `y_ceiling` 被 clamp 后导致深度失真；
- polygon 自交，但 preview 仍尝试渲染。

Future assistant 必须先判断是否与 current preview geometry compatible。若出现无法解释的 order/pairing/closure mismatch，应输出 `compatibility_failure`，而不是给出 snap suggestion。

## 6. Compatibility tests / fixtures plan

后续只写计划，本轮不写代码：

1. 选择 3-5 个已知 layout fixture：
   - axis-aligned clean rectangle；
   - wraparound seam case；
   - duplicate / near-duplicate corner case；
   - odd keypoint count case；
   - self-intersecting or wrong-order case。
2. 同一输入分别经过 current 3D preview 和 future Manhattan assistant。
3. 检查以下对象是否一致：
   - polygon / wall order；
   - corner order；
   - `x/y_ceiling/y_floor` pair；
   - room height / camera height semantics；
   - floor / ceiling pairing；
   - closure handling。
4. 若不一致，assistant 不得给 adjustment suggestion，只能输出 `compatibility_failure`。

## 7. 禁止

- 不绕过现有 3D preview 逻辑。
- 不用独立 BEV 解释替代当前 preview。
- 不在当前实验 worker-facing UI 中显示提示。
- 不自动覆盖标注结果。
- 不把 preview-only snapped candidate 写回 Label Studio annotation。
- 不把 compatibility check 写成 correctness metric、formal `g_t` 或 routing input。
