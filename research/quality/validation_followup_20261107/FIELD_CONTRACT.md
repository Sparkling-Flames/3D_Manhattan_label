# 本轮字段与分析支持合同

不改变consensus_research_20260923_v1正式方法、资格、评分或标签。本目录全部尺度变体仅为固定输出诊断。

- SENSITIVITY_DESIGN.json：评分参数、固定支持及起点规则；在计算前写出，不依结果选择规格。
- NATURAL_SUPPORT.csv：一行=主目标池×k；attempted_paths保留256路径频次，common_scored为所有尺度/指标共同有效端点，缺失不置零。
- NATURAL_FIXED_PATH_CHANGES.csv：一行=池×3→6或20→30×指标×统计量；start/end/delta基于同一条路径两端共同有效集合。mean、p10、sd分别是这批同路径团队的均值、分位和样本SD，不是逐路径差值的分位/SD。
- NATURAL_SUMMARY.csv：逐图等权汇总；不同人数区间图片范围不同；difficulty=ALL/Easy/Medium/Hard，图/楼/路径计数分开。
- SMALL_CHANGE_ONSETS.csv：每池×指标×容差的最早合格k；至少64条共同有效路径，尾段观察长度max(5,ceil(.15N))；未找到为缺失。指标之间同为2分不表示物理容差等效。
- HALF_COMMON_EVENTS.csv.gz：一行=实际合法ABC事件×自动/辅助版本×指标；A/B/C三端共同有效后计算GA、GS、CB，缺失保留。所有指标支持一致。GA=|C−A|−|B−A|，GS=(|C−A|+|C−B|)/2−|B−A|，CB=C−B。
- HALF_IMAGE_EFFECTS.csv：背景→块→池→图逐层等权；HALF_SUMMARY按图等权。此处CB也要求A有效，与原仅B/C有效的CB分母可能不同。
- CONTROL_RESPONSE_MATRIX.csv：96条合成几何配置，不是96个独立场景。八类、三尺度、四级，所有几何保存在CONTROL_GEOMETRIES.json.gz。角点移到邻点中点表示逐渐抹去凹角；不把角点计数变化当作正确性。局部均高不变不强制采样高度残差为0。
- 人评导出schema=overall_quality_review_20261107_v3；固定R00共30题。grades分别为显示左右good/medium/poor/unknown，不再采集scope空间判断，self为本人回避，reason选填。缺陷采用左右独立多选，不收集把握程度、练习或结构对应判断。
- score_viewed第一次为true前保存不可覆盖的before_score快照（grades/defects/reason/reference_viewed/recorded_at）；最终grades另记。回收后依私有flip映射恢复左右原答身份；看分前与看分后分开统计。未知等级和本人回避不合并为差。
- 全景二维标注、2D底面与3D线框同时显示，不改点坐标。公开包包含待揭示B8L2/D10分数，但不含人员身份、类别或原答ID；源码可读，界面隐藏不是严格防窥。

缺陷字段defects.left/right取missing（漏墙/转折）、extra（多画）、position（位置）、height（高度）、connection（连接）、other、none、unknown。none/unknown与其它项互斥；空数组表示未答，不等于无缺陷。before_score同时保存缺陷快照，collector按flip恢复左右并分别输出看分前与最终缺陷。完成计数及看分入口要求两侧等级和缺陷均已作答；本人回避单列。

2026-11-07补充：查看分数后显示B8L2的暂定解释分档：好80≤Q≤100、中60≤Q<80、差0≤Q<60。分界为本轮解释建议，未由人评校准，不重标人工判断、不改变正式评分或任何下游研究分组；D10不直接沿用。
