# HoHoNet 标注员使用手册 (Annotator Guide)

欢迎参与 HoHoNet 标注任务！本手册将指导你完成环境配置并开始标注。

## 1. 环境配置 (只需执行一次)

为了在标注时实时预览 3D 效果，你需要安装浏览器插件并配置密钥。

### 第一步：安装 Tampermonkey (篡改猴)

1.  在 Chrome 或 Edge 商店搜索并安装 **Tampermonkey** 插件。
2.  点击插件图标 -> "添加新脚本"。
3.  将管理员提供的 `tools/official/ls_userscript_annotator.js` 内容全部覆盖粘贴进去并保存 (Ctrl+S)。

### 第二步：配置连接密钥 (Token)

1.  打开 Label Studio 标注页面。
2.  按下 `F12` 键打开开发者工具，切换到 **Console (控制台)** 选项卡。
3.  输入以下代码并回车：
    ```javascript
    localStorage.setItem("HOHONET_LOG_TOKEN", "hoho-20260228-zjw200408250904!");
    localStorage.setItem("HOHONET_HELPER_BASE_URL", "http://175.178.71.217:8000");
    ```
4.  如果管理员已把 `/tools/vis_3d.html` 反代到 Label Studio 同源，再额外执行：
    ```javascript
    localStorage.setItem("HOHONET_VIEWER_BASE_URL", location.origin);
    ```
5.  刷新页面。

---

## 2. 标注流程

### 2.1 开始标注

1.  登录平台，进入分配给你的项目。
2.  点击 **"Label All Tasks"**。

### 2.2 核心操作

**标注对象规则（请务必遵守）**：只标 **相机所在的主房间（camera room）** 的布局包络。

- 门洞后/走廊/相邻房间等“连通空间”默认不纳入当前房间布局。
- 不要以“3D 更方正”为依据扩大房间范围；以“主房间边界是否可合理闭合”为准。

核心操作：

1.  **微调角点 (Corner)**: 拖动红色的点，使其精确对齐天花板与墙壁、地板与墙壁的交界处（以主房间为准）。
2.  **垂直对齐**: 确保同一面墙的上下两个角点在垂直方向上是对齐的。
3.  **3D 预览**:

    - 点击下方的 **"🔄 刷新 3D 视图"** 按钮。
    - 在右侧 3D 窗口检查房间形状是否正确。
    - **操作**: 左键旋转，右键平移，滚轮缩放。

4.  **难度/异常反馈 (Difficulty & Issues)**：请按下面顺序填写（这是新版三字段，统计更严谨）。

        - **范围判定 `scope`（单选：决定是否进入主指标）**
            - `In-scope：只标相机房间 (Normal / Camera room only)`：能在不"猜"的情况下稳定闭合包络，即墙-天花与墙-地面的外边界可形成唯一、可复现的包络（存在稳定的 y_ceil(x), y_floor(x)）。
            - `OOS：几何假设不成立 / 边界不可判定 / 错层多平面 / 证据不足`：主指标剔除（单列统计）。

            门洞规则：如果门框/墙垛清晰，边界止于门框处，不跨门洞，仍选 `In-scope`；只有当没有可靠停止点、必须猜边界时，才选 `OOS：边界不可判定`。

        - **困难因素 `difficulty`（多选：解释耗时/误差来源）**
            - 遮挡 / 低纹理 / 拼接缝拉伸 / 反光玻璃 / `画质差/被遮罩影响 (Blur/Masked/Low quality)`（例如上下被 mask/黑边导致证据缺失）
            - `尽力调整但 3D 仍不佳 (Hard to align / residual)`：遵守规则并充分调整后，3D 仍不稳定或明显畸形（不等同于 OOS）。

        - **模型初始化问题 `model_issue`（仅半自动项目，多选；初始化很好无需修改可不选；OOS 时允许不选）**
            - 跨门扩张 / 漏标 / 角点漂移 / **角点重复/一角多点**（新）/ 配对异常 / 预标注失效

### 2.3 提交

- 检查无误后，点击右下角的 **"Submit"** (提交) 或 **"Update"** (更新)。

---

## 3. 常见问题

- **看不到 3D 窗口**: 检查 Tampermonkey 脚本是否已启用，并确认 `HOHONET_HELPER_BASE_URL` 设置正确。
- **3D 视图里没有图片**: 刷新页面重试，或联系管理员检查服务器配置。
- **控制台里出现关于 8000 iframe 的 CSP report-only 提示**: 这通常表示 3D viewer 仍在走跨源 iframe。若管理员已配置同源 `/tools` 代理，请执行 `localStorage.setItem("HOHONET_VIEWER_BASE_URL", location.origin)` 后刷新。
- **无法提交**: 确保所有必填标签（如 Quality Feedback）已勾选。

---

_如有疑问，请在标注群内联系技术支持。_
