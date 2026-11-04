"""Select transparent post-outcome illustrations from the frozen full results.

This does not select scientific teams. All cases are already computed physical
pairs; their selection role and the surrounding image mean are retained.
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd
from mechanism_core import ROOT,OUT,sha,save_csv,save_json

SOURCE=OUT.parent/'analysis/PHYSICAL_PAIRS_AUTOMATIC.csv.gz'

def nearest(d,col,target):
    return d.assign(_distance=(d[col]-target).abs()).sort_values(['_distance','canonical_physical_pair_id']).iloc[0]

def main():
    names=['event_id','source_event_id','original_event_id','source_leg','source_registry','analysis_source','analysis_cohort',
           'pool_id','image','building','scope','condition','layer','reference_id','reference_version',
           'A_team_key','C_team_key','A_workers','C_workers','D_workers','X_workers','Z_workers',
           'source_class_current','target_class_current','current_direction','class_pair','direction','n','m',
           'canonical_physical_pair_id','orientation_sign','current_D_class_counts','design_family','method_event_aliases',
           'official_difficulty','structural_condition','geometric_challenge','room_type','A_B8L2','C_B8L2','dQ','abs_dQ','A_nodes','C_nodes']
    d=pd.read_csv(SOURCE,usecols=lambda x:x in names,keep_default_na=False,low_memory=False)
    for c in ['n','m','A_B8L2','C_B8L2','dQ','abs_dQ','A_nodes','C_nodes']:d[c]=pd.to_numeric(d[c],errors='coerce')
    old=d[d.analysis_cohort.eq('legacy_current_conditional')].copy()
    if old.empty:
        # The registry's immutable source identity is authoritative if a report
        # chooses another display name for its cohort.
        old=d[d.analysis_source.eq('legacy_target_stock_current_label_conditional')].copy()
    base=old[old.scope.eq('primary')&old.condition.eq('manual')&old.layer.eq('ordinary_manual')&old.n.eq(20)&old.m.eq(7)&old.dQ.notna()].copy()
    choices=[];context=[]
    def add(row,role,title,reason,context_value=None):
        r=row.to_dict();r.pop('_distance',None)
        if 'canonical_physical_pair_id' not in r:r['canonical_physical_pair_id']=str(row.name)
        r.update(selection_role=role,purpose_zh=title,selection_reason=reason,selection_is_post_outcome=True,
                 context_image_mean_dQ=context_value)
        choices.append(r)
    for pair,g in base.groupby('class_pair',sort=True):
        images=g.groupby(['pool_id','image','building','official_difficulty'],as_index=False).agg(image_mean_dQ=('dQ','mean'),physical_pairs=('canonical_physical_pair_id','nunique'))
        context.extend(dict(class_pair=pair,**r) for r in images.to_dict('records'))
        positive=images[images.image_mean_dQ.gt(1)]
        if positive.empty:positive=images[images.image_mean_dQ.gt(0)]
        assert len(positive)>0
        pi=positive.assign(_distance=(positive.image_mean_dQ-positive.image_mean_dQ.median()).abs()).sort_values(['_distance','pool_id']).iloc[0]
        pgroup=g[g.pool_id.eq(pi.pool_id)]
        pr=nearest(pgroup,'dQ',pi.image_mean_dQ)
        add(pr,pair+'_typical_positive',pair.replace('_','→')+'：接近正向逐图中位的实例',
            '20/7; choose positive image closest to positive image-mean median, then physical pair closest to that image mean.',float(pi.image_mean_dQ))
        negative_images=images[images.official_difficulty.eq(pi.official_difficulty)&images.image_mean_dQ.lt(-1)]
        if not negative_images.empty:
            ni=negative_images.assign(_distance=(negative_images.image_mean_dQ-negative_images.image_mean_dQ.median()).abs()).sort_values(['_distance','pool_id']).iloc[0]
            nr=nearest(g[g.pool_id.eq(ni.pool_id)],'dQ',ni.image_mean_dQ)
            add(nr,pair+'_counterexample',pair.replace('_','→')+'：同预算同难度的负向图片',
                'Same 20/7 and official difficulty as typical positive; negative image nearest negative-image median, physical pair nearest image mean.',float(ni.image_mean_dQ))
        else:
            # If image means are all positive, a negative member realization is
            # explicitly a within-image example, not a negative population mean.
            candidates=pgroup[pgroup.dQ.lt(-1)]
            if not candidates.empty:
                nr=nearest(candidates,'dQ',candidates.dQ.median())
                add(nr,pair+'_member_counterexample',pair.replace('_','→')+'：均值正向图片内的负向成员实现',
                    'No same-difficulty negative image mean <= -1. Use negative physical pair within the very same typical image; image mean remains positive.',float(pi.image_mean_dQ))
            else:
                candidates=pgroup[pgroup.dQ.abs().le(1)]
                if candidates.empty:candidates=g[g.official_difficulty.eq(pi.official_difficulty)]
                nr=nearest(candidates,'abs_dQ',0)
                ci=images[images.pool_id.eq(nr.pool_id)].iloc[0]
                add(nr,pair+'_nearzero_or_low_effect',pair.replace('_','→')+'：同条件小变化实例',
                    'No suitable negative same-image member realization. Lowest absolute physical effect at the same budget/difficulty, explicitly not a negative image-mean claim.',float(ci.image_mean_dQ))
    diag=pd.read_csv(OUT/'DIAGNOSTIC_PAIR_RESULTS.csv.gz',keep_default_na=False,low_memory=False)
    for c in ['delta_Q','abs_delta_Q','n','m','A_Q','C_Q']:diag[c]=pd.to_numeric(diag[c],errors='coerce')
    lookup=old.set_index('canonical_physical_pair_id')
    def diag_add(z,role,title,reason,target=None):
        if z.empty:return
        if target is None:target=z.abs_delta_Q.median()
        selected=z.assign(_distance=(z.abs_delta_Q-target).abs()).sort_values(['_distance','canonical_pair_id']).iloc[0]
        row=lookup.loc[selected.canonical_pair_id]
        if isinstance(row,pd.DataFrame):row=row.sort_values('event_id').iloc[0]
        add(row,role,title,reason)
    positive_cross=diag[diag.n.eq(14)&diag.unordered_pair.eq('C2_C3')&diag.difficulty.eq('困难')&diag.stable_threshold_cross_any&diag.delta_Q.ge(10)]
    diag_add(positive_cross,'vote_cross_positive','14/7 困难图：跨过同一票门槛后升质',
             'Outcome-blind diagnostic sample, 14/7 C2->C3 hard images with stable-anchor crossing and dQ>=10; nearest median absolute change.')
    negative_cross=diag[diag.n.eq(14)&diag.unordered_pair.eq('C2_C3')&diag.difficulty.eq('困难')&diag.stable_threshold_cross_any&diag.delta_Q.lt(0)]
    diag_add(negative_cross,'vote_cross_negative','14/7 困难图：同样过票却降质',
             'Same budget, class pair and difficulty as vote-positive role; negative stable-anchor crossings, nearest median absolute change.')
    positions=diag[diag.n.eq(20)&diag.same_node_count&~diag.stable_threshold_cross_any&~diag.D_partition_changed&diag.abs_delta_Q.ge(10)]
    diag_add(positions,'same_nodes_position','20/7：节点与对应不变，定位和几何仍改变',
             'Outcome-blind sample, same node count and D partition, no detected stable-anchor crossing, abs dQ>=10; nearest median absolute change.')
    high=diag[diag.n.eq(20)&diag.A_Q.ge(90)&diag.C_Q.ge(90)&diag.abs_delta_Q.le(1)&diag.same_node_count]
    diag_add(high,'high_score_nearzero','20/7：两端高分、质量接近',
             'Outcome-blind sample; both Q>=90, abs dQ<=1 and equal node count; nearest median absolute change. Illustrates bounded quality headroom, not an independent proof of mechanism.')
    loss=diag[diag.n.eq(14)&diag.A_score_status.ne('no_connection')&diag.C_score_status.eq('no_connection')]
    if not loss.empty:
        chosen=loss.sort_values('canonical_pair_id').iloc[0];row=lookup.loc[chosen.canonical_pair_id]
        if isinstance(row,pd.DataFrame):row=row.sort_values('event_id').iloc[0]
        add(row,'connection_lost','14/7：入选节点增加，但完整来源环消失',
            'First canonical physical pair in frozen diagnostic sample with evaluable A and no_connection C. Missing Q remains missing.')
    small=diag[diag.n.eq(20)&diag.stable_threshold_cross_any&diag.abs_delta_Q.lt(5)&diag.abs_delta_Q.notna()]
    diag_add(small,'vote_cross_small','20/7：票数跨门槛，也可能只有数分变化',
             'Outcome-blind sample, observed stable-anchor crossing with abs dQ<5; smallest absolute change. Threshold crossing is not sufficient for a >=5-point jump.',target=0)
    selected=pd.DataFrame(choices)
    # Duplicate physical examples have one entry, with every requested role kept.
    merged=[]
    for key,g in selected.groupby('canonical_physical_pair_id',sort=False):
        r=g.iloc[0].to_dict();r['selection_roles']='|'.join(g.selection_role);r['additional_purposes_json']=json.dumps(g.purpose_zh.tolist(),ensure_ascii=False)
        r['selection_reasons_json']=json.dumps(g.selection_reason.tolist(),ensure_ascii=False)
        r['canonical_pair_id']=key;r['unordered_pair']=r['class_pair'];r['n_A']=r['n_C']=int(r['n']);r['m_X']=r['m_Z']=int(r['m'])
        r['case_id']=f'AC{len(merged)+1:02d}';merged.append(r)
    output=pd.DataFrame(merged)
    assert sum(len(x.split('|')) for x in output.selection_roles)==len(choices),'An indexed source row lost its physical-pair identity.'
    target=OUT/'CASE_SELECTION.csv'
    if target.exists():
        previous=pd.read_csv(target,keep_default_na=False)
        assert previous.canonical_pair_id.tolist()==output.canonical_pair_id.tolist(),'Do not replace frozen illustrative cases after inspecting native traces.'
    else:save_csv(target,output)
    save_csv(OUT/'CASE_SELECTION_IMAGE_CONTEXT.csv',context)
    receipt=dict(source=str(SOURCE.relative_to(ROOT)),source_sha256=sha(SOURCE),selected_cases=len(output),requested_roles=len(choices),
                 selection_sha256=sha(target),original_images=output.image.nunique(),unique_endpoints=len(set(output.A_team_key)|set(output.C_team_key)),
                 selection_is_post_outcome=True,case_frequencies_not_population_estimates=True,new_scientific_teams=0,
                 cases=output[['case_id','image','n','m','class_pair','dQ','selection_roles']].to_dict('records'))
    save_json(OUT/'CASE_SELECTION_RECEIPT.json',receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
