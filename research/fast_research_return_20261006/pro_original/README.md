# 快速研究交付｜2026-10-06

先看 [REPORT_ZH.md](REPORT_ZH.md)。两个紧凑表见 `results/table1_quality.csv` 和 `results/table2_complete.csv`；五张完整图在 `figures/`。

## 本包包含什么

四个真实质量案例的已有结果摘录；2t7-06 三份已保存路线终点、同组原作答和固定 GT；e9z-19 原有 24 人的完整声明足迹、选中代表／scope 候选的上下点与两版 GT；e9z-16 一份真实作答与两版 GT。`results/` 包含可重用的完整 GeoJSON 范围和选中原作答完整上下点，不只有局部清单。

GeoJSON 仅借用容器格式，坐标单位是共同相机高度 h，**不是经纬度**。ERP 为连续坐标 1024×512。文件中的表示节点不自动等于物理墙角。

## 复算

环境已有依赖时，不必安装；需要时执行 `python -m pip install -r requirements.txt`。

```bash
python reproduce.py --out recomputed
python -c "from pathlib import Path; from make_figures import render; render(result_dir=Path('recomputed'), figure_dir=Path('recomputed_figures'))"
```

脚本只运行报告所列小计算。e9z-19 调用原 `tile_consensus` 一次重建全池终点；该复用函数内部同时计算 MV50 和 strict，报告只消费原 MV50，不搜索门槛，也不运行人数／构成轨迹。真实主面板指标从 `inputs/quality_selected.json` 读取，不重新执行十二图实验。

## 来源与局限

详见 [SOURCES.md](SOURCES.md)。输入由 GitHub 文本读取摘取，不是仓库逐字节复制或全量输入认证。大多数人员仅需其既有足迹；只为实际完整展示的少数原作答保留上下点。排除人员记录保留在 `inputs/e9z19_selected.json`，未恢复其资格。

`src/arc_excerpt.py`、`src/lee_excerpt.py` 是现有正确模块中所需部分的摘录；`reproduce.py` 是新增小计算。没有加入通用研究框架。

原图 PNG 字节在本执行环境未取得。所有图都是文件坐标重绘；没有新的原图视觉裁决。点位 RMSE 缺真实对应，保留 NA。质量结论不跨过这些限制。
