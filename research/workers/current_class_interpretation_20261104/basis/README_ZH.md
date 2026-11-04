# 当前类别、训练合同与实际人员支持

## 核心结论

当前普通 Manual 的正向分类是 `TARGET_DSTRUCT_K3`，`TARGET_DSTRUCT_K2` 是粗层；`RFUSE_GEOM_K2` 用于解释人群如何影响融合；`OPPJOINT_K3/K4` 用于联合原答、Q、记录劳动和混合人群画像。三者分别保留实际方法身份。旧文档把 OPPJOINT 写为主法、把分类写为“尚未定案”的段落属于其日期对应的历史记录，不能替代当前职责。

本次读取和补统计冻结在 GitHub 提交 `48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b`。没有重拟合分类、改变 K、选取新团队、融合或重新评分。来源、SHA256 和 Git blob SHA1 均见 [INPUT_MANIFEST.csv](INPUT_MANIFEST.csv)，机器可读方法合同见 [CURRENT_METHOD_CONTRACT.json](CURRENT_METHOD_CONTRACT.json)。

用户要求的逐类“类别—原答—团队效果”已经接成[四方法可读表](CLASS_ORIGINAL_TEAM_TABLES.md)和[12类完整矩阵](CLASS_ORIGINAL_TEAM_MATRIX.csv)。它们包括ALL名单、每图楼外容量、共同支持的原答Q/标法/边界、独立支持的new记录时间、同人同楼困难响应，以及有明确方向的[16项ABC/AC/纯类/联盟证据](CLASS_TEAM_DIRECTION_LINKS.csv)。团队配比方差仅在方法层解释，不分摊成单类贡献。

## 1. 三类方法实际依据什么

|方法|实际输入和训练对象|Q、T的关系|当前标签源|
|---|---|---|---|
|TARGET_DSTRUCT K2/K3|普通 Manual 合法目标的个人原答；有效转折、短墙、近共线点、9°匹配门槛下未匹配参考点比例；整体与困难响应两个等权域|Q/T不直接进入特征；参考匹配进入了结构域，故属于参考辅助的标法分类|`image_difficulty_20261030/classification/LABELS_ALL_LOBO.csv.gz`|
|RFUSE_GEOM K2|普通 Manual 的实际自然团队输出；六个人数10/12/14/16/20/24；从团队成员占比解释融合结构、边界、尺度变化的岭回归响应系数|Q/T不直接进入GEOM聚类或α选择；但训练合格支持要求几何与质量输出齐全，所以仍有质量可评性的间接支持条件|`image_difficulty_20261030/rfuse/RFUSE_LABELS_ALL_LOBO.csv.gz`|
|OPPJOINT K3/K4|普通 Manual 原答在连续几何机会下的结构、边界/尺度、Q、logT四个等权域|Q总体、加权低尾与响应，来源内中心化logT总体与响应，直接进入建类；历史Q/T差异是类别定义的一部分|`personnel_v21_reselection_20261029/classification/MAIN45_LABELS_ALL_LOBO.csv.gz` 中对应两法|

TARGET/JOINT 的原始行为和Q先在同图、同目标、同模式内减去同伴中位数；时间还区分 `origin` 和 `time_source`。个人历史按目标→图片→建筑等权汇总，每个楼外折重新排除目标楼。各域采用中位数和p85−p15尺度、截断到±3、至多两个主成分、域内RMS及等域归一化，再对同一棵Ward树切出登记的K。这里引用已有的冻结分类算法，没有使用本次画像结果反向优化分类。

TARGET结构四轴中，`unmatched_ref_9` 同时受遗漏结构和位置偏差影响。因此它不能被解释为完全脱离参考和质量的“纯风格”。困难与简单是当前已确认的图片等级。同图不同目标仍分别绑定参考，图片等级不重复评级。

OPPJOINT的连续几何机会由参考转折超过四个的部分、自遮挡H、短转折边构成，经训练范围内的稳健标准化组合。它与图片人工难度不是同一个变量。当前难度更新没有改变其建类所用的64个整体、机会、挑战和时间历史字段：1,426个人×折记录逐值核查一致，容差1e−10，见 [LABEL_VERSION_CHECKS.json](LABEL_VERSION_CHECKS.json)。

RFUSE在池×人数内同时中心化成员占比与融合输出，保留原自然路径的端点重复出现权重；建筑等权、楼内图片等权，再对同图可用池×人数组等权。每个外层目标楼完全排除；α在0.1/1/10中按内层楼的归一化几何响应误差选取。当前共有28,312个登记端点，28,002个进入训练，209池、200图、22楼。`TARGET_RFUSE`改变了多目标的计权，`GEOMQ`加入质量域，均是独立方法，不能替换当前`RFUSE_GEOM_K2`的身份。

RFUSE标签文件中`underlying_data_version=v2`是复用函数写出的遗留字段。当前实际输入含v2.1空间与评分、当前图片难度，文件路径和散列已冻结；本表额外保存`source_underlying_data_version`与`current_research_release`，没有通过改写原文件消除历史痕迹。

算法依据为仓库作者（2026）的`build_target_aware_candidates.py`、`prepare_natural_training.py`、`learn_natural_fusion_roles.py`及`recompute_v21_image_difficulty_20261030.py`；完整路径及内容散列见输入清单。这些是本研究实际实现，不用通用算法文献代替项目中的具体定义。

