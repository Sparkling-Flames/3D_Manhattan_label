# 16项原始comment逐条数值答复

本报告只核对文字来源与数值，不新增视觉裁决。下列距离为当前同一有效点集；9°/25.6px仅为既有中间探针。全部成员、其他阈值、逐端点和阻挡明细在同目录CSV/JSON。

## 1. 7y3sRwLe3Va-21 / manual：W002—W033

状态：暂缓，未裁决。

原文：
> 这主要是 p6,p7和p15,16的区别,其实两位都是想标完全看不见的墙角的位置,但是w02偏左,33偏右,但是x坐标相差的还蛮大的,导致如果计算x坐标的话,顺序差异有点大.
> 其实001也和002,033的状态是差不多的,都是想标这个地方,但是标的有偏差
> 而且这图疑似oos.
> 实质上这图的顺序是,我拿002举例(只取bottom):15,12,11,8,7,2,20,5,17,19
> 

原文说明的是同一隐藏墙角的作答意图及明显位置漂移，不能据此自动补齐跨人员对应。所给W002 bottom连接序列属于单份作答内墙体连接顺序，不直接替代跨人员点位映射。当前数值对应可计算，但“唯一最优横向绑定”不等于物理对应已确认。保持暂缓；需核对W001/W002/W033这一局部的完整上下对应。

|视图|距离|分组|残差|同组|
|---|---|---|---:|---|
|automatic|sphere|complete|20.075143|否|
|automatic|sphere|representative|20.075143|否|
|automatic|image|complete|57.135929|否|
|automatic|image|representative|57.135929|否|
|human_correspondence|sphere|complete|20.075143|否|
|human_correspondence|sphere|representative|20.075143|否|
|human_correspondence|image|complete|57.135929|否|
|human_correspondence|image|representative|57.135929|否|

旧审核簇3的身份：517087c6def062efa361。在all_case_members_and_representatives.csv.gz按身份查看新归属，不按新簇号追认。
## 2. S9hNv5qa7GM-12 / manual：W011—W012

状态：暂缓，未裁决。

原文：
> 12确实标p12,11的时候有点偏差,但是你这配对是对的,这细节每个点的细节上相差不是很多,但是你把他们分簇的原因,是不是多个点的偏差累计了?

不是多个点偏差累加：当前距离取所有端点中的最大值。更直接的障碍是W012的数值上下绑定仍有并列最优解，不能把角色分开视图中的可比较，直接升级为唯一绑定可计算。本项给出角色分开固定顺序的残差，但不擅自选择一组绑定。原文“配对是对的”保留；仍需把所指审核候选明确绑定到原点号后才可机器应用。

指定对不具有唯一绑定；保留角色分开诊断，不填零距离，不新造单人簇。

## 3. b8cTxDM8gDG-17 / manual：W027—W029

状态：暂缓，未裁决。

原文：
> 这还是同一个问题,w29 的p11,12 和w27 的p5,p6实质上还是想标同一个点位,但是确实被完全遮挡,x 轴的偏差确实有点大.w31是完全没标这个地方

文字已指出W027/W029试图标同一被完全遮挡的位置，但位置差不为零；这与W031遗漏该处不是同一种观测。当前严格整份表达仍受有效点数硬门约束。没有完整人工跨人映射时只报告固定/循环/自由诊断，不以自由匹配更小自动纠正。保持暂缓。

|视图|距离|分组|残差|同组|
|---|---|---|---:|---|
|automatic|sphere|complete|10.954170|否|
|automatic|sphere|representative|10.954170|否|
|automatic|image|complete|35.307104|否|
|automatic|image|representative|35.307104|否|
|human_correspondence|sphere|complete|10.954170|否|
|human_correspondence|sphere|representative|10.954170|否|
|human_correspondence|image|complete|35.307104|否|
|human_correspondence|image|representative|35.307104|否|

