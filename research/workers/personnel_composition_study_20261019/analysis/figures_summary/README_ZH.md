# 两张科学摘要图

`01_candidate_utility_coverage.png` 展示发现侧7个全域代表候选的实际融合预测效用、同新来源支持，以及公平历史Q／来源控制后的增量；困难角色单列三种Q控制。“来源残差关系”不表示去除了一切来源作用。B模型的原scene字段实际是OOS／doorway的scope条件，不是功能房型。难度的非盲复核条件及不同误差分母均在图下注明。

`02_specific_replacements_discovery_validation.png` 使用固定13个类别块方向。发现与冻结内部建筑复查并列：菱形为建筑等权均值，小点为各楼均值，三角为逐事件配对差值p10。图右列出有限事件／图片／建筑及缺分事件数。没有依据验证结果更换行或改变类别。

## 直接从精简数据重画

无需全量融合缓存、全部逐事件表或全部逐楼方向表。保留本目录的CSV/JSON、小脚本及指定中文字体，安装主包中的numpy/pandas/matplotlib依赖后运行：

```bash
python analysis/figures_summary/make_summary_figures.py --root /path/to/package --from-sources --font /path/to/NotoSansSC-Regular.ttf
```

`01_plot_source.csv`、`01_candidate_coverage_source.csv`和`01_screen_manifest.json`提供图1输入；`02_plot_source.csv`、`02_building_points.csv`和`02_comparison_manifest.json`提供图2输入。所有值来自已算正式表。重画时仍断言每个说明层的逐楼平均等于其汇总均值。

若主研究输入与全部分析结果已由代码重建，去掉`--from-sources`即可从原结果表重新抽取作图输入。`FIGURE_SOURCE_RECEIPT.json`记录原表hash，`FIGURE_RECEIPT.json`记录最近重画的输入hash、脚本及字体hash、像素密度和PNG实际大小。图只是既有分析的展示，不拟合模型，也不增加假设。
