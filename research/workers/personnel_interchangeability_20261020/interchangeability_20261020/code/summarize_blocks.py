"""Actual exact-team replacement effects, without predictions replacing fusion.

Pool-level final geometries are scratch inputs. The retained event table and
exact requests are sufficient to identify/rebuild every reported comparison.
Missing or failed native outcomes are retained; scores are never imputed zero.
"""
from __future__ import annotations
import argparse, collections, concurrent.futures, gzip, hashlib, io, json, math, os, sys, time
from pathlib import Path
for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[key]='1'
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'analysis/composition'))
sys.path.insert(0,str(ROOT/'interchangeability_20261020/independent'))
import summarize_grid as old
import pair_diagnostics as new
from design_history_panel import read, write, digest, team_key

LEGACY_KEYS=['both_complete','B8L2_change','D10_change','abs_B8L2_change','abs_D10_change',
    'floor_jaccard_difference','floor_symdiff_h2','structure_bound_cyclic_deg',
    'node_count_difference','node_count_change','mean_height_prism_pair_iou',
    'height_ratio_pair_abs_logdiff','ref_node_set_jaccard_difference_9','ref_edge_set_jaccard_difference_9',
    'joint_stable_strict','joint_stable_main','joint_stable_wide']
RICH_KEYS=['geometry_noQ_strict','geometry_noQ_main','geometry_noQ_wide',
    'geometry_shape_strict','geometry_shape_main','geometry_shape_wide',
    'wall_coverage_symmetric_min_main','true_corner_F1_main','true_corner_count_difference',
    'true_reflex_corner_n_a','true_reflex_corner_n_b','boundary_distance_normalized_p95',
    'boundary_distance_normalized_max','bottom_y_absdiff_deg_p95','bottom_y_absdiff_deg_max',
    'top_y_absdiff_deg_p95','top_y_absdiff_deg_max','radius_abs_logratio_p95',
    'boundary_total_height_abs_logratio_p95','exact_flat_prism_pair_iou',
    'geometry_shape_main_and_prism_proxy_iou_lt_095','different_original_nodes_shape_main_passes']
ARM_KEYS=['B8L2','D10','IoU3D100','iou_2d','omission','extension','Hmean','Hcenter',
          'height_mean_ratio','nodes','ref_node_recall_9','ref_edge_recall_9','minimum_support',
          'selected_support_min','new_n','old_n']
FEAT_KEYS=['q_beta','q_abs_p10','q_residual_sd','t_source_origin_effect','pair_count_effect',
           'bottom_y_effect','height_log_effect','hard_minus_easy','semi_new_error_nonedit_effect',
           'semi_new_edit_effect','semi_old_edit_effect','scope_out_effect']

def csv_write(frame, path):
    """Single atomic compressed write after observed interrupted gzip streams."""
    path=Path(path); raw=frame.to_csv(index=False).encode('utf-8')
    packed=gzip.compress(raw,mtime=0) if path.suffix=='.gz' else raw
    tmp=path.with_name(path.name+'.tmp')
    with tmp.open('wb') as f:
        f.write(packed); f.flush(); os.fsync(f.fileno())
    tmp.replace(path)
    if path.suffix=='.gz':
        assert gzip.decompress(path.read_bytes())==raw

def valid_part(path, events):
    if not path.exists():return False
    try:
        frame=pd.read_csv(io.BytesIO(gzip.decompress(path.read_bytes())),usecols=['event_id'])
        return len(frame)==len(events) and set(frame.event_id)=={e['event_id'] for e in events}
    except (EOFError,OSError,ValueError):
        return False

def finite(x):
    return float(x) if x is not None and isinstance(x,(int,float,np.number)) and math.isfinite(float(x)) else None

def subtract(a,b):
    a,b=finite(a),finite(b)
    return b-a if a is not None and b is not None else None

def full_mean(values):
    v=[finite(x) for x in values]
    return float(np.mean(v)) if v and all(x is not None for x in v) else None

def field_q(domain):
    return 'theta_hard' if domain.startswith('hard') else 'theta_'+domain if domain in ['easy','medium'] else domain+'_q_effect' if domain in ['semi_new','semi_v1','doorway'] else 'q_beta'