旧审核簇3的身份：34724d21eb0d44dfc22d。在all_case_members_and_representatives.csv.gz按身份查看新归属，不按新簇号追认。
## 4. jtcxE69GiFV-28 / manual：W002—W036

状态：暂缓，未裁决。

原文：
> 还是之前提到的那个问题,就是p12,p18都是想标同一个点位,但是被挡住,导致有偏差,而且这偏差确实有一定距离

该例不能仅凭“想标同一点”把实际坐标差清零。应分别记录意图解释、对应和定位残差；是否把这种残差容许在同组内仍由用户裁决。本轮保留原点与原暂缓状态。

|视图|距离|分组|残差|同组|
|---|---|---|---:|---|
|automatic|sphere|complete|10.286571|否|
|automatic|sphere|representative|10.286571|否|
|automatic|image|complete|32.923709|否|
|automatic|image|representative|32.923709|否|
|human_correspondence|sphere|complete|10.286571|否|
|human_correspondence|sphere|representative|10.286571|否|
|human_correspondence|image|complete|32.923709|否|
|human_correspondence|image|representative|32.923709|否|

旧审核簇3的身份：15f271d72bbfaefc7da7。在all_case_members_and_representatives.csv.gz按身份查看新归属，不按新簇号追认。
## 5. wc2JMjhGNzB-46 / manual：W006—W008

状态：暂缓，未裁决。

原文：
> 还是和前面同样的问题,w08的p8的点对和w06的p11

W008存在上下绑定歧义；仅给出W008 p8与W006 p11的局部文字关联，尚不能授权完整整份绑定。采用角色分开诊断而不是把不可计算填成零、单人簇或不存在。保持暂缓。

指定对不具有唯一绑定；保留角色分开诊断，不填零距离，不新造单人簇。


旧审核簇3的身份：846f35a4fc23776b55a2, 19607f73ad540646568e。在all_case_members_and_representatives.csv.gz按身份查看新归属，不按新簇号追认。
## 6. zsNo4HB9uLZ-16 / manual：W032—W033

状态：暂缓，未裁决。

原文：
> w32的p12点对和w33的p6

原文指定了W032 p12点对与W033 p6，应核对该局部的上下点号及整份跨人对应；当前两个端点最大差异不由平均值掩盖。保持暂缓，数值超阈值不自动推翻遮挡解释。

|视图|距离|分组|残差|同组|
|---|---|---|---:|---|
|automatic|sphere|complete|13.704384|否|
|automatic|sphere|representative|13.704384|否|
|automatic|image|complete|39.146596|否|
|automatic|image|representative|39.146596|否|
|human_correspondence|sphere|complete|13.704384|否|
|human_correspondence|sphere|representative|13.704384|否|
|human_correspondence|image|complete|39.146596|否|
|human_correspondence|image|representative|39.146596|否|
## 7. X7HyMhZNoso-13 / manual：W002—W030

状态：可视为相近。

原文：
> 很接近,其实簇2 和簇1 我个人没看到很大差别

两份指定作答本身近；完整链接拆分需查看所属两组中的其他成员，不能用两份之间的距离解释整组关系。代表半径可以保留它们在一组，但同时必须检查代表组内最远成员。原文对“簇1与簇2”的更广泛意见仍绑定旧审核版本，不能仅用指定对符合就称两整个旧簇已通过。

|视图|距离|分组|残差|同组|
|---|---|---|---:|---|
|automatic|sphere|complete|2.080941|否|
|automatic|sphere|representative|2.080941|是|
|automatic|image|complete|6.266889|否|
|automatic|image|representative|6.266889|是|
|human_correspondence|sphere|complete|2.080941|否|
|human_correspondence|sphere|representative|2.080941|是|
|human_correspondence|image|complete|6.266889|否|
|human_correspondence|image|representative|6.266889|是|

