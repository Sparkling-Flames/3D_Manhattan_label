"""Analyze the outcome-blind native diagnostic sample; no fusion or scoring.

One sampled physical pair per pool/class-pair/budget. Pooled figures first average
within image. Associations describe observed native transitions, not randomized
mechanism interventions. Opposite directions are not independent observations.
"""
from __future__ import annotations
import hashlib,json
import numpy as np
import pandas as pd
from mechanism_core import ROOT,OUT,read_json,sha,save_json,save_csv,diagnose_pair,clean

FLAGS=['stable_threshold_cross_any','D_partition_changed','same_node_count','same_selected_anchor_set','ring_topology_changed']

def cluster_interval(frame,metric,seed_text):
    z=frame.dropna(subset=[metric])
    if z.building.nunique()<3:return (None,None)
    g=z.groupby('building')[metric].agg(['sum','count'])
    rng=np.random.default_rng(int(hashlib.sha256(seed_text.encode()).hexdigest()[:16],16))
    pick=rng.integers(0,len(g),size=(2000,len(g)))
    vals=g['sum'].to_numpy()[pick].sum(axis=1)/g['count'].to_numpy()[pick].sum(axis=1)
    return tuple(map(float,np.quantile(vals,[.025,.975])))

def summary(g,meta):
    # An image may contain more than one class-pair stratum. Every image has
    # equal weight after the within-image mean, even in ALL-pair displays.
    fields=['Q_pair_valid','abs_delta_Q','jump5','jump10','state_changed','evaluability_changed',
            'stable_threshold_cross_any','D_partition_changed','same_node_count','same_selected_anchor_set',
            'stable_anchored_groups','ambiguous_anchor_links','A_selected_unanchored_groups','C_selected_unanchored_groups',
            'stable_selected_node_horizontal_abs_shift_mean_deg','stable_selected_node_top_abs_shift_mean_deg',
            'stable_selected_node_bottom_abs_shift_mean_deg']
    im=g.groupby(['image','building'],as_index=False)[fields].mean(numeric_only=False)
    out=dict(meta,physical_pairs=len(g),images=g.image.nunique(),buildings=g.building.nunique(),
             jointly_scored_pairs=int(g.Q_pair_valid.sum()),joint_Q_images=g.loc[g.Q_pair_valid,'image'].nunique(),
             q_missing_pairs=int((~g.Q_pair_valid).sum()),jump5_pairs=int(g.jump5.eq(True).sum()),jump10_pairs=int(g.jump10.eq(True).sum()),
             stable_threshold_cross_pairs=int(g.stable_threshold_cross_any.sum()),D_partition_changed_pairs=int(g.D_partition_changed.sum()),
             same_node_count_pairs=int(g.same_node_count.sum()),ring_topology_comparable_pairs=int(g.ring_topology_comparable.sum()),
             ring_topology_changed_pairs=int(g.ring_topology_changed.eq(True).sum()))
    for f in fields:out[f+'_image_mean']=float(im[f].mean()) if im[f].notna().any() else None
    for f in ['abs_delta_Q','jump5','jump10']:
        ci=cluster_interval(im,f,'202611041303|'+json.dumps(meta,sort_keys=True)+'|'+f)
        out[f+'_cluster_ci_low'],out[f+'_cluster_ci_high']=ci
    return clean(out)