def event_row(e, teams, pool, features, rich=True, cache=None, signature_cache=None):
    recs={r['worker_id']:r for r in pool['records']}
    row={k:e.get(k) for k in ['event_id','phase','method_id','domain','family','context_id','pool_id',
        'building','image','difficulty','layer','condition','reference_id','n','m','outgoing_class',
        'incoming_class','background_policy','matching','actual_source_match','outside_background_n',
        'complete_turnover','direction','available_population_n','replicate','pattern','changed_category_slots','B_to_C_actual_turnover']}
    row['scene']=pool['meta'].get('scene')
    row['scale']='m_ge_2' if e['m']>=2 else 'm_1'
    row['n_band']='02-05' if e['n']<=5 else '06-10' if e['n']<=10 else '11-17' if e['n']<=17 else '18-25' if e['n']<=25 else '26plus'
    row['replacement_fraction']=e['m']/e['n']
    row['m_fraction_band']='0-.2' if e['m']/e['n']<=.2 else '.2-.4' if e['m']/e['n']<=.4 else '.4-.6' if e['m']/e['n']<=.6 else '.6-1'
    row['A_composition']=json.dumps(e['A_counts'],sort_keys=True,separators=(',',':'))
    row['C_composition']=json.dumps(e['C_counts'],sort_keys=True,separators=(',',':'))
    row['core_composition']=json.dumps(e['core_counts'],sort_keys=True,separators=(',',':'))
    for arm in ['A','C']:
        for name,cl in [('out',e['outgoing_class']),('in',e['incoming_class'])]:
            row[arm+'_'+name+'_fraction']=e[arm+'_counts'].get(cl,0)/e['n']
    row['class_added']=e['A_counts'].get(e['incoming_class'],0)==0
    row['class_removed']=e['C_counts'].get(e['outgoing_class'],0)==0
    if e.get('pattern')=='multi_class_block':
        for arm in ['A','C']:
            for name in ['out','in']:row[arm+'_'+name+'_fraction']=None
        row['class_added']=any(c!='outside_group' and v>0 and e['A_counts'].get(c,0)==0 for c,v in e['C_counts'].items())
        row['class_removed']=any(c!='outside_group' and v>0 and e['C_counts'].get(c,0)==0 for c,v in e['A_counts'].items())
    row['core_new_n']=sum(recs[w]['origin']=='new' for w in e['core_workers'])
    row['core_n']=len(e['core_workers'])
    arms={arm:teams[e[arm+'_team_key']] for arm in 'ABC'}
    for arm,t in arms.items():
        assert team_key(e['pool_id'],e[arm+'_workers'])==t['team_key']
        assert sorted(e[arm+'_workers'])==sorted(t['member_workers'])
        assert t['k']==e['n'] and t['reference_id']==e['reference_id']
        row[arm+'_team_key']=t['team_key']; row[arm+'_complete']=bool(t.get('complete_evaluable'))
        row[arm+'_score_status']=t.get('score_status'); row[arm+'_geometry_reason']=t.get('geometry_reason')
        for key in ARM_KEYS:
            row[arm+'_'+key]=finite(t.get(key))
        if t['team_key'] not in signature_cache:
            signature_cache[t['team_key']]=old.signature(t,pool['reference']['floor_xz_h'],cache.setdefault('reference_diagnostic',{}))
        sig=signature_cache[t['team_key']]
        for key in ['diag_wall_coverage_03','diag_wall_coverage_05','diag_corner_recall_05','floor_area_camera_h2']:
            row[arm+'_'+key]=finite(sig.get(key))
    for name,a,b in [('within','A','B'),('cross','A','C'),('net','B','C')]:
        aa,bb=arms[a],arms[b]
        if rich and name!='net':
            pair=new.pair_metrics(aa,bb,cache=cache.setdefault('shape',{}))
        else:
            pair=old.pair_metrics(aa,bb,signature_cache[aa['team_key']],signature_cache[bb['team_key']])
            for band,q,f,s in [('strict',1,.02,2),('main',2,.05,3),('wide',5,.1,5)]:
                pair['geometry_noQ_'+band]=bool(pair['both_complete'] and pair['node_count_difference']==0 and pair['floor_jaccard_difference'] is not None and pair['floor_jaccard_difference']<=f and pair['structure_bound_cyclic_deg'] is not None and pair['structure_bound_cyclic_deg']<=s)
        if name in ['within','cross']:
            assert pair['turnover']==e['m']
        row.update({name+'_'+key:pair.get(key) for key in LEGACY_KEYS})
        if name!='net':
            row.update({name+'_'+key:pair.get(key) for key in RICH_KEYS})
        else:
            row['net_geometry_noQ_main']=pair['geometry_noQ_main']
    row['rich_shape_computed']=rich
    for key in ARM_KEYS+['diag_wall_coverage_03','diag_wall_coverage_05','diag_corner_recall_05','floor_area_camera_h2']:
        row['net_'+key+'_delta']=subtract(row['B_'+key],row['C_'+key])
    row['net_complete_lost']=row['B_complete'] and not row['C_complete']
    row['net_complete_restored']=not row['B_complete'] and row['C_complete']
    for criterion in ['joint_stable_strict','joint_stable_main','joint_stable_wide','geometry_noQ_strict','geometry_noQ_main','geometry_noQ_wide','geometry_shape_strict','geometry_shape_main','geometry_shape_wide']:
        a,b=row['within_'+criterion],row['cross_'+criterion]
        row['gap_'+criterion]=int(a)-int(b) if a is not None and b is not None else None
    for key in ['floor_jaccard_difference','abs_B8L2_change','structure_bound_cyclic_deg','node_count_difference']:
        row['excess_'+key]=subtract(row['within_'+key],row['cross_'+key])
    dq=row['net_B8L2_change']
    row['net_Q_improve_gt2']=dq>2 if dq is not None else None
    row['net_Q_worsen_gt2']=dq< -2 if dq is not None else None
    row['net_Q_close2_shape_changed']=abs(dq)<=2 and not row['net_geometry_noQ_main'] if dq is not None else None
    row['within_bad_Q_gt5']=row['within_abs_B8L2_change']>5 if row['within_abs_B8L2_change'] is not None else None
    row['cross_bad_Q_gt5']=row['cross_abs_B8L2_change']>5 if row['cross_abs_B8L2_change'] is not None else None
    row['within_Q_drop_gt5']=row['within_B8L2_change']< -5 if row['within_B8L2_change'] is not None else None
    row['cross_Q_drop_gt5']=row['cross_B8L2_change']< -5 if row['cross_B8L2_change'] is not None else None
    qcol=field_q(e['domain']); row['history_Q_column']=qcol
    for name,ws in [('out',e['outgoing_workers']),('within',e['within_incoming']),('cross',e['cross_incoming'])]:
        row[name+'_block_new_n']=sum(recs[w]['origin']=='new' for w in ws)
        for col in dict.fromkeys([qcol]+FEAT_KEYS):
            row[name+'_history_'+col]=full_mean([features.get(w,{}).get(col) for w in ws])
        row[name+'_history_Q']=row[name+'_history_'+qcol]
        row[name+'_actual_annotation_Q']=full_mean([recs[w].get('B8L2') for w in ws])
        for kind in ['source','target']:
            vals=[finite(recs[w].get(kind+'_time_seconds')) for w in ws]
            row[name+'_'+kind+'_time_known_n']=sum(x is not None for x in vals)
            row[name+'_'+kind+'_block_seconds']=sum(vals) if all(x is not None for x in vals) else None
    for a,b in [('out','within'),('out','cross'),('within','cross')]:
        row[b+'_minus_'+a+'_history_Q']=subtract(row[a+'_history_Q'],row[b+'_history_Q'])
    row['all_blocks_history_Q_close3']=all(row[k] is not None and abs(row[k])<=3 for k in ['within_minus_out_history_Q','cross_minus_out_history_Q','cross_minus_within_history_Q'])
    row['history_Q_excess_abs']=subtract(abs(row['within_minus_out_history_Q']) if row['within_minus_out_history_Q'] is not None else None,abs(row['cross_minus_out_history_Q']) if row['cross_minus_out_history_Q'] is not None else None)
    for kind in ['source','target']:
        wb,cb=row['within_'+kind+'_block_seconds'],row['cross_'+kind+'_block_seconds']
        row['net_'+kind+'_block_seconds']=subtract(wb,cb)
        row['cross_over_within_'+kind+'_block_time']=cb/wb if wb is not None and cb is not None and wb>0 else None
    return row

