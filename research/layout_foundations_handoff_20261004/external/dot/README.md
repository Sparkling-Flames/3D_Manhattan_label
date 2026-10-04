# 全景布局基础研究独立复审

先读 REVIEW_ZH.md，包含独立判断、实跑范围、新理论与实验、应修正的解释和下一项具体实验。

## 文件

- source/layout_foundations_20261004_v2：本轮作者原交付，用于核对与复算，不包含新改动
- source_binding：完整源字节核验后的最小源摘录、495字段检查、初次严格对象比较的差异和解释
- reproductions：三个可单独解包运行的审核与增量实验包，分别针对数值算法、质量指标、几何高度与来源支持
- crosscheck：新增性质的独立反方证明及细步长复算

## 快速运行

使用Python 3.12及NumPy、SciPy、Shapely，具体版本见各子包requirements/environment文件。此研究单位h是共同相机高度，不是米。

从本总包根目录运行：

    python source_binding/recheck.py
    python crosscheck/check_new_findings.py

第一条重验本包所附来源摘录。若另有固定080949提交的完整仓库，使用 --repo /path/to/repo 可同时重新检查两份完整输入Git blob。原本次执行已完成完整blob检查，其结果附在source_binding中；无需用户电脑在线才能阅读本报告。

算法、质量和高度支持包分别解包后按各自README运行。原作者包也可直接执行tests与run_research.py；必须输出到新目录，不覆盖其原始结果。

## 范围

只读审核与隔离数值研究。真实主实验是两张图的3份及24份记录，额外复杂确认环为两份明确选中的域外控制；参数、规则、输出行和合成次数均不是独立真人样本。未作原图裁决、完整仓库集成、全137图新版重跑或远程发布。

所有子包的范围说明必须与综合报告一起阅读。部分子包本身未做完整源字段核验，此项已由本总包source_binding补上；不能将某一子包的局部范围说明解读为整轮未完成。
