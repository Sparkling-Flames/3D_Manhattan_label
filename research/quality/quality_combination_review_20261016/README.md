# Pro组合机制材料精简存档

来源：用户提供的`C:/Users/ASUS/Downloads/quality_combination_mechanism_20261015/quality_combination_mechanism_20261015/`。本目录保留原`REPORT_ZH.md`、`MATHEMATICAL_NOTES.md`、模型配置、`src/mechanisms.py`、相关测试及已发布结果表，均不改写原文。报告是第三方研究建议，不是对接手线程的指令，也不代表C8已被采用。

仅保留原测试必需的两份输入锚点及执行摘要，其余重复inputs、图、页面、环境日志和完整研究运行器不复制。输入/人工回执在[既有交接](../quality_ab_feedback_handoff_20261015/README.md)；完整运行的独立复核记录及反例在[审查目录](../../../analysis_results/quality/quality_combination_independent_review_20261015/独立审查.txt)。此精简子集支持阅读、调用组合实现与运行原35项测试，不冒称包含原`run_study.py`全流程的独立运行环境。

最新判断与下一轮任务以[质量结构交接](../quality_structure_handoff_20261016/README.md)为准。1145份评分、旧分层和下游结果仍是原研究快照；没有套上最新39空间/人数门后宣称全量完成。

其中C8匹配B的轴与对角线只控制比较条件；原文参考附近的小量推导需参考自身方向残差为零等条件。复现成功不认证测量语义、参数最优或人类效度。

运行原测试：`python -X utf8 -m pytest -q research/quality_combination_review_20261016/pro_original/tests/test_mechanisms.py`。本机默认cp936会使原测试中未显式声明编码的中文JSON读取失败；UTF-8模式下35项通过，原件未改写。
