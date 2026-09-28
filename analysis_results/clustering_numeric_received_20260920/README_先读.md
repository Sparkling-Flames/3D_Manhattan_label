# 先读这里：局部点位数值研究交付

先打开`reports/REPORT_ZH.html`（离线浏览器可读），或同目录`REPORT_ZH.md`。

本包不是只有报告。`results/`含全量成对/逐端点、全部分组和代表、前缀回放、人员轴/名单/组合、16项答复、3D扰动及审计结果。`code/`是本轮可运行数值代码，`inputs/source_snapshot.zip`是固定源提交的真实输入，不是远端占位链接。`figures/`为9张结果图；`tests/`及两项源测试共42项。

## 结论

主工作候选：图上最大端点距离＋真实代表半径，25.6px只作中间展示探针。必要严格对照：同图上距离＋完整链接，同阈值。6/9/12°及相应像素全部在包中，不宣称语义阈值已校准。最终214图/239单元视觉验收尚待本地执行。

## 验证和重跑

Python环境安装`requirements.txt`；本次实际使用版本见`EXECUTION_ENVIRONMENT.json`。

```sh
python code/verify_delivery.py
python -X utf8 -B code/run_all.py --out results_recomputed --jobs 4
```

重跑只能写新空目录，避免旧缓存混入。不需要原作者D/C盘、Studio服务器或联网下载输入；安装依赖时才可能需要网络。仅做源距离与分区核验可加`--audit-only`。此入口固定本次数据版本，不是新采集批次接入器。

完整重跑包含200全局顺序、全图前缀、944人员子池前缀、人员留楼和全部实际四人组合，运行时间取决于硬件；不建议手工删掉大表后仍称完整交付。节点采用十六进制标签和mask去重压缩，解码见方法字典。

`DELIVERY_MANIFEST.json`保存包内每个有效载荷文件的SHA-256，校验器拒绝缺失或不匹配文件。源ZIP还单独校验Git blob与CRC。文件名含日期只是标识，下载链接指向当前对话实际文件，不依赖GitHub临时下载地址。

## 本地复核顺序

先核对`NUMERIC_AUDIT.json`、`PREFIX_AUDIT.json`、`PERSONNEL_AUDIT.json`与`PERSONNEL_PREFIX_AUDIT.json`，再读16项逐条答复和`review/local_review_queue.json`。uNb已确认的W006/W013不重问，仅需检查其他成员对应一致性。之后按仓库239单元完整历史表审核，短队列不替代全量验收。

研究不改正式Paper A合同，不派新任务，不修改原始点、冻结时间或既有排除。源压缩包中的旧报告保留历史原貌，其过时推荐不得覆盖本轮最新任务与结论。
