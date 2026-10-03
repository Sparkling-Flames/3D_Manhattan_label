# 全员融合结果工作台：全景与3D

打开[融合结果工作台](http://127.0.0.1:8879/analysis_results/consensus_result_studio_20261004/index.html)。默认展示同一张图全部当前人员形成的一份上下点共识；下方用同一组点和环显示3D。原有整份标法簇改为辅助页签。

- 四个固定案例分别使用22、15、15、8人的全员池，接入两种投票规则的8个输出。默认5°为未校准探索阈值，允许不同点数共同参与；失败显示为不可用，不改用最大簇。
- 保留24个原簇内候选供解释不同标法，与全员点身份分区严格区分。全员ERP上下轮廓、Lee底边并列对照；ERP尚无稀疏角点，Lee尚无top_y。
- GT默认关闭，构造与选择结果均不读GT。主图标明人数、点支持、连接不足和完整结构支持，后者不是坐标完全相同，也不要求输出复制某个人。
- 3D复用Panorama Studio，以`continuous`坐标且`compute_fit=False`显示，不拟合成Manhattan、不改候选点或环。相机高度为相对单位1，顶部深度沿用配对底点的水平距离；墙顶是代理重建。可绘制及`ok`都不等于物理真值或环序人工确认。
- 来源坐标、资格、人工确认环和旧Lee结果不改写。图片与共享渲染器沿仓库相对路径引用，没有复制原图；单独复制该目录不足以携带依赖。

整体证据见[137图基础报告](../global_pair_consensus_20261004/REPORT.md)及[Pro独立审查](../../research/full_layout_pro_review_20261004/REVIEW.md)。[字段合同](field_contract.json)、[全员8输出展示绑定](global_display_audit.json)、[历史24簇候选绑定](geometry_audit.json)、[浏览器检查](ui_check.json)分别记录范围，不能把簇候选数当作全图共识数。

在仓库根目录运行`python -m http.server 8879 --bind 127.0.0.1`。复现工作台用`python -B -m tools.thesis_main.analysis.consensus_result_studio_20261004 --out analysis_results/<新的目录>`；默认读取已完成的137图点结果，也可显式传`--global-results`。已有输出目录拒绝覆盖。

前端在`tools/thesis_main/analysis/consensus_result_studio_20261004.js`及同名CSS。共享工作台不属于本轮修改。截图仅内联目视检查，无截图文件留存。
