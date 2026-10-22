"""Evaluate frozen metadata-enumerated n20 ABC events from existing endpoints.

No fusion or scoring calls. Uses the original pair geometry/corner contracts.
"""
from __future__ import annotations
import argparse, collections, csv, gzip, json, math, os, sys, time
from pathlib import Path
import numpy as np
import pandas as pd
from discover_n20_abc import HERE,STUDY,read_csv,save_csv,save_json,sha

sys.path.insert(0,str(STUDY/'composition'))
import global_study as gs
sys.path.insert(0,str(STUDY/'analysis'))
from analyze_global import COMPONENTS

BATCHES=HERE.parent/'next_stage/batches'
TEXT={'team_key','pool_id','reference_id','reference_version','image','image_id','building','condition','layer','difficulty','scene','room_id',
      'score_status','geometry_status','geometry_reason','order_status','diag_status','endpoint_origin','time_source_table','time_source_kinds','continuation_batch'}
LISTS={'member_workers','member_object_ids','node_supports','ref_matched_edges_5','ref_matched_edges_9','ref_matched_nodes_5','ref_matched_nodes_9'}

def typed(row):
    d={}
    for k,v in row.items():
        if v=='':d[k]=None
        elif k in TEXT:d[k]=v
        elif k in LISTS:
            if k.startswith('member_'):d[k]=v.split('|')
            else:d[k]=[int(float(x)) for x in v.split('|')]
        elif v in ('True','False'):d[k]=v=='True'
        else:
            try:d[k]=float(v) if '.' in v or 'e' in v.lower() else int(v)
            except ValueError:d[k]=v
    # Scalar CSV serializes an empty matched-index set as an empty cell. A
    # known zero recall distinguishes that empty set from an unavailable set.
    for kind in ['nodes','edges']:
        singular='node' if kind=='nodes' else 'edge'
        for threshold in [5,9]:
            key=f'ref_matched_{kind}_{threshold}'
            if key in d and d[key] is None and d.get(f'ref_{singular}_recall_{threshold}')==0:d[key]=[]
    return d

def available_sources():
    out=[]
    reuse=BATCHES/'REUSED_ENDPOINT_SCALARS.csv.gz'
    if reuse.exists():out.append((reuse,BATCHES/'REUSED_ENDPOINT_GEOMETRY.csv.gz'))
    for folder in sorted(BATCHES.glob('batch_*')):
        # In-progress files must never be mistaken for completed output.
        if (folder/'COMPLETION.json').exists():
            out.append((folder/'ENDPOINT_SCALARS.csv.gz',folder/'ENDPOINT_GEOMETRY.csv.gz'))
    return out

def load_teams(keys):
    teams={};sources=[]
    for scalars,geometry in available_sources():
        for r in read_csv(scalars):
            if r['team_key'] in keys:
                assert r['team_key'] not in teams
                teams[r['team_key']]=typed(r)
        for r in read_csv(geometry):
            if r['team_key'] in keys:
                key=r['team_key'];assert key in teams
                assert r['member_workers']=='|'.join(teams[key]['member_workers'])
                teams[key]['geometry']=json.loads(r['geometry_json']) if r['geometry_json'] else None
        sources.extend([{'path':str(p.relative_to(STUDY)),'sha256':sha(p)} for p in [scalars,geometry]])
    assert all('geometry' in r for r in teams.values())
    return teams,sources

def safe_delta(a,b,k):
    x,y=a.get(k),b.get(k)
    return y-x if x is not None and y is not None and isinstance(x,(int,float)) and isinstance(y,(int,float)) else None

def finite(x):return isinstance(x,(int,float,np.number)) and np.isfinite(x)

