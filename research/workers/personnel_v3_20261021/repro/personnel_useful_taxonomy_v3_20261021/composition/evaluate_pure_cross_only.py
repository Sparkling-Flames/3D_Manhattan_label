"""Actual directed class-block effects without a same-class matched arm.

These rows deliberately do not claim a same-vs-cross stability comparison.
They retain genuine whole-class seat transfer when a rare class cannot supply
two disjoint copies of the block at the same n and actual m.
"""
from __future__ import annotations
import collections,json,math,sys,time
import numpy as np
import pandas as pd
from multin_design import HERE,OLD,gs,h,write_csv,sha
from evaluate_matched_events import load_pool,read_csv,write_event_shard,load_expression
sys.path.insert(0,str(OLD/'analysis'))
from analyze_global import COMPONENTS

FEATURES=['turn_history','short_history','redundancy_history','area_history','height_history','simple_turn_history','complex_turn_history','complex_short_history']

def run():
    request=read_csv(HERE/'matched/PURE_BLOCK_CROSS_ONLY_EVENTS.csv.gz');groups=collections.defaultdict(list)
    for r in request:groups[r['pool_id']].append(r)
    _,_,sg,corner=gs.setup_engine();features=pd.read_csv(HERE.parent/'taxonomy/CONTINUOUS_FEATURES_LOBO.csv.gz')
    histories={(r.condition,r.heldout_building,r.worker_id):r for r in features.itertuples()}
    labels=pd.read_csv(HERE.parent/'taxonomy/ALL_METHOD_LABELS_LOBO.csv.gz')
    families={(r.method,r.condition,r.heldout_building):(r.selected_family,r.coarse_k,r.fine_k) for r in labels.itertuples()}
    ledger=[];pending=[];start=time.monotonic()
    for pid,rr in sorted(groups.items()):
        path=HERE/'matched/results/pure_cross'/(h('pure-cross-result',pid)[:20]+'.csv.gz');rp=path.with_suffix('.json')
        if path.exists() and rp.exists():
            receipt=gs.read(rp)
            if receipt['request_digest']!=gs.digest(rr):raise ValueError('changed pure cross design')
            ledger.append(receipt);continue
        needed={r['team_'+a] for r in rr for a in 'AC'};teams=load_pool(pid,needed)
        if not needed<=teams.keys():pending.append(dict(pool_id=pid,events=len(rr),missing_endpoints=len(needed-teams.keys())));continue
        rows=[];signatures={};pairs={}
        for req in rr:
            r=dict(req);r['n']=int(r['n']);r['m_AC']=int(r['m_AC']);r['within_parent_fine_change']=str(r['within_parent_fine_change']).lower()=='true'
            a,c=teams[r['team_A']],teams[r['team_C']]
            assert a['k']==c['k']==r['n'] and len(set(a['member_workers'])-set(c['member_workers']))==r['m_AC']
            assert r['m_AC']==int(r['class_seat_transfer'])
            r['physical_pair_id']=h('pure-pair',sorted([r['team_A'],r['team_C']]))[:24]
            r['all_complete']=bool(a['complete_evaluable'] and c['complete_evaluable']);r['all_scored']=a.get('B8L2') is not None and c.get('B8L2') is not None
            r['A_failure']=not bool(a['complete_evaluable']);r['C_failure']=not bool(c['complete_evaluable']);r['failure_difference']=int(r['C_failure'])-int(r['A_failure'])
            r['complete_to_failure']=bool(not r['A_failure'] and r['C_failure']);r['failure_to_complete']=bool(r['A_failure'] and not r['C_failure'])
            r['fold_selected_family'],r['fold_coarse_k'],r['fold_fine_k']=families.get((r['method_id'],r['condition'],r['building']),('legacy_method',None,None))
            for arm,t in [('A',a),('C',c)]:
                for key,value in t.items():
                    if key=='geometry':continue
                    r['endpoint_'+arm+'__'+key]='|'.join(map(str,value)) if isinstance(value,list) else value
                for key in ['B8L2','D10','nodes','source_time_total_seconds']:r[arm+'_'+key]=t.get(key)
            for metric in COMPONENTS:
                av,cv=a.get(metric),c.get(metric);r['cross_'+metric]=cv-av if av is not None and cv is not None else None
            for threshold in [5,10]:
                r[f'quality_loss_gt{threshold}']=float(r['cross_B8L2'] < -threshold) if r['cross_B8L2'] is not None else None
                r[f'quality_gain_gt{threshold}']=float(r['cross_B8L2'] > threshold) if r['cross_B8L2'] is not None else None
            for key in [r['team_A'],r['team_C']]:
                if key not in signatures:signatures[key]=sg.signature(teams[key])
            pk=(r['team_A'],r['team_C'])
            if pk not in pairs:
                values=sg.pair_metrics(a,c,signatures[pk[0]],signatures[pk[1]]);co,_=corner(a,c);values.update({'corner_'+k:v for k,v in co.items()});pairs[pk]=values
            r.update({'cross_geometry_'+k:v for k,v in pairs[pk].items()})
            for block,col in [('X','outgoing_block_X'),('Z','changed_count_block_Z')]:
                for feature in FEATURES:
                    vals=[];flag='context_supported' if feature.startswith(('simple_','complex_')) else 'base_supported'
                    for worker in r[col].split('|'):
                        x=histories.get((r['condition'],r['building'],worker));vals.append(getattr(x,feature,np.nan) if x is not None and getattr(x,flag,False) else np.nan)
                    r[block+'_'+feature+'_known_n']=int(np.isfinite(vals).sum());r[block+'_'+feature]=float(np.mean(vals)) if np.isfinite(vals).all() else None
            for feature in FEATURES:
                av,cv=r['X_'+feature],r['Z_'+feature];r['cross_'+feature+'_change']=cv-av if av is not None and cv is not None else None
            ta,tc=a.get('source_time_total_seconds'),c.get('source_time_total_seconds')
            compatible=a.get('source_time_known_n')==a['k'] and c.get('source_time_known_n')==c['k'] and a.get('time_source_kinds')==c.get('time_source_kinds') and '|' not in str(a.get('time_source_kinds'))
            r['recorded_time_comparable']=bool(compatible and ta is not None and tc is not None and ta>0 and tc>0);r['recorded_time_pct']=100*(tc/ta-1) if r['recorded_time_comparable'] else None
            rows.append(r)
        receipt=write_event_shard(path,rows,{r['event_id'] for r in rr});receipt.update(pool_id=pid,image=rr[0]['image'],building=rr[0]['building'],condition=rr[0]['condition'],request_digest=gs.digest(rr),all_complete=sum(r['all_complete'] for r in rows),all_scored=sum(r['all_scored'] for r in rows),native_calls=0)
        gs.save(rp,receipt);ledger.append(receipt)
    write_csv(HERE/'matched/PURE_CROSS_RESULT_SHARDS.csv',pd.DataFrame(ledger));write_csv(HERE/'matched/PURE_CROSS_PENDING.csv',pd.DataFrame(pending))
    receipt=dict(status='partial_checkpoint' if pending else 'complete',registered_events=len(request),completed_events=sum(r['rows'] for r in ledger),pending_events=sum(r['events'] for r in pending),pending_pools=len(pending),native_calls=0,seconds=time.monotonic()-start,strict_matched_stability_comparison=False)
    gs.save(HERE/'matched/PURE_CROSS_RESULT_RECEIPT.json',receipt);print(json.dumps(receipt),flush=True)

