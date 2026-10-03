# 融合结果工作台：全景与3D

推荐在仓库根目录启动本地HTTP服务，再打开[融合结果工作台](http://127.0.0.1:8879/analysis_results/consensus_result_studio_20261004/index.html)。本页以融合后上下角点和全景轮廓为主视图，复用已有空间标本工作台的3D墙体、纹理和线框。

- 当前只接入既有四例的全员结果，共24个标法簇候选；所有簇保留，不按GT或簇大小筛成唯一结果。
- 完整点候选沿用已有上下坐标与环序。3D只做`analyze(..., compute_fit=False, coordinate_convention='continuous')`显示重建，没有重新分簇、融合、评分或Manhattan拟合。
- 3D相机高度为相对单位1。上点深度沿用对应底点水平距离；墙顶封口是显示假设，不能解释成真实天花板深度或质量验证。
- ERP多数轮廓和Lee-BEV底边保留为方法对照；前者是稠密上下轮廓，后者只有底边，不冒充完整稀疏角点输出。
- 图片和共享渲染器沿仓库相对路径加载，没有复制或改写原图。保留完整仓库路径并通过本地HTTP服务访问；`file://`加载纹理可能受到浏览器跨域限制，单独复制此文件夹不足以携带依赖。
- 原始输入、既有指标与旧demo不改写。[旧详情](../lee_consensus_demos_20261003/index.html)保留人数和分组追溯。

字段见[field_contract.json](field_contract.json)，24份候选坐标／几何核对见[geometry_audit.json](geometry_audit.json)。所有成功重建的点数组与既有候选逐值完全相同，拟合状态为`not_requested`；不可用输入保留错误。

本地服务：在仓库根目录运行`python -m http.server 8879 --bind 127.0.0.1`。

复现：`python -B -m tools.thesis_main.analysis.consensus_result_studio_20261004 --out analysis_results/<新的目录>`。已有目录拒绝覆盖。前端适配器位于`tools/thesis_main/analysis/consensus_result_studio_20261004.js`及同名CSS；共享工作台文件保持原样。
