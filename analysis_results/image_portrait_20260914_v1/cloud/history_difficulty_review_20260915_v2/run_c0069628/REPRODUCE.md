# 本轮复算

在包内repo目录执行；建议单独Python虚拟环境。原图和视觉权重不需要。

```bash
python -m pip install -r requirements-review.txt
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
python -m tools.thesis_main.analysis.image_portrait.history_difficulty_review_v2 --orders 200
python -m tools.thesis_main.analysis.image_portrait.history_difficulty_review_summary_v2
python -m tools.thesis_main.analysis.image_portrait.history_difficulty_review_panel_v2
python -m tools.thesis_main.analysis.image_portrait.history_difficulty_review_summary_v2
python -m tools.thesis_main.analysis.image_portrait.history_difficulty_review_extra_v2
python -m tools.thesis_main.analysis.image_portrait.history_difficulty_review_discovery_v2
python -m tools.thesis_main.analysis.image_portrait.history_difficulty_review_figures_v2
python -m tools.thesis_main.analysis.image_portrait.history_difficulty_review_finalize_v2
python -m pytest tests/test_history_difficulty_review_v2.py -q
```

Windows可省略export或用PowerShell的`$env:OPENBLAS_NUM_THREADS="1"`。当前环境Python3.13；完整原始回放约8分钟，补充子集/18人比较再需数分钟，其他机器时间不同。

新输出固定写入 `analysis_results/image_portrait_20260914_v1/cloud/history_difficulty_review_20260915_v2/run_c0069628/`，不会覆盖上一轮。默认重新运行会重写本轮自身输出；需要保留多个实验时先复制本轮目录/修改OUT版本。

原始responses.jsonl.gz被完整保留，仅选择白名单字段；不能将内含但未使用的旧difficulty字段误称为新算法输入。主空间/模型A–E未在本轮重拟合，上一轮成绩不能声称对应新初稿。

本地输入字节与c0069628最新GitHub的raw/metadata blob完全一致，详见audit/INPUT_METHOD_MANIFEST.json。
