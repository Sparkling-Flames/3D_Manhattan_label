"""Assemble adoption tables from completed frozen-label experiments; no fitting/fusion."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

W = Path(__file__).resolve().parents[2]
OUT = W / 'stage07_adoption'
KEY = ['method','condition','scope','role_direction','n','m']

def save(df, name):
    p=OUT/name; tmp=p.with_name(p.name+'.tmp')
    df.to_csv(tmp,index=False,compression='gzip' if p.suffix=='.gz' else None)
    tmp.replace(p)

def semantics(r):
    method=r['method']
    if method in ('DSTRUCT_K3','TARGET_DSTRUCT_K3','OPPSTRUCT_K3'):
        return '复杂结构机会转折中间角色','较多转折角色','结构表达与定位；群体倾向不等于每图必要细节'
    if method=='OPPJOINT_K4':
        return '楼外历史Q最低角色，通常记录较短','楼外历史Q最高角色，通常较多转折','主要质量方向跨K3父类；四细层用于时间和成员组织'
    if method=='DJOINT_K4':
        return '楼外历史Q第2角色','楼外历史Q最高角色','难度结构与Q/T联合，作为旧联合候选保留'
    if method=='RFUSE_GEOM_K2':
        return '人数最多的几何响应类','小容量几何响应类','当前冻结融合下的响应分区，不等于纯原答类型'
    if method in ('OPPGEOM_K3','MSDGEOM_SCOPE_K4'):
        s,t=r['role_direction'].split('->')
        return '相对面积排序'+s.split(':')[-1], '相对面积排序'+t, '角色由楼外尺度中心对齐，另结合位置、结构或跨条件/scope'
    if method=='Q_MEDIAN2':
        if ':2/' in r['role_direction']: return '较高历史Q','较低历史Q','降质与时间变化对照；有方向性损失也属于分类差异'
        return '较低历史Q','较高历史Q','质量一维基线，保留同支持比较'
    return '见逐折角色表','见逐折角色表','全量比较保留'

def recommendation(r):
    m,n,k=r['method'],r['n'],r['m']
    if m=='OPPJOINT_K4':
        return { (12,6):('主要采用','半队大块区分与用时间换质量；粗层已承担主效应'),
                 (20,5):('主要采用：较大队伍','多数图片升质、幅度区分较弱、时间代价较小'),
                 (26,3):('补充：较小比例','多数仍有质量收益，不作为最大区分条件') }[(n,k)]
    if m=='TARGET_DSTRUCT_K3':
        if (n,k)==(14,7):return '主要结构补充','半队结构/定位差异；完整困难/简单分项与背景证据'
        return '结构规模补充','保留真实规模效应，不假设替换块越大或人数越多越好'
    if m=='RFUSE_GEOM_K2':
        return ('核心反推对照' if (n,k)==(12,4) else '反推规模补充'),'小容量响应类可产生有效差异，不要求每类都大'
    if m=='MSDGEOM_SCOPE_K4':return '跨条件与scope补充','保留Manual/Semi/scope历史联合的有效方向，不混合两种评价终点'
    if m=='OPPGEOM_K3' and (n,k)==(26,3):return '不作升质推荐，保留近零对照','扩展后净质量接近零，不能沿用广筛峰值'
    if m=='OPPGEOM_K3':return '位置/结构补充','用于角点数不变定位改善等机制；容量小于主方法'
    if m=='Q_MEDIAN2':return '保留基线及风险方向','用同目标n/m比较；不把降质结果删除'
    if m=='DSTRUCT_K3':return '保留旧主法对照','仍有多数支持；新目标感知方案并非在每个共同配置都胜出'
    return '有用但不另设主法','与主要联合/结构用途重叠，保留全部方向和结果'

def main():
    d=pd.read_csv(W/'analysis/focused_summary/ALL_DIRECTION_N_M_RESULTS.csv.gz')
    p=pd.read_csv(W/'analysis/focused_contexts/MEMBER_BACKGROUND_STABILITY_BY_POOL.csv.gz')
    c=pd.read_csv(W/'experiment/focused_design/REGISTERED_COVERAGE.csv.gz',dtype={'strict_ABC_member_background_count':str,'xyz_unordered_AB_count':str})
    c['role_direction']=c.apply(lambda r:f"{r.role_axis}:{int(r.source_rank)}/{int(r.method.rsplit('K',1)[-1]) if '_K' in r.method else 2}->{int(r.target_rank)}/{int(r.method.rsplit('K',1)[-1]) if '_K' in r.method else 2}",axis=1)
    event_cols=['event_id','method','condition','scope','n','m','pool_id','image','building','source_A_seat_fraction','source_candidate_fraction','target_candidate_fraction','background_target_n','seat_net_change_l1','source_capacity','target_capacity','D','X','Y','Z','A_team_key','B_team_key','C_team_key','B8L2_gap','B8L2_CA','B8L2_CB','Q_loss10_CA','Q_loss10_CB','C_failed']
    # The delivered compact effects and exact event design are the canonical
    # relational inputs; no duplicated 764-column working cache is required.
    compact=W/'analysis/focused_compact/EVENT_EFFECTS_COMPLETE.csv.gz'
    available=set(pd.read_csv(compact,nrows=0).columns)
    e=pd.read_csv(compact,usecols=[v for v in event_cols if v in available])
    missing=[v for v in event_cols if v not in available]
    design=pd.read_csv(W/'experiment/focused_design/EVENTS_EXACT.csv.gz',usecols=['event_id','method']+missing)
    e=e.merge(design,on=['event_id','method'],validate='one_to_one')
    roles=pd.read_csv(W/'analysis/focused_summary/EVENT_ROLE_LINKS.csv.gz',usecols=['event_id','method','role_direction'])
    e=e.merge(roles,on=['event_id','method'],validate='one_to_one')
    extras=[]
    for key,g in p.groupby(KEY,dropna=False):
        f=e
        cc=c
        for a,b in zip(KEY,key): f=f[f[a].eq(b)];cc=cc[cc[a].eq(b)]
        z=dict(zip(KEY,key))
        for metric in ['source_capacity','target_capacity','pool_n','background_target_min','background_target_max']:
            z[metric+'_min']=float(g[metric].min());z[metric+'_max']=float(g[metric].max())
        for metric in ['XYZ_blocks','backgrounds','target_Z_sets','source_X_sets','source_Y_sets']:
            z['pools_with_multiple_'+metric]=int((g[metric]>1).sum())
        z['sampled_pool_count']=len(g)
        z['pool_majority_event_gap_positive']=int((g['B8L2_gap_positive_fraction']>.5).sum())
        z['pool_all_event_gap_positive']=int((g['B8L2_gap_positive_fraction']==1).sum())
        z['pool_majority_event_CB_positive']=int((g['B8L2_CB_positive_fraction']>.5).sum())
        for metric in ['B8L2_gap_positive_fraction','B8L2_CB_positive_fraction','B8L2_CB_std']:
            z[metric+'_mean_image']=float(g.groupby('image')[metric].mean().mean())
        for metric in ['source_A_seat_fraction','source_candidate_fraction','target_candidate_fraction']:
            z[metric+'_min']=float(f[metric].min());z[metric+'_max']=float(f[metric].max())
        z['strict_ABC_combination_capacity_unordered_AB']=str(sum(int(float(v)) if '.' in str(v) else int(v) for v in cc.strict_ABC_member_background_count))
        z['XYZ_combination_capacity_unordered_AB']=str(sum(int(float(v)) if '.' in str(v) else int(v) for v in cc.xyz_unordered_AB_count))
        extras.append(z)
    d=d.merge(pd.DataFrame(extras),on=KEY,validate='one_to_one')
    d['replacement_fraction']=d.m/d.n;d['actual_m_AB']=d.m;d['actual_m_AC']=d.m;d['class_seat_l1_change']=2*d.m
    d['background_size']=d.n-d.m
    d['background_design']='共同D；每池最多2组X/Y/Z，按可行目标类背景人数取低/中/高，成员哈希抽取；相同端点复用'
    d['hierarchy']=d.method.map(lambda x:'三粗四细中的细层；主方向跨父类' if x=='OPPJOINT_K4' else '独立工作分类，见逐折中心')
    d['evaluation']='普通Manual；原主合法目标；v2.1；楼外标签'
    d['person_domain']='该目标正式可用池；X/Y/Z需该折已知类，D可含未知类'
    d[['source_role_zh','target_role_zh','role_interpretation_zh']]=d.apply(lambda r:pd.Series(semantics(r)),axis=1)
    d[['adoption_zh','adoption_reason_zh']]=d.apply(lambda r:pd.Series(recommendation(r)),axis=1)
    d['comparison_identity']='同一事件D/X/Y/Z严格互斥；跨方法同池比较不意味着所有事件同一D'
    d['time_interpretation']='来源匹配的库存记录秒数求和之比，百分数；不是新测生产耗时'
    d['event_link']='analysis/focused_compact/EVENT_EFFECTS_COMPLETE.csv.gz'
    save(d,'ALL32_EXTENDED_CONDITIONS_COMPLETE.csv')
    concise=['method','source_role_zh','target_role_zh','hierarchy','n','m','replacement_fraction','class_seat_l1_change','background_size','source_capacity_min','source_capacity_max','target_capacity_min','target_capacity_max','source_A_seat_fraction_min','source_A_seat_fraction_max','scope','images','buildings','events','blocks','backgrounds','ABC_scored_events','B8L2_within_mean_image','B8L2_cross_mean_image','B8L2_gap_positive_images','B8L2_gap_valid_images','B8L2_gap_positive_buildings','B8L2_gap_valid_buildings','B8L2_BA_mean_image','B8L2_CA_mean_image','B8L2_CB_mean_image','B8L2_CA_positive_images','B8L2_CA_valid_images','B8L2_CB_positive_images','B8L2_CB_valid_images','B8L2_CB_positive_buildings','B8L2_CB_valid_buildings','D10_CB_mean_image','IoU3D100_CB_mean_image','iou_2d_CB_mean_image','fusion_turn_n_CB_mean_image','matched_ref_top_abs_deg_CB_mean_image','matched_ref_bottom_abs_deg_CB_mean_image','record_time_CB_pct_source_matched_mean_image','record_time_CB_pct_source_matched_valid_images','A_failed_events','B_failed_events','C_failed_events','Q_loss10_CB_events','Q_loss10_CB_events_valid','pools_with_multiple_XYZ_blocks','pools_with_multiple_backgrounds','pools_with_multiple_target_Z_sets','pool_majority_event_CB_positive','strict_ABC_combination_capacity_unordered_AB','adoption_zh','adoption_reason_zh']
    save(d[[x for x in concise if x in d]],'EFFECTIVE_EXCHANGE_CONDITIONS.csv')
    # Keep every failure or contrary/flat image of the adopted directions.
    ims=pd.read_csv(W/'analysis/focused_summary/DIRECTION_IMAGE_RESULTS.csv.gz')
    selected=[('OPPJOINT_K4',12,6),('OPPJOINT_K4',20,5),('TARGET_DSTRUCT_K3',14,7),('RFUSE_GEOM_K2',12,4)]
    keep=ims.apply(lambda r:(r.method,r.n,r.m) in selected,axis=1)
    ims=ims[keep].copy()
    def flags(r):
        a=[]
        if pd.notna(r.B8L2_gap) and r.B8L2_gap<=0:a.append('跨类Q幅度未大于同类')
        if pd.notna(r.B8L2_CB) and r.B8L2_CB<=0:a.append('C−B净Q未提高')
        if r.C_failed>0:a.append('存在C不可评分')
        if pd.isna(r.B8L2_gap):a.append('无三队共同质量支持')
        return '；'.join(a)
    ims['counterexample_type']=ims.apply(flags,axis=1)
    counter=ims[ims.counterexample_type.ne('')]
    save(ims,'RECOMMENDED_CONDITIONS_ALL_IMAGES.csv')
    save(counter,'RECOMMENDED_CONDITIONS_COUNTEREXAMPLES.csv')
    ce=e.merge(counter[KEY+['image','counterexample_type']],on=KEY+['image'],how='inner',validate='many_to_one')
    save(ce,'COUNTEREXAMPLE_EXACT_EVENT_LINKS.csv.gz')
    # Main-table markdown used in the updated existing report.
    lines=['|分类与方向|n / m|图 / 楼|同类 / 跨类幅度|跨类更大图|C−A / C−B|C−B提高图|记录时间 C−B|','|---|---:|---:|---:|---:|---:|---:|---:|']
    picks=[('OPPJOINT_K4',12,6),('OPPJOINT_K4',20,5),('OPPJOINT_K4',26,3),('TARGET_DSTRUCT_K3',14,7),('TARGET_DSTRUCT_K3',18,7),('RFUSE_GEOM_K2',12,4),('MSDGEOM_SCOPE_K4',14,7)]
    for m,n,k in picks:
        r=d[(d.method==m)&(d.n==n)&(d.m==k)].iloc[0]
        lines.append(f'|{m}|{n} / {k}|{r.images} / {r.buildings}|{r.B8L2_within_mean_image:.2f} / {r.B8L2_cross_mean_image:.2f}|{int(r.B8L2_gap_positive_images)}/{int(r.B8L2_gap_valid_images)}|{r.B8L2_CA_mean_image:+.2f} / {r.B8L2_CB_mean_image:+.2f}|{int(r.B8L2_CB_positive_images)}/{int(r.B8L2_CB_valid_images)}|{r.record_time_CB_pct_source_matched_mean_image:+.2f}%（{int(r.record_time_CB_pct_source_matched_valid_images)}图）|')
    (OUT/'CONDITION_TABLE_FRAGMENT.md').write_text('\n'.join(lines)+'\n')
    receipt=dict(source_commit='a476461d7ede8db95da43de4139e612c05e618bc',data_release='v2.1',conditions=len(d),recommended_image_rows=len(ims),counterexample_image_rows=len(counter),counterexample_event_links=len(ce),new_fusion=0,new_labels=0,interpretation='Image-equal effects; all 32 extension conditions retained regardless of sign. Combination capacity is not completed coverage.')
    (OUT/'CONDITION_TABLE_READ_CHECK.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()
