# 完整布局质量独立审核与五轮研究

先读「独立结论与五轮研究_20261007.md」。A/B/C为密度与连续拟合链，D为信息增量检验，E将冻结策略接到C/D；E2是终审发现下界遗漏后追加的后验检查。基线复现与API修补不计入五轮。

## 文件

- research/density_study：A/B/C代码、逐项结果、全部选择输入和派生候选、失败状态与三份中文报告
- research/information_study：D/E及E2代码、全Manual面板结果、独立核验、策略代价、参考反转和局部负结果
- research/round1_reproduction：Pro端到端复现、独立数值核、NA/AUC诊断、可选最小API补丁及测试
- SEMANTIC_CLAIMS_AUDIT_ZH.md：原图与评论绑定、接口适用域和结论强度审读
- source_versions.json：本次固定的原交付身份及版本
- executed_environment.json：实际运行环境；不是要求未来执行器强行匹配所有补丁版本

没有修改原始资料、GitHub、本地仓库、GT、人员资格或融合。拟合及选择均为隔离研究副本，不是人员新作答或产品修复。

## 复算输入

使用已经上传的两个来源包，解压到任意路径：

1. panorama_quality_deep_20261007.zip，或其数值版ZIP：根目录quality_deep_20261007。Library libfile_0795ec2cb2608191b10064911ebaf791；数值版libfile_d7f5980f1fc481918d101e7579895a70。后者足够无图数值复算，视觉证据需完整版。
2. pro_quality_expanded_data_20261007.zip：解压后具有current/panel.json。Library libfile_71977790d08c81918700d41c91aec899。

本附件不重复装入大量原图和原始包。引用METHOD固定为本次19:55 UTC返回的v1，不从同名更新文件悄悄换版本。

依赖Python、numpy、scipy、pandas、shapely、scikit-learn、matplotlib，实际版本见executed_environment.json。下列为命令示意；将SOURCE、EXPANDED、OUTPUT替换为自己的路径。各目录README给出完整命令及顺序。

    python research/density_study/round_a.py --source SOURCE --expanded EXPANDED --out OUTPUT/density
    python research/density_study/round_b.py --source SOURCE --expanded EXPANDED --out OUTPUT/density
    python research/density_study/round_c.py --source SOURCE --expanded EXPANDED --out OUTPUT/density
    python research/information_study/round_d.py --source SOURCE --expanded EXPANDED --out OUTPUT/information
    python research/information_study/summarize_d.py --source SOURCE --expanded EXPANDED --out OUTPUT/information
    python research/information_study/round_e.py --source SOURCE --expanded EXPANDED --density OUTPUT/density --out OUTPUT/information

E依赖C的完整输出和D的汇总。独立积分核验、E2及附加检查见对应README。不要将新输出写进原数据目录。官方reproduce.py要求输出目录尚不存在，使用新的目录名。

## 如何解释结果

图、建筑、人员、同房视角、参考版本、派生控制、候选和输出行是不同单位。记录重复及NA均保留。非正交、门洞/OOS与主质量入口分开。所有阈值是公开研究设定，未经用户用途标定。几何可算、参考更近、结构合理和完整配对正确是不同判断。
