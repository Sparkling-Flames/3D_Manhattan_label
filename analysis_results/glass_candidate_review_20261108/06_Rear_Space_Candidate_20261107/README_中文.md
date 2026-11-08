# 06后侧空间 B候选：三张图与当前代码

本包只包含本次提供的B候选，不代表已确认的完整房间还原。三张PNG与当时提供的图片保持原字节；两份可编辑工程也按冻结文件原样保存。

## 内容

- 根目录三图：Detail为后侧局部、Main为整体预览、Plan为中文估计平面示意。
- `models/B.blend`：三图对应的展示工程；`B_full_model.blend`：对应完整模型状态，可编辑。
- `code/snapshots/B/`：两份当前几何、对象、曲线、修饰器、集合、灯光与相机快照。
- `code/assets/B/`：无任何几何或对象的原生材质/世界/渲染模板，画作纹理已内嵌。
- `code/assets/fonts/`：计划图使用的原版Noto Sans CJK字体；许可见`code/assets/FONT_LICENSE.txt`。
- `verification/`：输入冻结哈希、几何检查、重建与图像复现核验。根清单可检查完整性。

代码从快照重新建立当前全工程，不是只打开完整模型渲染；着色模板保留原生节点以避免转换损失。这是当前几何状态的可重建代码，不是从照片自动推断房间，也不是最初逐步建模的历史脚本。无需其他案例、原始全景、旧项目或网络才能运行。

## 使用

Blender **5.2.3 LTS**。3D重建与渲染入口需要Python **3.9以上**，仅使用标准库；计划图需要Python **3.11以上**及**Pillow 13.0.0**（该Pillow版本要求Python≥3.11），所用字体已随包附带。完整重出三张图时请使用Python 3.11以上。

在本包目录运行，将Blender路径替换为实际可执行文件路径：

```bash
# 仅计划图需要此依赖；已有匹配Pillow时无需重复安装。
python -m pip install -r code/requirements.txt

# 检查交付文件。
python code/scripts/verify_package.py

# 重建两份工程，保存后重开并核验。
python code/run.py --blender "/你的路径/blender" --output "./rebuilt"

# 从当前快照重建，并重出本次三张预览图。
python code/run.py --blender "/你的路径/blender" --variant both --render --output "./reproduced"

# 单独重出计划图，无需启动Blender。
python code/draw_plan.py --output "./plan.png"
```

`--views main rear plan`指定重出哪些图；`--samples`默认12，`--percentage`默认100。快速检查可改为25%和8 samples，但不用于替代本次原图。视图渲染使用`B`展示状态，`B_full_model`仅重建保存，不将顶盖遮挡状态误当作展示图。

主、后侧图均为900×694、Cycles CPU、12 samples、固定2线程。主相机`MAIN`，后侧相机`B_REAR_BRANCH_REVIEW`；继承AgX、Medium High Contrast、透明底及保存的可见性。只把渲染alpha合成为白底，不重绘几何像素。渲染覆盖参数不另存回输入工程。计划图为1400×1450，按脚本内的估计参数绘制，不是自动模型投影；修改几何时需同步修改示意参数。

## 解释边界

新增尺寸均属讨论估计，不是实测或GT标定。2.30m岛台不比此前2.70m具有更准确的证据；后支段约2.2m深、约0.93m净宽、柜后墙可能作为内隔墙的解释均未确认。

冰箱到照片23的连通路线、23门的位置及完整后界尚未证实。支段开放端与虚线仅表示未建/未知范围，不等同真实走道终点；没有补成完整后侧房间。照片中的灰色后退实面位置未定，已放在禁用集合中，不应据此另造门洞。保留的0.705m通道也不表示规范合规认证。

原有其他交付与模型不在本包内，未被本次打包修改。
