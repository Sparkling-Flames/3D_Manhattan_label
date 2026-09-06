# 研究分析交付入口

## 2026-09-06：瓶颈五项前置研究

[完整报告](analysis_results/preflight_20260906_v2/REPORT_ZH.md) · [文献及算法模拟](analysis_results/preflight_20260906_v2/REFERENCES_AND_SIMULATION.md) · [一页讨论HTML](analysis_results/preflight_20260906_v2/DISCUSSION_ONE_PAGE.html)

[真实图像案例卡：GitHub可读](analysis_results/preflight_20260906_v2/cases/CASE_CARDS.md) · [离线案例HTML](analysis_results/preflight_20260906_v2/cases/index.html)

[完整ZIP](analysis_results/preflight_20260906_v2/preflight_analysis_20260906.zip) · [ZIP SHA-256](analysis_results/preflight_20260906_v2/preflight_analysis_20260906.zip.sha256) · [逐文件清单](analysis_results/preflight_20260906_v2/DELIVERY_MANIFEST.json)

[所有普通结果文件](analysis_results/preflight_20260906_v2/)：包括人数/分母/容差、相同留出建筑下的早期预测、失败案例、当前20人支持缺口、固定面板依赖和随机分组基准。完整逐次预测存为CSV.GZ，未因文件较大而隐藏。

HTML在GitHub页面上可能显示源码；下载后用浏览器打开，或解压ZIP后打开。Markdown和CSV可直接在仓库浏览。

[复现和交付故障说明](analysis_results/preflight_20260906_v2/DELIVERY_AND_REPRODUCTION.md)。此前bottleneck远端分析因编码源码损坏未运行，旧包没有被伪称为完整恢复；本轮使用可读源码重新构建核心与新增研究。

## 后续分析的最低交付要求

新的结果目录必须同时提交报告、关键明细、运行参数/来源、可运行源码和清单；不能只上传四个执行文件就宣布完成。调用通用验证器`tools/thesis_main/analysis/verify_analysis_delivery.py`验证本地SHA、ZIP CRC、成员SHA，以及main读回的实际字节。Actions artifact仅作第二份备份，不取代普通文件和ZIP进入main。

本入口不规定论文最终方向，不改变导师与研究者共同确定研究问题的边界。
