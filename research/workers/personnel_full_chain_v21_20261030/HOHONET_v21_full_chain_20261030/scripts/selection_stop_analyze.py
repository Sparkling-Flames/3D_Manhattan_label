"""Current quality, lawful labor, low tails, and frozen stopping/cold-start rules."""
from pathlib import Path
import sys,os,json,gzip,hashlib,types,importlib.util,collections,math
import numpy as np
import pandas as pd
from selection_stop_prepare import STUDY,WORK,OUT,PORT,INP,REPLAY,OLD,read,digest,teamkey,native_pools,save
from selection_stop_endpoints import iterjson

FIELDS=['B8L2','D10','nodes','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','S_bottom_deg','dir','Hmean','Hcenter','omission','extension','ref_node_recall_5','ref_node_recall_9','ref_edge_recall_5','ref_edge_recall_9','iou_2d','IoU3D100','boundary_loss','direction_loss','height_loss','geometry_area_h2','centroid_x_h','centroid_z_h','height_mean_h']

def endpoint_scalars(only_stopping=False):
    rows=[]
    selected=set(read(OUT/'design/STOPPING_CONTRACT.json')['affected_pools']) if only_stopping else None
    for p in sorted((OUT/'endpoints/pools').glob('*.jsonl.gz')):
        if selected is not None and p.name[:-9] not in selected:continue
        for r in iterjson(p):
            z={k:r.get(k) for k in FIELDS+['team_key','pool_id','reference_id','reference_version','score_status','complete_evaluable','geometry_status','connection_available','recorded_time_eligible','recorded_time_total_seconds','source_time_total_seconds','source_time_known_n','time_source_kinds','difficulty','k','downstream_acquisition']}
            z['member_workers']='|'.join(r['member_workers']);z['member_object_ids']='|'.join(r['member_object_ids'])
            z['geometry_source']=str(p.relative_to(STUDY))+'#'+r['team_key']
            z['target_activity_seconds']=r.get('recorded_time_total_seconds') if r.get('recorded_time_eligible') else None
            z['observed_fusion_failure']=r.get('score_status') in ['fusion_exception','below_four','no_connection','invalid_floor','invalid_full_geometry']
            z['measurement_unavailable']=r.get('B8L2') is None and not z['observed_fusion_failure']
            rows.append(z)
    d=pd.DataFrame(rows);assert d.team_key.is_unique
    req=pd.read_csv(OUT/'design/ENDPOINT_REQUESTS.csv.gz')
    if selected is not None:req=req[req.pool_id.isin(selected)]
    assert set(req.team_key)==set(d.team_key)
    save('endpoints/'+('STOPPING_SCALARS.csv.gz' if only_stopping else 'SCALARS.csv.gz'),d)
    return d

def summarize(d,keys,metrics,image='target_image'):
    images=d.groupby(keys+['building',image],dropna=False)[metrics].mean().reset_index()
    buildings=images.groupby(keys+['building'],dropna=False)[metrics].mean().reset_index()
    out=[];support=[]
    for key,g in d.groupby(keys,dropna=False):
        key=key if isinstance(key,tuple) else (key,);base=dict(zip(keys,key));bs=buildings
        ims=images
        for k,v in base.items():bs=bs[bs[k].eq(v)];ims=ims[ims[k].eq(v)]
        row=dict(base,events=len(g),images=g[image].nunique(),buildings=g.building.nunique(),unique_teams=g.team_key.nunique())
        for m in metrics:
            row[m]=bs[m].mean();row[m+'_image_equal']=ims[m].mean()
            support.append(dict(base,metric=m,valid_events=int(g[m].notna().sum()),valid_images=int(ims[m].notna().sum()),valid_buildings=int(bs[m].notna().sum()),positive_images=int(ims[m].gt(1e-9).sum()),negative_images=int(ims[m].lt(-1e-9).sum()),zero_images=int(ims[m].abs().le(1e-9).sum())))
        row['B8L2_pooled_p10']=g.B8L2.quantile(.1)
        row['B8L2_mean_target_p10']=g.groupby(['building',image]).B8L2.quantile(.1).groupby('building').mean().mean()
        row['delta_Q_pooled_p10']=g.delta_Q.quantile(.1)
        row['activity_ratio_geometric']=np.exp(row['log_activity_ratio'])
        out.append(row)
    return pd.DataFrame(out),images,buildings,pd.DataFrame(support)

