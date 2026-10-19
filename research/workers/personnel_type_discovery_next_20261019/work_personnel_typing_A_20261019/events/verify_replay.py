"""Verify all registered identities and replayed native outputs, without class fitting."""
from __future__ import annotations
from collections import Counter,defaultdict
from pathlib import Path
import csv,gzip,hashlib,json,math
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ARCHIVE=HERE.parent/'recovered'/'work_v2_20261019'

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()

def save(name,x):
    (HERE/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=lambda v:v.item() if isinstance(v,np.generic) else str(v))+'\n')

def main():
    design=json.loads((HERE/'DESIGN.json').read_text())
    cols=['event_id','panel_id','pool_id','image_id','building','difficulty','reference_id','reference_version','k','background_id','background_members','background_order',
          'worker_a','worker_b','member_workers_a','member_workers_b','request_a','request_b','team_id_a','team_id_b','chain_id',
          'B8L2_a','B8L2_b','B8L2_change','abs_B8L2_change','D10_a','D10_b','D10_change','abs_D10_change',
          'both_complete','complete_a','complete_b','quality_comparable','joint_stable_main','joint_stable_strict','joint_stable_wide',
          'floor_jaccard_difference','structure_bound_cyclic_deg','node_count_difference','edge_relation_jaccard_difference',
          'changed_coidentity_pairs','selected_shared_observation_difference','mean_height_prism_pair_iou',
          'source_time_change_seconds','target_time_change_seconds','source_time_complete_a','source_time_complete_b',
          'target_time_complete_a','target_time_complete_b','upper_bound_shift_max_deg','lower_bound_shift_max_deg']
    df=pd.read_csv(HERE/'common_events.csv.gz',usecols=cols,low_memory=False)
    assert len(df)==design['n_events'] and df.event_id.is_unique
    registered=pd.read_csv(HERE/'event_design.csv.gz',usecols=['event_id','panel_id','pool_id','request_a','request_b','member_workers_a','member_workers_b','reference_id','reference_version'],low_memory=False)
    compared=df.merge(registered,on='event_id',suffixes=('','_registered'),validate='one_to_one')
    for c in ('panel_id','pool_id','request_a','request_b','member_workers_a','member_workers_b','reference_id','reference_version'):
        assert (compared[c]==compared[c+'_registered']).all(),c
    for r in df[['k','background_members','worker_a','worker_b','member_workers_a','member_workers_b']].itertuples(index=False):
        a,b=set(r.member_workers_a.split('|')),set(r.member_workers_b.split('|'))
        assert len(a)==len(b)==r.k and a-b=={r.worker_a} and b-a=={r.worker_b}
        assert a&b==set(r.background_members.split('|')) and r.worker_a<r.worker_b
    n=df[df.panel_id=='A_nested_even_v1']
    for cid,g in n.groupby('chain_id',sort=False):
        assert g.worker_a.nunique()==g.worker_b.nunique()==g.pool_id.nunique()==1
        g=g.sort_values('k'); previous=[]
        for r in g[['k','background_order']].itertuples(index=False):
            order=r.background_order.split('|');assert len(order)==r.k-1 and order[:len(previous)]==previous
            previous=order
    for nkey,q,f,s in [('strict',1,.02,2),('main',2,.05,3),('wide',5,.10,5)]:
        expected=(df.both_complete & df.B8L2_change.notna() & df.abs_B8L2_change.le(q) & df.node_count_difference.eq(0)
                  & df.floor_jaccard_difference.le(f) & df.structure_bound_cyclic_deg.le(s))
        assert expected.equals(df['joint_stable_'+nkey]),nkey
    assert (~df.loc[~df.both_complete,'joint_stable_main']).all()
    assert np.allclose(df.B8L2_change,df.B8L2_b-df.B8L2_a,equal_nan=True)
    assert np.allclose(df.abs_B8L2_change,df.B8L2_change.abs(),equal_nan=True)
    bounds=np.maximum(df.upper_bound_shift_max_deg,df.lower_bound_shift_max_deg)
    mask=df.structure_bound_cyclic_deg.notna()
    assert np.allclose(bounds[mask],df.loc[mask,'structure_bound_cyclic_deg'])
    coverage=df.groupby(['panel_id','k'],dropna=False).agg(events=('event_id','size'),pools=('pool_id','nunique'),images=('image_id','nunique'),buildings=('building','nunique'),
                 both_complete=('both_complete','sum'),quality_comparable=('quality_comparable','sum'),joint_stable_main=('joint_stable_main','sum'),
                 source_time_complete_a=('source_time_complete_a','sum'),source_time_complete_b=('source_time_complete_b','sum'),
                 target_time_complete_a=('target_time_complete_a','sum'),target_time_complete_b=('target_time_complete_b','sum')).reset_index()
    coverage.to_csv(HERE/'event_coverage.csv',index=False,encoding='utf-8-sig')
    # Retained old per-event case candidates are a deterministic subset of old
    # outputs, not all original team states. Verify every recoverable ordinary
    # event in that table, including both score and geometric changes.
    old=pd.read_csv(ARCHIVE/'clusters'/'fusion_analysis'/'case_candidates_all_pools.csv',low_memory=False)
    old=old[old.layer=='ordinary_manual'].drop_duplicates(['request_a','request_b'])
    fresh=df[df.panel_id=='Pro_exact_fixed_background_v1']
    parity=old.merge(fresh,on=['request_a','request_b'],suffixes=('_old','_new'),validate='one_to_one')
    assert len(parity)==len(old)
    metrics=['B8L2_a','B8L2_b','D10_a','D10_b','B8L2_change','D10_change','abs_B8L2_change',
             'floor_jaccard_difference','structure_bound_cyclic_deg','node_count_difference','edge_relation_jaccard_difference',
             'changed_coidentity_pairs','selected_shared_observation_difference','mean_height_prism_pair_iou',
             'source_time_change_seconds','target_time_change_seconds']
    checks=[]
    for c in metrics:
        a,b=parity[c+'_old'],parity[c+'_new']
        assert a.isna().equals(b.isna()),c+' missingness'
        known=a.notna();maximum=float(np.max(np.abs(a[known].to_numpy()-b[known].to_numpy()))) if known.any() else 0.
        assert maximum<1e-8,c
        checks.append(dict(field=c,known_n=int(known.sum()),missing_n=int((~known).sum()),max_abs_difference=maximum))
    for c in ('team_id_a','team_id_b','complete_a','complete_b','both_complete','joint_stable_main','joint_stable_strict','joint_stable_wide'):
        assert parity[c+'_old'].equals(parity[c+'_new']),c
    pd.DataFrame(checks).to_csv(HERE/'retained_legacy_event_parity.csv',index=False,encoding='utf-8-sig')
    # The raw rows make exact quality/geometry parity externally inspectable.
    parity[['request_a','request_b','pool_id_new','B8L2_a_old','B8L2_a_new','B8L2_b_old','B8L2_b_new',
            'floor_jaccard_difference_old','floor_jaccard_difference_new','joint_stable_main_old','joint_stable_main_new']].to_csv(
        HERE/'retained_legacy_event_parity_details.csv.gz',index=False,compression='gzip',encoding='utf-8-sig')
    receipt=dict(pass_all=True,design_sha256=sha(HERE/'DESIGN.json'),common_events_sha256=sha(HERE/'common_events.csv.gz'),
                 total_events=len(df),pool_count=df.pool_id.nunique(),image_count=df.image_id.nunique(),building_count=df.building.nunique(),
                 real_entrant_ids=len(set(df.worker_a)|set(df.worker_b)),
                 panels=dict(df.panel_id.value_counts()),nested_chains=n.chain_id.nunique(),
                 legacy_retained_event_parity=dict(matched_events=len(parity),images=parity.image_id_new.nunique(),buildings=parity.building_new.nunique(),
                     max_abs_difference=max(x['max_abs_difference'] for x in checks),
                     limit='All ordinary events in retained case-candidate table; this is not all omitted historical states bytewise equality.'),
                 assertions=['all frozen event IDs present exactly once','all pairs share exact k-1 real background','lexicographic signed orientation retained',
                             'new chains identical entrant pair and strictly nested background across available k','same reference preserved from requests',
                             'joint thresholds independently recomputed; failures remain false','separate upper/lower max equals native bound cyclic maximum',
                             'all retained legacy event component values replay within tolerance'],
                 provenance='Native fusion/scoring and pair-comparison source files unmodified; only derived output directory redirected.')
    save('EVENT_VERIFICATION_RECEIPT.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False,indent=2,default=lambda v:v.item() if isinstance(v,np.generic) else str(v)))

if __name__=='__main__':main()
