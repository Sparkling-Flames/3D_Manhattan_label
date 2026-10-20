#!/usr/bin/env python3
"""Matched original-context summary of the explicitly post hoc W132 probe."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from assessment_summary_common import BASE,ROOT,HERE,sha,load_exact,write_csv,write_json

METHOD='R_directswap_geometry_partition_b2_K2__ordinary_new__mixed_history_v1'
METRICS=[
    'net_B8L2_change','net_D10_change','A_B8L2','B_B8L2','C_B8L2',
    'within_abs_B8L2_change','cross_abs_B8L2_change',
    'within_joint_stable_main','cross_joint_stable_main','gap_joint_stable_main',
    'within_geometry_noQ_main','cross_geometry_noQ_main','gap_geometry_noQ_main',
    'within_geometry_shape_main','cross_geometry_shape_main','gap_geometry_shape_main',
    'within_floor_jaccard_difference','cross_floor_jaccard_difference',
    'within_prism_distance','cross_prism_distance','within_node_count_changed','cross_node_count_changed',
    'net_diag_wall_coverage_05_delta','net_diag_corner_recall_05_delta','net_IoU3D100_delta',
    'A_complete','B_complete','C_complete','A_score_missing','B_score_missing','C_score_missing',
    'net_Q_improve_gt2','net_Q_worsen_gt2','net_Q_worsen_gt5','net_complete_lost','net_complete_restored',
]


def hierarchy(frame,keys,metrics,alternative_frame):
    pk=keys+['building','image_id','pool_id']
    p=frame.groupby(pk,dropna=False)[metrics].mean().reset_index()
    im=p.groupby(keys+['building','image_id'],dropna=False)[metrics].mean().reset_index()
    bu=im.groupby(keys+['building'],dropna=False)[metrics].mean().reset_index()
    ag=bu.groupby(keys,dropna=False)[metrics].mean().reset_index()
    support=[]
    for key,g in frame.groupby(keys,dropna=False):
        key=key if isinstance(key,tuple) else (key,)
        alternatives=alternative_frame[alternative_frame.parent_event_id.isin(g.parent_event_id)]
        r=dict(zip(keys,key))|dict(original_events=len(g),alternative_events=len(alternatives),
            pools=g.pool_id.nunique(),true_images=g.image_id.nunique(),buildings=g.building.nunique(),
            alternative_people=alternatives.probe_replacement_worker.nunique(),
            actual_replacement_teams=len(set(alternatives.A_team_key)|set(alternatives.B_team_key)|set(alternatives.C_team_key)),
            finite_Q_original_events=int(g.paired_net_B8L2_change.notna().sum()),
            finite_Q_alternative_comparisons=int(g.net_B8L2_change_paired_alternatives.sum()))
        for s,tab in [('images',im),('buildings',bu)]:
            z=tab
            for col,val in zip(keys,key):z=z[z[col].eq(val)]
            for metric in ['replacement_matched_net_B8L2_change','paired_net_B8L2_change']:
                r[metric+'_positive_'+s]=int((z[metric]>1e-9).sum())
                r[metric+'_negative_'+s]=int((z[metric]<-1e-9).sum())
                r[metric+'_equal_'+s]=int((z[metric].abs()<=1e-9).sum())
        support.append(r)
    ag=ag.merge(pd.DataFrame(support),on=keys,validate='one_to_one')
    return im,bu,ag


def main():
    out=HERE/'w132_probe';design=json.load(open(out/'DESIGN_RECEIPT.json'))
    assert sha(out/'REGISTER.json')==design['register_sha256']
    f,md,meta=load_exact('w132_probe',[METHOD]);assert meta['request_sha256']==design['request_sha256']
    fields=['event_id','parent_event_id','probe_role','probe_variant','probe_replacement_worker','probe_alternatives_n','probe_status']
    f=f.merge(md[fields],on='event_id',validate='one_to_one')
    originals=f[f.probe_variant.eq('original')];alternatives=f[f.probe_variant.eq('same_class_replacement')]
    assert len(originals)==116 and len(alternatives)==235
    orig=originals.set_index('event_id')
    # Native reruns of the original teams must reconstruct the frozen panel.
    earlier=[]
    for pid in originals.pool_id.unique():
        z=pd.read_csv(BASE/'assessment/nested_new2_metrics/event_parts'/(pid+'.csv.gz'))
        earlier.append(z[z.event_id.isin(orig.index)])
    earlier=pd.concat(earlier).set_index('event_id').loc[orig.index]
    checked=0
    for metric in [x for x in METRICS if x in earlier]:
        a=pd.to_numeric(orig[metric]).to_numpy(float);b=pd.to_numeric(earlier[metric]).to_numpy(float)
        assert np.array_equal(np.isnan(a),np.isnan(b)) and np.allclose(a,b,atol=1e-12,rtol=0,equal_nan=True),metric
        checked+=1
    detailed=[];parents=[]
    for parent,g in alternatives.groupby('parent_event_id'):
        baseline=orig.loc[parent]
        p={k:baseline[k] for k in ['pool_id','building','image_id','image','outgoing_class','incoming_class','probe_role']}
        p.update(parent_event_id=parent,alternative_events=len(g),alternative_people=g.probe_replacement_worker.nunique())
        for metric in METRICS:
            old=float(baseline[metric]);new=pd.to_numeric(g[metric]).astype(float)
            mask=np.isfinite(new)&np.isfinite(old)
            p['original_all_'+metric]=old
            p['replacement_all_'+metric]=float(new.mean())
            p['original_matched_'+metric]=old if mask.any() else np.nan
            p['replacement_matched_'+metric]=float(new[mask].mean())
            p['paired_'+metric]=float((new[mask]-old).mean())
            p[metric+'_paired_alternatives']=int(mask.sum())
        for _,row in g.iterrows():
            r={k:row[k] for k in ['event_id','parent_event_id','probe_role','probe_replacement_worker','pool_id','image_id','building','image','outgoing_class','incoming_class']}
            for metric in METRICS:
                a=float(baseline[metric]);b=float(row[metric]);r['original_'+metric]=a;r['replacement_'+metric]=b;r['paired_'+metric]=b-a
            if row.probe_role=='A_outgoing_only':
                assert row.B_team_key==baseline.B_team_key and row.C_team_key==baseline.C_team_key
                for metric in ['net_B8L2_change','net_D10_change','B_B8L2','C_B8L2']:
                    a=float(baseline[metric]);b=float(row[metric]);assert (np.isnan(a) and np.isnan(b)) or abs(a-b)<=1e-12
            detailed.append(r)
        parents.append(p)
    parentdf=pd.DataFrame(parents);detail=pd.DataFrame(detailed)
    write_csv(out/'matched_parent_effects.csv.gz',parentdf)
    write_csv(out/'exact_alternative_effects.csv.gz',detail)
    nums=[c for c in parentdf if c.startswith(('original_all_','replacement_all_','original_matched_','replacement_matched_','paired_'))]
    for rolemode in ['all_available','by_W132_position']:
        z=parentdf.copy()
        if rolemode=='all_available':z['probe_role']='all_available'
        tables=hierarchy(z,['outgoing_class','incoming_class','probe_role'],nums,alternatives)
        for level,t in zip(['per_true_image','per_building','aggregate'],tables):write_csv(out/(rolemode+'_'+level+'.csv.gz'),t)
    # Baseline groups whose capacity differs remain fully explicit.
    capacity=[]
    for key,g in originals.groupby(['outgoing_class','incoming_class','probe_role','probe_status']):
        capacity.append(dict(zip(['outgoing_class','incoming_class','probe_role','probe_status'],key))|dict(
            original_events=len(g),pools=g.pool_id.nunique(),true_images=g.image_id.nunique(),buildings=g.building.nunique(),
            alternatives_requested=int(g.probe_alternatives_n.sum())))
    write_csv(out/'CAPACITY_SUMMARY.csv',pd.DataFrame(capacity))
    # A compact exact selection, post hoc by design, does not create additional rules.
    cases=[];mdmap={r['event_id']:r for r in md.to_dict('records')}
    for key,g in detail.groupby(['outgoing_class','probe_role']):
        for reason,ascending in [('largest_effect_reduction',True),('largest_effect_increase',False)]:
            z=g[g.paired_net_B8L2_change.notna()].sort_values(['paired_net_B8L2_change','event_id'],ascending=[ascending,True])
            if z.empty:continue
            r=z.iloc[0]
            cases.append(dict(selection_reason=reason,analysis_status='post_assessment_mechanism_probe',
                original_event=mdmap[r.parent_event_id],replacement_event=mdmap[r.event_id],
                metrics=r.to_dict(),native_pool_path=str((BASE/'assessment/native_w132_probe/pools'/(r.pool_id+'.json.gz')).relative_to(ROOT))))
    write_json(out/'EXACT_MECHANISM_CASES.json',cases)
    write_json(out/'PROBE_ANALYSIS_RECEIPT.json',dict(meta,register_sha256=sha(out/'REGISTER.json'),
        design_receipt_sha256=sha(out/'DESIGN_RECEIPT.json'),code_sha256=sha(Path(__file__)),
        original_metric_columns_reconstructed=checked,original_events_reconstructed=len(originals),
        replacement_events=len(alternatives),originals_with_actual_replacements=len(parentdf),
        A_only_pairs_verified_unchanged_netQ=int(alternatives.probe_role.eq('A_outgoing_only').sum()),
        aggregation='Equal alternatives per original event, then original events per reference pool, pools per true image, images per building, buildings equally.',
        quality_matching='Matched before/after Q uses finite original-and-replacement pairs; all-attempt failure rates and unpaired available means are separately retained.',
        primary_frozen_rules_not_changed=True,external_blind_validation=False))
    cols=['outgoing_class','incoming_class','probe_role','original_events','alternative_events','true_images','buildings',
        'original_matched_net_B8L2_change','replacement_matched_net_B8L2_change','paired_net_B8L2_change',
        'original_matched_gap_geometry_shape_main','replacement_matched_gap_geometry_shape_main']
    for name in ['all_available','by_W132_position']:
        print(pd.read_csv(out/(name+'_aggregate.csv.gz'))[cols].to_string(index=False),flush=True)


if __name__=='__main__':main()