def main():
    sel=OUT/'DIAGNOSTIC_SAMPLE.csv.gz';sample=pd.read_csv(sel,keep_default_na=False,low_memory=False)
    frozen=read_json(OUT/'DIAGNOSTIC_SAMPLE_FREEZE_RECEIPT.json')
    assert frozen['sample_sha256']==sha(sel)
    pools={p['pool_id']:p for p in read_json(OUT/'source/DIAGNOSTIC_POOLS.json.gz')['images']}
    rows=[];links=[]
    for e in sample.to_dict('records'):
        A=read_json(OUT/'trace_endpoints'/(e['A_team_key']+'.json.gz'))
        C=read_json(OUT/'trace_endpoints'/(e['C_team_key']+'.json.gz'))
        p=pools[e['pool_id']];row,ll=diagnose_pair(e,A,C,p)
        row['difficulty']=p['meta']['difficulty'];row['reference_id']=p['meta']['reference_id'];row['reference_version']=p['meta']['reference_version']
        row['A_team_key']=A['team_key'];row['C_team_key']=C['team_key'];row['D_workers']=e['D_workers'];row['X_workers']=e['X_workers'];row['Z_workers']=e['Z_workers']
        row['source_event_aliases']=e['source_event_aliases'];row['current_D_class_counts']=e['current_D_class_counts']
        for field in ['IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension','nodes',
                      'fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','ref_node_recall_9','ref_edge_recall_9',
                      'boundary_loss','direction_loss','height_loss','geometry_area_h2','height_mean_h']:
            a,b=A.get(field),C.get(field);row['A_'+field]=a;row['C_'+field]=b
            row['delta_'+field]=b-a if a is not None and b is not None else None
        rows.append(row);links.extend(ll)
    d=pd.DataFrame(rows);assert len(d)==frozen['sample_pairs'] and not d.canonical_pair_id.duplicated().any()
    save_csv(OUT/'DIAGNOSTIC_PAIR_RESULTS.csv.gz',d);save_csv(OUT/'D_OBSERVATION_ANCHOR_LINKS.csv.gz',links)
    summaries=[];associations=[];transitions=[];difficulty_associations=[];coverage=[]
    for (n,m),g in d.groupby(['n','m']):
        for pair,h in [('ALL_image_equal',g)]+list(g.groupby('unordered_pair',sort=True)):
            meta=dict(n=int(n),m=int(m),class_pair=pair)
            summaries.append(summary(h,meta))
            for flag in FLAGS:
                for value,z in h.dropna(subset=[flag]).groupby(flag):
                    associations.append(summary(z,dict(meta,mechanism=flag,mechanism_present=bool(value))))
            for (a,c),z in h.groupby(['A_score_status','C_score_status']):
                transitions.append(dict(meta,A_status=a,C_status=c,physical_pairs=len(z),images=z.image.nunique(),buildings=z.building.nunique()))
            for difficulty,z in h.groupby('difficulty'):
                for flag in ['stable_threshold_cross_any','D_partition_changed']:
                    for value,v in z.groupby(flag):
                        difficulty_associations.append(summary(v,dict(meta,difficulty=difficulty,mechanism=flag,mechanism_present=bool(value))))
            coverage.append(dict(meta,physical_pairs=len(h),images=h.image.nunique(),buildings=h.building.nunique(),
                endpoint_visits=2*len(h),selected_nodes_A=int(h.A_selected_groups.sum()),selected_nodes_C=int(h.C_selected_groups.sum()),
                selected_nodes_without_stable_anchor_A=int(h.A_selected_groups_without_stable_anchor.sum()),
                selected_nodes_without_stable_anchor_C=int(h.C_selected_groups_without_stable_anchor.sum()),
                selected_nodes_with_no_D_observation_A=int(h.A_selected_unanchored_groups.sum()),
                selected_nodes_with_no_D_observation_C=int(h.C_selected_unanchored_groups.sum()),
                endpoints_with_unmapped_selected_nodes_A=int(h.A_selected_groups_without_stable_anchor.gt(0).sum()),
                endpoints_with_unmapped_selected_nodes_C=int(h.C_selected_groups_without_stable_anchor.gt(0).sum()),
                pairs_with_unmapped_selected_nodes=int((h.A_selected_groups_without_stable_anchor.gt(0)|h.C_selected_groups_without_stable_anchor.gt(0)).sum()),
                stable_anchor_links=int(h.stable_anchored_groups.sum()),ambiguous_anchor_links=int(h.ambiguous_anchor_links.sum())))
    save_csv(OUT/'DIAGNOSTIC_SUMMARY.csv',summaries)
    save_csv(OUT/'MECHANISM_QUALITY_ASSOCIATIONS.csv',associations)
    save_csv(OUT/'DIAGNOSTIC_STATE_TRANSITIONS.csv',transitions)
    save_csv(OUT/'MECHANISM_DIFFICULTY_ASSOCIATIONS.csv',difficulty_associations)
    save_csv(OUT/'ANCHOR_MAPPING_COVERAGE.csv',coverage)
    numeric=['abs_delta_Q','jump5','jump10','Q_pair_valid','stable_threshold_cross_any','D_partition_changed','same_node_count','same_selected_anchor_set']
    im=d.groupby(['n','m','image','building','difficulty'],as_index=False)[numeric].mean()
    counts=d.groupby(['n','m','image']).size().reset_index(name='physical_pairs')
    im=im.merge(counts,on=['n','m','image'],validate='one_to_one');save_csv(OUT/'DIAGNOSTIC_IMAGE_RESULTS.csv',im)
    cross=d.groupby(['n','m','unordered_pair','stable_threshold_cross_any','D_partition_changed'],dropna=False).agg(
        physical_pairs=('canonical_pair_id','size'),images=('image','nunique'),buildings=('building','nunique'),
        jointly_scored_pairs=('Q_pair_valid','sum'),jump5_pairs=('jump5','sum'),jump10_pairs=('jump10','sum')).reset_index()
    save_csv(OUT/'VOTES_GROUPING_JUMP_CROSS_TABLE.csv',cross)
    # Explicitly retain counterexamples: large Q changes with no observed stable
    # threshold crossing, and threshold crossings with small/no Q changes.
    exclusions=d[(d.Q_pair_valid & ((d.abs_delta_Q.ge(5)&~d.stable_threshold_cross_any)|(d.abs_delta_Q.lt(1)&d.stable_threshold_cross_any)))].copy()
    exclusions['counterexample_type']=np.where(exclusions.stable_threshold_cross_any,'stable_crossing_but_absQ_under1','absQ_atleast5_without_stable_anchor_crossing')
    save_csv(OUT/'MECHANISM_COUNTEREXAMPLE_CANDIDATES.csv.gz',exclusions)
    receipt=dict(status='passed',sample_sha256=sha(sel),pairs=len(d),unique_images=d.image.nunique(),unique_buildings=d.building.nunique(),
                 all_nominal_thresholds_unchanged=not d.nominal_threshold_changed.any(),all_shared_D_observation_id_sets_equal=True,
                 observation_anchor_links=len(links),stable_anchor_links=sum(r['link_type']=='exact_same_nonempty_D_observations' for r in links),
                 diagnostic_association_only=True,new_fusions=0,new_scores=0,new_physical_teams=0,
                 weighting='Within image first. Budget and class-pair strata are separate. ALL tables average across observed class-pairs within each image.',
                 missing_Q='Quality jumps require both original automatic Q values. State/evaluability counts retain every frozen pair.',
                 intervals='2,000 deterministic building-cluster bootstrap draws for image-equal descriptive means; fewer than 3 buildings leave interval missing.',
                 threshold_absence='False stable_threshold_cross_any means no crossing detected among unchanged shared-D anchors; it does not prove no threshold role in ambiguous or unanchored groups.',
                 ring_comparison='Only when every selected node maps bijectively through stable shared-D anchors and selected anchor sets agree; otherwise topology change is not declared from local names.')
    save_json(OUT/'DIAGNOSTIC_ANALYSIS_CHECKS.json',receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