def selection(scalars):
    d=pd.read_csv(OUT/'design/SELECTION_DESIGN.csv.gz');d=d.merge(scalars.drop(columns=['member_workers','k']),on='team_key',validate='many_to_one')
    key=['version','pair_id','source_pool_id','target_pool_id','domain','n']
    basecols=['B8L2','D10','target_activity_seconds','team_key','complete_evaluable']+FIELDS[2:]
    base=d[d.policy=='outside_Q'][key+basecols].rename(columns={c:'base_'+c for c in basecols})
    d=d.merge(base,on=key,validate='many_to_one');d['policy_original']=d.policy;d['policy']=d.policy.str.replace(r'random_\d$','random',regex=True)
    d['delta_Q']=d.B8L2-d.base_B8L2;d['delta_D10']=d.D10-d.base_D10;d['absolute_delta_Q']=d.delta_Q.abs()
    paired=d.B8L2.notna()&d.base_B8L2.notna();timeok=d.target_activity_seconds.gt(0)&d.base_target_activity_seconds.gt(0)
    d['loss_over5']=(d.delta_Q<-5).astype(float).where(paired);d['gain_over5']=(d.delta_Q>5).astype(float).where(paired)
    d['within2']=(d.delta_Q>=-2).astype(float).where(paired)
    d['both_scored']=paired.astype(float);d['complete_rate']=d.complete_evaluable.astype(float);d['Q_available_rate']=d.B8L2.notna().astype(float)
    d['low_Q50']=d.B8L2.lt(50).astype(float).where(d.B8L2.notna());d['low_Q80']=d.B8L2.lt(80).astype(float).where(d.B8L2.notna())
    d['same_team']=(d.team_key==d.base_team_key).astype(float)
    d['log_activity_ratio']=np.log(d.target_activity_seconds/d.base_target_activity_seconds).where(timeok)
    d['joint_save20_loss_atmost2']=(d.delta_Q.ge(-2)&(d.target_activity_seconds/d.base_target_activity_seconds<=.8)).astype(float).where(paired&timeok)
    d['source_plus_target_over_base_target']=((d.source_roster_activity_seconds+d.target_activity_seconds)/d.base_target_activity_seconds).where(timeok&d.source_roster_activity_seconds.gt(0))
    for f in FIELDS[2:]:d['delta_'+f]=d[f]-d['base_'+f]
    save('selection/POLICY_EVENT_RESULTS.csv.gz',d)
    keys=['version','condition','layer','scope_comparable','domain','n','policy']
    metrics=FIELDS+['delta_Q','absolute_delta_Q','delta_D10','loss_over5','gain_over5','within2','same_team','both_scored','complete_rate','Q_available_rate','low_Q50','low_Q80','observed_fusion_failure','measurement_unavailable','target_activity_seconds','base_target_activity_seconds','log_activity_ratio','joint_save20_loss_atmost2','source_roster_activity_seconds','source_plus_target_over_base_target']+['delta_'+x for x in FIELDS[2:]]
    sm,im,bm,sup=summarize(d,keys,metrics)
    save('selection/POLICY_SUMMARY.csv',sm);save('selection/POLICY_IMAGE_RESULTS.csv.gz',im);save('selection/POLICY_BUILDING_RESULTS.csv',bm);save('selection/METRIC_SUPPORT.csv',sup)
    o=d[d.version=='v2_fixed_selection_current_score'];n=d[d.version=='v21_history_reselected_fixed_candidates']
    join=['pair_id','source_pool_id','target_pool_id','domain','n','policy_original']
    z=o.merge(n,on=join,suffixes=('_frozen','_updated'),validate='one_to_one')
    z['same_team']=z.team_key_frozen.eq(z.team_key_updated);z['updated_minus_frozen_Q']=z.B8L2_updated-z.B8L2_frozen
    z['updated_minus_frozen_time']=z.target_activity_seconds_updated-z.target_activity_seconds_frozen
    save('selection/HISTORY_RESELECTION_EVENT_CHANGE.csv.gz',z[['pair_id','source_pool_id','target_pool_id','domain','n','policy_original','building_updated','target_image_updated','team_key_frozen','team_key_updated','member_workers_frozen','member_workers_updated','same_team','updated_minus_frozen_Q','updated_minus_frozen_time']])
    oldsum=pd.read_csv(INP/OLD/'native_teams/POLICY_SUMMARY.csv')
    c=sm[sm.version=='v2_fixed_selection_current_score'].merge(oldsum,on=['condition','layer','scope_comparable','domain','n','policy'],suffixes=('_current','_v2'),validate='one_to_one')
    for f in ['B8L2','D10','delta_Q','loss_over5','log_activity_ratio']:
        c['current_minus_v2_'+f]=c[f+'_current']-c[f+'_v2']
    assert (c.events_current==c.events_v2).all() and (c.images_current==c.images_v2).all() and (c.buildings_current==c.buildings_v2).all()
    save('selection/FROZEN_SELECTION_V2_TO_CURRENT.csv',c)
    tail=d[(d.layer=='ordinary_manual')&d.scope_comparable&(d.domain=='new_timed_history')&(d.n==5)&(d.policy=='outside_Q_outside_T_fast')]
    save('selection/ALL_MAIN_TIME_POLICY_CASES.csv',tail.sort_values(['version','delta_Q']))
    print('selection analyzed',len(d),'events',len(sm),'conditions',flush=True)

