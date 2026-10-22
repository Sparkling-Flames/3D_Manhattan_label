#!/usr/bin/env python3
"""Write adoption-facing common-denominator tables and the Chinese report."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from analyze_same_anchor import HERE, OLD, BASE, METRICS, write, text, levels

def fmt(v,n=3): return '未知' if pd.isna(v) else f'{v:+.{n}f}'
def table(header,rows):
    return '| '+' | '.join(header)+' |\n| '+' | '.join(['---']*len(header))+' |\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows)

def main():
    # Same comparison quantity for all selected operating conditions.
    S=pd.read_csv(BASE/'COMMON_ABC_SIGNED_EFFECTS.csv')
    I=pd.read_csv(BASE/'COMMON_ABC_SIGNED_IMAGES.csv')
    B=pd.read_csv(BASE/'COMMON_ABC_SIGNED_BUILDINGS.csv')
    keep=((S.stage.eq('A')&S.direction.eq('q_up__faster')&S.n.eq(20))|
          (S.stage.eq('A')&S.direction.eq('q_up__faster')&S.n.eq(21)&S.m.eq(3))|
          S.stage.eq('B'))
    S=S[keep].copy(); out=[]
    for row in S.to_dict('records'):
        for lvl,T in [('image',I),('building',B)]:
            z=T[T.stage.eq(row['stage'])&T.view.eq(row['view'])]
            for pre in ['same','cross','net','sym']:
                q=z[pre+'_B8L2']; t=z[pre+'_recorded_time_logratio']
                row[lvl+'_'+pre+'_Q_known']=int(q.notna().sum())
                row[lvl+'_'+pre+'_Q_positive']=int(q.gt(1e-9).sum())
                row[lvl+'_'+pre+'_QT_known']=int((q.notna()&t.notna()).sum())
                row[lvl+'_'+pre+'_both_Q_up_time_down']=int((q.gt(1e-9)&t.lt(-1e-12)).sum())
                row[lvl+'_'+pre+'_time_down']=int(t.lt(-1e-12).sum())
        row['same_definition']='B-A'
        row['cross_definition']='C-A'
        row['net_definition']='C-B'
        row['sym_definition']='C-(A+B)/2'
        out.append(row)
    A=pd.DataFrame(out)
    write(A,'ADOPTED_MATCHED_ABC_COMMON.csv')
    ids=set(zip(S.stage,S.view))
    for name,T in [('IMAGES',I),('BUILDINGS',B)]:
        write(T[[x in ids for x in zip(T.stage,T.view)]],'ADOPTED_MATCHED_ABC_'+name+'.csv')
    # Exact available fold role rosters, not ALL class numbers concatenated.
    ah=pd.read_csv(BASE/'ACTUAL_DIRECTION_HISTORY.csv')
    ah=ah[ah.registered_direction.eq('q_up__faster')&ah.n.eq(20)&ah.m.isin([3,4,5,6])].copy()
    ah['stage']='A'; ah['role']='higher_training_Q_relative_faster'
    bh=pd.read_csv(BASE/'phase_b_highq_slower/ACTUAL_DIRECTION_HISTORY.csv')
    bh['stage']='B'; bh['role']='highest_training_Q_relative_slower'
    roles=pd.concat([ah,bh],ignore_index=True)
    domains=pd.read_csv(BASE/'INPUT_NEW_ONLY_DOMAINS.csv')[['pool_id','image','building']]
    roles=roles.merge(domains,on='pool_id',how='left',validate='many_to_one')
    write(roles,'ADOPTED_FOLD_ROLES_AND_MEMBERS.csv')
    centers=pd.read_csv(BASE/'AVAILABLE_CLASS_CENTERS_AND_MEMBERS.csv')
    used=set()
    for r in roles.itertuples():
        used.add((r.pool_id,r.source_class));used.add((r.pool_id,r.target_class))
    write(centers[[x in used for x in zip(centers.pool_id,centers.fold_class)]],
          'ADOPTED_AVAILABLE_CLASS_HISTORY.csv')

    # Pairwise policies share A; their difference equals P2-P1 and actual m can
    # be less than the m-person replacement relative to A.
    G=pd.read_csv(HERE/'GLOBAL_POLICIES_SAME_ANCHOR.csv.gz')
    cols=['delta_'+x for x in METRICS]+['delta_logT','all_time_delta_logT','target_failure_rate','loss_gt5','loss_gt10']
    denominator_rows=[]
    for scope,tab in [('all_available_policies',G),('frozen_target_reservoir',
                    pd.read_csv(HERE/'FINITE_POLICIES_SAME_ANCHOR.csv.gz'))]:
        for (n,m,policy),part in tab.groupby(['n','m','policy']):
            for metric in cols:
                valid=part[part[metric].notna()]
                denominator_rows.append(dict(scope=scope,n=n,m=m,policy=policy,metric=metric,
                    registered_anchor_rows=len(part),observed_anchor_rows=len(valid),
                    observed_panels=valid.panel_id.nunique(),observed_images=valid.image.nunique(),
                    observed_buildings=valid.building.nunique()))
    write(pd.DataFrame(denominator_rows),'METRIC_DENOMINATORS.csv')
    ref=G[G.policy.eq('class_QT_10')][['panel_id','team_A','P_member_workers']+cols]
    pair=G[G.policy.isin(['continuous_Q_0','continuous_QT_20'])].merge(ref,on=['panel_id','team_A'],
              suffixes=('','_QT10'),validate='many_to_one')
    pair['actual_policy_difference_m']=[len(set(x.split('|'))-set(y.split('|')))
        for x,y in zip(pair.P_member_workers,pair.P_member_workers_QT10)]
    for col in cols: pair[col]=pair[col]-pair[col+'_QT10']
    pair=pair.drop(columns=[x for x in pair if x.endswith('_QT10') and x!='P_member_workers_QT10'])
    write(pair,'GLOBAL_POLICY_INCREMENT_OVER_QT10.csv.gz')
    levels(pair,['n','m','policy'],cols,'GLOBAL_POLICY_INCREMENT_OVER_QT10')

    # Pin down the reason finite-reservoir QT10 and global QT10 differ.
    sel=pd.read_csv(HERE/'FINITE_SELECTED_BLOCKS.csv')
    gp=G[G.policy.eq('class_QT_10')][['panel_id','team_A','team_P','P_member_workers']]
    fp=pd.read_csv(HERE/'FINITE_POLICIES_SAME_ANCHOR.csv.gz')
    fp=fp[fp.policy.eq('finite_QT10')][['panel_id','team_A','m','selected_team','selected_Z']]
    diff=fp.merge(gp,on=['panel_id','team_A'],validate='one_to_one')
    diff['same_selected_team']=diff.selected_team.eq(diff.team_P)
    write(diff,'FINITE_VS_GLOBAL_QT10_IDENTITY.csv.gz')
    ds=diff.groupby('m').agg(anchors=('team_A','size'),same_teams=('same_selected_team','sum'),
           panels=('panel_id','nunique')).reset_index()
    write(ds,'FINITE_VS_GLOBAL_QT10_SCOPE_SUMMARY.csv')
    unique=diff[~diff.same_selected_team].drop_duplicates(['panel_id','selected_team','team_P'])
    write(unique,'FINITE_VS_GLOBAL_QT10_DIFFERENT_BLOCKS.csv')

    F=pd.read_csv(HERE/'FINITE_POLICIES_COMMON_SUMMARY.csv')
    Inc=pd.read_csv(HERE/'FINITE_SELECTION_INCREMENT_SUMMARY.csv')
    GS=pd.read_csv(HERE/'GLOBAL_POLICIES_COMMON_SUMMARY.csv')
    r4={r.policy:r for r in F[F.m.eq(4)].itertuples()}
    inc4=Inc[Inc.m.eq(4)&Inc.policy.eq('finite_QT10')].iloc[0]
    g4={r.policy:r for r in GS[GS.m.eq(4)].itertuples()}
    manual=[]
    for r in A.itertuples():
        if r.n==20 and r.m in [3,4,5,6]:
            manual.append([r.stage,f'{r.n}/{r.m}',f'{r.images}/{r.buildings}',
                fmt(r.same_B8L2),fmt(r.cross_B8L2),fmt(r.net_B8L2),
                fmt(r.net_recorded_time_geomean_pct,2)+'%',
                f'{r.image_net_Q_positive}/{r.image_net_Q_known}；{r.building_net_Q_positive}/{r.building_net_Q_known}',
                f'{r.image_net_both_Q_up_time_down}/{r.image_net_QT_known}；{r.building_net_both_Q_up_time_down}/{r.building_net_QT_known}'])
    grows=[]
    for pol in ['class_QT_10','continuous_Q_0','continuous_QT_20']:
        r=g4[pol]
        grows.append([pol,fmt(r.delta_B8L2),fmt(r.delta_D10),fmt(r.delta_logT_geomean_pct,2)+'%',
            f'{r.image_Q_improved}/{r.image_Q_known}',f'{r.image_both_improved}/{r.image_Q_known}'])
    frows=[]
    for m in [3,4,5,6]:
        for pol in ['finite_uniform','finite_Q','finite_QT10','finite_QT20']:
            r=F[F.m.eq(m)&F.policy.eq(pol)].iloc[0]
            frows.append([m,pol,fmt(r.delta_B8L2),fmt(r.delta_logT_geomean_pct,2)+'%',
                f'{int(r.image_Q_improved)}/{int(r.image_Q_known)}；{int(r.building_Q_improved)}/{int(r.building_Q_known)}',
                f'{int(r.image_both_improved)}/{int(r.image_Q_known)}',f'{int(r.quality_common_anchors)}/{int(r.registered_anchor_rows)}'])
    incrows=[]
    for r in Inc.itertuples():
        if r.policy!='finite_QT20':
            incrows.append([r.m,r.policy,fmt(r.delta_B8L2),fmt(r.delta_logT_geomean_pct,2)+'%',
                f'{r.image_Q_improved}/{r.image_Q_known}；{r.building_Q_improved}/{r.building_Q_known}',
                f'{r.image_both_improved}/{r.image_Q_known}'])
    correction=GS[GS.m.eq(5)&GS.policy.eq('continuous_QT_20')].iloc[0]
    report=f'''# Manual联合分类：采用方向与连续Q/T的同口径衔接

## 采用结论

保留Manual结构＋Q/T联合分类，优先采用**n20/m4、换入楼外历史Q较高且相对源类更快的角色**；需要以时间换质量时，采用**n20/m4、训练折最高Q而相对较慢的目标角色**。两者是共同背景下实际整块替换结果，选择场景明确，可以收尾。

分类的组织价值与类内连续选择分两层：先用楼外角色明确往哪里换、需要多少容量，再在该角色内按Q或QT选择具体成员。本轮补分析显示，这第二层具有实际质量—时间取舍，不能用一个“连续特征是否胜过分类”的单值替代。

新读取main提交为`cf053a6e31d17393c0e8216ce15660fa37b8b7bb`；底层v2。新分析只重聚合保存的端点、政策和标签，**0次新融合、0次重新拟类**。原已完成实验保留阶段身份，本文补齐相同原队、相同候选域和相同评价量。内部材料已经多轮探索，不称全新外部验证。

## 1. 主替换条件：三个差值共用三队可评分分母

A=D+X、B=D+Y、C=D+Z；X/Y同源类，Z目标类，每块m人且彼此与D不交。以下每行的B−A、C−A、C−B和时间来自同一三队可评分事件、同一层级权重。先背景内平均，再图、楼等权。阶段A为相对较快高Q方向，阶段B为最高Q较慢方向的新增背景检查。

{table(['阶段','n/m','图/楼','B−A Q','C−A Q','C−B Q','C/B记录时间','C−B升质图；楼','C−B升质且节时图；楼'],manual)}

主推较快m4的三队共同分母为8,645/8,820事件，C−B净质量在22/27可评背景平均升质；对称量C−(A+B)/2为21/27。另1背景C全失败保留。净Q+3.142在6/7图、5/5楼正向；同类与对称跨类绝对变化3.303/4.608，6/7图、5/5楼跨类幅度较大。目标失败端点5/252；“失败端点数”与背景/楼平衡风险率不混写。m3有更广10图8楼，但同跨幅度接近；m5仍升质而幅度分离弱；m6仅3图2楼，目标块几乎全类入队，成员可替代性不由此推断。

最高Q较慢角色阶段B共同分母19,755/21,000事件，C−B净质量在29/39可评背景升质；对称量为30/39。净Q+4.707、时间+7.165%，16/20图、10/14楼升质。同/跨幅度3.860/8.038，17/20图、13/14楼跨幅更大。C端点0/600失败，A/B分别38/1,400与45/1,400失败；相对源队的较大损失尾部仍存在，适合接受耗时和风险的定向升质，不按“所有高Q慢类”概括。该方向是阶段A之后选择、阶段B新增背景验证，非独立建筑盲测。

完整公共分母和逐图/楼结果：`ADOPTED_MATCHED_ABC_COMMON.csv`、`ADOPTED_MATCHED_ABC_IMAGES.csv`、`ADOPTED_MATCHED_ABC_BUILDINGS.csv`。对称Q保留用于消除A/B任意命名；它不代替C−A或C−B。

## 2. 分类是谁，怎样组织人

全数据描述J1—J5的五类名单与结构中心继续保留，实际替换用目标建筑外的标签。22折里K4/K5/K6均有出现，角色按历史中心语义对齐，不跨折直接拼J编号。较快m4实际目标联合名单为W102、W109、W115、W122、W126、W130；最高Q较慢方向另包含W112。它们是跨折角色联合名单，不是永久固定快/慢类。

较快m4的源可用类跨图包含24名新来源人员，具体哪类、哪些人可用应查`ADOPTED_FOLD_ROLES_AND_MEMBERS.csv`。m4需要源类至少8人、目标类至少4人、共同D16人，严格ABC并集至少28人；不能在只够20名人的池内假装完成这一设计。实际可用子集快慢可能与完整训练类中心略有不同，名单与中心同时保存。

结构作用是困难机会下转折/短边的保留倾向，Q/T说明质量与成本；类别内不把所有人的低尾、速度或局部定位当成一样。画像定稿中W109/W112总体Q接近但时间及困难条件不同，W122/W126共同图低尾也不同，支持保留连续历史和具体成员选择，而不是不断另造细类。scope、筛除、错误初始化机会分别保留，未进入每个分类并不意味着无用。

## 3. 全候选政策：类别QT10与连续QT10完全同队

19,896个相同A/D/m锚点上，类别约束QT10和全候选QT10选择成员完全相同。初始候选人员域相同；前者先限目标类再排序，后者可从全部A外候选选择。这个数据支持下类别没有带来连续QT10之外的附加选队收益，却提供可解释的候选角色和容量规则。精确同队键见`CLASS_QT10_EXACT_IDENTITY.csv.gz`。

以下仅n20/m4，四种政策共同可评分1,890/1,960锚点，都是**P−A**。表内时间也是这一共同可评分支持；与旧全时间分母的−4.124%略有不同。不要与上一节C−B直接排名。

{table(['政策','P−A Q','P−A D10','P/A记录时间','升质图','升质且节时图'],grows)}

Q-only与QT10不是“多换4个人”的互换，两个新队之间实际差0—2人，见`GLOBAL_POLICY_INCREMENT_OVER_QT10.csv.gz`。QT10兼顾升质与节时；QT20多省少量时间、Q略降；Q-only没有在m4提供明显额外质量，却增加了记录时间。由此可以选择操作规则，不必调类来追求类别压过连续特征。

**一处必要口径更新：** 原m5 QT20政策Q+2.351来自其自身可评分集合；四政策共同支持上为**{correction.delta_B8L2:+.3f}**，对应QT10+1.768。QT20自身失败更少，因此成功集合不同。旧值不作数值错误删除，但不能用它声称同一原队支持上QT20升质更多；本表保存共同支持的比较。

## 4. 新分析：同一目标储备内，怎样选具体成员

复用104个已冻结背景/成员储备、748个实际目标端点，保留19,896个源A锚点。每一背景内，把储备内所有m人目标块完全枚举成均匀选块分布，再以原分类实际使用的楼外`q_history/t_history`选择Q、QT10、QT20块；成员选择不读取目标图质量。所有政策都从**同一有限目标储备**选择，不称全类穷举或全池最优。

质量比较要求A和三个确定性政策端点都可评分；均匀目标块的Q为可评分块的均值，失败概率另计。所有质量、时间、尾部在该共同锚点上比较。源锚点包含原ABC的A/B两半，所以与只保留三队均可评分的原ABC均值可略有不同。图/楼/背景层级权重一致，事件或锚点数不是独立样本数。

{table(['m','同储备政策','P−A Q','P/A记录时间','升质图；楼','升质且节时图','共同可评/登记锚点'],frows)}

下面把每种选择减去相同A下均匀Z结果；这里两项原来都是P−A，因此质量差可直接解释为类内选择增量。时间按每锚的记录时间比取对数后同样聚合，表中是选择相对均匀分布的几何平均比，不是两个百分比直接相减。

{table(['m','政策','相对均匀Z的Q','相对均匀Z记录时间','Q增加图；楼','两者同时改善图'],incrows)}

**采用方式：** m3的类内按Q选择可作为偏质量的补充；m4使用QT10能进一步节时，但平均要付出约{abs(inc4.delta_B8L2):.2f}分Q。它相对原队仍有明确升质和省时，不能把相对均匀目标块的Q代价误说成相对原队降质。m5也主要是节时取舍；m6每背景目标块唯一，全部策略必然相同，选择增量为0属于容量事实，不能作为分类稳定性的证据。

有限目标储备QT10和全候选QT10是两个选择空间，但本轮m4的1,960个锚点、m5的6,048个锚点和m6的11,088个锚点都选中相同团队，因此同支持下的Q与时间也相同。m4两套QT10正式结果均为Q+2.708743、时间−4.149787%；此前草算−4.080%使用了辅助历史接口，已被本轮正式字段对齐结果替代，不再作为另一种实证结论。m3则有20/800锚点不同，来自一个有限储备未包含全候选QT10选中的W115，类内改选W102，保留另外两名目标成员W109/W126。精确同队计数与不同块见`FINITE_VS_GLOBAL_QT10_SCOPE_SUMMARY.csv`和`FINITE_VS_GLOBAL_QT10_DIFFERENT_BLOCKS.csv`。原事件的`Z_history_q_effect/t_effect`是辅助历史接口，正式选择统一使用原分类政策的`q_history/t_history`；本目录最终表与本文均为对齐版本。

![相同原队和有限目标储备下的质量—记录时间取舍](FINITE_QT_TRADEOFF.png)

图中每一点是相同A、相同有限目标储备下P−A的建筑等权平均；同一面板内可以比较，不把三个m的不同支持当作人数因果曲线。m3按Q提高均匀选块质量但多用少量时间；m4按QT进一步节时但有约0.42分质量代价。

## 5. 分项、失败与适用条件

主联合m4较快方向的对称结果同时改善底点角距、底面IoU、三维代理与参考节点/边召回；平均新增节点不到0.3，不把升质全部说成补角。最高Q较慢方向新增转折/短边更多，也改善遗漏和底点定位。完整数值继承旧`ALL_COMPONENTS_AND_DENOMINATORS.csv.gz`；本轮政策的各分项另在`GLOBAL_POLICIES_COMMON_*`与`FINITE_POLICIES_COMMON_*`中保留同一比较支持。

质量收尾说明：dir是自身最佳正交轴残差，不是GT旋转偏差；IoU3D100是角点均高棱柱代理，不是完整物理体积。遗漏/外扩不能自动当作范围意图或新增结构错误。难度/范围收尾则要求同目标参考、保留短边与几何自遮挡机会。上述解释支持本轮工作分类的用途，不修改原资格、参考或评分。

有限m4确定性三种政策各有1/28选中端点失败；均匀目标储备5/252端点失败。楼/图/背景等权失败率均约2.5%，与原始端点比率不同。均匀选块与QT策略的损失尾部分别保留，不能把Q缺失填0。B6同一目标块在不同同构成D中有有效结果和无效底面，表明背景具体成员会改变连接；W130与W126同类定位/时间取舍同样保留。它们界定操作条件，不否定多数图上的平均用途。

记录时间采用`user_processed_reported_not_raw_log_replayed`来源，单位秒，每队20名成员均有记录后求和；是已有库存记录时间，未新测生产工时，不等同并行完成时长。策略时间百分比是对记录总时间比取对数后在背景/图片/建筑层级聚合，再指数还原。

## 6. 本轮可以收尾的判断与复现

1. 联合分类已具备可解释人员角色、真实成员、n/m容量以及实际换类方向，不需要重新全面搜分类。
2. n20/m4较快高Q方向用于兼顾质量与记录时间；最高Q较慢角色用于时间换质量。更大块不必然更好，m5/m6按已有容量和效果作补充。
3. 类别约束与连续QT10同队，分类在这项政策上有组织解释价值，没有额外数值收益；同目标储备的连续选择则确实改变质量—时间取舍。
4. 本次新增均为有限范围再分析，整体人群空间未穷举。无需为收尾继续增加大量重复端点或调整冻结融合。

运行`python analyze_same_anchor.py`再运行`python finalize_adoption.py`。前者读取旧完整政策、事件、端点标量及实际楼外标签，分阶段写身份表、有限候选表、精确锚点和分层结果；后者整理采用表与本文。必要输入路径均相对本主题兄弟目录，`ANALYSIS_RECEIPT.json`记录v2和新main身份。`SOURCE_ABC_LINKS.csv.gz`把新增政策关联到旧精确ABC，`FROZEN_TARGET_CANDIDATES.csv.gz`给出每个目标块、D与必要标量；未重复打包全量几何。
'''
    text('MANUAL_QT_ADOPTION_REPORT_ZH.md',report)
    index=[]
    for f in sorted(HERE.iterdir()):
        if f.is_file() and f.name not in ['FILE_INDEX.csv'] and not f.name.endswith('.tmp'):
            index.append({'file':f.name,'bytes':f.stat().st_size,'stage':
                'existing_endpoint_reanalysis','new_fusion':False,
                'note':'main report' if f.name=='MANUAL_QT_ADOPTION_REPORT_ZH.md' else ''})
    write(pd.DataFrame(index),'FILE_INDEX.csv')
    print('Report and adopted tables saved',flush=True)
    print(ds.to_string(index=False))

if __name__=='__main__':main()
