# 人员子类与完整共识：Pro／dot精选返回

2026-10-04。这里保存外部原件；采纳判断、当前输入版本纠正及本地验证以[综合审查](../../analysis_results/worker_subtype_review_20261004/REPORT.md)为准，当前路线见[研究方向](../../docs/thesis_main/研究方向_空间差异与共识_20260930.md)。报告意见不自动成为方法合同。

## 保留内容

|入口|有用内容|范围|
|---|---|---|
|[Pro报告](pro/REPORT_ZH.md)、[字段说明](pro/FIELD_GUIDE_ZH.md)|嵌套留建筑、子类有限池过程、两图全部六人组合、校准名单传播；源码、输入、测试、结果和图示|24人×10图评分矩阵；两张24人图的几何。不是44张高人数图全量重算；T/S/B当前验证未完成|
|[dot人员核验](dot/personnel_repro_audit_20261004/审核结论_ZH.md)|独立数值复现、原始失败及GEOS并集反例定位|保留失败与定位证据，不把核验器的并集问题写成Pro公式错误|
|`dot/personnel_inference/`、[十图补充](dot/ten_image_subtype_check/REPORT_ZH.md)|预测收益集中性、十图同人数融合波动方向|集中性不是人员资格依据；固定面板方向计数不是总体概率|
|`dot/oct4-correspondence-audit/`|三人认证反例、隔离guard、最小diff及回归|针对旧Pro锚点原型；guard不等于通用求解器|
|`dot/oct4-repo-audit/`|当前全员点方法并列反例、共同覆盖的阈值对照|开发例不能代替阈值校准；本地最小修复见综合审查|

共253个文件、约13.56 MB按来源字节保留，复制与213项省略记录见[ARCHIVE.json](ARCHIVE.json)。省略缓存、重复内嵌HTML、重复author bundle、clean replay及已归档的旧完整layout源码／大块重放。完整layout旧原型复用[上一轮归档](../full_layout_pro_review_20261004/REVIEW.md)。原件中的过时统计、相对路径和原有格式没有悄悄改写。

## 复算入口与删重边界

从`pro/`目录可按其[说明](pro/README_ZH.md)运行`python -m unittest discover -s tests -v`，或`python run_all.py --out <一个尚不存在的新目录>`。已冻结输入为计算入口，无须重新执行`restore_*.py`。本轮本地执行的是综合审查列明的定向复算，未声称重新运行全包35项测试及11个阶段。

dot原`reproduce.sh`记录当时目录结构；删重后不直接按旧路径执行。需使用其Python入口并将bundle/source参数指向本归档`pro/`，输出另设新目录。旧完整layout原型应指向上一轮`full_layout_pro_review_20261004/external/`。便于直接重做的本地审查入口为：

```powershell
D:/anaconda/python.exe -B analysis_results/worker_subtype_review_20261004/worker/audit_workers.py
D:/anaconda/python.exe -B analysis_results/worker_subtype_review_20261004/layout/reproduce.py
```

本地复算脚本位于仓库根目录下的上述路径。它们核验数值／来源和有限反例，不裁决原图或改变人员资格。外部requirements是环境记录，不要求为其版本号重装仓库环境。

## 必须带着阅读的纠正

- 约11%是图内相对分数的预测SSE降低，不是共识IoU增加11%。收益集中于少数人员，但这不否定研究者定义的粗子类及其对照实验。
- 外包高人数难度统计是旧标签。当前33张主质量图为简单6／中等7／困难5／未定2／未记录13；更新分组曲线仍待执行。
- 六张主共识候选的质量限制是`hold_scene_or_reference`：五张`unconfirmed`、一张`doorway_annotatable`。不能统一解释成“只有GT不适用”，更不等于没有人工审核。
- 历史全员点输出的`ok`尚未经过本轮新增的并列分区检查；本轮没有覆盖旧137图结果。
