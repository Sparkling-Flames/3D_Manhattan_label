# 路线A方法文献与本轮对应关系

Jérôme Kunegis, Stephan Schmidt, Andreas Lommatzsch, Jürgen Lerner, Ernesto W. De Luca, and Sahin Albayrak. 2010. **Spectral Analysis of Signed Graphs for Clustering, Prediction and Visualization.** *Proceedings of the 2010 SIAM International Conference on Data Mining*, pp. 559–570. DOI: [10.1137/1.9781611972801.49](https://doi.org/10.1137/1.9781611972801.49).

- [作者机构官方PDF](https://www.uni-konstanz.de/algo/publications/ksllda-sasgcpv-10.pdf)
- [SIAM出版方PDF](https://epubs.siam.org/doi/pdf/10.1137/1.9781611972801.49)

本轮已直接核阅作者机构PDF的有符号图定义：度矩阵取`D_ii = sum_j |A_ij|`，对称归一化拉普拉斯为`I - D^(-1/2) A D^(-1/2)`。路线A2在保持本轮关系定义的前提下，取相应归一化有符号邻接矩阵的最大特征向量空间，再用固定种子的KMeans离散化。

这条引用支持算子与有符号关系分区的方法来源。跨图同点数关系、同图来源组合中心化、建筑等权、两栋楼收缩先验、K的小规模候选与开发建筑选择、楼外检验和具体成员均为本轮研究设计及数据结果，不冒充原论文结论。Q、参考与融合结果没有进入路线A2的拟合关系。

既有9°/12°整份原答分簇和绑定循环角距直接调用仓库冻结输入与`tools/thesis_main/analysis/paired_split_research/study.py`实现，输入和参数出处见`DESIGN_AND_RECEIPT.json`及`run_route_a.py`；没有把9°/12°与融合内部7.5°墙角对应门槛混为一谈。