def pool_job(pool,events,native,out,features,rich):
    target=Path(out)/'event_parts'/(pool['pool_id']+'.csv.gz');target.parent.mkdir(parents=True,exist_ok=True)
    source=Path(native)/'pools'/(pool['pool_id']+'.json.gz')
    data=read(source); teams={x['team_key']:x for x in data['teams']}
    cache={}; signatures={}; rows=[]; start=time.monotonic()
    for e in events:
        rows.append(event_row(e,teams,pool,features,rich=rich,cache=cache,signature_cache=signatures))
        # Geometry signatures are a runtime optimization, not evidence. Bound
        # their size while retaining all numerical rows and native geometries.
        if len(cache.get('shape',{}))>900:cache['shape'].clear()
    csv_write(pd.DataFrame(rows),target)
    return dict(pool_id=pool['pool_id'],events=len(rows),requested_unique_teams=len({e[arm+'_team_key'] for e in events for arm in 'ABC'}),
                seconds=time.monotonic()-start,native_sha256=hashlib.sha256(source.read_bytes()).hexdigest())

def support(frame,columns):
    by=frame.groupby(columns,dropna=False,observed=True,sort=True)
    return by.agg(events=('event_id','size'),pools=('pool_id','nunique'),buildings=('building','nunique')).reset_index()

