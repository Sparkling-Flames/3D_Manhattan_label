# 六图并行研究返回

先读 `REPORT_ZH.md`，看图打开 `GALLERY.html`。

六图118份输入记录，109份按既有规则纳入，来自24名人员；9份历史/排除记录不投票。特殊场景四图新算全员区域，细节两图复用现成全员区域。没有重跑Codex的57池或人数/构成面板。

`results/full_consensus.geojson`包含12个完整区域（6图×2规则），不包含生成的上界。`results/roster.csv`列出完整人员与资格。`results/diagnostic_patches.geojson`是另行标记的两处只读测量窗口，不是GT、候选或额外票。

输入副本位于inputs。运行 `python reproduce.py --out reproduced` 即可复算本次有限内容；依赖见requirements.txt。报告数字对应results。没有更改源坐标、GT、门槛或人员主质量资格。

uNb-47的+90°结果只在 `uNb47_orientation_diagnostic.json` 中作为一次图像驱动的诊断，不进入任何主表、人员分数或全员区域。报告保留未旋转两版参考。

本轮数值绘图均来自实际文件和计算，没有使用生成式图片。