def summarize():
    receipt=gs.read(HERE/'matched/PURE_CROSS_RESULT_RECEIPT.json')
    if receipt['status']!='complete':raise RuntimeError('Incomplete registered pure cross events')
    index=pd.read_csv(HERE/'matched/PURE_CROSS_RESULT_SHARDS.csv');expression=load_expression();frames=[]
    for r in index.itertuples():
        d=pd.read_csv(HERE/r.path,low_memory=False)
        if not (set(d.team_A)|set(d.team_C))<=expression.keys():raise RuntimeError('Wait for complete expression derivation')
        for metric in ['fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n']:
            for arm in 'AC':d[arm+'_'+metric]=d['team_'+arm].map(lambda k:expression[k][metric])
            d['cross_'+metric]=d['C_'+metric]-d['A_'+metric]
        frames.append(d)
    d=pd.concat(frames,ignore_index=True);metrics=['cross_'+c for c in COMPONENTS]+['cross_fusion_turn_n','cross_fusion_short_turn_edges','cross_fusion_redundancy_n','A_failure','C_failure','failure_difference','complete_to_failure','failure_to_complete','quality_loss_gt5','quality_loss_gt10','quality_gain_gt5','quality_gain_gt10','recorded_time_pct','cross_geometry_floor_jaccard_difference','cross_geometry_structure_bound_cyclic_deg','cross_geometry_mean_height_prism_pair_iou']
    base=['method_id','tier','condition','source_domain','within_parent_fine_change'];rows=[]
    for view,extra in [('overall',[]),('by_n_m',['n','m_AC']),('by_difficulty',['difficulty'])]:
        keys=base+extra;b=d.groupby(keys+['building','image','pool_id'])[metrics].mean().groupby(level=keys+['building','image']).mean().groupby(level=keys+['building']).mean().reset_index()
        for kk,g in b.groupby(keys):
            meta=dict(zip(keys,kk));mask=np.ones(len(d),bool)
            for key,value in meta.items():mask &=d[key].eq(value).to_numpy()
            sub=d[mask]
            for metric in metrics:
                v=g[metric].dropna().to_numpy(float);lo=hi=None
                if len(v)>=3:
                    rng=np.random.default_rng(2026102154);boot=v[rng.integers(len(v),size=(2000,len(v)))].mean(axis=1);lo,hi=np.quantile(boot,[.025,.975])
                rows.append(dict(meta,view=view,metric=metric,mean=float(v.mean()) if len(v) else None,lo95=lo,hi95=hi,events=len(sub),distinct_pairs=sub.physical_pair_id.nunique(),images=sub.image.nunique(),buildings=sub.building.nunique(),valid_events=int(sub[metric].notna().sum()),valid_buildings=len(v),strict_same_class_comparison=False))
    write_csv(HERE/'matched/PURE_CROSS_COMPONENT_SUMMARY.csv',pd.DataFrame(rows))
    for condition,g in d.groupby('condition'):
        path=HERE/'matched'/f'PURE_CROSS_{condition.upper()}_COMPLETE_EVENTS.csv.gz'
        exported=write_event_shard(path,g.to_dict('records'),set(g.event_id))
        exported.update(request_sha256=sha(HERE/'matched/PURE_BLOCK_CROSS_ONLY_EVENTS.csv.gz'),
            gzip_EOF_verified=True,unique_keys=True)
        gs.save(path.with_suffix('.json'),exported)
    gs.save(HERE/'matched/PURE_CROSS_SUMMARY_COMPLETE.json',dict(status='complete',events=len(d),metrics=len(metrics),summary_rows=len(rows),same_class_stability_comparison_not_estimated=True,source_request_sha256=sha(HERE/'matched/PURE_BLOCK_CROSS_ONLY_EVENTS.csv.gz')))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('action',choices=['run','summary']);a=p.parse_args();run() if a.action=='run' else summarize()