完整链接最终两组的超阈值阻挡成员示例（不是对唯一历史合并路径的宣称）：
automatic / image：W021(5436c4f88262ddc5) 对 W012(b2be1df92c78eded) = 31.822962；共有3个超阈值跨组对。
automatic / sphere：W021(5436c4f88262ddc5) 对 W012(b2be1df92c78eded) = 11.107192；共有3个超阈值跨组对。
human_correspondence / image：W021(5436c4f88262ddc5) 对 W012(b2be1df92c78eded) = 31.822962；共有3个超阈值跨组对。
human_correspondence / sphere：W021(5436c4f88262ddc5) 对 W012(b2be1df92c78eded) = 11.107192；共有3个超阈值跨组对。

旧审核簇3的身份：5e3a87e01e8c7a68。在all_case_members_and_representatives.csv.gz按身份查看新归属，不按新簇号追认。
## 8. b8cTxDM8gDG-07 / semi：W029—W031

状态：可视为相近。

原文：
> 只是p6的bottom标的偏差稍大,但是还好

原文已接受p6 bottom略有偏差。最大端点指标会保留这个偏差，但当前探针下指定对仍相近；完整链接的分开主要需解释整簇跨成员约束，而不是再把这两份判成不相近。

|视图|距离|分组|残差|同组|
|---|---|---|---:|---|
|automatic|sphere|complete|4.131098|否|
|automatic|sphere|representative|4.131098|是|
|automatic|image|complete|11.755767|否|
|automatic|image|representative|11.755767|是|
|human_correspondence|sphere|complete|4.131098|否|
|human_correspondence|sphere|representative|4.131098|是|
|human_correspondence|image|complete|11.755767|否|
|human_correspondence|image|representative|11.755767|是|

完整链接最终两组的超阈值阻挡成员示例（不是对唯一历史合并路径的宣称）：
automatic / image：W030(3c2427034d519a1a) 对 W035(33a4dc1fd6be1bdd) = 31.205988；共有2个超阈值跨组对。
automatic / sphere：W030(3c2427034d519a1a) 对 W035(33a4dc1fd6be1bdd) = 10.640940；共有2个超阈值跨组对。
human_correspondence / image：W030(3c2427034d519a1a) 对 W035(33a4dc1fd6be1bdd) = 31.205988；共有2个超阈值跨组对。
human_correspondence / sphere：W030(3c2427034d519a1a) 对 W035(33a4dc1fd6be1bdd) = 10.640940；共有2个超阈值跨组对。

旧审核簇3的身份：39008f0fe7a1d27b, 3e32b8564185e9c7, 62376c3351699bc6, 517e0e79ed73ad98, c9609d6092bb0730, 5c8fc29a99324dd7, db6e2e902a7635ad, ffdffd1443b1cef9, afda73e02ce84841, 7129ad7e523aa525, 3c2427034d519a1a, 0225fd516c992f7f, ca291f0b645de9fa。在all_case_members_and_representatives.csv.gz按身份查看新归属，不按新簇号追认。
## 9. wc2JMjhGNzB-15 / manual：W017—W029

状态：可视为相近。

原文：
> 

指定对相近已确认；无文字理由不补造视觉解释。距离改变可能改变其他成员的合并顺序，因此图上完整链接是否合在一起不能简化成“所有距离都更小”。完整组成员同时输出。

|视图|距离|分组|残差|同组|
|---|---|---|---:|---|
|automatic|sphere|complete|1.701422|否|
|automatic|sphere|representative|1.701422|是|
|automatic|image|complete|4.839621|是|
|automatic|image|representative|4.839621|是|
|human_correspondence|sphere|complete|1.701422|否|
|human_correspondence|sphere|representative|1.701422|是|
|human_correspondence|image|complete|4.839621|是|
|human_correspondence|image|representative|4.839621|是|

完整链接最终两组的超阈值阻挡成员示例（不是对唯一历史合并路径的宣称）：
automatic / sphere：W008(718f9a7977eee15c) 对 W010(841caf4abb7eaa52) = 11.441116；共有3个超阈值跨组对。
human_correspondence / sphere：W008(718f9a7977eee15c) 对 W010(841caf4abb7eaa52) = 11.441116；共有3个超阈值跨组对。
## 10. b8cTxDM8gDG-19 / oos：W028—W032