def stopping(scalars):
    original=pd.read_csv(INP/REPLAY/'replay_nodes.csv.gz',low_memory=False);d=original.copy()
    contract=read(OUT/'design/STOPPING_CONTRACT.json');mask=d.pool_id.isin(contract['affected_pools'])&(d.k!=2)
    idx=d.index[mask];d['current_team_key']=[teamkey(p,ws.split('|')) for p,ws in zip(d.pool_id,d.member_workers)]
    ep=scalars.set_index('team_key');cols=['B8L2','D10','reference_id','reference_version']
    for c in cols:d.loc[idx,c]=d.loc[idx,'current_team_key'].map(ep[c])
    assert d.loc[idx,'current_team_key'].isin(ep.index).all()
    for c in ['nodes','geometry_status','connection_available']:
        same=d.loc[idx,c].fillna('<missing>').astype(str).to_numpy()==d.loc[idx,'current_team_key'].map(ep[c]).fillna('<missing>').astype(str).to_numpy()
        if c=='nodes':same=np.isclose(d.loc[idx,c].to_numpy(float),d.loc[idx,'current_team_key'].map(ep[c]).to_numpy(float),equal_nan=True)
        assert same.all(),(c,int((~same).sum()))
    save('stopping/REPLAY_NODE_PATCHES.csv.gz',d.loc[idx,['request_id','pool_id','current_team_key','member_workers','member_object_ids']+cols])
    # Re-run the exact archived rule implementation with only the explicit node-table patch.
    path=INP/OLD/'prior_integration/rebuild_stopping.py';text=path.read_text();start=text.index('from pathlib import Path\nimport argparse')
    mod=types.ModuleType('frozen_stopping_rules_v21');mod.__file__=str(path)
    def read_csv(path,*a,**kw):
        if Path(path).name=='replay_nodes.csv.gz':return d.copy()
        return pd.read_csv(path,*a,**kw)
    def op(path,mode='rt',**kw):
        p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
        return gzip.open(p,mode,**kw) if p.suffix=='.gz' else open(p,mode,**kw)
    mod.__dict__.update(_read_csv=read_csv,_write_csv=lambda df,path,**kw:df.to_csv(path,**kw),_open_data=op,_write_bytes=lambda p,b:Path(p).write_bytes(b),_data_exists=lambda p:Path(p).exists())
    exec(compile(text[start:],str(path),'exec'),mod.__dict__)
    dest=OUT/'stopping';dest.mkdir(exist_ok=True);mod.main(INP,dest)
    summary=pd.read_csv(dest/'stopping_summary.csv');old=pd.read_csv(INP/OLD/'prior_integration/stopping_summary.csv')
    keys=['history_budget','panel','support','policy','time_support','weighting'];comp=summary.merge(old,on=keys,suffixes=('_v21','_v2'),validate='one_to_one')
    for c in ['mean_k','q_mean','q10','loss_gt5_to_full_rate_paired','mean_activity_ratio_to_fixed7_geometry','d10_mean']:comp['delta_'+c]=comp[c+'_v21']-comp[c+'_v2']
    save('stopping/V2_TO_V21_STOPPING_COMPARISON.csv',comp)
    oldcost=pd.read_csv(INP/OLD/'prior_integration/source_acquisition_summary.csv');newcost=pd.read_csv(dest/'source_acquisition_summary.csv');ck=['history_budget','panel','policy']
    cc=newcost.merge(oldcost,on=ck,suffixes=('_v21','_v2'),validate='one_to_one')
    for c in ['project_ratio_to_fixed7_geometry','project_ratio_to_full_common_pool','mean_target_activity_seconds']:cc['delta_'+c]=cc[c+'_v21']-cc[c+'_v2']
    save('stopping/V2_TO_V21_COST_COMPARISON.csv',cc)
    decisions=pd.read_csv(dest/'decisions_whole_maxhistory.csv.gz');s=decisions[decisions.policy=='source_within2_min3_geometry'];b=decisions[decisions.policy=='fixed_7_geometry']
    paired=s.merge(b,on=['group_id','split_id','target_image','replay'],suffixes=('_source','_fixed7'),validate='one_to_one');paired['delta_Q']=paired.B8L2_source-paired.B8L2_fixed7;paired['delta_k']=paired.selected_k_source-paired.selected_k_fixed7
    im=paired.groupby(['building_source','group_id','image_code_source','target_image'])[['delta_Q','delta_k']].mean().reset_index();save('stopping/SOURCE_VS_FIXED7_IMAGE_EFFECTS.csv',im)
    manifest=read(dest/'REBUILD_RECEIPT.json');manifest['original_script_identity']=manifest.pop('identity');manifest['identity']='v2.1 downstream replay of original exact team/order/source-budget design';manifest['current_commit']='13a7861334749805a86dc19e9ea79fcaa71020c0';manifest['node_patch_path']='REPLAY_NODE_PATCHES.csv.gz';manifest['node_patch_sha256']=hashlib.sha256((dest/'REPLAY_NODE_PATCHES.csv.gz').read_bytes()).hexdigest();manifest['patched_rows']=len(idx);manifest['patched_unique_teams']=d.loc[idx,'current_team_key'].nunique();manifest['all_other_rows_reused']=len(d)-len(idx);manifest['geometry_and_order_unchanged_verified']=True
    save('stopping/REBUILD_RECEIPT.json',manifest)

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('stage',nargs='?',choices=['all','selection','stopping'],default='all');args=ap.parse_args()
    s=endpoint_scalars(only_stopping=args.stage=='stopping')
    if args.stage in ['all','selection']:selection(s)
    if args.stage in ['all','stopping']:stopping(s)
