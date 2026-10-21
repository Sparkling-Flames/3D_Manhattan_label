"""All registered nested-background paths, reusing every deterministic endpoint.

Each fixed variable six-person subset is followed through all distinct n values
of its registered panel. This is an explicit finite path population, not all
joining orders. No added background or ordering is chosen from outcomes.
"""
from __future__ import annotations
import collections,csv,gzip,json,math,sys,time
from pathlib import Path
import numpy as np
import pandas as pd
from multin_design import HERE,ROOT,OLD,CONT,gs,h,write_csv,sha
from evaluate_matched_events import load_pool,write_event_shard
from design_matched_events import label_maps,vecstr
sys.path.insert(0,str(OLD/'analysis'))
from analyze_global import COMPONENTS

def path_geometry(a,b,sa,sb,sg):
    """Existing geometric definitions with no equal-team-size assertion."""
    bound,reason,shift=sg.structural_distance(sa['points'],sb['points'])
    out=dict(floor_jaccard_difference=None,floor_symdiff_h2=None,mean_height_prism_pair_iou=None,mean_height_prism_pair_difference=None,structure_bound_cyclic_deg=bound,structure_reason=reason,bound_cyclic_shift=shift,height_ratio_pair_abs_logdiff=None,centroid_distance_h=None,floor_area_abs_log_ratio=None,comparison_error='')
    pa,pb=sa['floor'],sb['floor']
    if pa is not None and pb is not None and a.get('complete_floor_evaluable') and b.get('complete_floor_evaluable'):
        try:
            inter=pa.intersection(pb).area;union=pa.area+pb.area-inter
            out['floor_jaccard_difference']=1-inter/union if union>0 else None;out['floor_symdiff_h2']=pa.area+pb.area-2*inter
            out['centroid_distance_h']=math.hypot(pb.centroid.x-pa.centroid.x,pb.centroid.y-pa.centroid.y)
            out['floor_area_abs_log_ratio']=abs(math.log(pb.area/pa.area))
            ha,hb=a.get('height_mean_ratio'),b.get('height_mean_ratio')
            if ha is not None and hb is not None and ha>0 and hb>0:
                vi=inter*min(ha,hb);vu=pa.area*ha+pb.area*hb-vi
                out['mean_height_prism_pair_iou']=vi/vu if vu>0 else None;out['mean_height_prism_pair_difference']=1-vi/vu if vu>0 else None;out['height_ratio_pair_abs_logdiff']=abs(math.log(ha/hb))
        except sg.GEOSException as error:
            out['comparison_error']=type(error).__name__+':'+str(error)
    return out