状态：暂缓，未裁决。

原文：
> 主要是32的p4和28的p3 差异较大,但看部分点的差异确实有,但是这图又是oos. 而且我发现簇2 的18 也是这个地方top y 标的靠下,但是好像还是分到同一簇了

OOS只是研究条件，不把该处top差异删除。W018在旧组中的归属不能作为W028/W032必同组或必异组的推理依据；本轮列出三人各自逐端点差异及所在整组。原关系空白且暂缓，保持未决。

|视图|距离|分组|残差|同组|
|---|---|---|---:|---|
|automatic|sphere|complete|8.436750|是|
|automatic|sphere|representative|8.436750|是|
|automatic|image|complete|23.997885|是|
|automatic|image|representative|23.997885|是|
|human_correspondence|sphere|complete|8.436750|是|
|human_correspondence|sphere|representative|8.436750|是|
|human_correspondence|image|complete|23.997885|是|
|human_correspondence|image|representative|23.997885|是|

旧审核簇3的身份：261aed6164dd9545, 231407e1e3c26cd5, 8de2872c37caa579。在all_case_members_and_representatives.csv.gz按身份查看新归属，不按新簇号追认。
## 11. x8F5xyUWy9e-09 / manual：W031—W032

状态：应分开保留差异。

原文：
> 这两个确实都不是正确的标法,截止位置确实也不同,有差异.但是我好奇的是簇3为什么会被单拎出来呢?

用户明确要求保留W031/W032差异，即使二者都不正确。球面与平面距离对此指定对的结论可不同，原因是投影测量而非错误更正。原“簇3为何单拎”另按旧成员身份回接新方法，不能把新簇号3误当旧簇3。

|视图|距离|分组|残差|同组|
|---|---|---|---:|---|
|automatic|sphere|complete|8.162378|是|
|automatic|sphere|representative|8.162378|是|
|automatic|image|complete|28.349151|否|
|automatic|image|representative|28.349151|否|
|human_correspondence|sphere|complete|8.162378|是|
|human_correspondence|sphere|representative|8.162378|是|
|human_correspondence|image|complete|28.349151|否|
|human_correspondence|image|representative|28.349151|否|

旧审核簇3的身份：11fd9f274cd93897。在all_case_members_and_representatives.csv.gz按身份查看新归属，不按新簇号追认。
## 12. yqstnuAEVhm-15 / oos：W017—W018

状态：暂缓，未裁决。

原文：
> oos,这里也主要是w18的p6和w08 的p10的差异.但是只是一个点的差异,不确定要不要单拎出来

原关系虽填“应分开”，但defer=true优先，本项仍未裁决。后续澄清为W017 p10与W018 p6，不覆盖旧文字的W008。一个局部端点是否足以形成独立整份表达组，不能由点的数量少直接否定；应结合该端点差和整组约束判断。

|视图|距离|分组|残差|同组|
|---|---|---|---:|---|
|automatic|sphere|complete|8.001212|是|
|automatic|sphere|representative|8.001212|是|
|automatic|image|complete|22.890523|是|
|automatic|image|representative|22.890523|是|
|human_correspondence|sphere|complete|8.001212|是|
|human_correspondence|sphere|representative|8.001212|是|
|human_correspondence|image|complete|22.890523|是|
|human_correspondence|image|representative|22.890523|是|

旧审核簇3的身份：58575767b314c57c。在all_case_members_and_representatives.csv.gz按身份查看新归属，不按新簇号追认。
## 13. B6ByNegPMKs-18 / manual：W011—W033

状态：可视为相近。

原文：
> 

已确认相近，原文字空白；保留该指定对作为开发约束，不推断全图或整个当前簇都已验收。