def summarize(frame,columns,subset):
    if frame.empty:return pd.DataFrame()
    metrics=[c for c in frame if (c.startswith(('gap_','within_joint','cross_joint','within_geometry','cross_geometry','within_bad','cross_bad','net_Q','net_complete','excess_')) or c in ['net_B8L2_change','net_D10_change','within_abs_B8L2_change','cross_abs_B8L2_change','within_floor_jaccard_difference','cross_floor_jaccard_difference','within_node_count_difference','cross_node_count_difference','within_structure_bound_cyclic_deg','cross_structure_bound_cyclic_deg','net_ref_node_recall_9_delta','net_ref_edge_recall_9_delta','net_IoU3D100_delta','net_omission_delta','net_extension_delta','net_diag_wall_coverage_05_delta','net_diag_corner_recall_05_delta','within_bottom_y_absdiff_deg_p95','cross_bottom_y_absdiff_deg_p95','within_top_y_absdiff_deg_p95','cross_top_y_absdiff_deg_p95','cross_over_within_source_block_time','cross_over_within_target_block_time','net_source_block_seconds','net_target_block_seconds','cross_minus_within_history_Q','history_Q_excess_abs','A_complete','B_complete','C_complete','B_B8L2','C_B8L2']) and pd.api.types.is_numeric_dtype(frame[c])]
    bycols=list(dict.fromkeys(columns+['pool_id','building']))
    image=frame.groupby(bycols,observed=True,dropna=False)[metrics].mean().reset_index()
    building=image.groupby(list(dict.fromkeys(columns+['building'])),observed=True,dropna=False)[metrics].mean().reset_index()
    means=building.groupby(columns,observed=True,dropna=False)[metrics].mean().add_suffix('_building_mean').reset_index()
    result=support(frame,columns).merge(means,on=columns)
    result['subset']=subset
    grouped=frame.groupby(columns,dropna=False,observed=True)
    for key in ['within_abs_B8L2_change','cross_abs_B8L2_change','within_floor_jaccard_difference','net_B8L2_change','B_B8L2','C_B8L2','net_D10_change']:
        stats=grouped[key].agg(['count','min']).rename(columns={'count':key+'_available_n','min':key+'_event_min'})
        stats[key+'_event_p10']=grouped[key].quantile(.1)
        stats[key+'_event_p90']=grouped[key].quantile(.9)
        result=result.merge(stats.reset_index(),on=columns)
    for kind in ['source','target']:
        key='cross_over_within_'+kind+'_block_time'
        stats=grouped[key].count().rename(key+'_available_n').reset_index()
        result=result.merge(stats,on=columns)
    return result

