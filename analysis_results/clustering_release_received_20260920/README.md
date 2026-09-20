# RC1 分簇与分析交付｜2026-09-20

先打开`00_START_HERE.html`；中文完整报告为`report/REPORT_ZH.html`，数值总览为`report/RESULTS_BROWSER.html`。原图没有被本轮重新视觉解释。

- `config.json`：明确的主方案、阈值和证据边界。
- `code/run_all.py`：全历史或追加新canonical响应的唯一主入口。
- `results/final_run/`：逐份成员、477092行端点对应、239单元摘要、复核队列、历史曲线、真实团队组成、同房/模型结果。
- `NEW_DATA.md`：追加规则、人工对应表、失败状态和版本管理。
- `PAPER_PLAN.md`：成稿图表提纲及新旧证据分工。
- `input/source/`：指定分支的自包含原包，按原ZIP逐字节核对。
- `input/supplement/`：由先前交付恢复的既有模型特征、同房注册和元数据，MANIFEST标明来源。不含模型权重、原始计时日志或凭据。
- `REPRODUCIBILITY.json`、`FILE_MANIFEST.json`：本轮重跑及文件核验。

运行：
```
python -B code/run_all.py --root . --config config.json --out results/my_rerun
python -B code/intake_tests.py
```

Python 3.13.5、numpy2.3.5、pandas2.2.3、scipy1.17.0为实际运行环境；其余版本写入执行/测试记录。允许其它满足依赖的环境，但应先跑核验，不能承诺任意环境哈希完全一致。原包中的Windows路径仅为历史来源，不是当前数值运行依赖。

本轮未修改main、SOP或原始坐标。9°是工作分辨率，不是正确性真值；A/B/C/D是训练侧历史偏离分位档，不是心理类型。新真人数据、永久停止人数与全量语义分簇准确性尚未得到验证。
