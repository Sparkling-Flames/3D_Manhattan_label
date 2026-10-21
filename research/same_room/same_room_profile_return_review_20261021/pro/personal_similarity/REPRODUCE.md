# 运行说明

在仓库外运行，输出写入独立目录；不改现有输入或评分。

```bash
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 python analyze.py --repo /path/to/3D_Manhattan_label --out /path/to/results
python lowtail_competitors.py --repo /path/to/3D_Manhattan_label --out /path/to/results
python lowtail_class_increment.py --repo /path/to/3D_Manhattan_label --out /path/to/results
python analyze.py --repo /path/to/3D_Manhattan_label --out /path/to/results --stage summarize
python summarize_descriptive.py --repo /path/to/3D_Manhattan_label --out /path/to/results
python extract_examples.py --repo /path/to/3D_Manhattan_label --out /path/to/results
python finalize_outputs.py --repo /path/to/3D_Manhattan_label --out /path/to/results
```

实际输入 commit 为 `561584c8f64d5349d497ec1c6e91f1aeb4bbd7c9`。确切输入路径、SHA256 和版本见 `PROVENANCE.json`。`records.json.gz` 包含当前逐份 Q 与证据；不依赖旧 `shared_records.csv` 是否单独发布。

Python 3.12；本轮环境：numpy 2.3.5、pandas 2.2.3、scipy 1.17.0、scikit-learn 1.8.0、matplotlib 3.10.8。另使用随 scikit-learn 提供的 threadpoolctl。无需 statsmodels、GPU、虚拟环境或重新下载原图。中文图可用输出父目录的 `NotoSansCJKsc-Regular.otf`；无此字体不影响全部计算表。

`--stage descriptive` 只计算直接图对、逐人及原声明矩阵。`--stage summarize` 从本轮 `prediction_rows.csv.gz` 重建预测汇总和图，不重训。主模型固定 Ridge alpha=10（总训练权归一到1000）、浅树绝对误差 boosting（100次、7叶、learning_rate=.06、l2=10、固定随机种子）、固定正则 logistic；没有据目标测试结果反复调参。

`prediction_rows.csv.gz`、`heldout_information.csv.gz` 是可选细粒度缓存。精简交付用 `main_prediction_rows_wide.csv.gz` 保留主要方法每次历史预测，另用 `worker_target_all_budgets_wide.csv.gz` 保留每个实际 m 的人员汇总；完整历史设计索引、原输入引用、参数和代码足以复算其它模型。`DELIVERY_MANIFEST.json` 明确建议主交付与重复/大缓存。原图与全量证据输入不复制入包。`ridge_parameters.json` 保留各折变换与线性参数，boosting 由固定代码和种子重训。

低尾扩展明确在首次丰富模型比较之后增加，目的是补足强简单基线及在它之上的直接类别增量；没有调正则、阈值、类别或搜索新模型。步骤与选择时序在 `LOWTAIL_EXTENSION.json` 记录，不能称为事先预注册实验。

计算性质：这是同一已有库存上的独立新增分析与内部留建筑检查；训练建筑隔离不等于一次未参与研究的未来外部验证。原多历史支持与历史量沿用，单源支持另外标记。
