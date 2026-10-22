# 复用的必要结构、门槛与失败机制

本小包只整理此前 closure 阶段已完成的真实案例。沿用 main `ef148c82df18582228b2d23837faa2659e79eba7` 的原答、楼外标签、几何、票账与叠图，底层真人 v2；本轮 **0 次新增融合、0 次评分、0 次状态重放**。案例原本在看到结果后挑选，用于解释总体结果，不能以这些案例估计成功率或失败率。

三个用途来自四个精确事件。它们均为 **Manual 自身结构分类 `V3_BEHAVIOR`**，不能改名成联合 Q/T 分类，亦不把全数据 ALL 类号直接套到目标折。

| 用途及图片 | n / 实际 m | D、成员块与方向 | A / B / C 的 B8L2 | 实际改变及边界 | 本包入口 |
|---|---|---|---|---|---|
| 必要转折补足；B6-47 | 20 / 7 | 同一 13 人 D；X/Y/Z 各 7 人互斥。常规表达→较多转折；常规/较多席位由17/3变10/10 | 49.196 / 53.929 / 59.826 | B 的 r3/r4/r7/r8 为6/9/8/8票，C为12/10/12/14票，跨10票门槛。Q净+5.897、D10净+6.763；外扩仍增加，补结构不等于全局定位正确 | `cases/manual_structure.json.gz`；`figures/STRUCTURE_LOCAL_VOTES.png` |
| 固定块的人数门槛失选；7y-03 | 20→21 / 4 | X/Y/Z 完全固定，三队 D 仅增加 W121；较多转折→常规。D16→17，门槛10→11 | n20：97.455 / 97.449 / 95.498；n21：97.162 / 96.355 / 54.210 | C 的关键 r1 仍为10票，原观察/归组相同；新增者未补该票，r1失选，C从6节点变5。C−B由−1.951变−42.146，是门槛导致的骤降，不是有符号净效应由正转负 | 两个 `manual_threshold*.json.gz`；`FIXED_BLOCK_THRESHOLD_MECHANISM.csv`；`figures/THRESHOLD_REVERSAL.png` |
| 只补一侧导致连接失败；B6-47 | 20 / 4 | 同一16人D；X/Y/Z各4人，常规→较多转折；与m7正例是不同成员/背景事件 | 47.979 / 47.243 / **不可评分** | C有8节点，r7达10票，相邻r8分裂组3/5票未过线；跳过r8的投影连接与另一底面边相交，原状态为 `invalid_floor`，没有给失败Q填0 | `cases/manual_failure.json.gz`；`FAILURE_CONNECTION_MECHANISM.json`；`figures/FAILURE_LOCAL_CONNECTION.png` |

## 精确成员与比较对象

`EXACT_EVENTS.csv.gz` 保存四个事件的 A/B/C 团队键及完整成员、D/X/Y/Z、人数向量、原设计和分类折。`EXACT_MEMBERS.csv.gz` 保存实际 worker/object_id、类别及所属臂；没有从组均值反推虚构成员。

- B6-47 m7：事件 `f6893bb1710e29da5802f39c`，X=`W103|W105|W108|W110|W121|W124|W129`，Y=`W111|W117|W118|W125|W127|W133|W134`，Z=`W002|W012|W027|W102|W109|W115|W126`。
- 7y-03：n20事件 `657a556b4b2e3e316cf60198`，n21事件 `268b3f37b6543564e1677b19`。固定X=`W027|W109|W126|W130`，Y=`W028|W102|W115|W122`，Z=`W100|W103|W120|W128`；D只增加W121。
- B6-47 m4失败：事件 `09b26209b5f3289de09fd298`，X=`W106|W108|W127|W128`，Y=`W104|W111|W118|W134`，Z=`W012|W027|W036|W126`。

所有D完整名单及原始观察在数据文件中。m7正例与m4失败的背景/成员不同，不把两例差别称作纯m响应。7y-03人数与背景一起改变，只对已核对的关键r1明确归因于门槛；其它分项仍可能受新增观察影响。

## 必要证据文件

- `ENDPOINT_METRICS.csv.gz`：12个原端点各冻结质量分项、状态与几何标量，失败保持缺失。
- `GROUP_VOTES.csv.gz`、`LOCAL_STRUCTURE_VOTES.csv`：各臂完整组票、阈值、选中状态、背景票及原成员。参考机会编号只在同图内解释，不按不同团队node编号硬配。
- `OBSERVATION_ASSIGNMENTS.csv.gz`：具体worker/object/pair到组的映射；`EDGE_VOTES.csv.gz`：直接与投影边支持。
- 四个案例JSON：原答、参考、团队状态、必要几何和成员完整保留。
- `figures/manual_structure/member_overlays.png`、`raw_three_views.png`：必要结构案例的真人原答叠加与ERP/BEV/3D。三个局部机制图含原图与实际融合，不是生成示意图。

B6-47结构补足的r8同时存在一个背景观察重新归组，原解释已经区分此项，不能把全部增票都归成新成员能力。失败例的两条实际边相交点为(−0.348285, −1.331797)，单位为相机高度；原源环和无效状态保持。既有较多转折类别在多数支持条件下的总体用途，仍由完整结果判断，不由这一反例推翻。

## 来源与阶段

原说明：`research/workers/personnel_exchange_closure_20261022/mechanisms/机制解释_原答到融合.md`第2、3、4节。`SOURCE_MANIFEST.csv` 逐文件给准确原路径、源/输出SHA256、大小、选择方式与阶段。图片和JSON按原字节复制；共用表只选择这四个case_id，保留原字段字符串，未重新计算任何数值。

运行 `python research/workers/personnel_mixture_comparison_20261022/integration/reused_cases/copy_selected_cases.py` 可从仓库原文件重建小包。原图全集、大旧案例包和不相关案例没有复制。画像中的jtc-26保留其原专题引用，本包不带入此前“W113没有画近邻点”的旧简化文字。
