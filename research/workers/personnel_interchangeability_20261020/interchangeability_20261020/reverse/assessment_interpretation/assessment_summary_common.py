"""True-image and building equal summaries for fixed assessment experiments."""
from __future__ import annotations
import functools
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
BASE=HERE.parents[1]
ROOT=BASE.parent

SIGN_METRICS=["gap_joint_stable_main","gap_geometry_noQ_main","gap_geometry_shape_main","net_B8L2_change"]
FINITE_METRICS=SIGN_METRICS+["within_floor_jaccard_difference","cross_floor_jaccard_difference","within_prism_distance","cross_prism_distance"]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(tuple,list,np.ndarray)):return [clean(v) for v in x]
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,float) and not np.isfinite(x):return None
    return x


def write_json(path,value):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(clean(value),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if str(path).endswith('.gz'):raw=gzip.compress(raw,mtime=0)
    temp=Path(str(path)+'.tmp');temp.write_bytes(raw);temp.replace(path)


def write_csv(path,frame):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    raw=frame.to_csv(index=False).encode();packed=gzip.compress(raw,mtime=0) if path.suffix=='.gz' else raw
    if path.suffix=='.gz':assert gzip.decompress(packed)==raw
    temp=path.with_name(path.name+'.tmp');temp.write_bytes(packed);temp.replace(path)
    if path.suffix=='.gz':assert gzip.decompress(path.read_bytes())==raw


def bit_count(values):return int(functools.reduce(int.__or__,map(int,values),0)).bit_count()


def decorate_support(g):
    out=dict(events=len(g),pools=g.pool_id.nunique(),true_images=g.image_id.nunique(),buildings=g.building.nunique(),
        unique_teams=len(set(g.A_team_key)|set(g.B_team_key)|set(g.C_team_key)),
        unique_AB_pairs=g.within_unordered_team_pair.nunique(),
        actual_people=bit_count(g.all_worker_mask),replaceable_people=bit_count(g.block_worker_mask),
        n_min=int(g.n.min()),n_max=int(g.n.max()),m_min=int(g.m.min()),m_max=int(g.m.max()))
    if 'path_id' in g:out['fixed_paths']=g.path_id.nunique()
    for arm in 'ABC':
        out[arm+'_attempt_events']=len(g)
        out[arm+'_complete_events']=int(g[arm+'_complete'].sum())
        out[arm+'_scored_events']=int(g[arm+'_B8L2'].notna().sum())
        out[arm+'_unique_teams']=g[arm+'_team_key'].nunique()
    for metric in FINITE_METRICS:
        if metric not in g:continue
        f=g[g[metric].notna()]
        for name,value in [('events',len(f)),('pools',f.pool_id.nunique()),('true_images',f.image_id.nunique()),('buildings',f.building.nunique())]:
            out[metric+'_finite_'+name]=value
    return out


def support_table(frame,keys):
    rows=[]
    for key,g in frame.groupby(keys,dropna=False):
        key=key if isinstance(key,tuple) else (key,)
        rows.append(dict(zip(keys,key))|decorate_support(g))
    return pd.DataFrame(rows)


def summarize(frame,keys,metrics,tails=True):
    """Events -> reference pool -> true image ID -> building -> all buildings.

    Return per-image, per-building and overall, with raw support at each level.
    Tail values are explicitly within-pool descriptors before that hierarchy.
    """
    if frame.empty:return pd.DataFrame(),pd.DataFrame(),pd.DataFrame()
    metrics=[m for m in metrics if m in frame]
    poolkeys=keys+['building','image_id','pool_id']
    p=frame.groupby(poolkeys,dropna=False)[metrics].mean().reset_index()
    if tails:
        tailcols=[m for m in ['net_B8L2_change','B_B8L2','C_B8L2','within_abs_B8L2_change','cross_abs_B8L2_change'] if m in frame]
        for q,suffix in [(.1,'p10'),(.9,'p90')]:
            t=frame.groupby(poolkeys,dropna=False)[tailcols].quantile(q).reset_index().rename(columns={m:m+'_per_pool_'+suffix for m in tailcols})
            p=p.merge(t,on=poolkeys,validate='one_to_one')
    numeric=[c for c in p if c not in poolkeys]
    im=p.groupby(keys+['building','image_id'],dropna=False)[numeric].mean().reset_index()
    bu=im.groupby(keys+['building'],dropna=False)[numeric].mean().reset_index()
    ag=bu.groupby(keys,dropna=False)[numeric].mean().reset_index()
    # The actual support quantities do not get averaged through this hierarchy.
    im=im.merge(support_table(frame,keys+['building','image_id']),on=keys+['building','image_id'],validate='one_to_one')
    bu=bu.merge(support_table(frame,keys+['building']),on=keys+['building'],validate='one_to_one')
    ag=ag.merge(support_table(frame,keys),on=keys,validate='one_to_one')
    for metric in SIGN_METRICS:
        if metric not in numeric:continue
        for units,table in [('true_images',im),('buildings',bu)]:
            # Machine-roundoff tolerance, not a scientific acceptance threshold.
            s=table.groupby(keys,dropna=False)[metric].agg(**{
                metric+'_positive_'+units:lambda x:int((x>1e-9).sum()),
                metric+'_negative_'+units:lambda x:int((x< -1e-9).sum()),
                metric+'_equal_'+units:lambda x:int((x.abs()<=1e-9).sum()),
                metric+'_min_'+units:'min',metric+'_max_'+units:'max'}).reset_index()
            ag=ag.merge(s,on=keys,validate='one_to_one')
    if 'source_block_log_ratio' in numeric:
        for table in [im,bu,ag]:table['source_block_geometric_ratio']=np.exp(table.source_block_log_ratio)
    return im,bu,ag


def add_fields(frame):
    f=frame.copy()
    for arm in 'ABC':f[arm+'_score_missing']=f[arm+'_B8L2'].isna()
    for kind in ['within','cross']:
        q=f[kind+'_B8L2_change']
        f[kind+'_Q_drop_gt5']=(q< -5).astype(float).where(q.notna())
        f[kind+'_absQ_gt5']=(q.abs()>5).astype(float).where(q.notna())
        f[kind+'_prism_distance']=1-f[kind+'_mean_height_prism_pair_iou']
        f[kind+'_node_count_changed']=f[kind+'_node_count_difference'].ne(0).astype(float).where(f[kind+'_node_count_difference'].notna())
    f['net_Q_worsen_gt5']=(f.net_B8L2_change< -5).astype(float).where(f.net_B8L2_change.notna())
    f['excess_prism_distance']=f.cross_prism_distance-f.within_prism_distance
    f['within_unordered_team_pair']=['|'.join(sorted(x)) for x in f[['A_team_key','B_team_key']].itertuples(index=False,name=None)]
    if 'within_source_block_seconds' in f:
        w=f.within_source_block_seconds;c=f.cross_source_block_seconds
        ok=(w>0)&(c>0)&w.notna()&c.notna()
        f['source_block_log_ratio']=np.log((c/w).where(ok))
        f['source_time_comparable']=ok
        save=c/w<=.8;good=f.B_complete&f.C_complete&f.net_B8L2_change.notna()&(f.net_B8L2_change>=-2)
        f['source_save20']=save.astype(float).where(ok)
        f['source_save20_Q_not_worse2']=(save&good).astype(float).where(ok)
        f['source_save20_Q_not_worse2_same_noQ_geometry']=(save&good&f.net_geometry_noQ_main).astype(float).where(ok)
    return f


METRICS=[
    'A_B8L2','B_B8L2','C_B8L2','A_D10','B_D10','C_D10',
    'A_complete','B_complete','C_complete','A_score_missing','B_score_missing','C_score_missing',
    'within_joint_stable_main','cross_joint_stable_main','gap_joint_stable_main',
    'within_joint_stable_strict','cross_joint_stable_strict','gap_joint_stable_strict',
    'within_joint_stable_wide','cross_joint_stable_wide','gap_joint_stable_wide',
    'within_geometry_noQ_main','cross_geometry_noQ_main','gap_geometry_noQ_main',
    'within_geometry_shape_main','cross_geometry_shape_main','gap_geometry_shape_main',
    'within_abs_B8L2_change','cross_abs_B8L2_change','excess_abs_B8L2_change',
    'within_absQ_gt5','cross_absQ_gt5','within_Q_drop_gt5','cross_Q_drop_gt5',
    'net_B8L2_change','net_D10_change','net_Q_improve_gt2','net_Q_worsen_gt2','net_Q_worsen_gt5',
    'net_complete_lost','net_complete_restored','within_floor_jaccard_difference','cross_floor_jaccard_difference',
    'excess_floor_jaccard_difference','within_prism_distance','cross_prism_distance','excess_prism_distance',
    'within_node_count_difference','cross_node_count_difference','within_node_count_changed','cross_node_count_changed',
    'within_structure_bound_cyclic_deg','cross_structure_bound_cyclic_deg',
    'within_true_corner_F1_main','cross_true_corner_F1_main',
    'within_wall_coverage_symmetric_min_main','cross_wall_coverage_symmetric_min_main',
    'within_different_original_nodes_shape_main_passes','cross_different_original_nodes_shape_main_passes',
    'net_diag_wall_coverage_05_delta','net_diag_corner_recall_05_delta','net_ref_node_recall_9_delta',
    'net_ref_edge_recall_9_delta','net_IoU3D100_delta','net_omission_delta','net_extension_delta',
    'A_nodes','B_nodes','C_nodes','A_minimum_support','B_minimum_support','C_minimum_support',
    'A_out_fraction','C_out_fraction','A_in_fraction','C_in_fraction','replacement_fraction',
    'actual_source_match','all_blocks_history_Q_close3','cross_minus_within_history_Q',
    'source_block_log_ratio','source_time_comparable','source_save20','source_save20_Q_not_worse2',
    'source_save20_Q_not_worse2_same_noQ_geometry','net_source_block_seconds',
    'within_source_block_seconds','cross_source_block_seconds']


def stream_events(path):
    decoder=json.JSONDecoder()
    with gzip.open(path,'rt') as f:
        # The nested manifest has a short ``design`` field before ``events``;
        # parse top-level JSON fields, without loading the large requests tail.
        buf='';eof=False
        def fill():
            nonlocal buf,eof
            part=f.read(1<<18);eof=not part;buf+=part
            assert len(buf)<16*(1<<20)
        def trim():
            nonlocal buf
            buf=buf.lstrip()
            while not buf and not eof:fill();buf=buf.lstrip()
        def value():
            nonlocal buf
            while True:
                trim()
                try:obj,end=decoder.raw_decode(buf)
                except json.JSONDecodeError:
                    if eof:raise RuntimeError('Truncated request header')
                    fill();continue
                buf=buf[end:];return obj
        trim();assert buf.startswith('{');buf=buf[1:]
        while True:
            name=value();assert isinstance(name,str)
            trim();assert buf.startswith(':');buf=buf[1:]
            if name=='events':
                trim();assert buf.startswith('[');buf=buf[1:];break
            value();trim();assert buf.startswith(',');buf=buf[1:]
        while True:
            buf=buf.lstrip()
            if buf.startswith(','):buf=buf[1:].lstrip()
            if buf.startswith(']'):return
            try:
                if not buf:raise json.JSONDecodeError('empty',buf,0)
                event,end=decoder.raw_decode(buf)
            except json.JSONDecodeError:
                if eof:raise RuntimeError('Truncated events array')
                part=f.read(1<<18);eof=not part;buf+=part
                assert len(buf)<16*(1<<20)
                continue
            yield event;buf=buf[end:]


def load_exact(panel,method_ids=None):
    """Read only the authorized exact panel, verify labels and real members."""
    assessment=BASE/'assessment';request=assessment/(panel+'_requests.json.gz')
    metricsdir=assessment/(panel+'_metrics')
    official=metricsdir/'SUMMARY_RECEIPT.json'
    if not official.exists():raise RuntimeError('Incomplete native/metric panel; missing teams are not failures')
    receipt=json.load(open(official));assert receipt['request_sha256']==sha(request)
    freeze=json.load(open(assessment/'ASSESSMENT_FREEZE.json'))
    labpath=BASE/'reverse/mixed_fit/worker_labels.csv.gz'
    assert sha(labpath)==freeze['file_sha256']['reverse/mixed_fit/worker_labels.csv.gz']
    contract=BASE/'independent/METRIC_CONTRACT.json'
    assert sha(contract)==freeze['file_sha256']['independent/METRIC_CONTRACT.json']
    labels=pd.read_csv(labpath)
    labels=labels[labels.known.astype(str).str.lower().isin(['true','1','1.0'])]
    if method_ids is not None:labels=labels[labels.method_id.isin(method_ids)]
    mapping={mid:dict(zip(g.worker_id,g.class_id)) for mid,g in labels.groupby('method_id')}
    snapshot=ROOT/'restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz'
    with gzip.open(snapshot,'rt') as f:payload=json.load(f)
    poolmeta={p['pool_id']:p['meta'] for p in payload['images']};del payload
    roster=pd.read_csv(ROOT/'analysis/forward/results/features_train.csv.gz',usecols=['worker_id']).worker_id.tolist()
    assert len(roster)<=64;bits={w:1<<i for i,w in enumerate(sorted(roster))}
    events=[]
    for original in stream_events(request):
        if method_ids is not None and original['method_id'] not in method_ids:continue
        e=dict(original);assert e['phase']=='assessment' and e['building'] in freeze['assessment_buildings']
        mp=mapping[e['method_id']]
        A,B,C,core=[set(e[k]) for k in ['A_workers','B_workers','C_workers','core_workers']]
        assert len(A)==len(B)==len(C)==e['n'] and A&B==A&C==core
        assert len(A-B)==len(A-C)==e['m']
        assert len(B-C)==e.get('B_to_C_actual_turnover',e['m'])
        from collections import Counter
        for arm,workers in [('A',A),('B',B),('C',C)]:
            assert Counter(mp.get(w,'outside_group') for w in workers)==Counter(e[arm+'_counts'])
        assert e['A_counts']==e['B_counts'] and e['A_counts']!=e['C_counts']
        for cl,workers in [(e['outgoing_class'],A-core),(e['outgoing_class'],B-core),(e['incoming_class'],C-core)]:
            assert all(mp.get(w)==cl for w in workers)
        e['image_id']=poolmeta[e['pool_id']]['image_id']
        e['all_worker_mask']=sum(bits[w] for w in A|B|C)
        e['block_worker_mask']=sum(bits[w] for w in (A|B|C)-core)
        e['event_definition_sha256']=hashlib.sha256(json.dumps(original,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        events.append(e)
    md=pd.DataFrame(events);assert not md.event_id.duplicated().any()
    selected_ids=set(md.event_id);parts=[];sources=[]
    for pid in sorted(md.pool_id.unique()):
        source=metricsdir/'event_parts'/(pid+'.csv.gz')
        f=pd.read_csv(source);f=f[f.event_id.isin(selected_ids)]
        assert set(f.event_id)==set(md[md.pool_id.eq(pid)].event_id)
        parts.append(f);sources.append(dict(pool_id=pid,sha256=sha(source)))
    frame=pd.concat(parts,ignore_index=True)
    fields=['event_id','image_id','all_worker_mask','block_worker_mask','event_definition_sha256',
        'A_workers','B_workers','C_workers','core_workers','outgoing_workers','within_incoming','cross_incoming']
    fields += [c for c in ['path_id','added_core_worker','core_prefix_n','path_step','primary_role'] if c in md]
    frame=frame.merge(md[fields],on='event_id',validate='one_to_one')
    assert len(frame)==len(md) and frame.phase.eq('assessment').all()
    meta=dict(panel=panel,request_sha256=sha(request),metric_receipt_sha256=sha(official),
        assessment_freeze_sha256=sha(assessment/'ASSESSMENT_FREEZE.json'),labels_sha256=sha(labpath),
        metric_contract_sha256=sha(contract),source_part_sha256=sources,
        events=len(frame),pools=frame.pool_id.nunique(),true_images=frame.image_id.nunique(),buildings=frame.building.nunique(),
        exact_member_class_count_turnover_verified=True)
    return add_fields(frame),md,meta