def run():
    panels=pd.read_csv(HERE/'PANELS.csv',keep_default_na=False);membership=pd.read_csv(HERE/'PANEL_MEMBERSHIP.csv.gz',keep_default_na=False)
    joined=membership.merge(panels[['panel_id','source_domain','n','building','condition','difficulty','image','background_workers','variable_panel_no']],on=['panel_id','n','variable_panel_no'],validate='many_to_one')
    maps,_=label_maps();_,_,sg,_=gs.setup_engine();index=[];blocks=[];pending=[];start=time.monotonic();expression={}
    for f in sorted((HERE.parent/'response/geometry_batches').glob('batch_*_EXPRESSION.csv.gz')):
        x=pd.read_csv(f);expression.update({r.team_key:r for r in x.itertuples()})
    for (pid,varno),g in joined.groupby(['pool_id','variable_panel_no'],sort=True):
        target=HERE/'paths/shards'/(h(pid,int(varno))[:20]+'.csv.gz');rp=target.with_suffix('.json')
        if target.exists() and rp.exists():index.append(gs.read(rp));continue
        keys=set(g.team_key);teams=load_pool(pid,keys)
        missing_endpoints=keys-set(teams);missing_expression=keys-expression.keys()
        if missing_endpoints or missing_expression:
            pending.append(dict(pool_id=pid,variable_panel_no=int(varno),expected_paths=924,expected_edges=924*(g.n.nunique()-1),missing_endpoints=len(missing_endpoints),missing_expression=len(missing_expression)))
            continue
        signs={}
        out=[];meta=g.iloc[0];ns=sorted(g.n.unique());labeldone=set()
        for selected,group in g.groupby('selected_variable_workers',sort=True):
            records=group.sort_values('n').to_dict('records');path_id=h('nested-path',pid,int(varno),selected)[:24]
            for left,right in zip(records[:-1],records[1:]):
                a,b=teams[left['team_key']],teams[right['team_key']];A,B=set(a['member_workers']),set(b['member_workers'])
                if not A<B:raise ValueError('registered backgrounds are not nested')
                added=sorted(B-A);eid=h('nested-edge',path_id,left['n'],right['n'])[:24]
                stage='12_to_20' if (left['n'],right['n'])==(12,20) else ('20_to_largest' if left['n']==20 else '12_to_largest' if left['n']==12 else 'other_registered_step')
                r=dict(event_id=eid,path_id=path_id,pool_id=pid,variable_panel_no=int(varno),source_domain=meta.source_domain,building=meta.building,image=meta.image,condition=meta.condition,difficulty=meta.difficulty,stage=stage,
                    from_panel_id=left['panel_id'],to_panel_id=right['panel_id'],n_from=int(left['n']),n_to=int(right['n']),added_n=len(added),added_workers='|'.join(added),selected_variable_workers=selected,team_from=left['team_key'],team_to=right['team_key'],
                    from_complete=bool(a['complete_evaluable']),to_complete=bool(b['complete_evaluable']),both_complete=bool(a['complete_evaluable'] and b['complete_evaluable']),
                    from_status=a.get('score_status'),to_status=b.get('score_status'),from_failure=not bool(a['complete_evaluable']),to_failure=not bool(b['complete_evaluable']),
                    complete_to_failure=bool(a['complete_evaluable'] and not b['complete_evaluable']),failure_to_complete=bool(b['complete_evaluable'] and not a['complete_evaluable']),
                    from_minimum_support=a.get('minimum_support'),to_minimum_support=b.get('minimum_support'))
                r['support_threshold_increase']=b['minimum_support']-a['minimum_support']
                for component in COMPONENTS:
                    av,bv=a.get(component),b.get(component);r['change_'+component]=bv-av if av is not None and bv is not None else None
                    if component in ['B8L2','D10','nodes','ref_node_recall_5','ref_edge_recall_5','source_time_total_seconds']:
                        r['from_'+component]=av;r['to_'+component]=bv
                r['quality_loss_gt5']=int(r['change_B8L2'] < -5) if r['change_B8L2'] is not None else None
                r['quality_loss_gt10']=int(r['change_B8L2'] < -10) if r['change_B8L2'] is not None else None
                r['node_count_loss']=int(r['change_nodes']<0) if r['both_complete'] else None
                r['reference_node_recall_loss']=int(r['change_ref_node_recall_5']<0) if r['change_ref_node_recall_5'] is not None else None
                ta,tb=a.get('source_time_total_seconds'),b.get('source_time_total_seconds')
                r['time_comparable']=ta is not None and tb is not None and ta>0 and tb>0 and a.get('source_time_known_n')==a['k'] and b.get('source_time_known_n')==b['k'] and a.get('time_source_kinds')==b.get('time_source_kinds') and '|' not in str(a.get('time_source_kinds'))
                r['source_log_time_ratio']=math.log(tb/ta) if r['time_comparable'] else None;r['source_time_increase_pct']=100*math.expm1(r['source_log_time_ratio']) if r['time_comparable'] else None
                for key,t in [(left['team_key'],a),(right['team_key'],b)]:
                    if key not in signs:signs[key]=sg.signature(t)
                pm=path_geometry(a,b,signs[left['team_key']],signs[right['team_key']],sg)
                for key,value in pm.items():r['geometry_'+key]=value
                for feature in ['fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n']:
                    av=getattr(expression.get(left['team_key']),feature,np.nan);bv=getattr(expression.get(right['team_key']),feature,np.nan)
                    r['from_'+feature]=float(av) if np.isfinite(av) else None;r['to_'+feature]=float(bv) if np.isfinite(bv) else None;r['change_'+feature]=float(bv-av) if np.isfinite([av,bv]).all() else None
                out.append(r)
                block_id=(left['panel_id'],right['panel_id'])
                if block_id not in labeldone:
                    labeldone.add(block_id)
                    for (method,tier,condition,building),(labels,parents) in maps.items():
                        if (condition,building)!=(meta.condition,meta.building):continue
                        unknown=set(added)-labels.keys()
                        blocks.append(dict(pool_id=pid,variable_panel_no=int(varno),source_domain=meta.source_domain,building=building,image=meta.image,condition=condition,difficulty=meta.difficulty,from_panel_id=left['panel_id'],to_panel_id=right['panel_id'],n_from=int(left['n']),n_to=int(right['n']),method_id=method,tier=tier,added_workers='|'.join(added),added_n=len(added),added_counts=vecstr(added,labels) if not unknown else '',unknown_workers='|'.join(sorted(unknown))))
        receipt=write_event_shard(target,out,{r['event_id'] for r in out});receipt.update(pool_id=pid,variable_panel_no=int(varno),source_domain=meta.source_domain,condition=meta.condition,building=meta.building,image=meta.image,paths=924,registered_n=ns,native_calls=0)
        gs.save(rp,receipt);index.append(receipt);print(json.dumps(dict(pool_id=pid,variable_panel_no=int(varno),edges=len(out),elapsed=time.monotonic()-start)),flush=True)
    # Build block labels directly from registered backgrounds, including shards
    # reused after interruption. They do not depend on any target endpoint.
    blocks=[]
    for (pid,varno),pg in panels.groupby(['pool_id','variable_panel_no']):
        rr=pg.sort_values('n').to_dict('records')
        for left,right in zip(rr[:-1],rr[1:]):
            added=sorted(set(right['background_workers'].split('|'))-set(left['background_workers'].split('|')))
            for (method,tier,condition,building),(labels,parents) in maps.items():
                if (condition,building)!=(left['condition'],left['building']):continue
                unknown=set(added)-labels.keys()
                blocks.append(dict(pool_id=pid,variable_panel_no=int(varno),source_domain=left['source_domain'],building=building,image=left['image'],condition=condition,difficulty=left['difficulty'],from_panel_id=left['panel_id'],to_panel_id=right['panel_id'],n_from=int(left['n']),n_to=int(right['n']),method_id=method,tier=tier,added_workers='|'.join(added),added_n=len(added),added_counts=vecstr(added,labels) if not unknown else '',unknown_workers='|'.join(sorted(unknown))))
    write_csv(HERE/'paths/PATH_SHARD_INDEX.csv',pd.DataFrame(index));write_csv(HERE/'paths/PATH_ADDED_CLASS_BLOCKS.csv',pd.DataFrame(blocks));write_csv(HERE/'paths/PATH_PENDING.csv',pd.DataFrame(pending));gs.save(HERE/'paths/PATH_COMPLETION.json',dict(status='partial_checkpoint' if pending else 'complete',paths=sum(r['paths'] for r in index),edges=sum(r['rows'] for r in index),panels=len(index),pending_panels=len(pending),pending_paths=sum(r['expected_paths'] for r in pending),pending_edges=sum(r['expected_edges'] for r in pending),native_calls=0,source_membership_sha256=sha(HERE/'PANEL_MEMBERSHIP.csv.gz'),seconds=time.monotonic()-start))

