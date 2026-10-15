# 多参考选择：已有人工规则与 Pro 实现的边界

2026-10-13。只读追溯原始回执、最新解释层和路由源码；不修改参考、正式资格或路由算法。

## 结论

**参考筛选原则已经有明确历史依据，不应再次询问用户，也不能按最终分数最高选参考。** 已表达的顺序是：人工指定优先；否则先看区别空间的局部角点、相邻连线及延伸/封口结构；残缺、斜跨、模糊时才按底面接近程度兜底，并保留不确定性。

这一方向不是 Pro 凭空发明；但 Pro 把方向推广为通用路由时采用的距离尺度、支持阈值和权重仍是研究实现，不能写成用户逐项确认或已校准的标准。

## 原意证据表

路径均相对仓库根目录 `D:/Work/HOHONET/`；行号定位原文件。

| 原意/决定 | 精确来源 | 使用边界 |
|---|---|---|
| 人工指定→局部结构→模糊时底面兜底；不用最高最终Q、不把最高整体IoU视为真实意图 | `research/quality_calibration_pro_handoff_20261011/PRO_PROMPT.txt:92–105`，特别第95–96行 | 这是当时交接记录的用户方向；不是新提出的方案。 |
| T30重新审查指定D | `research/quality_four_space_recompute_20261011/inputs/library/空间范围人工审核_2026-10-11.json:449–460`，原始 `matches_selected`、`matching_region_ids=[space_d]`；解释层 `research/quality_calibration_pro_handoff_20261011/USER_DECISIONS.json:56–61` | 具体对象R02962；人工优先，即使其他参考得分更高也不能覆盖。原始置信度为空，不补“高置信”。 |
| T29明确按A评价 | `research/quality_four_space_recompute_20261011/inputs/previous/quality_review30_receipt.json:389–399`，原话“标了大空间的较小空间,实际计算的时候按照空间A进行匹配”；`USER_DECISIONS.json:49–54` | 原选项“两者均不匹配”与计算参考A并不矛盾；A是指定评价目标，不是声明标注已正确。 |
| T25先B后纠正A | 原始 `quality_review30_receipt.json:345–354`；`research/quality_calibration_pro_handoff_20261011/USER_DECISIONS.json:81–91` | 最新纠正生效，旧原话保留。 |
| T26、T27仅B可匹配；T28无法判断 | `quality_review30_receipt.json:356–386` | 前两例可作明确指定；T28不可虚构指定，备注“在玻璃处停止了,但是也没标玻璃”仍保留。 |
| W031/R03258、W034/R01412均包含狭长延伸 | `research/quality_calibration_pro_handoff_20261011/USER_DECISIONS.json:63–79`；`PRO_PROMPT.txt:98–99` | 用户只确认结构族，`exact_reference_label=null`、`quality_good_confirmed=false`。可限制至A/B族，不能改写成人工指定B。W034入口转折缺失/斜跨仍需评价。 |
| 入口点不等于包含延伸，漏一个点不等于漏整个空间 | `PRO_PROMPT.txt:96–99`；`research/quality_four_space_recompute_20261011/RESULTS_ZH.md:34–38` | T30的第5/8对入口与6/7远端仅属本图证据，不能硬编码到其他图。 |

## Pro实际落实了什么

- `research/quality_pro_joint_archive_20261013/source/routing/prepare_inputs.py:132–148`：读取原始明确选择，并由最新 `USER_DECISIONS` 覆盖；另存两份延伸族指令A/B。
- 同目录 `run_routing.py:68–75`：先在人工允许族内运行几何路由，再应用人工明确参考指定；保留未经人工覆盖的自动结果。
- 同目录 `REPORT_ZH.md:47–71` 和 `config.json:5–24`：0.03倍尺度、15°角点、20°方向尺度、0.65/0.35权重、0.55支持、0.20差距、0.60/0.40覆盖及0.03低差距提示均为具体实现参数，未证明由人评识别。底面IoU兜底实现了旧方向，但阈值与精确并列时的边界距离/稳定ID规则仍属算法选择。
- 同目录 `REPORT_ZH.md:7`：333份多候选作答去除人工指令后，选择与全局最大底面IoU全部一致。因此目前不能声称局部方法已提升真实选择准确率。T29自动B、人工A的反例说明指定优先不可省。

## 不可混同的两种“多参考”

**原始GT与修订GT是版本关系；A/B/C/D是具体图片上已登记的可评价空间候选。** 不能因为有两个GT对象，就自动认定是两个合法空间；也不能认为一个合法底面候选必有完整三维参考。

Pro `routing/prepare_inputs.py:56–81` 按底面几何差异构造/去重候选，并检查确认底面是否与已有完整参考同一几何。`routing/REPORT_ZH.md:33`给出两个实际例子：q9-21的对象ID不同但底面相同，不新增候选；wc2-26的B恰好既是已有人工修订GT，也是本次确认底面，故保留该完整对象，未嫁接A的顶面。**这只是具体证据支持的重合，不能一般化成“所有原始/修订版都是A/B”。**

T30的A/B继承已有合理参考，C/D来自另一次明确确认的底面。`research/quality_four_space_recompute_20261011/README.md:11–17`及`:42`明确C/D仍 `top_pending`。人工指定D只确定计算目标，不补出D的顶界；可以算相应底面，不能制造完整Q或3D IoU。

后续执行应复用这些既有指定和族限制，先检查参考身份、几何及顶面可用性，再按已有规则评价。不得为了得到更高Q换空间，不因当前参考缺顶面而悄悄退回另一完整参考。

核验为文档与源码调用关系检查，未重跑路由、未增加测试或改算法。原始回执可追溯；没有将实现参数误升为人工规范。共享索引由主线程统一同步。
