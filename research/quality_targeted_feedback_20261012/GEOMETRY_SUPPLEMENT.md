# C02 / C01 几何辅助复核

请求：2026-10-12 用户要求具体数值与可旋转3D；仅补充原有 Site，不覆盖旧9组回执。

输入：quality_structure_height_extension_20261012_v1.zip，SHA256 398cc1aa6e76e68a6486d670e951d45d0fc3e2fc3ef4c47dff15578a3bf14d42；使用 structure/review_pairs/inputs/selected_pairs_full.json 中固定的 top3d/bottom3d 与 selection_research.json 的原始几何指标核对。4份作答，2个同图对照。坐标未做吸附、平顶拟合、缩放配准或新推断。

重建数据：python3 build_geometry_supplement.py --study-root <解压后的 structure_height_preference_20261012 目录>。逐例独立复算底面面积、凸参考裁剪IoU、最佳正交轴方向误差D、沿墙长积分平均高度，分别核对 Pro 的 IoU、D、Hmean，误差阈值1e-9。高度标准差与极差为直观诊断量，明确不等于 Hcenter；不显示候选总分。

UI：无外部依赖，Canvas正交投影，A/B共享中心、半径、旋转与缩放；保留原顶角高度，仅绘顶环不填虚构平顶。数值表内角可点选高亮，支持鼠标/触摸旋转、滚轮和键盘。数值辅助回执独立localStorage键、dataset、schema与导出；空白不算负例。

验证：Node语法、旧回执状态测试、新投影与状态测试通过。Chromium在环境中因socket权限被拒绝而未能启动，浏览器交互测试未执行，不声明全浏览器QA通过。
