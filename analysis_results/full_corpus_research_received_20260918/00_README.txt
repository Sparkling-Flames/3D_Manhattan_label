全量布局标注分簇与模型研究——恢复交付包
日期：2026-09-18

【首先打开】
解压整个ZIP到本地文件夹，再用浏览器打开 00_START_HERE.html。
01_REPORT_ZH.html 是恢复后的完整阅读报告；01_REPORT_ZH.md 是可编辑纯文本版本。
02_full_corpus_atlas.html 是全量交互图册：239个图片×条件，27种结果视图。

【这是哪一轮】
这是被中断的全量研究，不是更早的39图试验。
研究分支 research/full-corpus-clustering-20260918。
固定提交 f8b7d60d4727fb7a7b4ce6d4b62d38019994fd0f。
原执行 GitHub Actions run 35329148252。
全量数值代码与结果从上述提交、原执行工件中恢复。
原GitHub说明：full_study_20260918/README.md（保留原字节）。
报告重新编排、图册重新生成，不宣称与未导出的旧本机HTML逐字节相同。

【研究口径】
2501份canonical记录；排除W019/W026的113份，保留2388份、24人、214图。
2364份进入上下配对几何；2381份可进入无序点集比较。
主几何18配置；无序点集6配置；另有3个球面相关结果视图。
原始审计表仍保留排除记录，分析输出已排除W019/W026。
奇数点严格沿用已确认恢复/排除；两项pending更新只做独立敏感性。

【阅读路径】
1. 01_REPORT_ZH.html：结论、奇数点、全量分簇、Bi及其他模型、预测检查、论文叙事。
2. 02_full_corpus_atlas.html：逐图、逐人、逐配置查看，切换原点和有效点、模型叠加。
3. full_study_20260918/results/memberships.csv：42552行配对方案成员。
4. full_study_20260918/results/pointset_memberships.csv：无序点集成员，含部分配对不可用记录。
5. full_study_20260918/results/all_response_audit.csv：原始/有效点数量、处理状态、排除和来源。
6. full_study_20260918/results/model_*.csv：模型覆盖、外层预测和内层调参结果。
7. recovery/REPRODUCTION_CHECK.json：此次六程序复跑及25表逐项对照。

【离线范围】
报告、全部数值、分组、原始/有效点、模型叠加数据可离线使用。
图册内嵌39张原图缩略图；其余175张原图可点击联网读取固定提交，或自行选择同图本地文件。
不含214张原尺寸全景、模型权重、字体。
不能据此称所有214张图已完成语义盲审。

【模型输入为何只有几MB】
保留642个NPZ中未改动程序实际读取的全部数组，删除未使用的大特征数组。
所有保留数组的dtype、形状与原始字节一致。
来源、原NPZ哈希与子集NPZ哈希详见model_snapshot/COMPACT_RECOVERY_MANIFEST.json。
完整原数组清单保留在model_snapshot/ARRAY_MANIFEST.json，不代表未使用字段也装入了子集。
恢复的全部数值输入可直接复算，不依赖GitHub临时artifact链接继续有效。

【校验】
运行 python verify_package.py 检查本包每个文件SHA256。
MANIFEST_SHA256.json 是实际交付文件清单。
recovery/RECOVERY_SOURCE_MANIFEST.json 则是原始导出源清单，包含为来源追踪保留的未交付工作流条目；不要与交付清单混淆。
恢复时ZIP已做CRC检查、实际解压及逐文件SHA256验证。

【复算】
建议独立Python3.13环境：
  python -m pip install -r requirements-reproduction.txt
  python reproduce_in_new_directory.py --output ../full_corpus_recomputed
程序只在新目录运行，不覆盖已交付结果。
必要时仅做身份与SOP验证：
  python full_study_20260918/code/source_validation.py
原始研究数值不等于语义验收；人员构成效应与未来真人收敛预测并未在本轮完成。
