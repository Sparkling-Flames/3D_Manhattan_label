#!/usr/bin/env python3
"""Legality/retention audit only: reuse exact prior TARGET ABC endpoints.

Identical physical endpoints necessarily have identical effects. This does not
test performance superiority of a new classification or expand design coverage.
"""
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
from refit_v21_structure_audit import save_csv,save_json

def members(v):return set(str(v).split('|')) if pd.notna(v) and str(v) else set()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--work',type=Path,required=True);ap.add_argument('--audit',type=Path,required=True);a=ap.parse_args()
    stages=[('global',a.work/'additional_delivery/packages/05A/experiment/global_screen_design/EVENTS_EXACT.csv.gz',a.work/'additional_delivery/packages/05A/analysis/global_screen_compact/EVENT_EFFECTS_COMPLETE.csv.gz'),('focused',a.work/'experiment/focused_design/EVENTS_EXACT.csv.gz',a.work/'analysis/focused_compact/EVENT_EFFECTS_COMPLETE.csv.gz')]
    source=[]
    for stage,dpath,mpath in stages:
        d=pd.read_csv(dpath,low_memory=False)
        d=d[d.method.isin(['TARGET_DSTRUCT_K2','TARGET_DSTRUCT_K3','TARGET_DSTRUCT_K4'])&d.layer.eq('ordinary_manual')].copy()
        metrics=pd.read_csv(mpath,low_memory=False)
        want=['event_id','method','ABC_scored','A_failed','B_failed','C_failed','B8L2_BA','B8L2_CA','B8L2_CB','B8L2_within','B8L2_cross','B8L2_gap','B8L2_AC_absolute','B8L2_AC_gap','D10_BA','D10_CA','D10_CB','IoU3D100_BA','IoU3D100_CA','IoU3D100_CB','fusion_turn_n_BA','fusion_turn_n_CA','fusion_turn_n_CB','fusion_short_turn_edges_BA','fusion_short_turn_edges_CA','fusion_short_turn_edges_CB','geometry_area_h2_BA','geometry_area_h2_CA','geometry_area_h2_CB','record_time_CA_pct_source_matched','record_time_CB_pct_source_matched']
        d=d.merge(metrics[want],on=['event_id','method'],validate='one_to_one');d['stage']=stage;source.append(d)
    src=pd.concat(source,ignore_index=True)
    src=src.sort_values('stage').drop_duplicates(['method','event_id'])
    for r in src.itertuples():
        blocks=[members(getattr(r,c)) for c in ['D','X','Y','Z']]
        assert len(blocks[0])==r.n-r.m and all(len(x)==r.m for x in blocks[1:])
        assert all(not x&y for i,x in enumerate(blocks) for y in blocks[i+1:])
        assert members(r.A_members)==blocks[0]|blocks[1] and members(r.B_members)==blocks[0]|blocks[2] and members(r.C_members)==blocks[0]|blocks[3]
    save_csv(src,a.audit/'SOURCE_TARGET_ABC_EXACT_AND_SELECTED_METRICS.csv.gz')
    lab=pd.read_csv(a.audit/'NEW_LABELS_ALL_LOBO.csv.gz');lab=lab[~lab.family.eq('REPRO_TARGET_DSTRUCT')]
    maps={(m,b):dict(zip(g.loc[g.known,'worker_id'],g.loc[g.known,'class_id'])) for (m,b),g in lab.groupby(['method','heldout_building'])}
    variants=sorted(lab.family.unique());rows=[]
    for r in src.itertuples():
        k=int(r.method[-1]);blocks={c:members(getattr(r,c)) for c in ['D','X','Y','Z']}
        for family in variants:
            method=family+'_K'+str(k);lm=maps[(method,r.building)]
            cs={c:{lm.get(w,'unknown') for w in blocks[c]} for c in ['X','Y','Z']}
            if any('unknown' in x for x in cs.values()):reason='unknown_XYZ_member'
            elif any(len(x)!=1 for x in cs.values()):reason='mixed_block_under_new_labels'
            elif cs['X']!=cs['Y']:reason='X_Y_different_classes'
            elif cs['X']==cs['Z']:reason='Z_same_as_source_class'
            else:reason='strict_ABC_retained'
            rows.append(dict(method=method,source_method=r.method,event_id=r.event_id,stage=r.stage,pool_id=r.pool_id,image=r.image,building=r.building,n=r.n,m=r.m,new_source_class=next(iter(cs['X'])) if len(cs['X'])==1 else None,new_target_class=next(iter(cs['Z'])) if len(cs['Z'])==1 else None,unknown_D=sum(w not in lm for w in blocks['D']),retained=reason=='strict_ABC_retained',reason=reason,ABC_scored=r.ABC_scored,A_failed=r.A_failed,B_failed=r.B_failed,C_failed=r.C_failed,B8L2_BA=r.B8L2_BA,B8L2_CA=r.B8L2_CA,B8L2_CB=r.B8L2_CB,B8L2_within=r.B8L2_within,B8L2_cross=r.B8L2_cross,B8L2_gap=r.B8L2_gap,B8L2_AC_absolute=r.B8L2_AC_absolute,B8L2_AC_gap=r.B8L2_AC_gap))
    r=pd.DataFrame(rows);save_csv(r,a.audit/'EXISTING_TARGET_ABC_RELABEL_EVENT_AUDIT.csv.gz')
    sm=r.groupby(['method','source_method','stage','n','m','reason']).agg(events=('event_id','size'),pools=('pool_id','nunique'),images=('image','nunique'),buildings=('building','nunique'),Q_evaluable=('ABC_scored','sum')).reset_index()
    save_csv(sm,a.audit/'EXISTING_TARGET_ABC_RETENTION_BY_CONDITION.csv')
    summary=[]
    for (m,srcm),g in r.groupby(['method','source_method']):
        z=g[g.retained]
        summary.append(dict(method=m,source_method=srcm,source_events=len(g),retained_events=len(z),retained_fraction=len(z)/len(g),source_images=g.image.nunique(),retained_images=z.image.nunique(),source_buildings=g.building.nunique(),retained_buildings=z.building.nunique(),retained_Q_evaluable_events=int(z.ABC_scored.sum())))
    save_csv(pd.DataFrame(summary),a.audit/'EXISTING_TARGET_ABC_RETENTION_SUMMARY.csv')
    save_json(dict(source_unique_events=len(src),audit_rows=len(r),new_fusion=0,new_physical_events=0,strict_DXYZ_validated=True,unknown_D_allowed=True,unretained_events_never_treated_as_strict_ABC=True,effects='Existing exact A/B/C outputs reused; conditional descriptive retention, not a new-method outcome trial',comparison_limit='Effects are identical for the same physical endpoints by definition; do not claim superiority or equal method performance from retained-only samples'),a.audit/'EXISTING_ABC_RELABEL_RECEIPT.json')
    print(pd.DataFrame(summary).to_string(index=False))

if __name__=='__main__':main()