## 2. 类别编号、名单与楼外身份

ALL标签用于整体描述；实验和原答画像使用目标建筑对应的楼外标签。共有62名登记人员、ALL加22个楼外折、五个当前方法，统一表为7,130行，键是`method, heldout_building, worker_id`。

|方法|ALL已知类人数|ALL描述性含义|
|---|---|---|
|TARGET_DSTRUCT K2|47 / 12|常规与简化结构合并 / 更多局部结构|
|TARGET_DSTRUCT K3|10 / 37 / 12|困难结构偏少且近共线冗余较多 / 常规结构 / 转折与短墙表达较多|
|RFUSE_GEOM K2|55 / 4|多数响应组 / 困难图转折响应较高的小组|
|OPPJOINT K3|19 / 29 / 8|几何机会下较简化 / 常规且混有长时间成员 / 较高历史Q与更多细节|
|OPPJOINT K4|26 / 19 / 3 / 8|常规较短记录劳动 / 较简化 / 长记录劳动 / 较高历史Q与更多细节|

RFUSE的ALL较高响应组是`W109、W112、W126、W130`；OPPJOINT K4的ALL长时间组是`W027、W036、W121`。完整人员名单与所有未知原因均已交付，不需要从示例图猜测类别：[CLASS_MEMBERS_ALL.csv](CLASS_MEMBERS_ALL.csv)、[WORKER_ROSTER_ALL.csv](WORKER_ROSTER_ALL.csv)、[WORKER_LABELS_ALL_LOBO.csv.gz](WORKER_LABELS_ALL_LOBO.csv.gz)。

数字编号具有每折训练范围内的排序含义：TARGET按困难转折中心升序，RFUSE按困难融合转折响应中心升序，OPPJOINT按训练Q残差中心升序。尤其OPPJOINT的C1、C2等不能永久命名为ALL表中的同一角色；K3→K4在哪一类内部细分也随楼外折而变化。本次保留原编号，只用训练中心解释其角色，没有按楼外表现重新对齐或重新分组。

每折中心可直接核对：[CLASS_TRAINING_CENTERS_BY_FOLD.csv.gz](CLASS_TRAINING_CENTERS_BY_FOLD.csv.gz) 是TARGET/JOINT建类用历史的描述中心；[RFUSE_FUSION_RESPONSE_CENTERS_BY_FOLD.csv.gz](RFUSE_FUSION_RESPONSE_CENTERS_BY_FOLD.csv.gz) 是融合响应系数。两者均不是本次楼外原答的结果表。

## 3. 每张图能有多少人

容量不能由ALL名单人数代替。[CLASS_CAPACITY_PER_POOL.csv.gz](CLASS_CAPACITY_PER_POOL.csv.gz)按实际图、目标、模式和楼外标签列出每类人员、人数、可用Q及正时间人数，并显式补零表示某类缺席；[CLASS_CAPACITY_SUMMARY.csv](CLASS_CAPACITY_SUMMARY.csv)给出范围及达到3人、7人的池数。

当前普通Manual主目标有206个图片池。TARGET K3的三个类人数中位数为4、22、6；RFUSE K2为31、3；OPPJOINT K3为14、11、6；OPPJOINT K4为11、14、1、6。RFUSE较高响应类在192图出现，其人数最多6人，因此这些实际池无法为该类构成七人同类块。这是队伍可行性的事实，不表示该方法没有解释价值。OPPJOINT K4第三类多数图只有一名成员，需要同时看类内分布和支持。

本容量表的明确范围是当前普通、正式评分原答库存：主目标Manual 6,512份、Semi 960份；其它合法目标Manual 227份、Semi 4份。它不把被hold的参考、门洞专题、特殊范围或未入本库存的历史原答恢复为可用队员。未知类人员单列，不能被改写为全局排除人员。

Semi表表示Manual训练标签下的跨模式表现，不能称为重新得到了一套Semi分类。

## 4. 与直接AC冻结分类的对应

本次另外核对了直接AC的`stage00_intake/FINAL_LABELS_FOR_AC_ALL_LOBO.csv.gz`，并逐个人、逐楼外折保留对应表：

- TARGET K3有34个人×折的类别编号变化；K2有5个。ALL分区未变不能替代楼外合法性验收。
- RFUSE K2全部22个楼外折×62人均与当前相同；AC源不含ALL描述折。
- OPPJOINT K3/K4各ALL加22折均与当前相同。

因此RFUSE和OPPJOINT的冻结AC可接续到当前相同标签，但仍应注明队伍与评分版本。TARGET的AC需要保留其冻结设计或检查更新标签下的合法关系，不能自动把旧C2→C3写成当前同一批人的跨类替换。详见 [AC_CURRENT_LABEL_CHECK_BY_FOLD.csv](AC_CURRENT_LABEL_CHECK_BY_FOLD.csv) 和 [AC_CURRENT_LABEL_CORRESPONDENCE.csv.gz](AC_CURRENT_LABEL_CORRESPONDENCE.csv.gz)。

## 5. 复现

在仓库根执行：

```bash
python research/workers/current_class_interpretation_20261104/basis/build_basis.py
```

脚本只读取上述冻结表并生成派生合同、人员/容量和数值验收表。下游RFUSE/JOINT原答画像见相邻`rfuse_joint/REPORT_ZH.md`；其楼外质量、时间、难度比较与本目录训练中心分开保存。
