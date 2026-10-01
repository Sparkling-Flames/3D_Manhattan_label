# 独立局部路径与方法研究包

先读 `REPORT_zh.md` 或离线图文版 `REPORT_zh.html`。

依据当前快照提交 `10a0fe54608f62668f73d705d6a0cf50a9179f21`。本包不是原仓库完整镜像：原容器 DNS 下载失败，源码规则及三张真实图坐标通过已授权 GitHub 阅读接口提取。独立实现复算主要数值并开展新增对照，没有执行原完整验证器。

Python 3.10+，依赖 NumPy、SciPy、Shapely 2、Matplotlib。

```sh
python -m pip install -r requirements.txt
python src/run_replication.py
python src/run_local_research.py
python src/run_insertion_noise.py
python src/run_order_and_hybrid.py
python src/make_figures.py
```

`inputs/real_excerpts.json` 包含三张图的原人员坐标和原始参考坐标，保留人员/参考身份与环确认状态；它们不是多名工人的同图样本。原参考均未人工确认环，不作视觉裁决。

`src/matching.py`：周期保序部分匹配、绑定/拆分端点成本、物理环角窗裁切。`src/run_order_and_hybrid.py`：局部路径三态距离判定。自动可靠锚点与正式跨人聚类尚未完成。

`results/snapshot_74_independent.csv`：当前规则的74个合成几何对照。`real_recomputed.csv`：三个真实复算。`cyclic_alignment_sensitivity.json`：45个参数组合。`insertion_noise.csv`：300个受控扰动、四种匹配输出，共1200行；不是新真人。`subtraction_exhaustive.json`：61个有效且严格含相机的删点子环。完整解释与局限见报告。

不包含 STAPLE、MACCHIatO 或 Lee 技术报告算法的完整复现。参数网格不是已校准权重。图中所有长度使用共同相机高度单位 h，不是米。