def aggregate_tables(events,out):
    out=Path(out); base=['phase','method_id','domain','context_id','direction']
    tables=[]
    subsets={'m_ge_2':events[(events.m>=2)&(events.n>=3)],
        'm_ge_2_all_n_attempts':events[events.m>=2],
        'n_2_deferred':events[events.n==2],
        'm_1':events[(events.m==1)&(events.n>=3)],
        'm_ge_2_source_match':events[(events.m>=2)&(events.n>=3)&events.actual_source_match],
        'm_ge_2_source_Qclose3':events[(events.m>=2)&(events.n>=3)&events.actual_source_match&events.all_blocks_history_Q_close3]}
    for name,frame in subsets.items():
        tables.append(summarize(frame,base,name))
    combined=pd.concat(tables,ignore_index=True)
    csv_write(combined,out/'direction_summary.csv.gz')
    primary=events[(events.m>=2)&(events.n>=3)]
    for key in ['difficulty','n_band','m_fraction_band','background_policy','m']:
        tab=summarize(primary,base+[key],'m_ge_2')
        csv_write(tab,out/('by_'+key+'.csv.gz'))
    per_building=summarize(primary,base+['building'],'m_ge_2')
    csv_write(per_building,out/'per_building.csv.gz')
    return combined

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--requests',type=Path,required=True)
    ap.add_argument('--native',type=Path,required=True);ap.add_argument('--features',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--jobs',type=int,default=3);ap.add_argument('--legacy-only',action='store_true');ap.add_argument('--aggregate-only',action='store_true')
    ap.add_argument('--stream',action='store_true',help='Consume atomically completed native pool files while the independent fusion job is running')
    ap.add_argument('--resume',action='store_true',help='Retain only fully readable parts with exact expected event IDs')
    ap.add_argument('--events-only',action='store_true',help='Use a separately defined aggregation for mixed-vector challenges')
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    payload=read(a.requests); events=payload['events']; by=collections.defaultdict(list)
    for e in events:by[e['pool_id']].append(e)
    receipts=[]
    if not a.aggregate_only:
        pools={p['pool_id']:p for p in read(a.snapshot)['images']}
        features=pd.read_csv(a.features).set_index('worker_id').replace({np.nan:None}).to_dict('index')
        with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as executor:
            pending={pid:es for pid,es in by.items() if not (a.resume and valid_part(a.out/'event_parts'/(pid+'.csv.gz'),es))}; futures={}
            print(json.dumps(dict(existing_valid_parts=len(by)-len(pending),pending=len(pending))),flush=True)
            while pending or futures:
                for pid in list(pending):
                    if len(futures)>=a.jobs:break
                    if a.stream and not (a.native/'pools'/(pid+'.json.gz')).exists():continue
                    future=executor.submit(pool_job,pools[pid],pending.pop(pid),a.native,a.out,features,not a.legacy_only)
                    futures[future]=pid
                if not futures:
                    time.sleep(1);continue
                done,_=concurrent.futures.wait(futures,timeout=1,return_when=concurrent.futures.FIRST_COMPLETED)
                for future in done:
                    r=future.result();futures.pop(future);receipts.append(r)
                    print(json.dumps(dict(r,done=len(receipts),pools=len(by))),flush=True)
    frame=pd.concat([pd.read_csv(a.out/'event_parts'/(pid+'.csv.gz')) for pid in by],ignore_index=True)
    assert len(frame)==len(events) and frame.event_id.nunique()==len(events)
    for arm in ['within','cross']:
        frame[arm+'_Q_drop_gt5']=frame[arm+'_B8L2_change'].lt(-5).where(frame[arm+'_B8L2_change'].notna())
    csv_write(frame,a.out/'event_metrics.csv.gz')
    tables=pd.DataFrame() if a.events_only else aggregate_tables(frame,a.out)
    write(a.out/'SUMMARY_RECEIPT.json',dict(request_sha256=hashlib.sha256(a.requests.read_bytes()).hexdigest(),events=len(events),
        pools=frame.pool_id.nunique(),images=frame.image.nunique(),buildings=frame.building.nunique(),workers=len({w for e in events for arm in 'ABC' for w in e[arm+'_workers']}),
        methods=frame[['method_id','domain','context_id']].drop_duplicates().shape[0],unique_teams=len({e[arm+'_team_key'] for e in events for arm in 'ABC'}),
        n_nodes=sorted(map(int,frame.n.unique())),m_nodes=sorted(map(int,frame.m.unique())),
        rich_shape_computed=not a.legacy_only,summary_rows=len(tables),by_pool=receipts,
        weighting='Events within pool -> pools within building -> equal buildings; event p10/p90/min explicitly descriptive. Failures kept; finite Q/time denominators reported; no imputation.',
        eligibility='Main uses n>=3 under inherited native qualification. All n=2 requests/legacy flags retained separately as two_person_deferred, not called computational fusion failures. All-n attempt table also retained.'))

if __name__=='__main__':main()
