# 验证记录

基准：f081b267907173cddf2580e34684ba81681cc585；提交前fetch确认线上main未改变。

使用环境已有 `/workspace/.venvs/manhattan/bin/python`，运行：

```bash
python -m pytest -q tests/test_local_inputs.py tests/test_scope_reference_reconstruction_20261016.py tests/test_difficulty_user_revision_20261015.py tests/test_scope_quality_scoring_20261016.py tests/test_scope_quality_binding_20261016.py
```

19 passed，3.90s。包括仓库默认、显式参数/环境变量优先、缺失文件、绝不回退下载目录、13个固定归档哈希、哈希漂移拒绝、显式回执目录不回退、原ZIP几何与当前GT不符仍拒绝，以及既有几何、评分和绑定回归。

所有修改Python文件AST解析通过；恢复指南和审计README相对链接通过；CLOUD_NAVIGATION既有GitHub文件链接逐一核对存在。路径扫描确认tools分析、数据准备和registry的Python代码不再含Downloads目录硬编码。Git ignore检查确认 `data/external/label_data.zip`、`inputs/local_reviews/example.json` 被忽略，指南和审计README可正常跟踪。差异空白检查通过。

没有运行昂贵研究算法，没有生成/改写评分或参考结果，没有访问本机输入。原ZIP真实身份及复制前后SHA256由本机核对；本次不能验证不存在于云端的原ZIP。