def summarize():
    p=HERE/'paths';index=pd.read_csv(p/'PATH_SHARD_INDEX.csv');allrows=[];out_fields=None;summary=[]
    if gs.read(p/'PATH_COMPLETION.json')['status']!='complete':raise RuntimeError('Cannot publish complete path summary with pending registered paths')
    wanted=['change_B8L2','change_D10','change_IoU3D100','change_iou_2d','change_S_bottom_deg','change_dir','change_Hmean','change_Hcenter','change_omission','change_extension','change_height_mean_ratio','change_nodes','change_ref_node_recall_5','change_ref_edge_recall_5','change_fusion_turn_n','change_fusion_short_turn_edges','change_fusion_redundancy_n','node_count_loss','reference_node_recall_loss','quality_loss_gt5','quality_loss_gt10','from_failure','to_failure','complete_to_failure','failure_to_complete','source_time_increase_pct','geometry_floor_jaccard_difference','geometry_structure_bound_cyclic_deg']
    # Raw time components remain in the exact event rows for provenance. Only
    # full-known, one-source comparable time is an aggregate time outcome.
    raw_time_components={'source_time_total_seconds','target_time_total_seconds','source_parallel_active_seconds'}
    wanted += [f'change_{c}' for c in COMPONENTS if f'change_{c}' not in wanted and c not in raw_time_components]
    wanted += ['comparable_source_time_difference_seconds']
    wanted += ['geometry_mean_height_prism_pair_difference','geometry_centroid_distance_h','geometry_floor_area_abs_log_ratio']
    group=['condition','source_domain','stage','difficulty','building','image','pool_id','variable_panel_no','n_from','n_to']
    for rec in index.to_dict('records'):
        d=pd.read_csv(HERE/rec['path'],low_memory=False)
        d['comparable_source_time_difference_seconds']=d['change_source_time_total_seconds'].where(d['time_comparable'])
        # A fixed background pair supplies all 924 variable subsets.
        gg=d.groupby(group,dropna=False);m=gg[wanted].mean();counts=gg[wanted].count().add_prefix('valid__');n=gg.size().rename('events')
        allrows.append(m.join(counts).join(n).reset_index())
    z=pd.concat(allrows,ignore_index=True);write_csv(p/'PATH_PANEL_METRICS.csv',z)
    for scope,extra in [('registered_step',['stage']),('exact_n',['n_from','n_to']),
                        ('registered_step_by_difficulty',['stage','difficulty']),
                        ('exact_n_by_difficulty',['n_from','n_to','difficulty'])]:
        keys=['condition','source_domain']+extra
        b=z.groupby(keys+['building','image','pool_id'])[wanted].mean().groupby(level=keys+['building','image']).mean().groupby(level=keys+['building']).mean().reset_index()
        for kk,g in b.groupby(keys):
            meta=dict(zip(keys,kk));mask=np.ones(len(z),bool)
            for key,v in meta.items():mask &=z[key].eq(v).to_numpy()
            sub=z[mask]
            for metric in wanted:
                vals=g[metric].dropna().to_numpy(float);lo=hi=None
                if len(vals)>=3:
                    rng=np.random.default_rng(2026102193);bt=vals[rng.integers(len(vals),size=(2000,len(vals)))].mean(axis=1);lo,hi=np.quantile(bt,[.025,.975])
                summary.append(dict(meta,scope=scope,metric=metric,events=int(sub.events.sum()),valid_events=int(sub['valid__'+metric].sum()),pools=sub.pool_id.nunique(),images=sub.image.nunique(),buildings=sub.building.nunique(),valid_buildings=len(vals),mean=float(np.mean(vals)) if len(vals) else None,lo95=lo,hi95=hi))
    write_csv(p/'PATH_SUMMARY.csv',pd.DataFrame(summary))
    for condition,g in index.groupby('condition'):
        from consolidate_deliverables import GzipCsv
        path=p/f'{condition.upper()}_ALL_PATH_EDGES.csv.gz';seen=set();fields=None;writer=None
        prior_receipt=path.with_suffix('.json')
        if path.exists() and prior_receipt.exists():
            saved=gs.read(prior_receipt)
            if saved.get('rows')==int(g.rows.sum()) and saved.get('sha256')==sha(path) and saved.get('gzip_EOF_verified'):
                continue
        for rel in g.path:
            with gzip.open(HERE/rel,'rt',encoding='utf-8-sig',newline='') as source:
                rd=csv.DictReader(source)
                if fields is None:fields=rd.fieldnames;writer=GzipCsv(path,fields,key='event_id')
                if rd.fieldnames!=fields:raise ValueError('inconsistent path fields')
                for r in rd:
                    if r['event_id'] in seen:raise ValueError('duplicate path edge')
                    seen.add(r['event_id']);writer.add(r)
        writer.finish(seen)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('action',choices=['run','summary']);a=p.parse_args();run() if a.action=='run' else summarize()