def evaluate(condition,allow_partial=False):
    begin=time.monotonic();folder=HERE/('design_'+condition)
    events=read_csv(folder/'MATCHED_ABC_EVENTS.csv.gz')
    keys={r['team_'+a] for r in events for a in 'ABC'}
    teams,sources=load_teams(keys)
    missing=keys-set(teams)
    if missing and not allow_partial:
        save_json(HERE/f'PENDING_{condition}.json',{'needed':len(keys),'available':len(teams),'missing':len(missing),'missing_keys':sorted(missing)})
        print(json.dumps({'condition':condition,'pending_endpoints':len(missing),'needed':len(keys)}),flush=True);return
    _,_,sg,corner=gs.setup_engine()
    signatures={};pairs={};out=[]
    histories=pd.read_csv(STUDY/'multivariate/continuous_features_lobo.csv.gz')
    hist={(r.condition,r.heldout_building,r.worker_id):r for r in histories.itertuples()}
    def history(ws,building,field):
        values=[getattr(hist.get((condition,building,w)),field,np.nan) for w in ws]
        return float(np.mean(values)) if values and np.isfinite(values).all() else None
    for ei,request in enumerate(events):
        r=typed(request)
        for k in ('A_member_workers','B_member_workers','C_member_workers','common_background','outgoing_block_X','same_count_block_Y','changed_count_block_Z'):
            r[k]=request[k]
        ids=[r['team_'+a] for a in 'ABC']
        if any(k not in teams for k in ids):r['computed_all_arms']=False;out.append(r);continue
        endpoints=[teams[k] for k in ids]
        a,b,c=endpoints;r['computed_all_arms']=True
        r['all_scored']=all(t.get('B8L2') is not None for t in endpoints)
        r['all_complete']=all(bool(t.get('complete_evaluable')) for t in endpoints)
        r['same_source_counts']=a['new_n']==b['new_n']==c['new_n']
        r['time_population']='new_only' if all(t['old_n']==0 for t in endpoints) else ('old_only' if all(t['new_n']==0 for t in endpoints) else 'mixed_origin')
        for arm,t in zip('ABC',endpoints):
            assert t['pool_id']==r['pool_id'] and t['k']==r['n']
            assert '|'.join(t['member_workers'])==r[arm+'_member_workers']
            r[arm+'_failure']=not bool(t.get('complete_evaluable'))
            r[arm+'_score_status']=t.get('score_status')
            for k,v in t.items():
                if k=='geometry':continue
                r['endpoint_'+arm+'__'+k]='|'.join(map(str,v)) if isinstance(v,list) else v
            for k in ['B8L2','D10','nodes','source_time_total_seconds']:r[arm+'_'+k]=t.get(k)
        for block,col in [('X','outgoing_block_X'),('Y','same_count_block_Y'),('Z','changed_count_block_Z')]:
            for feature in ['q_effect','t_effect','q_downside','hard_minus_easy']:
                r[block+'_history_'+feature]=history(r[col].split('|'),r['building'],feature)
        for name,left,right in [('same','X','Y'),('cross','X','Z'),('net','Y','Z')]:
            x,y=r[left+'_history_q_effect'],r[right+'_history_q_effect']
            r[name+'_history_block_Q_change']=y-x if x is not None and y is not None else None
        for threshold in [2,5]:
            r['source_and_historyQ'+str(threshold)+'_matched']=bool(r['same_source_counts'] and
              r['same_history_block_Q_change'] is not None and r['cross_history_block_Q_change'] is not None and
              abs(r['same_history_block_Q_change'])<=threshold and abs(r['cross_history_block_Q_change'])<=threshold)
        for prefix,ia,ib in [('same',0,1),('cross',0,2),('net',1,2)]:
            left,right=endpoints[ia],endpoints[ib]
            for k in COMPONENTS:r[prefix+'_'+k]=safe_delta(left,right,k)
            q=r[prefix+'_B8L2'];r[prefix+'_abs_B8L2']=abs(q) if q is not None else None
            r[prefix+'_loss_gt5']=float(q < -5) if q is not None else None
            r[prefix+'_loss_gt10']=float(q < -10) if q is not None else None
            r[prefix+'_quality_comparable']=q is not None
            lt,rt=left.get('source_time_total_seconds'),right.get('source_time_total_seconds')
            tc=lt is not None and rt is not None and lt>0 and rt>0 and left.get('time_source_kinds')==right.get('time_source_kinds')
            r[prefix+'_source_log_time_ratio']=math.log(rt/lt) if tc else None
            r[prefix+'_time_comparable']=bool(tc)
            pair=(ids[ia],ids[ib]);gp='within' if prefix=='same' else prefix
            if pair not in pairs:
                for key in pair:
                    if key not in signatures:signatures[key]=sg.signature(teams[key])
                va,vb=signatures[pair[0]],signatures[pair[1]]
                values=sg.pair_metrics(left,right,va,vb)
                co,_=corner(left,right);values.update({'corner_'+k:v for k,v in co.items()})
                if values['mean_height_prism_pair_iou'] is not None:values['mean_height_prism_pair_difference']=1-values['mean_height_prism_pair_iou']
                pa,pb=va['floor'],vb['floor']
                if values['both_complete'] and pa is not None and pb is not None:
                    values['centroid_distance_h']=math.hypot(pb.centroid.x-pa.centroid.x,pb.centroid.y-pa.centroid.y)
                    values['floor_area_abs_log_ratio']=abs(math.log(pb.area/pa.area))
                values['joint_stable_D10_main']=bool(values['both_complete'] and values['abs_D10_change'] is not None and values['abs_D10_change']<=2 and values['node_count_difference']==0 and
                    values['floor_jaccard_difference'] is not None and values['floor_jaccard_difference']<=.05 and
                    values['structure_bound_cyclic_deg'] is not None and values['structure_bound_cyclic_deg']<=3)
                pairs[pair]=values
            assert pairs[pair]['turnover']==r['m_'+('AB' if prefix=='same' else 'AC' if prefix=='cross' else 'BC')]
            r.update({gp+'_'+k:v for k,v in pairs[pair].items()})
        r['common_quality_within_abs']=r['same_abs_B8L2'] if r['all_scored'] else None
        r['common_quality_cross_abs']=r['cross_abs_B8L2'] if r['all_scored'] else None
        r['abs_Q_change_advantage']=r['cross_abs_B8L2']-r['same_abs_B8L2'] if r['all_scored'] else None
        r['stable_advantage']=int(r['within_joint_stable_main'])-int(r['cross_joint_stable_main'])
        r['stable_D10_advantage']=int(r['within_joint_stable_D10_main'])-int(r['cross_joint_stable_D10_main'])
        r['net_failure_difference']=int(r['C_failure'])-int(r['B_failure'])
        out.append(r)
        if (ei+1)%1000==0:print(json.dumps({'condition':condition,'evaluated':ei+1,'unique_pairs':len(pairs),'seconds':time.monotonic()-begin}),flush=True)
    result_folder=HERE/('results_'+condition+('_partial' if missing else ''));result_folder.mkdir(parents=True,exist_ok=True)
    # Stable union ordering, and missing fields explicitly empty. Keep every
    # attempted row; uncomputed data are distinct from native fusion failures.
    columns=list(dict.fromkeys(k for r in out for k in r))
    clean=[{k:gs.clean(r.get(k)) for k in columns} for r in out]
    e_result=save_csv(result_folder/'N20_ABC_ALL_COMPONENT_EVENTS.csv.gz',clean,columns,key='event_id')
    frame=pd.DataFrame(out)
    metric_cols=[k for k in columns if k.startswith(('same_','cross_','net_','within_','common_quality_')) and pd.api.types.is_numeric_dtype(frame[k])]
    metric_cols=[k for k in metric_cols if not k.startswith('within_parent') and k not in ['same_source_counts','net_shared_workers','cross_shared_workers','within_shared_workers']]
    metric_cols+=['A_failure','B_failure','C_failure','stable_advantage','stable_D10_advantage','abs_Q_change_advantage']
    metric_cols=list(dict.fromkeys(metric_cols))
    results,buildings=summary(frame[frame.computed_all_arms],metric_cols)
    outputs=[e_result,save_csv(result_folder/'N20_ABC_METRIC_SUMMARY.csv',results),save_csv(result_folder/'N20_ABC_BUILDING_METRICS.csv.gz',buildings)]
    primary_metrics={'common_quality_within_abs','common_quality_cross_abs','stable_advantage','stable_D10_advantage','within_joint_stable_main','cross_joint_stable_main','within_joint_stable_D10_main','cross_joint_stable_D10_main',
      'same_loss_gt5','cross_loss_gt5','same_loss_gt10','cross_loss_gt10','B_failure','C_failure','within_floor_jaccard_difference','cross_floor_jaccard_difference','within_structure_bound_cyclic_deg','cross_structure_bound_cyclic_deg'}
    outputs.append(save_csv(result_folder/'N20_ABC_PRIMARY_SUMMARY.csv',[r for r in results if r['metric'] in primary_metrics]))
    receipt={'condition':condition,'events_registered':len(events),'events_computed':int(frame.computed_all_arms.sum()),
      'all_scored':int(frame.all_scored.fillna(False).sum()),'all_complete':int(frame.all_complete.fillna(False).sum()),
      'distinct_endpoint_keys_needed':len(keys),'distinct_endpoint_keys_available':len(teams),'missing_endpoint_keys':len(missing),
      'unique_oriented_geometry_pairs':len(pairs),'fusion_calls':0,'score_calls':0,
      'design_sha256':sha(folder/'MATCHED_ABC_EVENTS.csv.gz'),'sources':sources,
      'geometry_contract':'original summarize_grid.pair_metrics + corresponding_corner_distance_v2; no geometry repair or alignment of originals',
      'aggregation':'events -> pool -> image -> building; building equal; each metric own nonmissing denominator; failures retained; CIs descriptive after exploration',
      'seconds':time.monotonic()-begin,'outputs':outputs}
    save_json(result_folder/'RESULT_RECEIPT.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False),flush=True)

def summary(frame,metrics):
    rows=[];bs=[]
    for (method,tier),g0 in frame.groupby(['method_id','tier'],dropna=False):
        scopes={'all_composition_changes':g0}
        if tier=='fine':
            scopes['within_parent_fine_change']=g0[g0.within_parent_fine_change]
            scopes['cross_parent_change']=g0[~g0.within_parent_fine_change]
        scopes['source_count_matched']=g0[g0.same_source_counts]
        scopes['source_history_Q2_matched']=g0[g0.source_and_historyQ2_matched]
        scopes['source_history_Q5_matched']=g0[g0.source_and_historyQ5_matched]
        for m in sorted(g0.m_AB.unique()):scopes['m_'+str(int(m))]=g0[g0.m_AB==m]
        for scope,g in scopes.items():
            if len(g)==0:continue
            pool=g.groupby(['building','image','pool_id'])[metrics].mean()
            im=pool.groupby(level=['building','image']).mean()
            building=im.groupby(level=['building']).mean()
            common=dict(method_id=method,tier=tier,condition=g.condition.iloc[0],scope=scope,events=len(g),
              images=g.image.nunique(),buildings=g.building.nunique(),m_min=int(g.m_AB.min()),m_max=int(g.m_AB.max()),
              actual_net_m_mean=float(g.m_BC.mean()),all_scored_events=int(g.all_scored.sum()),all_complete_events=int(g.all_complete.sum()))
            for metric in metrics:
                z=building[metric].dropna();lo=hi=None
                if len(z)>=3 and metric in {'stable_advantage','stable_D10_advantage','abs_Q_change_advantage'}:
                    rng=np.random.default_rng(2026102141);a=z.to_numpy(float)
                    boots=a[rng.integers(len(a),size=(2500,len(a)))].mean(axis=1);lo,hi=map(float,np.quantile(boots,[.025,.975]))
                rows.append(dict(common,metric=metric,mean=float(z.mean()) if len(z) else None,
                  valid_events=int(g[metric].notna().sum()),valid_buildings=len(z),lo95=lo,hi95=hi,
                  positive_buildings=int(z.gt(0).sum()),negative_buildings=int(z.lt(0).sum())))
                for b,v in z.items():bs.append(dict(method_id=method,tier=tier,condition=common['condition'],scope=scope,building=b,metric=metric,value=v))
    return rows,bs

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--condition',choices=['manual','semi'],required=True);ap.add_argument('--allow-partial',action='store_true');args=ap.parse_args()
    evaluate(args.condition,args.allow_partial)
