"""Create readable key tables and fill the final report from frozen results.

This command aggregates existing endpoint/event tables only. It does not
construct, select or fuse additional teams.
"""
from __future__ import annotations
import csv as csvlib
import json
import os
import sys
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
sys.path.insert(0,str(STUDY/'analysis'))
from analyze_global import balanced,write

NAMES={'M_structure':'Manual M结构','SP_scale':'Semi SP尺度','A2_relation':'A2原答关系',
       'MV_QTD_manual_new':'新批Manual QTD','MV_QTD_manual':'混来源Manual QTD',
       'MV_QTScopeSemi_semi_new':'新批Semi行为','MV_TDScopeSemi_manual_new':'无Q四域','Rnew2':'Rnew2','F01':'F01'}

def md(headers,rows):
    return '\n'.join(['|'+'|'.join(headers)+'|','|'+'|'.join(['---']*len(headers))+'|']+
                     ['|'+'|'.join(str(x) for x in row)+'|' for row in rows])

def csv(d,p):
    """Publish only a complete, read-back-validated CSV.

    A prior delivery contained a valid CSV prefix (6663 of 12953 events).
    Checking the input DataFrame alone cannot catch an interrupted write.
    """
    p=Path(p)
    fd,tmp=tempfile.mkstemp(prefix=p.name+'.',suffix='.pending',dir=p.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8-sig',newline='') as f:
            d.to_csv(f,index=False)
            f.flush();os.fsync(f.fileno())
        count=0;event_ids=[]
        with open(tmp,encoding='utf-8-sig',newline='') as f:
            rows=csvlib.reader(f);header=next(rows)
            assert header==list(d.columns),(p,'header mismatch')
            event_index=header.index('event_id') if 'event_id' in header else None
            for row in rows:
                assert len(row)==len(header),(p,count+2,'incomplete CSV row')
                count+=1
                if event_index is not None:event_ids.append(row[event_index])
        assert count==len(d),(p,'incomplete CSV output',count,len(d))
        if event_ids:
            assert event_ids==d.event_id.astype(str).tolist(),(p,'event identity mismatch')
            assert len(event_ids)==len(set(event_ids)),(p,'duplicate events')
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def supplementary(events):
    metrics=['net_B8L2','net_D10','net_nodes','net_ref_node_recall_5','net_ref_edge_recall_5','net_omission','net_extension',
             'net_height_mean_h','net_height_mean_ratio','net_S_bottom_deg','net_dir','net_Hmean','net_Hcenter','net_iou_2d',
             'net_IoU3D100','net_source_log_time_ratio','net_failure_difference','net_history_block_Q_change','m_BC']
    g=events[events.tier.eq('coarse')&events.event_mode.eq('cross_composition')&events.n.ge(20)&events.m_AB.ge(4)&
             events.layer.isin(['ordinary_manual','ordinary_semi'])&events.method_id.isin(['M_structure','SP_scale','MV_QTD_manual_new'])]
    s,b=balanced(g,metrics,['method_id','condition','layer','direction'])
    write(s,'COARSE_LARGE_DIRECTIONAL_SUMMARY.csv');write(b,'COARSE_LARGE_DIRECTIONAL_BUILDINGS.csv')
    measures=['common_quality_within_abs','common_quality_cross_abs','stable_advantage','within_joint_stable_main','cross_joint_stable_main']
    g=events[events.n.eq(15)&events.m_AB.ge(4)&events.layer.isin(['ordinary_manual','ordinary_semi'])]
    s,b=balanced(g,measures,['method_id','tier','event_mode','condition','layer']);write(s,'ABC_N15_BLOCK_SUMMARY.csv')
    # Fixed m and common images distinguish a size condition from merely
    # mixing different pool support. Each n still uses its registered S.
    g=events[(events.method_id=='SP_scale')&(events.tier=='fine')&
        (events.event_mode=='within_coarse_fine_change')&events.n.isin([15,20])&events.m_AB.eq(4)]
    common=set(g[g.n.eq(15)].pool_id)&set(g[g.n.eq(20)].pool_id)
    g=g[g.pool_id.isin(common)];s,b=balanced(g,measures,['n','m_AB'])
    write(s,'SP_SIZE_SHARED_POOLS.csv');write(b,'SP_SIZE_SHARED_BUILDINGS.csv')

def main():
    events=pd.read_csv(STUDY/'analysis/ABC_ALL_COMPONENT_EVENTS.csv.gz',low_memory=False)
    assert len(events)==12953 and events.event_id.nunique()==12953 and events.computed_all_arms.all()
    supplementary(events)
    large=pd.read_csv(STUDY/'analysis/ABC_LARGE_SUMMARY.csv')
    moderate=pd.read_csv(STUDY/'analysis/ABC_N15_BLOCK_SUMMARY.csv')
    fields=['method_id','condition','tier','event_mode','layer','events','images','buildings',
      'common_quality_within_abs_mean','common_quality_cross_abs_mean','common_quality_within_abs_events',
      'abs_Q_change_advantage_mean','abs_Q_change_advantage_lo','abs_Q_change_advantage_hi',
      'within_joint_stable_main_mean','cross_joint_stable_main_mean','stable_advantage_mean','stable_advantage_lo','stable_advantage_hi',
      'B_failure_mean','C_failure_mean','same_loss_gt5_mean','cross_loss_gt5_mean','same_loss_gt10_mean','cross_loss_gt10_mean',
      'within_floor_jaccard_difference_mean','cross_floor_jaccard_difference_mean',
      'within_mean_height_prism_pair_difference_mean','cross_mean_height_prism_pair_difference_mean']
    principal=large.reindex(columns=fields).copy();principal['size_scope']='n_ge20_m_ge4'
    small=moderate.reindex(columns=fields).copy();small['size_scope']='n15_m_ge4'
    principal=pd.concat([principal,small],ignore_index=True);csv(principal,HERE/'PRIMARY_RESULTS.csv')
    keycols=['event_id','method_id','condition','tier','event_mode','layer','image','building','difficulty','pool_id','n','m_AB','m_AC','m_BC',
       'team_A','team_B','team_C','common_background','outgoing_block_X','same_count_block_Y','changed_count_block_Z',
       'composition_A','composition_C','composition_delta','computed_all_arms','all_scored','all_complete',
       'A_B8L2','B_B8L2','C_B8L2','A_D10','B_D10','C_D10','A_nodes','B_nodes','C_nodes','A_failure','B_failure','C_failure',
       'A_source_time_seconds','B_source_time_seconds','C_source_time_seconds','time_population','same_source_counts',
       'same_abs_B8L2','cross_abs_B8L2','net_B8L2','net_D10','within_joint_stable_main','cross_joint_stable_main','stable_advantage',
       'within_floor_jaccard_difference','cross_floor_jaccard_difference','within_mean_height_prism_pair_difference','cross_mean_height_prism_pair_difference',
       'net_nodes','net_iou_2d','net_IoU3D100','net_S_bottom_deg','net_dir','net_Hmean','net_Hcenter','net_omission','net_extension',
       'net_height_mean_h','net_ref_node_recall_5','net_ref_edge_recall_5','net_source_log_time_ratio','net_loss_gt5',
       'net_loss_gt10','net_failure_difference','same_history_block_Q_change','cross_history_block_Q_change',
       'source_and_historyQ5_matched','source_and_historyQ2_matched']
    # Keep the actual members and all three composition vectors visible in
    # the independent event export, not only opaque endpoint keys.
    for arm,block in [('A','outgoing_block_X'),('B','same_count_block_Y'),('C','changed_count_block_Z')]:
        events[arm+'_member_workers']=[
            '|'.join(sorted(set(filter(None,s.split('|')))|set(filter(None,x.split('|')))))
            for s,x in zip(events.common_background.fillna(''),events[block].fillna(''))]
    keycols += ['image_id','reference_id','reference_version','registration_stage','ABC_sampling',
       'labelled_pool_n','formal_pool_n','class_capacities','composition_B',
       'overlap_AB','overlap_AC','overlap_BC','new_block_YZ_overlap','composition_turnover_AC',
       'A_member_workers','B_member_workers','C_member_workers',
       'A_score_status','B_score_status','C_score_status']
    missing=[c for c in keycols if c not in events]
    assert not missing,('required event export fields missing',missing)
    csv(events[keycols],HERE/'ABC_EVENT_RESULTS_KEY.csv')

    domain=pd.read_csv(STUDY/'integration/DOMAIN_SUBSET_COVERAGE_26x2.csv')
    domainrows=[]
    for subset,g in domain.groupby('domain_subset',sort=False):
        m=g[g.condition.eq('manual')].iloc[0];s=g[g.condition.eq('semi')].iloc[0]
        old='有纯定义' if m.legacy_all_conditions_pure_definitions else ('条件式' if m.legacy_all_conditions_conditioned_definitions else '未找到纯定义')
        current='；'.join(str(v) for v in g.current_frozen_methods.dropna().unique())
        if current:
            current=current.replace('MV_QTD_manual_new','新批QTD').replace('MV_QTD_manual','混来源QTD').replace('MV_TDScopeSemi_manual_new','无Q四域').replace('MV_QTScopeSemi_semi_new','Semi行为').replace('|','／')
            count=int(g.current_actual_event_count.fillna(0).sum())
            current+=f'：{count:,}事件'
        else:current='仅筛查'
        domainrows.append([subset,old,'已拟合',('机会不足' if s.current_screen_status!='screened' else '已拟合'),current])
    domain_table=md(['变量域子集','旧定义状态','本轮Manual','本轮Semi','本轮深入构成'],domainrows)

    chosen=[('M_structure','manual','coarse'),('M_structure','manual','fine'),('A2_relation','manual','single'),
       ('MV_QTD_manual_new','manual','coarse'),('MV_QTD_manual_new','manual','fine'),('Rnew2','manual','coarse'),
       ('SP_scale','semi','coarse'),('SP_scale','semi','fine'),('A2_relation','semi','single')]
    rows=[]
    for method,cond,tier in chosen:
        r=large[(large.method_id==method)&(large.condition==cond)&(large.tier==tier)&large.event_mode.eq('cross_composition')&large.layer.eq('ordinary_'+cond)].iloc[0]
        name=NAMES[method]+'·'+{'coarse':'粗','fine':'细','single':cond}[tier]
        rows.append([name,f'{int(r.events)}／{int(r.images)}／{int(r.buildings)}',f'{r.common_quality_within_abs_mean:.3f}／{r.common_quality_cross_abs_mean:.3f}',
                     f'{100*r.within_joint_stable_main_mean:.2f}%／{100*r.cross_joint_stable_main_mean:.2f}%',
                     f'{100*r.stable_advantage_mean:+.2f} [{100*r.stable_advantage_lo:+.2f}, {100*r.stable_advantage_hi:+.2f}]'])
    main_table=md(['方法／层','事件／图／楼','平均绝对ΔQ：同／跨','联合稳定：同／跨','稳定差百分点[区间]'],rows)

    fine_rows=[]
    for method,cond in [('M_structure','manual'),('MV_QTD_manual_new','manual'),('SP_scale','semi')]:
        r=large[(large.method_id==method)&large.event_mode.eq('within_coarse_fine_change')&large.layer.eq('ordinary_'+cond)].iloc[0]
        fine_rows.append([NAMES[method],f'{int(r.events)}／{int(r.buildings)}',f'{r.common_quality_within_abs_mean:.3f}／{r.common_quality_cross_abs_mean:.3f}',
          f'{100*r.within_joint_stable_main_mean:.2f}%／{100*r.cross_joint_stable_main_mean:.2f}%'])
    fine_table=md(['同父类内部换细类块','事件／楼','绝对ΔQ：同／跨','联合稳定：同／跨'],fine_rows)

    main_findings='''**本轮推荐按用途保留几套有实际成员的工作分类：Manual 的 M 表达层级、Semi 的 SP 尺度层级、两条件分别形成的 A2 原答关系分区；新增同批 Manual 的 Q→T/D 细层用于效率解释。新 Semi 的 Q→T/scope/编辑报告细层保留为条件性探索。** 它们没有合并成一套虚构的统一人员树。

新的实验证据将用途进一步分清：

1. **结构类型有局部团队价值。** M11 在另一建筑 pa4 的真实事件中使某位置从7票到9票、跨过8票门槛，底面遗漏33.7%→3.9%；相同类别构成仍会因具体成员的局部表达不同而失选，不能把类人数向量当作精确票型。
2. **大团队整体可互换性只得到弱或条件性支持。** n≥20、m≥4时，Manual M粗同构成／改构成的平均绝对Q变化为7.238／8.175；A2联合稳定率40.88%／37.35%，差+3.53个百分点。但A2在保持来源人数后的优势消失，不能称已证明超出来源的统一换人规律。Rnew2、SP的若干比较反向，均保留。
3. **细类的明确增量主要在效率，质量增量没有成立。** 同新批Manual较慢细类在22/22楼更慢，约1.595倍；跨楼近全员团队时长响应相对Q父层MSE降8.96%，16/18楼改善。连续Q/T仍明显更强。细类既没有改善同图持出成员的质量预测，也没有给近全员跨楼质量响应带来可采用增量。
4. **Semi存在人数条件。** n15、m≥4同父类内部换细类块时，SP和新Semi行为层的同构成稳定优势分别为11.39和7.14个百分点；SP在n≥20时反向，新Semi缺少同规模大块容量。结论是有限条件下有用的细层，并非大团队质量预测器。
5. **覆盖是可数、可恢复的。** 最终291,904个实际成员集合、12,953个ABC事件全部有结果；相对旧恢复索引新增289,315个集合。全部非空集合、全部人数向量、从零开始全部顺序的剩余量明确列出。全员减0/1/2人的129,046个集合，以及末两步243,030条顺序路径，是真正完成的有限穷举层。[S3—S7]
'''

    completion='''### 已完成的有限阶段

|对象|精确要求|实际完成|解释|
|---|---:|---:|---|
|全部229池N−2/N−1/N成员集合|129,046|129,046|这一有限层穷尽；全员单例不提供成员波动证据。|
|声明配比面板的类别人数向量|42,036|42,036|含402个纯类格；所有可行配比均覆盖。|
|上述格子的具体成员引用|125,494|125,494|每格最多3队；仅347格穷尽成员，其中297格只有唯一集合。|
|ABC实际成功构造事件|12,953|12,953|17,957次构造中5,004次无可行替代Z，全部保留失败账。|
|理论可行的每n/模式最大m机会|1,380|1,380|最大实际m20；不意味着全部成员三元组已枚举。|
|最终去重团队终点|291,904|291,904|2,589个旧集合补回几何；289,315个相对历史索引的新集合。|
|所有方法空间中已触及人数向量|1,847,304可行|54,853|这比42,036多，因为近全员及ABC也触及其它格；仍有1,792,451格未触及。|

291,904个终点中276,156个可完整条件评价；13,807个少于4点、1,565个无法连接、328个底面无效、48个两人队按合同暂不评价。失败没有删出请求或改写成零分。12,953个ABC中11,652个三臂均可评价，1,301个含至少一臂不可完整评价；普通Manual为7,617/7,835，普通Semi为1,972/2,069，门洞为2,063/3,049。[S5]

本轮先对155个实际端点测吞吐：单进程含加载约10.8–37.2队/秒，融合与评分合计中位0.04254秒、P90 0.10075秒。5个旧端点回放B8L2/D10在1e−7内一致。随后按池六进程计算、原子检查点和精确集合键去重；阶段耗时和重用数保留在回执，不拿基准外推替代实际完成量。

历史请求索引虽有583,261集合，本轮请求与现存旧完整几何／画像精选标量缓存的交集均为0。因此对重叠的2,589旧集合必须恢复几何；它们不计新增集合。52个本轮吞吐基准集合被后续阶段复用，未再次作为新的独立样本计数。其余本轮新集合为289,263。[S5]
'''

    global_results=f'''### 5.1 主结果：n≥20、实际m≥4

主范围有7,225个事件，其中普通Manual4,312、普通Semi1,227、门洞1,686。下面只列普通任务跨构成比较；各方法人群和容量不同，横行不能直接作公平算法排名。表中Q是B8L2；“同／跨”分别为A/B、A/C，两个比较的背景、n、实际m一致。区间为探索后的建筑重采样95%区间，未校正多方法选择。[S6]

{main_table}

![大团队主结果：质量波动与质量/形状联合稳定分别比较，各方法按自身合法支持报告。](figures/large_replacement_quality_and_shape.png)

**M粗类显示平均质量波动分离，但几何分离很小。** 绝对Q变化差为+0.937分，区间−0.291到+2.083；底面1−IoU同／跨为0.06706／0.06635，均高棱柱差0.07231／0.07169。几何并未随质量差同步分开。A2的联合稳定优势较清楚，但平均Q波动差+0.522仍跨零；因此保留其原答几何关系用途，对团队用途只给有限的总作用支持。

**推荐的新Manual细类不比粗类更能稳定团队形状。** 同／跨平均绝对Q变化为6.971／7.519，联合稳定40.93%／40.60%；底面差0.05625／0.06242、均高棱柱差0.06038／0.06708有一定方向分离，但联合稳定差仅+0.32个百分点、区间−6.34到+7.96。结构、位置、质量和完成状态不能由一个距离替代。

Rnew2在10个合法且有容量的目标楼，改构成Q波动反而较小：7.508／6.759；这保留为真实负结果，不抹去旧中小团队发现。F01只有4楼6格、14个成员集合且无ABC容量，不能与其它法宣称完成同规模检验。

### 5.2 在同一粗类内部换细类块

{fine_table}

M细类以及SP细类在大团队上没有形成“固定细构成更稳定”的优势。新Manual QTD同父层细块的Q波动方向略符合预期，但稳定差仅+0.47个百分点、区间跨零。细类仍可解释成员怎样不同；它们尚不能代替对具体位置、实际成员和支持余量的检查。

人数条件另有正结果。**n15、m≥4时**，SP同父层细块有100事件／9楼，同／跨绝对Q变化3.376／4.637，联合稳定66.25%／54.86%，差+11.39个百分点[+4.17,+20.69]；新Semi行为细层有78事件／11楼，其中73事件三臂可评分，同／跨Q变化2.323／3.004，联合稳定59.90%／52.76%，差+7.14个百分点[+1.14,+13.47]。Q变化分别在SP 98/100、新Semi 73/78个三臂可评分事件上估计；联合稳定率使用全部100/78事件，未完整评价记为未稳定。这些是实际成立的条件性分离，未扩张为全部人数规律。

为区分人数与换了图片的影响，SP细块在相同7个池、固定m4的n15/n20对照中：n15的21事件同／跨稳定75%／46.43%；n20的20事件为75%／75%。两种n使用各自注册的背景，所以这仍不是同一个背景的因果人数实验，但确实表明分离不只由纳入不同图片解释。新Semi正式新批可用人数约20，n≥20没有m≥4可行ABC；它的缺口是容量不足，不填作零作用。

### 5.3 大块越大，成员敏感性与构成差异怎样变化

![固定n20，在共同15图15楼上比较实际m4、8、12；大小块使用各自注册背景。](figures/replacement_m_response.png)

M粗类在共同15图／15楼的n20面板上，m4、8、12时同构成绝对Q变化为6.175、8.411、8.294，跨构成为6.182、9.166、10.465。跨构成质量波动随大块增强；联合稳定却从同构成41.67%／跨33.33%，变成35.00%／26.67%，再到16.67%／21.67%。到m12，同构成也容易改变具体结构，不能只根据较小Q波动称其形状可互换。

困难条件同样重要。M粗类在困难图15图14楼同／跨Q波动9.669／11.019，联合稳定20.76%／19.22%；简单图4楼为1.983／2.437、74.91%／65.86%。新QTD细层困难图联合稳定21.17%／24.73%，简单图82.19%／69.38%。这揭示类别作用随结构机会而变；不能把普通或容易图的稳定率移用到困难图。完整表保留所有n/m与难度，门洞独立报告。

### 5.4 构成的方向性作用：增减哪一类

在n≥20、m≥4注册事件中，以B→C观察实际净换类，增加M1的194事件平均B8L2+1.866、D10+2.059、输出角点+0.341、参考角点召回+3.93个百分点、遗漏−1.31个百分点；减少M1的312事件为Q−1.472、角点−0.210、遗漏+1.36个百分点。增加M1的Q区间跨零，减少方向的区间为−3.113到−0.075。平均B/C实际换约2.18／2.17人，不能把这条净效应称为整个m_AB块的独立效应。

方向与旧“常保留短转折”相符，也连接到pa4的实际补票。它仍包含历史Q关系：增加／减少M1时，Z相对Y的楼外历史Q效应约+4.11／−4.25。因此这先是类别的总作用，不能直接归为超出Q的结构收益。增加新QTD的QH对应Q+0.835、遗漏−0.90个百分点；减少QH为Q−1.573、遗漏+1.49个百分点。SP_LOW增加的平均推导高度下降约0.00157个相机高度，Q小幅+0.373；“偏低尺度”不是自动的坏类别。[S6]

### 5.5 Q／来源敏感性、低尾和失败

保持来源人数的事后子集中，A2 Manual联合稳定优势由+3.53变成−7.00个百分点，区间−21.19到+4.73；再要求X→Y和X→Z楼外块均Q差都≤2，只剩43事件／18楼，稳定差−6.02个百分点。**本轮没有把A2的总作用晋升为已证实的来源/Q之外团队增量。** 原答几何在共享点数和Q/来源下的旧匹配差仍保留，是另一项独立结果。

M粗按来源及双边历史块Q差≤5后124事件／19楼，同／跨Q波动9.418／11.177，但稳定差+2.25个百分点、区间仍宽。新Manual细类同来源且块Q差≤2时83事件／18楼，同／跨Q波动5.867／6.361，稳定差反而−6.62个百分点。匹配是总作用之后的附加信息检查；这些子集没有替代完整总体，也没有强称独立因果效果。

风险并非只来自程序失败。M粗大块同／跨下降超过5分的楼平衡比例为16.67%／17.90%，超过10分为12.11%／12.74%，B/C不完整评价率约1.32%／1.56%。新Manual细类为18.40%／19.63%和13.13%／13.74%。SP粗同／跨下降超过5分为10.62%／5.48%，与其平均波动反向结果一致。损失率只在对应边Q已知时估计；失败率用全部实际事件，不能把缺分记作无损失。

门洞事件中986/3,049至少一臂不完整评价，远高于普通Manual的218/7,835。它既有类别容量和结构难度，也有特殊范围资格，报告单列，不据此推断某类人员普遍能力差。
'''

    incremental='''### 6.1 细分能否概括新的实际成员

本轮在每个fine人数向量的最多三队中逐队持出，用其它同fine向量队预测，并用相同端点的父类向量作比较，避免粗细两套独立抽样造成假增量。n≥20时，新Manual QTD质量MSE由父层70.557变为细层96.101，M结构由70.066变为93.461，SP由22.740变为29.504；对应D10也变差。新Manual18楼没有一楼改善，M仅2/22楼改善，SP为0/10楼。[S6]

这检验的是给定图片内、稀疏同格样本对新成员集合的概括。细格只剩1–2个可训练队，父格有更多样本，方差成本是真实的使用代价，不能把这些差值解释为细类必然不存在。它支持当前实际用法：不能仅靠细格平均数替代成员级结果。下一个跨楼模型对照提供另一估计方式。

### 6.2 目标建筑外的连续特征、粗类与细类对照

在完整N−1/N−2层上，以目标楼外相同人员映射形成训练及目标团队特征，固定ridge=0.01；来源、QT均值、QT二阶矩、粗类、细类、QT加类并列。结果先去除每图固定人数的有限池均值，因此是相对构成响应；不是未知图的绝对Q预测。未知人员固定留在共同背景，只替换共同有标签和历史支持的成员；全员单例不参加。[S6]

N−2、n≥20共同现代Manual有165图22楼、59,622个可评分端点。B8L2池均值基线MSE15.25765，连续QT15.26221，M粗／细15.26496／15.27105，新Manual QTD粗／细15.26636／15.26606。新细相对粗仅改善0.000306（0.002%），9楼改善、13楼变差，中位改善−0.00704，D10不支持这点均值改善。**没有可采用的跨楼质量细层增量。**

共同Semi有21图11楼、3,235个可评分端点。池均值0.66701、QT0.67565、SP粗／细0.66876／0.67187、新Semi粗／细0.66877／0.67295。节点、失败及高度比也没有显示稳定细层收益。一个正式大池没有共同可替换人员，明确记不可估；Semi时间预测仅3楼有同口径机会，各目标楼外训练不足3楼，未给零效应。

**效率细层有实际增量。** 新Manual QTD在18楼的N−2大团队总源时长log响应中，细类相对Q父层MSE下降8.963%，16/18楼改善，楼级改善区间为0.00006198到0.00014956。粗／细相对池均值R²为0.0098／0.0985；连续QT为0.5126，QT二阶矩为0.5714。细类是一种可读的成本工作分区，仍没有超越连续历史。

![同新批Manual楼外细类对照：时间差跨楼重复，转折表达差较弱。](figures/manual_efficiency_vs_structure.png)

在大块事件中进一步只保留QH人数不变、QL.1↔QL.2的细类转移，方向依据训练T排序确定，没有用目标时间选方向。n≥20/m_AB≥4时，减少较慢QL.2的114事件／18楼，B→C来源时间平均−3.21%，79.25%事件方向符合预期；增加较慢类的124事件／17楼平均+2.92%，符合率76.24%。两个数均为建筑平衡比例，不是简单样本频率。B/C真实净换人数平均1.55／1.77，Q父层不变但具体成员会变；减少较慢类的平均Q+0.092，区间−1.903到+2.044，不能承诺无质量代价。对应下降超过5分约10.39%。[S6]

Rnew2与现代方法在原目标域11楼、82图、31,293个端点具有完全相同支持，复用已有拟合形成公平的人员集合对照：M粗MSE5.52369、M细5.53827、QT5.54608、Rnew2粗5.55730、A2为5.56110、新QTD细5.56305。旧Rnew2标签使用固定10楼历史，现代连续特征使用排除目标楼后的21楼历史；这是同人员集合的可用研究工件对照，不是相同训练预算下的算法比较。M粗仅解释约0.5%有限池质量方差，旧反向类型没有显示统一近全员预测收益。F01纳入七法共同交集后使Rnew2只剩一类，明确不可识别；F01自身保留成本区分用途，未借这个退化面板证明Rnew2失败。

近全员全部成员对的辅助检查也没有显示细层突增。N−2、m2、n≥20时，M粗同／跨平均Q差1.803／1.856，M细1.804／1.858；新Manual粗2.365／2.483、细2.322／2.459。不同方法支持不同，这些只作各方法内部有限总体描述；该配对层控制n/m/图片但不逐对对齐同一背景，所以正式大块结论仍用ABC。
'''

    unfinished='''### 9.3 已完成、复用与本轮未展开的边界

已完成：26子集逐条件机会筛查；4套新候选的实际成员与楼外标签；9法/10方法条件统一接口；全部注册的291,904终点、42,036配比格、12,953ABC；近全员精确成员层、跨楼连续/粗细对照、末两步全部顺序，以及五个真实机制案例。旧分类、反向学习、直接m2负结果、核查与画像组合成果按其原阶段身份复用。

未展开：全部池、全部n的所有具体成员集合；1,792,451个尚未触及的可行方法人数向量；所有配置内的全部成员组合；全部ABC成员三元组；每池全N!从零加入顺序。三者的精确规模与当前覆盖/剩余量已经逐池逐n落表。已穷尽的129,046近全员集合和243,030末两步路径不会因这些更大空间未展开而丧失完整性，也不冒充更大空间已经完成。

机会不足另记：Semi自身D域15子集；F01大块ABC；新Semi行为类n≥20/m≥4；无共同可变成员的池；缺失或不兼容时间；缺少物理语义唯一裁定的少量局部。未用修改GT、资格、原答、投票门槛或定义未知类来填满这些缺口。
'''

    source=(HERE/'REPORT_TEMPLATE_ZH.md').read_text(encoding='utf8')
    replacements={'MAIN_FINDINGS':main_findings,'DOMAIN_TABLE':domain_table,'COMPLETION_COVERAGE':completion,
                  'GLOBAL_RESULTS':global_results,'INCREMENTAL_RESULTS':incremental,'UNFINISHED_SCOPE':unfinished}
    for k,v in replacements.items():
        assert '{{'+k+'}}' in source
        source=source.replace('{{'+k+'}}',v.strip())
    assert '{{' not in source
    (HERE/'REPORT_ZH.md').write_text(source,encoding='utf8')
    (HERE/'REPORT_DATA_RECEIPT.json').write_text(json.dumps({'endpoint_count':291904,'event_count':len(events),
       'key_event_columns':keycols,'unavailable_requested_key_column_names':missing,
       'source':'Frozen analysis tables; no new endpoint calls','report_placeholders_remaining':False},ensure_ascii=False,indent=2),encoding='utf8')
    print('Final report and key tables written.')

if __name__=='__main__':main()
