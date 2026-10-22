#!/usr/bin/env python3
"""Reaggregate frozen pure-class direct A/C changes; no native fusion or refit.

Input: restored original finite-design/pure endpoint packages. Output keeps all
registered class directions and actual member exchanges. Cross-fold aggregation
uses history-direction roles only for the four focal methods; old method IDs
stay fold-specific in the exact and image tables.
"""
from pathlib import Path
import argparse, hashlib, json, gzip, io, os
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FEATURES = ['turn_history','short_history','redundancy_history','area_history',
            'height_history','q_history','q_downside','t_history']
METRICS = ['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter',
 'omission','extension','nodes','ref_node_recall_9','ref_edge_recall_9',
 'diag_wall_coverage_03','diag_wall_coverage_05','diag_corner_recall_05',
 'geometry_area_h2','height_mean_h','height_mean_ratio','top_y_mean_px',
 'bottom_y_mean_px','minimum_support','fusion_turn_n','fusion_short_turn_edges',
 'fusion_redundancy_n','source_time_total_seconds']

def workers(s):
    return set(str(s).split('|')) if pd.notna(s) and str(s) else set()

def vector(s):
    return {a:int(b) for a,b in (v.split(':') for v in str(s).split('|'))}

def expression(s):
    g=json.loads(s); p=np.asarray(g.get('footprint') or [],dtype=float)
    if p.ndim!=2 or len(p)<3 or not np.isfinite(p).all(): return [np.nan]*3
    e=np.roll(p,-1,axis=0)-p; le=np.linalg.norm(e,axis=1)
    if np.any(le<1e-10): return [np.nan]*3
    angles=np.degrees(np.arccos(np.clip(np.sum(np.roll(e,1,axis=0)*e,axis=1)/
                                      (np.roll(le,1)*le),-1,1)))
    red=angles<=5
    short=(le/le.sum()<.04)&(angles>=15)&(np.roll(angles,-1)>=15)
    return [int((~red).sum()),int(short.sum()),int(red.sum())]

def save(d,name):
    p=HERE/name
    raw=d.to_csv(index=False).encode('utf-8-sig')
    payload=gzip.compress(raw,mtime=0) if p.suffix=='.gz' else raw
    tmp=p.with_name(p.name+'.partial')
    with tmp.open('wb') as f:
        f.write(payload);f.flush();os.fsync(f.fileno())
    decoded=gzip.decompress(tmp.read_bytes()) if p.suffix=='.gz' else tmp.read_bytes()
    assert len(pd.read_csv(io.BytesIO(decoded)))==len(d)
    os.replace(tmp,p)
    return p

