from pathlib import Path
import json, hashlib
import pandas as pd
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results'
f=pd.read_csv(OUT/'risk_decomposition_all10.csv');d=pd.read_csv(OUT/'all_upper_minus_all_lower.csv');dups=json.loads((OUT/'duplicate_summary.json').read_text());s=json.loads((OUT/'summary.json').read_text())
# Check all 274 declared record IDs against frozen input; no upstream reads.
obj=json.loads((ROOT/'inputs/input.json').read_text());binding=json.loads((ROOT/'inputs/source_binding.json').read_text());pairs={(im['code'],r['id']) for im in obj['images'] for r in im['annotations']+im['references']};bound={(r['image'],r['id']) for r in binding['records']};assert pairs==bound and len(pairs)==274
roster=json.loads((ROOT/'inputs/rosters.json').read_text());bs={(r['image'],r['id']):r for r in binding['records']}; selected=[bs[(g['image'],r)] for g in roster['groups'] for r in g['record_ids']];assert len(selected)==240 and all(r['coordinates']=='exact_source_index_match' for r in selected)
summary={'input_and_declared_binding_record_sets_equal':True,'object_n':274,'selected_candidate_n':240,'selected_candidates_with_declared_exact_source_index_match':240,'upstream_independence_proven':False,'boundary':'The source_binding file is a frozen declaration. Original private submission generation, initialization, history and worker identity contracts were not independently retrieved.'}
(OUT/'binding_internal_checks.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
# Under one policy and fixed selected ensemble, GT changes B and R, never unnormalized V.
x=f[f.version=='manual_revision'].merge(f[f.version=='original'],on=['image','building','calibration_policy','method','k','higher_n','lower_n','subset_n'],suffixes=('_revision','_original'))
refrows=[]
for _,r in x.iterrows():
    row={c:r[c] for c in ['image','calibration_policy','method','higher_n']}
    for c in ['R_h2','B_h2','V_h2','pair_symdiff_h2','R_gt','B_gt','V_gt']:
        row['revision_minus_original_'+c]=r[c+'_revision']-r[c+'_original']
    assert abs(row['revision_minus_original_V_h2'])==0
    assert abs(row['revision_minus_original_R_h2']-row['revision_minus_original_B_h2'])<1e-10
    refrows.append(row)
pd.DataFrame(refrows).to_csv(OUT/'GT_version_effect_at_fixed_composition.csv',index=False)
means=pd.read_csv(OUT/'matched_policy_image_means.csv');bmeans=pd.read_csv(OUT/'matched_policy_building_means.csv')

def table(headers,rows):
    return '\n'.join(['|'+'|'.join(headers)+'|','|'+'|'.join(['---']*len(headers))+'|']+['|'+'|'.join(map(str,r))+'|' for r in rows])

duptab=table(['图片','24份中的精确足迹种数','逐值相同组'],[(r['image'],r['unique_exact_footprints'],'；'.join('/'.join(g) for g in r['duplicate_footprint_groups'])) for r in dups])
end=[]
for (policy,method),g in means.groupby(['calibration_policy','method']):
    g=g.set_index('higher_n');a,b=g.loc[0],g.loc[4]
    end.append(['原参考' if policy=='original' else '修订优先',method]+[f'{a[c]:.6f} → {b[c]:.6f}' for c in ['iou_mean','R_gt','B_gt','V_gt','pair_symdiff_union']])
endtab=table(['校准和评价政策','规则','平均IoU','R/GT','B/GT','V/GT','2V/候选并集'],end)
image=d[(d.calibration_policy=='original')&(d.version=='original')&(d.method=='mv50')]
imtab=table(['图片','Δ平均IoU','ΔR/GT','ΔB/GT','ΔV/GT'],[[r.image]+[f'{r[c]:+.6f}' for c in ['delta_iou_mean','delta_R_gt','delta_B_gt','delta_V_gt']] for _,r in image.iterrows()])
within=means[(means.calibration_policy=='original')&(means.method=='mv50')]
comptab=table(['上半人数','平均IoU','R/GT','B/GT','V/GT','2V/候选并集'],[[int(r.higher_n)]+[f'{r[c]:.6f}' for c in ['iou_mean','R_gt','B_gt','V_gt','pair_symdiff_union']] for _,r in within.iterrows()])
report=f'''# 全10图补充核验：保存几何重复与共识风险分解

固定提交：405f3041fdd76977f625d50c558c63dbf342699d。范围：B线24人×10图、8栋建筑，固定k=4；不修改或重新裁决原记录。输入SHA256与Git blob SHA1见input_manifest.json。该报告补足原独立研究的一图机制示范，不替代全源重放报告。

## 一、核心结果

1. P002/P012此前7幅“双指标相同”的图，现在已核对为保存footprint与嵌入的预处理points均逐值完全相同，其余3图不同。所有10图都存在至少一组精确重复；240个图×人员槽位按图内精确足迹计207种，共46个同图相同人员对。207不是人员数，46不是独立事件数。
2. 这只证明当前保存数据重复，不证明人员身份相同、抄袭、数据造假或某一种生成原因。全部24票原样保留，没有合并、删除或重定资格。
3. 280个图-校准-规则-配比-GT状态完成R=B+V与两次独立抽组区域差=2V。原校准/原GT的MV50中，全下半→全上半的图均值：平均IoU增加0.041332；R/GT减少0.043753；B/GT减少0.049321，足以抵消V/GT增加0.005568。该现象已由一图例子扩展为全10图有限池的平均结果。
4. 不能改写成“上半人员必然更波动”：MV50仅5/10图的区域波动增加；严格多数的平均V反而下降，尽管也有5/10图增加。组内相对校准、成员依赖、GT政策和投票规则必须分开。

## 二、来源与方法边界

只读使用当前input.json中的保存坐标、既有环顺序、候选资格、匿名worker别名与record ID；保留全部26个图内来源记录，但分析人池严格按rosters.json选择既有24份候选。未调用原仓库融合/超几何函数，未重新投影、修环、删点或给标注重新定性。

本输入共有260份标注对象和14份GT，source_binding.json声明274份均matched_S2_and_current_bundle，其中254份exact_source_index_match、20份unavailable_preserved。该20份是每图2个非本24人池对象。独立局部核对表明，输入与该声明的274个(image,record ID)集合完全一致，全部240份候选在声明里属于exact_source_index_match；这仍是冻结文件之间的契约核对，不是重新读取上游原始提交生成链。

另一个完整源重放检查已独立比对当前提交的S2快照：全部274对象的人池、资格、环序等字段零不匹配；254份可用预处理points重建足迹最大坐标差4.44×10⁻¹⁶，20份不可用对象原样保留，准备步骤0改变、0警告。其检查摘要和证据文件哈希保存在results/source_provenance_summary.json。完整current bundle源索引重新连接仍未执行；它需要超出本次约定范围的大体量预处理/研究源文件。此处明确区分已验证的S2字段、保存points→footprint一致性，与未验证的原始生成独立性。

提交与文件Git blob核验说明“取得的是哪个冻结源”，不能证明生成源彼此独立。报告不下载完整原始私密身份、评论、任务URL或映射；也不声称已审阅原图。当前source_manifest表明坐标为1024×512、shared_x_periodic_shortest_arc_v1，契约consensus_research_20260923_v1，review_context_revision=20260930。沿用这些版本，不把上游改写成未预处理的原始提交。

## 三、实际重复足迹与坐标

{duptab}

以上46个相同人员对不仅保存footprint相同，points也逐值相同；source_point_indices、source_point_labels、source_pair_indices和order_used亦相同。各对仍有不同record ID。对每图全部276对，额外检查了环循环起点/反向等价、Shapely拓扑相等与区域对称差；这没有增加新的“精确相等”对。因此结论没有从IoU或质心相同倒推几何。

P002/P012的7图是7y3…-04、X7H…-13、e9z…-19、q9v…-02、q9v…-32、wc2…-15、yqs…-34；不同的3图为UwV…-09、rPc…-06、yqs…-32。逐图完整名称、record ID、坐标比较布尔结果和面积差保存在P002_P012_all10.csv。

另有一个重要的质量维度例子：yqstnuAEVhm-34的P010/P014，BEV对称差仅1.6611×10⁻¹⁵ h²，足迹最大坐标差7.77×10⁻¹⁶ h；但预处理points中一个上轮廓y相差7.2707像素。这对没有被标为精确重复。近乎相同底面不等于完整上下轮廓相同，更不证明3D质量等同。它支持分别测量底面和上轮廓，而非用BEV相等替代全部布局相等。

### 来源问题怎样表述才准确

当前manual、independent=true、borrowed_points=false是已有记录标签，不是本轮对生成过程的独立验证。下一步需要核实这些候选的原始提交ID、人员键、版本和共享初始化/预填规则是否正确绑定，或是否发生了引用/版本复制。相同保存几何可以来自不同真实人员；必须先查ID与版本契约。现有证据不足以选择一种解释，也不足以去重重算为“正确人数”。本补充不开展该上游私密链调查。

## 四、精确计算对象

每个图的24份候选构成固定有限池；每个目标建筑使用既有LOBO上/下半，各12人。两个校准政策分别为original和revised_where_available，未把目标建筑带入训练。对h=0…4，均匀无放回抽h名上半与4−h名下半，组合数依次495、2640、4356、2640、495。MV50为≥2票；严格多数为≥3票。

全24份足迹边界的共同细分仅作为离线面积积分基底，不把未抽到的人员票数计入当前组合。每块tile已知上、下半覆盖人数mH和mL；q通过整数超几何计数求得：满足a+b达到阈值的C(mH,a)C(12−mH,h−a)C(mL,b)C(12−mL,4−h−b)之和，除以C(12,h)C(12,4−h)。这里q是随机抽组的融合覆盖概率，不是原始支持率、GT概率或个人可靠性。

令G固定、g为其二值指示。定义R=E|C△G|、B=∫(q−g)²、V=∫q(1−q)。二值输出平方误差等于不一致面积，故R=B+V。两次抽组相互独立，允许共享人员或恰好相同；因此E|C△C′|=2V。无需各空间位置相互独立，也不要求候选是独立同分布的真实人群样本。

实现中的遗漏=|G|−ΣIₜqₜ；外扩=Σ(aₜ−Iₜ)qₜ；B=Σ[Iₜ(1−qₜ)²+(aₜ−Iₜ)qₜ²]+|G∖候选并集|。最后的GT外部常数项被显式保留，不能只在候选并集内计算偏差。

面积单位为保存BEV的h²，不是已经标定的平方米。每个状态同时输出原面积、除以该GT面积、除以固定24人候选并集面积三种口径。源member_symdiff_union是2V/候选并集，不是2V/GT、两次输出的随机并集或IoU距离。不同图先各自归一化再等权平均，不能和总面积相加后再相除混用。

B描述随机融合场相对固定GT的偏差，不是图片固有难度；V描述该抽组机制的几何波动，不是人员能力方差。R、B、V都是面积量。EIoU仍由全部10626组合直接计算；ratio_expected_intersection_union是期望交集/期望并集，与EIoU不同，本批最大差约{abs(f.iou_mean-f.ratio_expected_intersection_union).max():.6f}，未混用。

## 五、全10图结果

### 5.1 两种完整政策的全下半→全上半

表中“原参考”表示原参考校准并用原GT评价；“修订优先”表示修订优先校准，并在4幅有修订的图使用修订GT、其余6图用原GT。表是10图等权均值，不是更大人群推断。

{endtab}

四图有两种GT的状态另外交叉保留：每个校准政策都分别评价原GT与修订GT，结果在risk_decomposition_all10.csv，共280行。没有给剩余6图虚构修订版本。对同一图/校准/规则/配比，只换GT时q和未归一化V完全相同，ΔR=ΔB；80条该检查在GT_version_effect_at_fixed_composition.csv。V/GT随GT面积变化，不代表几何输出波动改变。

### 5.2 原政策MV50：完整配比曲线

{comptab}

平均IoU和R在该曲线上逐级改善，但区域波动先升后略降；4上0下的V小于3上1下。因此，即使只描述同一固定池，“上半人数越多，波动越大”也不成立。这里仍然没有估计未知新人员或新建筑。

### 5.3 原政策MV50：逐图端点变化

以下Δ均为4上0下减0上4下：

{imtab}

9/10图平均IoU增加、R减少；5/10图V增加，这5图的B下降均足以抵消V增加。X7HyMhZNoso-13端点质量小幅变差，不能被总均值遮掉。原政策严格多数的平均IoU改善7/10图，区域波动增加5/10图，但平均V下降。修订优先完整政策下，MV50质量改善9/10图、波动增加4/10图；严格多数质量改善7/10图、波动增加5/10图。

除10图等权平均，还保存先在建筑内平均、再对8建筑等权的敏感性结果matched_policy_building_means.csv。原政策严格多数的ΔV/GT由图等权−0.002131变为建筑等权+0.000405，符号对汇总权重敏感；MV50的平均B减少抵消V增加在两种权重下均成立。修订优先严格多数两种权重下均下降。该分析只是权重敏感性，不把建筑数扩大成独立重复数。

## 六、独立检验与可信度

- 每图、两规则、所有10626组均直接枚举；超几何q与枚举覆盖比例最大差0
- 两GT版本实际只在4图出现，累计297,528个保存IoU值独立交叉核对；连同组合摘要共1148个误差记录，最大绝对差{s['source_max_abs']:.3g}
- 280个状态的R=B+V最大残差{s['decomposition_max_abs']:.3g} h²，R与直接枚举面积损失的最大差{s['risk_enum_max_abs']:.3g} h²
- 每图/两校准/两规则在0、2、4上半人数各选一个组合，重新仅由这4人切tile；168条图-GT检验一致，最大区域差{s['fresh_subset_geometry_max_abs']:.3g} h²
- 6项针对性测试通过：所有配比超几何对枚举、全覆盖/零覆盖、环顺序规范比较、GT在候选并集外的偏差项、两次抽组全笛卡尔积区域差、当前子集与共同细分一致
- 当前运行未记录几何运行时警告；依赖与运行信息见results/summary.json和requirements.txt

精算仅消除固定记录池的抽样计算误差。10626个组共享24份作答，10图仅来自8栋建筑，重复几何还可能有共同上游来源；不把组数当新增独立证据，不给人群推广或因果人员能力结论。这个分解解释了“更接近GT而成员几何波动更大”如何同时发生，不证明高波动导致高质量，也不替代GT审核。

## 七、对当前研究重点的含义

人员区分：先澄清别名/版本/初始化契约，再评价跨建筑区分的可重复性；当前相对半组仍是研究设定，不是稳定二分类的发现。

质量分项：底面、完整上下轮廓和相对参考面积误差承担不同测量职责。底面近似一致且上点不同的实际例子，比从指标相关性低直接决定加权更能说明为什么要先定义测量对象。

组合方差：同时保留准确性R、场偏差B、成员区域波动2V和直接平均IoU；本轮已经完成固定k=4、全部10图、两校准政策与全部可用GT版本的所需扩展，无需先上复杂模型或扩展到更多人数。

## 文件入口

- analyze.py：独立数学/几何实现与主复算断言
- test_analysis.py：6项独立小规模测试
- results/duplicate_summary.json、geometry_all_pairs.csv、P002_P012_all10.csv：全部保存几何与points重复检查
- results/risk_decomposition_all10.csv：280状态的R、B、V、遗漏、外扩和直接IoU
- results/all_upper_minus_all_lower.csv：逐图端点对照
- results/matched_policy_image_means.csv、matched_policy_building_means.csv：图权重与建筑权重分开的均值
- results/source_comparisons.csv、current_subset_direct_checks.csv、tests.log：检验明细
- input_manifest.json、results/binding_internal_checks.json：冻结输入与局部记录契约
'''
(ROOT/'REPORT_zh.md').write_text(report)
print('report written',len(report),'chars')
