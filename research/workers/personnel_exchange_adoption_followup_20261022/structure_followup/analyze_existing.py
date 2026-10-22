#!/usr/bin/env python3
"""Reaggregate saved frozen-v2 events; no fusion or reclassification."""
from pathlib import Path
import hashlib,json,os
import pandas as pd
import numpy as np

HERE=Path(__file__).resolve().parent
OLD=HERE.parents[1]/'personnel_exchange_closure_20261022'/'structure'

def save(name,df):
    path=HERE/name;path.parent.mkdir(parents=True,exist_ok=True)
    raw=df.to_csv(index=False).encode('utf-8-sig')
    if str(path).endswith('.gz'):
        import gzip
        raw=gzip.compress(raw,mtime=0)
    tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
    return {'file':name,'rows':len(df),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def levels(df,metrics,key):
    i=df.groupby(['building','image']+key,dropna=False)[metrics].mean().reset_index()
    b=i.groupby(['building']+key,dropna=False)[metrics].mean().reset_index()
    return i,b

def main():
    E=pd.read_csv(OLD/'EVENTS_COMPLETE.csv.gz',low_memory=False)
    P=pd.read_csv(OLD/'M_PATHS.csv.gz')
    fields=['event_id','team_A','team_B','team_C','A_member_workers','B_member_workers','C_member_workers',
        'common_background','outgoing_block_X','same_count_block_Y','changed_count_block_Z','background_stratum',
        'A_B8L2','B_B8L2','C_B8L2','A_D10','B_D10','C_D10','A_failure','B_failure','C_failure',
        'A_score_status','B_score_status','C_score_status','A_source_time_total_seconds','B_source_time_total_seconds','C_source_time_total_seconds',
        'recorded_time_single_source','A_nodes','B_nodes','C_nodes']
    metrics=['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension',
        'nodes','fusion_turn_n','ref_node_recall_5','ref_edge_recall_5']
    fields += [p+'_'+m for p in ['same','cross','net'] for m in metrics if p+'_'+m in E]
    rows=[];long=[]
    for r in P.to_dict('records'):
        g=E[E.linked_m_path_id.eq(r['linked_m_path_id'])]
        if len(g)==0:continue
        r4=g[g.m.eq(4)].iloc[0];rt=g[g.m.eq(r['maximum_m'])].iloc[0]
        o={**r,'m_from':4,'m_to':int(r['maximum_m'])}
        for f in fields:o[f+'_4']=r4[f];o[f+'_max']=rt[f]
        assert r4.team_A==rt.team_A
        o['actual_incremental_B_turnover']=len(set(rt.B_member_workers.split('|'))-set(r4.B_member_workers.split('|')))
        o['actual_incremental_C_turnover']=len(set(rt.C_member_workers.split('|'))-set(r4.C_member_workers.split('|')))
        o['D_removed_to_X']='|'.join(sorted(set(r4.common_background.split('|'))-set(rt.common_background.split('|'))))
        o['Y_added']='|'.join(sorted(set(rt.same_count_block_Y.split('|'))-set(r4.same_count_block_Y.split('|'))))
        o['Z_added']='|'.join(sorted(set(rt.changed_count_block_Z.split('|'))-set(r4.changed_count_block_Z.split('|'))))
        qgood=all(pd.notna(x) for x in [r4.A_B8L2,r4.B_B8L2,r4.C_B8L2,rt.B_B8L2,rt.C_B8L2])
        o['common_five_endpoint_Q']=qgood
        for met in metrics:
            valid=all(pd.notna(x) for x in [r4['same_'+met],r4['cross_'+met],rt['same_'+met],rt['cross_'+met]])
            dc=rt['cross_'+met]-r4['cross_'+met] if valid else np.nan
            db=rt['same_'+met]-r4['same_'+met] if valid else np.nan
            dn=dc-db
            if met=='B8L2':
                assert valid==qgood
                for name,x in [('C_change',dc),('B_change',db),('net_advantage_change',dn)]:o[name]=x
            long.append({k:o[k] for k in ['linked_m_path_id','image','building','source_role','target_role','m_from','m_to']}|dict(metric=met,common_metric_support=valid,C_change=dc,B_change=db,net_advantage_change=dn))
        rows.append(o)
    D=pd.DataFrame(rows);L=pd.DataFrame(long);met=['C_change','B_change','net_advantage_change']
    files=[save('FIXED_A_PATHS_EXACT.csv.gz',D),save('FIXED_A_METRIC_CHANGES.csv.gz',L)]
    key=['source_role','target_role','m_from','m_to']
    I,B=levels(D,met,key);files += [save('FIXED_A_IMAGE_EFFECTS.csv',I),save('FIXED_A_BUILDING_EFFECTS.csv',B)]
    ML,MB=levels(L,met,key+['metric']);files += [save('FIXED_A_METRIC_IMAGE_EFFECTS.csv',ML),save('FIXED_A_METRIC_BUILDING_EFFECTS.csv',MB)]
    sums=[]
    for k,g in D.groupby(key):
        ii=I
        bb=B
        for kk,v in zip(key,k):ii=ii[ii[kk].eq(v)];bb=bb[bb[kk].eq(v)]
        s=dict(zip(key,k))|dict(registered_paths=len(g),registered_images=g.image.nunique(),registered_buildings=g.building.nunique(),common_scored_paths=int(g.common_five_endpoint_Q.sum()))
        for m in met:
            s[m]=bb[m].mean();s[m+'_images_positive']=int(ii[m].gt(0).sum());s[m+'_images_evaluable']=int(ii[m].notna().sum());s[m+'_buildings_positive']=int(bb[m].gt(0).sum());s[m+'_buildings_evaluable']=int(bb[m].notna().sum())
        s['identity_error']=s['C_change']-s['B_change']-s['net_advantage_change']
        sums.append(s)
    files.append(save('FIXED_A_COMMON_DECOMPOSITION.csv',pd.DataFrame(sums)))

    M=E[E.study_group.eq('main_n20')&E.source_role.eq('TURN/K3/E2')&E.n.eq(20)&E.m.eq(7)].copy()
    good=M[['A_B8L2','B_B8L2','C_B8L2']].notna().all(axis=1)
    for f in ['same_B8L2','cross_B8L2','net_B8L2']:
        M[f]=M[f].where(good)
    keys=['building','image','pool_id','background_target_seats','background_target_band','background_stratum','panel_id']
    metrics=['A_B8L2','B_B8L2','C_B8L2','same_B8L2','cross_B8L2','net_B8L2','A_failure','B_failure','C_failure']
    pp=M.groupby(keys,dropna=False)[metrics].mean().reset_index()
    ss=pp.groupby(keys[:-1],dropna=False)[metrics].mean().reset_index()
    ii=ss.groupby(keys[:5],dropna=False)[metrics].mean().reset_index()
    files.append(save('OLD_BACKGROUND_WITHIN_IMAGE_SEATS.csv',ii))
    contrasts=[]
    for (building,image),g in ii.groupby(['building','image']):
        if g.background_target_seats.nunique()<2:continue
        lo=g.sort_values('background_target_seats').iloc[0];hi=g.sort_values('background_target_seats').iloc[-1]
        rr=dict(building=building,image=image,low_seats=int(lo.background_target_seats),high_seats=int(hi.background_target_seats),
            crosses_old_band=lo.background_target_band!=hi.background_target_band,comparison='同图分层条件关联，X/Y/Z与具体D未匹配')
        for mm in metrics:rr[mm+'_low']=lo[mm];rr[mm+'_high']=hi[mm];rr[mm+'_high_minus_low']=hi[mm]-lo[mm]
        contrasts.append(rr)
    C=pd.DataFrame(contrasts);files.append(save('OLD_BACKGROUND_WITHIN_IMAGE_ASSOCIATIONS.csv',C))
    counts=M.groupby('image').background_target_band.nunique();dual=list(counts[counts.gt(1)].index)
    receipt={'status':'existing_results_reaggregated','underlying_data':'real_v2','new_native_calls':0,'input_complete_events':str(OLD/'EVENTS_COMPLETE.csv.gz'),
        'main_source_commit':'cf053a6e31d17393c0e8216ce15660fa37b8b7bb','m7_low_band_images':int(M[M.background_target_band.eq('low_0_to_1_3')].image.nunique()),
        'm7_middle_band_images':int(M[M.background_target_band.eq('middle_1_3_to_2_3')].image.nunique()),'m7_union_images':int(M.image.nunique()),
        'common_band_images':dual,'within_image_seat_varying_images':len(C),'files':files}
    (HERE/'STAGE1_EXISTING_REAGGREGATION.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(pd.DataFrame(sums).to_string(index=False))
    print('Common old band image',C[C.crosses_old_band][['image','net_B8L2_low','net_B8L2_high','net_B8L2_high_minus_low']].to_dict('records'))
    print('Stage 1 files saved',len(files))

if __name__=='__main__':main()
