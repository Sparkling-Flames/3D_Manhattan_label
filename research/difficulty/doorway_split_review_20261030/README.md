# 门洞交界初审结果与工作台

归档2026-10-30交付的20图空间初审材料。来源包称全部20图、708份作答均已判定；本次导入验证了ZIP CRC并保留逐图、逐份结果。**这些是人工初审记录，不等同最终空间/GT采用，也尚未接入质量分重算。**

## 内容

- [原始交付说明](review_results/README.md)及[初审JSON](review_results/review_result_v2.json)：初审结果本体。
- [逐份判定](review_results/verdicts_all.csv)、[逐图汇总](review_results/summary_per_image.csv)：JSON的表格副本。
- [附加程序初判](review_results/附_程序初判/)：空间归属和GT门框带审计；属于机器诊断，不是人工结论。
- [可复核工作台源码](workbench_root/research/difficulty/doorway_split_review_20261030/README.md)：包含当时页面和依赖快照。
- [导入回执](IMPORT_RECEIPT.json)：导入计数、排除项及ZIP CRC状态。

## 本机工作台

交付包中的20张2048×1024全景原图留在本机，并由`.gitignore`排除，不随仓库上传。本机副本已放在`workbench_root/data/mp3d_layout/{valid,test}/img/`相应位置；其他工作副本需单独补入本地原图后才能显示。

在`workbench_root`目录运行`python research/difficulty/doorway_split_review_20261030/serve.py 8787`，然后打开`http://127.0.0.1:8787/research/difficulty/doorway_split_review_20261030/index.html`。这保留原交付的HTTP运行要求；不将旧浏览器审核状态当作此归档的一部分。

## 研究边界

此包保存审核证据与当时工作台，不改变参考、资格、GT、评分或CURRENT。初审“可用/需修正/无法判断”与另一页面的“空间1/空间2/全部/都不符合”用途不同，不自动合并。后续须结合用户最终确认、逐图参考绑定与双版本处理，再判断哪些记录进入质量对照。