def summary(events,keys,outcome_cols):
    # Average each image first. Buildings receive equal image means internally.
    im=events.groupby(list(dict.fromkeys(keys+['image','building','difficulty'])),dropna=False)[outcome_cols].mean().reset_index()
    bu=im.groupby(keys+['building'],dropna=False)[outcome_cols].mean().reset_index()
    rows=[]
    for key,g in events.groupby(keys,dropna=False,sort=True):
        if not isinstance(key,tuple):key=(key,)
        vals=dict(zip(keys,key)); a=im.copy(); b=bu.copy()
        for k,v in vals.items():
            a=a[a[k].isna()] if pd.isna(v) else a[a[k]==v]
            b=b[b[k].isna()] if pd.isna(v) else b[b[k]==v]
        row=vals|{'events':len(g),'physical_AC_pairs':g.physical_AC.nunique(),
          'images':g.image.nunique(),'buildings':g.building.nunique(),
          'backgrounds':g.background_id.nunique(),'both_scored':int(g.both_scored.sum()),
          'A_failed_endpoints':g.loc[g.A_failure==1,'team_A'].nunique(),
          'C_failed_endpoints':g.loc[g.C_failure==1,'team_C'].nunique(),
          'A_endpoints':g.team_A.nunique(),'C_endpoints':g.team_C.nunique(),
          'm_min':g.actual_m_AC.min(),'m_max':g.actual_m_AC.max(),
          'r_min':g.actual_seat_transfer.min(),'r_max':g.actual_seat_transfer.max(),
          'source_replaced_fraction_min':g.source_replaced_fraction.min(),
          'source_replaced_fraction_max':g.source_replaced_fraction.max()}
        for c in outcome_cols:
            row[c+'_image_mean']=a[c].mean(); row[c+'_building_mean']=b[c].mean()
            row[c+'_valid_events']=int(g[c].notna().sum())
        for c in ['delta_B8L2','delta_nodes','delta_fusion_turn_n','delta_recorded_time_pct']:
            z=a[c].dropna();q=b[c].dropna()
            row[c+'_images']=len(z);row[c+'_positive_images']=int((z>1e-9).sum())
            row[c+'_negative_images']=int((z< -1e-9).sum());row[c+'_p10_images']=z.quantile(.1)
            row[c+'_p90_images']=z.quantile(.9);row[c+'_buildings']=len(q)
            row[c+'_positive_buildings']=int((q>1e-9).sum())
            row[c+'_negative_buildings']=int((q< -1e-9).sum())
        rows.append(row)
    return pd.DataFrame(rows),im,bu

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--composition',type=Path,required=True)
    args=ap.parse_args();comp=args.composition
    src=comp/'matched/PURE_BLOCK_CROSS_ONLY_EVENTS.csv.gz'
    e=pd.read_csv(src)
    s=pd.concat([pd.read_csv(f) for f in sorted((comp/'batches').glob('pure_*/ENDPOINT_SCALARS.csv.gz'))],ignore_index=True)
    s=s.drop_duplicates('team_key'); need=set(e.team_A)|set(e.team_C)
    if need-set(s.team_key): raise ValueError('missing frozen endpoints')
    s=s[s.team_key.isin(need)].copy()
    geo=pd.concat([pd.read_csv(f) for f in sorted((comp/'batches').glob('pure_*/ENDPOINT_GEOMETRY.csv.gz'))],ignore_index=True).drop_duplicates('team_key')
    geo=geo[geo.team_key.isin(need)].copy()
    ex=pd.DataFrame([expression(x) for x in geo.geometry_json],columns=['fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n'])
    ex['team_key']=geo.team_key.to_numpy();s=s.merge(ex,on='team_key',validate='1:1')
    labels=pd.read_csv(REPO/'research/workers/personnel_exchange_closure_20261022/classification/ALL_METHOD_LABELS_LOBO.csv.gz')
    centres={}
    for tier in ['coarse','fine']:
        z=labels[labels.known].groupby(['condition','heldout_building','method',tier+'_label'])[FEATURES].mean().reset_index()
        for _,r in z.iterrows():centres[(r.condition,r.heldout_building,r.method,tier,r[tier+'_label'])]=r.to_dict()
    rows=[]
    for _,r in e.iterrows():
        a,c=workers(r.A_member_workers),workers(r.C_member_workers);d=workers(r.common_background)
        m=len(a-c);va,vc=vector(r.A_counts),vector(r.C_counts)
        seats=sum(abs(va.get(k,0)-vc.get(k,0)) for k in set(va)|set(vc))/2
        assert len(a)==len(c)==r.n and len(c-a)==m and a&c==d and m==r.m_AC
        extra={'actual_m_AC':m,'actual_seat_transfer':seats,'replacement_fraction_team':m/r.n,
          'source_replaced_fraction':m/va[r.direction_source_class],
          'source_pool_fraction':m/r.source_class_capacity,
          'background_id':hashlib.sha256((r.pool_id+'|'+'|'.join(sorted(d))).encode()).hexdigest()[:20],
          'physical_AC':hashlib.sha256('|'.join(sorted([r.team_A,r.team_C])).encode()).hexdigest()[:20]}
        role='fold_specific_unaligned'
        cs=centres.get((r.condition,r.building,r.method_id,r.tier,r.direction_source_class))
        ct=centres.get((r.condition,r.building,r.method_id,r.tier,r.direction_target_class))
        if cs is not None and ct is not None:
            for f in FEATURES:extra['source_'+f]=cs[f];extra['target_'+f]=ct[f];extra['history_delta_'+f]=ct[f]-cs[f]
            if r.method_id=='V3_BEHAVIOR':role='turn_more' if ct['turn_history']>cs['turn_history'] else 'turn_less'
            elif r.method_id=='V3_JOINT_QT':
                role=('q_up' if ct['q_history']>cs['q_history'] else 'q_down')+'__'+('faster' if ct['t_history']<cs['t_history'] else 'slower')
        extra['direction_role']=role;rows.append(extra)
    e=pd.concat([e.reset_index(drop=True),pd.DataFrame(rows)],axis=1)
    fields=list(dict.fromkeys(METRICS+['complete_evaluable','source_time_known_n','k','time_source_kinds','centroid_x_h','centroid_z_h','score_status']))
    for letter in ['A','C']:
        z=s[['team_key']+fields].rename(columns={c:letter+'_'+c for c in fields})
        e=e.merge(z,left_on='team_'+letter,right_on='team_key',validate='m:1').drop(columns='team_key')
    e['both_scored']=e.A_complete_evaluable & e.C_complete_evaluable & e.A_B8L2.notna() & e.C_B8L2.notna()
    e['A_failure']=(~e.A_complete_evaluable).astype(float);e['C_failure']=(~e.C_complete_evaluable).astype(float)
    outcomes=[]
    for f in METRICS:
        col='delta_'+f;e[col]=e['C_'+f]-e['A_'+f];outcomes.append(col)
    for f in ['B8L2','D10']:
        e.loc[~e.both_scored,'delta_'+f]=np.nan
    e['abs_delta_B8L2']=e.delta_B8L2.abs()
    e['AC_centroid_distance_h']=np.hypot(e.C_centroid_x_h-e.A_centroid_x_h,e.C_centroid_z_h-e.A_centroid_z_h)
    reliable=pd.Series(True,index=e.index)
    for letter in ['A','C']:
        reliable &= (e[letter+'_source_time_known_n']==e.n)&(e[letter+'_source_time_total_seconds']>0)&e[letter+'_time_source_kinds'].notna()&~e[letter+'_time_source_kinds'].fillna('').str.contains('|',regex=False)
    reliable &= e.A_time_source_kinds==e.C_time_source_kinds
    e['time_comparable']=reliable
    e['delta_recorded_time_pct']=np.where(reliable,100*(e.C_source_time_total_seconds/e.A_source_time_total_seconds-1),np.nan)
    e.loc[~reliable,'delta_source_time_total_seconds']=np.nan
    e['loss_gt10']=np.where(e.both_scored,(e.delta_B8L2< -10).astype(float),np.nan)
    e['loss_gt5']=np.where(e.both_scored,(e.delta_B8L2< -5).astype(float),np.nan)
    outcomes+=['abs_delta_B8L2','AC_centroid_distance_h','delta_recorded_time_pct','A_failure','C_failure','loss_gt10','loss_gt5']
    save(e,'EXACT_AC_EVENTS_AND_OUTCOMES.csv.gz')
    save(s,'USED_ENDPOINT_SCALARS.csv.gz'); save(geo,'USED_ENDPOINT_GEOMETRY.csv.gz')
    keys=['method_id','condition','tier','source_domain','direction_role','n','actual_m_AC','within_parent_fine_change']
    summ,im,bu=summary(e,keys,outcomes)
    save(summ,'CONDITION_COMPARISON.csv');save(im,'IMAGE_EFFECTS.csv.gz');save(bu,'BUILDING_EFFECTS.csv.gz')
    # Difficulty group summaries preserve the same role/n/m cells.
    summ_d,_,_=summary(e,keys+['difficulty'],outcomes)
    save(summ_d,'DIFFICULTY_CONDITIONS.csv')
    rolekeys=['method_id','condition','tier','direction_role','within_parent_fine_change']
    rol,_,_=summary(e,rolekeys,outcomes);save(rol,'ROLE_SUMMARY.csv')
    receipt={'source':str(src),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
      'main':'ef148c82df18582228b2d23837faa2659e79eba7','data':'real_v2',
      'events':len(e),'endpoint_count':len(s),'conditions':len(summ),'new_fusion':0,
      'design':'direct AC only, no inferred B or within-class comparator',
      'direction_role':'four focal methods from LOBO history centres; old schemes remain fold-specific',
      'quality_denominator':'native complete and finite for Q/D10; other outcomes own nonmissing denominator',
      'time':'original recorded seconds, sum of all team members, same nonmixed provenance; not new production measurement',
      'weighting':'event -> image equal; image -> building equal; no inferential independent-event claim'}
    (HERE/'RUN_MANIFEST.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()