|视图|距离|分组|残差|同组|
|---|---|---|---:|---|
|automatic|sphere|complete|1.548843|是|
|automatic|sphere|representative|1.548843|是|
|automatic|image|complete|4.405615|是|
|automatic|image|representative|4.405615|是|
|human_correspondence|sphere|complete|1.548843|是|
|human_correspondence|sphere|representative|1.548843|是|
|human_correspondence|image|complete|4.405615|是|
|human_correspondence|image|representative|4.405615|是|
## 14. B6ByNegPMKs-48 / manual：W032—W034

状态：可视为相近。

原文：
> 

已确认相近，原文字空白；报告数值和当前整簇范围，不额外制造视觉理由。

|视图|距离|分组|残差|同组|
|---|---|---|---:|---|
|automatic|sphere|complete|2.005949|是|
|automatic|sphere|representative|2.005949|是|
|automatic|image|complete|5.706114|是|
|automatic|image|representative|5.706114|是|
|human_correspondence|sphere|complete|2.005949|是|
|human_correspondence|sphere|representative|2.005949|是|
|human_correspondence|image|complete|5.706114|是|
|human_correspondence|image|representative|5.706114|是|
## 15. e9zR4mvMWw7-09 / manual：W014—W034

状态：可视为相近。

原文：
> 

已确认相近，原文字空白；维持已有判断，同时保留整组内端点极值与成员检查。

|视图|距离|分组|残差|同组|
|---|---|---|---:|---|
|automatic|sphere|complete|2.630565|是|
|automatic|sphere|representative|2.630565|是|
|automatic|image|complete|7.487242|是|
|automatic|image|representative|7.487242|是|
|human_correspondence|sphere|complete|2.630565|是|
|human_correspondence|sphere|representative|2.630565|是|
|human_correspondence|image|complete|7.487242|是|
|human_correspondence|image|representative|7.487242|是|
## 16. q9vSo1VnCiC-34 / manual：W015—W030

状态：可视为相近。

原文：
> 

已确认相近，原文字空白；当前一致仅属于开发案例符合，不能称独立验证准确率。

|视图|距离|分组|残差|同组|
|---|---|---|---:|---|
|automatic|sphere|complete|1.760835|是|
|automatic|sphere|representative|1.760835|是|
|automatic|image|complete|5.167630|是|
|automatic|image|representative|5.167630|是|
|human_correspondence|sphere|complete|1.760835|是|
|human_correspondence|sphere|representative|1.760835|是|
|human_correspondence|image|complete|5.167630|是|
|human_correspondence|image|representative|5.167630|是|
## 17. uNb9QFRL6hY-21 / manual：W006—W013

状态：可视为相近。

原文：
> 后续完整对应确认；原点不改；不设统一容差。

完整人工对应和相近判断已经确认，不再询问。映射变化不强制合并所属整簇。

|视图|距离|分组|残差|同组|
|---|---|---|---:|---|
|automatic|sphere|complete|32.500091|否|
|automatic|sphere|representative|32.500091|否|
|automatic|image|complete|92.567282|否|
|automatic|image|representative|92.567282|否|
|human_correspondence|sphere|complete|4.592694|否|
|human_correspondence|sphere|representative|4.592694|是|
|human_correspondence|image|complete|14.435625|否|
|human_correspondence|image|representative|14.435625|是|

完整链接最终两组的超阈值阻挡成员示例（不是对唯一历史合并路径的宣称）：
human_correspondence / image：W017(74051761f655b31b) 对 W013(a4e0cac5adec2e1e) = 92.567282；共有1个超阈值跨组对。
human_correspondence / sphere：W017(74051761f655b31b) 对 W013(a4e0cac5adec2e1e) = 32.500091；共有1个超阈值跨组对。

## 开发约束与验收范围

8项已决定的指定对并非独立测试集，也不等于8张图的所有组通过。完整图级范围214图/239单元仍待本地逐图验收。

人工只替换某一作答对的对应后，全表可能不再满足三角不等式；本轮显式检查并输出违反项。不能再无条件用“直径≤2倍半径”的度量空间性质解释该后见视图。