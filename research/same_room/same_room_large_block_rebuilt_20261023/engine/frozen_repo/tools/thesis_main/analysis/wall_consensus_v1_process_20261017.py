"""Data v1 real subset replays, fixed gap/MV50/median; module-owned outputs only."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
import gzip
import itertools
import json
from pathlib import Path
import shutil
import time

import numpy as np
import pandas as pd
from shapely.ops import unary_union

from . import ring_correspondence_20261007 as ring
from .consensus_delivery_20261008 import fuse, WORKING_GAP
from .wall_consensus_population_20261014 import compact, summarize_state, compare_outputs, transition, footprint
from .wall_consensus_quality_20261015 import measured
from .quality_b8l2_d10_20261017 import read, dual_scores, model_parameters
from .wall_consensus_b8l2_20261016 import COMPONENTS, finite
from .research_round_20260929 import prepare_record, reconstruct
from ..data_prep.consolidate_research_input import load_current_bundle
from ..data_prep.project_public_research_20260929 import project_bundle
from .scope_quality_scoring_20261016 import scoring_engine

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/fusion/wall_consensus_v1_process_20261017'
QUALITY=ROOT/'research/quality/quality_b8l2_d10_20261017'
ENGINE=ROOT/'research/statistics/b8l2_shared_v6_20261016/inputs'
SEED=20261017


def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


@contextmanager
def cached_matching():
    original=ring.cyclic_match; cache={}
    def match(cost,gap):
        key=(cost.shape,cost.tobytes(),gap)
        if key not in cache:cache[key]=original(cost,gap)
        return cache[key]
    ring.cyclic_match=match
    try:yield cache
    finally:ring.cyclic_match=original


def selected_state(records,cache):
    key='|'.join(sorted(r['id'] for r in records))
    if key not in cache:cache[key]=compact(fuse(records,gap=WORKING_GAP)['automatic'])
    return cache[key]


def original_disagreement(indices,dist,union_area):
    vals=[dist[i,j] for i,j in itertools.combinations(indices,2) if np.isfinite(dist[i,j])]
    mean=float(np.mean(vals)) if vals else None
    return dict(R_symdiff_h2=mean,R_union_normalized=mean/union_area if mean is not None and union_area else None,
                R_valid_pairs=len(vals),R_possible_pairs=len(indices)*(len(indices)-1)//2)


def explicit_true(value):
    return str(value) == 'True'


def measurement_context(im):
    ref=im['reference']
    return dict(reference={k:ref[k] for k in ('target_id','reference_version','floor_xz_h','points_1024x512','full_reference_available')},
                records=[{k:r.get(k) for k in ('id','worker','points','source_pair_indices','ring_confirmed','order_used')}
                         for r in sorted(im['records'],key=lambda r:r['id'])],gap=WORKING_GAP)


def prepare():
    contract=read(QUALITY/'CROSS_MODULE_INPUTS.json')
    bundle=load_current_bundle(ROOT/contract['input_manifest']); data,aliases=project_bundle(bundle)
    objects={o['object_id']:o for o in bundle['data']['objects']}
    projected={r['id']:r for im in data['images'] for r in im['annotations']}
    inventory=pd.read_csv(ROOT/contract['full_inventory_with_metric_eligibility'],keep_default_na=False)
    pools=pd.read_csv(ROOT/contract['source_pools'],keep_default_na=False)
    bindings=pd.read_csv(ROOT/contract['all_pre_score_bindings'],keep_default_na=False).set_index('object_id')
    refs={r['target_id']:r for r in read(ROOT/contract['reference_catalog'])}
    labels={r['image_id']:r for r in read(ROOT/contract['difficulty_records'])}
    legacy_holds={r['object_id'] for r in read(ROOT/'research/fusion/wall_consensus_b8l2_20261016/member_registry.json') if r['original_holdout']}
    snapshot=[];ledger=[]
    for p in pools.to_dict('records'):
        why=[]
        if not p['pool_analysis_eligible']:why.append('existing_pool_gate')
        if p['n_effective_workers']<3:why.append('source_pool_below3')
        group=inventory[(inventory.image_id==p['image_id']) & (inventory.condition==p['condition']) & inventory.pool_vote_eligible]
        records=[];failure=None
        if not why:
            for row in group.to_dict('records'):
                oid=row['object_id']; obj=objects[oid]; source=projected[aliases['records'][oid]]
                try:r=prepare_record(dict(source,source_pair_indices=obj['ordered_source_pair_indices']))
                except ValueError as e:failure=str(e);break
                r.update(object_id=oid,worker_id=obj['worker_id'],chosen_target_id=bindings.loc[oid,'chosen_target_id'],
                    quality_usable=bool(row['quality_usable']),original_holdout=explicit_true(row['original_holdout']) or oid in legacy_holds,
                    source_time_seconds=row.get('source_active_time_seconds'),
                    target_time_seconds=row.get('target_matched_time_seconds'))
                if r['points'] is None:failure='paired_points_unavailable';break
                records.append(r)
            if failure:why.append('whole_pool_input_failure:'+failure)
            else:
                assert len(records)==p['n_effective_workers'] and len({r['worker_id'] for r in records})==len(records)
        label=labels[p['image_id']];ref=refs[label['target_version']]
        poolid=p['image_code']+'__'+p['condition']
        ledger.append(dict(pool_id=poolid,image=p['image_code'],condition=p['condition'],source_workers=p['n_effective_workers'],
            scene=label['scene'],difficulty=label['current_class'],included=not why,reasons='|'.join(why)))
        if why:continue
        snapshot.append(dict(pool_id=poolid,image=p['image_code'],image_id=p['image_id'],condition=p['condition'],
            building=p['building_id'],scene=label['scene'],difficulty=label['current_class'],reference=ref,
            records=sorted(records,key=lambda r:(r['worker'],r['id'])),
            layer='oos_diagnostic' if 'oos' in label['scene'] or p['condition']=='oos' else
                  'doorway_conditional' if 'doorway' in label['scene'] else
                  'ordinary' if p['ordinary_difficulty_eligible'] else 'restricted'))
    save(OUT/'input_snapshot.json',dict(data_release='v1',input_manifest=contract['input_manifest'],shared_contract=contract,
        images=snapshot,seed=SEED,random_paths=4,fusion_gap=WORKING_GAP,
        selection='all image-condition pools passing existing source gate and >=3 independent voters; no score selection'))
    pd.DataFrame(ledger).to_csv(OUT/'pool_eligibility.csv',index=False,encoding='utf-8-sig')
    print('Prepared',len(snapshot),'pools',len({r['image'] for r in snapshot}),'images',flush=True)


def legacy_states(im):
    cache={};origins={}
    source=ROOT/'research/fusion/wall_consensus_population_20261014'
    snap=read(source/'input_snapshot.json')['images']
    special=ROOT/'research/fusion/wall_consensus_quality_20261015/special'
    snap += read(special/'input_snapshot.json')['images']
    old=next((x for x in snap if x['image']==im['image']),None)
    if old is None or im['condition']!='manual':return cache,origins
    signature=lambda rows:{r['id']:(r['worker'],r['points'],r.get('source_pair_indices')) for r in rows}
    if signature(old['records'])!=signature(im['records']):return cache,origins
    path=source/'states'/f"{im['image']}.json.gz"
    if not path.exists():path=special/'states'/f"{im['image']}.json.gz"
    workers={r['worker']:r['id'] for r in old['records']}
    for e in json.load(gzip.open(path,'rt',encoding='utf-8'))['states']:
        key='|'.join(sorted(workers[w] for w in e['workers']))
        cache[key]=e['automatic'];origins[key]=str(path.relative_to(ROOT))
    return cache,origins


def run_image(im):
    started=time.monotonic(); records=im['records'];lookup={r['worker_id']:r for r in records}
    workers=sorted(lookup);rng=np.random.default_rng(SEED)
    orders=[dict(path_id='random_'+str(i),kind='random',workers=rng.permutation(workers).tolist(),request_id='') for i in range(4)]
    orders += im.get('requested_orders',[])
    cache,origins=legacy_states(im)
    target=OUT/'pools'/im['pool_id']
    scores={}
    if (target/'states.json.gz').exists():
        for e in json.load(gzip.open(target/'states.json.gz','rt',encoding='utf-8'))['states']:
            cache[e['subset']]=e['automatic'];origins[e['subset']]=e['origin']
        cache_file=target/'score_cache.json'
        if cache_file.exists():
            payload=read(cache_file)
            if payload['context']!=measurement_context(im):raise ValueError('measurement_cache_context_changed')
            scores=payload['measurements']
        # Legacy flat tables cannot preserve the raw payload; absent caches are remeasured on saved geometry.
    # A previous completion marker must not expose a pool while its request expansion is being written.
    (target/'DONE.json').unlink(missing_ok=True)
    initial=set(cache);used=set();observations=[];changes=[];swaps=[]
    polygons=[]
    for r in records:
        g=reconstruct(r,coordinate_convention='continuous');polygons.append(footprint(g['floor']))
    valid=[p for p in polygons if p is not None];union=unary_union(valid).area if valid else None
    dist=np.full((len(records),len(records)),np.nan)
    for i,j in itertools.combinations(range(len(records)),2):
        if polygons[i] is not None and polygons[j] is not None:dist[i,j]=dist[j,i]=polygons[i].symmetric_difference(polygons[j]).area
    indices={r['id']:i for i,r in enumerate(records)}
    ref=im['reference'];ref_input=dict(floor=ref['floor_xz_h'],points=ref['points_1024x512'] if ref['full_reference_available'] else None)
    by_path={}
    with cached_matching() as pair_cache, scoring_engine(ENGINE/'measurement_engine.zip',ENGINE/'working_models.py') as (engine,models):
        for order in orders:
            if len(set(order['workers']))!=len(order['workers']) or not set(order['workers'])<=set(workers):raise ValueError('invalid_requested_members')
            previous=None;by_path[order['path_id']]=[]
            for k in range(1,len(order['workers'])+1):
                selected=[lookup[w] for w in sorted(order['workers'][:k])];key='|'.join(sorted(r['id'] for r in selected))
                try:state=selected_state(selected,cache)
                except ValueError as e:
                    save(OUT/'failures'/f"{im['pool_id']}.json",dict(pool_id=im['pool_id'],reason=str(e),whole_pool_preserved=True,failed_subset=key))
                    return dict(pool_id=im['pool_id'],status='input_failure',reason=str(e),elapsed=time.monotonic()-started)
                used.add(key);summary=summarize_state(state)
                if key not in scores:
                    raw=measured(engine,state,ref_input)
                    dual=dual_scores(raw,models) if finite(raw,COMPONENTS) else dict(B8L2=None,D10=None)
                    scores[key]=dict(raw,diagnostic_B8L2=dual['B8L2'],diagnostic_D10=dual['D10'])
                score=scores[key];same_target=all(r['chosen_target_id']==ref['target_id'] for r in selected)
                quality_allowed=im['layer']!='oos_diagnostic' and same_target and all(r['quality_usable'] for r in selected)
                main=quality_allowed and not any(r['original_holdout'] for r in selected) and im['layer'] in ('ordinary','doorway_conditional')
                time_values=[r['source_time_seconds'] for r in selected]
                time_ok=all(v!='' and v is not None and np.isfinite(float(v)) for v in time_values)
                row=dict(pool_id=im['pool_id'],image=im['image'],condition=im['condition'],layer=im['layer'],difficulty=im['difficulty'],
                    scene=im['scene'],reference_id=ref['target_id'],reference_version=ref['reference_version'],
                    full_reference_available=ref['full_reference_available'],path_id=order['path_id'],path_kind=order['kind'],
                    request_id=order.get('prefix_request_ids',[order['request_id']]*len(order['workers']))[k-1],
                    replay_id=order.get('replay_id',''),side=order.get('side',''),
                    selection_metric=order.get('selection_metric','none'),policy=order.get('policy','random'),
                    focus_support=order.get('policy_has_focus_support',True),
                    member_workers='|'.join(sorted(order['workers'][:k])),member_records=key,
                    member_object_ids='|'.join(sorted(r['object_id'] for r in selected)),subset=key,added_worker=order['workers'][k-1],
                    subset_origin=origins.get(key,'new_actual_subset_replay'),same_target=same_target,quality_allowed=quality_allowed,
                    main_comparison_allowed=main,source_time_available=time_ok,
                    source_active_seconds=sum(float(v) for v in time_values) if time_ok else None,
                    original_valid_polygons=len(valid),original_pool_n=len(records),
                    **summary,**original_disagreement([indices[r['id']] for r in selected],dist,union),**score,
                    B8L2=score['diagnostic_B8L2'] if quality_allowed else None,D10=score['diagnostic_D10'] if quality_allowed else None)
                observations.append(row);by_path[order['path_id']].append((key,state))
                if previous:
                    changes.append(dict(pool_id=im['pool_id'],path_id=order['path_id'],path_kind=order['kind'],k_from=k-1,k_to=k,
                        added_worker=order['workers'][k-1],nodes_from=len(previous['node_consensus']['nodes']),nodes_to=summary['nodes'],
                        **transition(previous,state),**{a:b for a,b in compare_outputs(previous,state).items() if a.startswith('floor_')}))
                previous=state
        random_paths=[o for o in orders if o['kind']=='random']
        for first,second in itertools.combinations(random_paths,2):
            for k,((ka,a),(kb,b)) in enumerate(zip(by_path[first['path_id']],by_path[second['path_id']]),1):
                swaps.append(dict(pool_id=im['pool_id'],k=k,path_a=first['path_id'],path_b=second['path_id'],same_subset=ka==kb,
                    shared_workers=len(set(first['workers'][:k])&set(second['workers'][:k])),**compare_outputs(a,b)))
    target.mkdir(parents=True,exist_ok=True)
    for name,rows in [('observations',observations),('transitions',changes),('same_k',swaps)]:
        pd.DataFrame(rows).to_csv(target/(name+'.csv'),index=False,encoding='utf-8-sig')
    with gzip.open(target/'states.json.gz','wt',encoding='utf-8') as f:
        json.dump(dict(pool_id=im['pool_id'],orders=orders,states=[dict(subset=k,automatic=cache[k],origin=origins.get(k,'new_actual_subset_replay')) for k in sorted(used)]),f,ensure_ascii=False,allow_nan=False)
    save(target/'original_pair_disagreement.json',dict(record_ids=[r['id'] for r in records],union_h2=union,
         valid_polygons=len(valid),possible_polygons=len(records),pair_symdiff_h2=[[float(v) if np.isfinite(v) else None for v in row] for row in dist]))
    save(target/'score_cache.json',dict(context=measurement_context(im),measurements={k:scores[k] for k in sorted(used)}))
    result=dict(pool_id=im['pool_id'],image=im['image'],condition=im['condition'],status='completed',
        path_states=len(observations),unique_subsets=len(used),
        reused_subsets=sum(origins.get(k,'new_actual_subset_replay')!='new_actual_subset_replay' for k in used),
        new_subsets=sum(origins.get(k,'new_actual_subset_replay')=='new_actual_subset_replay' for k in used),
        computed_this_run=len(used-initial),
        pair_matches_cached=len(pair_cache),elapsed_seconds=time.monotonic()-started)
    save(target/'DONE.json',result);return result


def prepare_worker_requests():
    request_path=ROOT/'research/workers/worker_v1_composition_20261017/TEAM_REQUESTS.json'
    if not request_path.exists():
        save(OUT/'worker_request_status.json',dict(status='not_arrived',source=str(request_path.relative_to(ROOT))));return []
    request=read(request_path);assert request['data_release']=='v1' and not request['selection_reads_target_scores']
    snapshot=read(OUT/'input_snapshot.json');lookup={(im['image_id'],im['condition']):im for im in snapshot['images']}
    teams={r['request_id']:r for r in request['teams']};accepted=[];rejected=[]
    for path in request['paths']:
        im=lookup.get((path['image_id'],'manual'))
        if im is None or (OUT/'failures'/f"{im['pool_id']}.json").exists():
            rejected.append(dict(path_id=path['path_id'],image=path['image_code'],reason='pool_input_failure_or_not_admitted'));continue
        members={r['worker_id']:r for r in im['records']}
        if set(path['source_pool_worker_ids'])!=set(members):
            rejected.append(dict(path_id=path['path_id'],image=path['image_code'],reason='request_source_pool_differs'));continue
        for k,rid in enumerate(path['prefix_request_ids'],1):
            team=teams[rid]
            assert set(team['worker_ids'])==set(path['ordered_worker_ids'][:k])
            assert set(team['object_ids'])=={members[w]['object_id'] for w in team['worker_ids']}
            assert len(team['evaluation_references'])==1 and team['evaluation_references'][0]['reference_id']==im['reference']['target_id']
        accepted.append(dict(pool_id=im['pool_id'],path_id='worker_'+path['path_id'],kind='worker_'+path['policy'],
            workers=path['ordered_worker_ids'],request_id=path['path_id'],prefix_request_ids=path['prefix_request_ids'],
            selection_metric=path['selection_metric'],policy=path['policy'],policy_has_focus_support=path['policy_has_focus_support']))
    directory=OUT/'request_inputs';directory.mkdir(exist_ok=True)
    shutil.copyfile(request_path,directory/'TEAM_REQUESTS.json')
    profiles=request_path.parent/'fold_person_profiles.csv'
    if profiles.exists():shutil.copyfile(profiles,directory/'fold_person_profiles.csv')
    save(OUT/'worker_orders.json',accepted)
    save(OUT/'worker_request_status.json',dict(status='validated_for_execution',source_schema=request['schema'],
        requested_paths=len(request['paths']),accepted_paths=len(accepted),rejected_paths=rejected,
        requested_teams=len(teams),accepted_images=len({p['pool_id'] for p in accepted})))
    for name in ['trajectory_scores.csv','by_pool_k.csv','same_k_stability.csv','STATUS.json','completion.csv']:
        dst=OUT/'random_baseline'/name;dst.parent.mkdir(exist_ok=True)
        if (OUT/name).exists() and not dst.exists():shutil.copyfile(OUT/name,dst)
    wanted={p['pool_id'] for p in accepted};images=[]
    for im in snapshot['images']:
        if im['pool_id'] in wanted:
            im['requested_orders']=[{k:v for k,v in p.items() if k!='pool_id'} for p in accepted if p['pool_id']==im['pool_id']]
            images.append(im)
    return images


def prepare_room_requests():
    path=ROOT/'research/same_room/same_room_v1_process_20261017/PAIR_PROCESS_REQUESTS.json'
    if not path.exists():
        save(OUT/'same_room_request_status.json',dict(status='not_arrived'));return []
    request=read(path);assert request['data_release']=='v1'
    snapshot=read(OUT/'input_snapshot.json');lookup={(im['image_id'],im['condition']):im for im in snapshot['images']}
    images={};accepted=[];rejected=[]
    for pair in request['pairs']:
        if pair['status']!='ready':
            rejected.append(dict(request_id=pair['request_id'],reason='request_not_ready'));continue
        views=[lookup.get((v['image_id'],v['condition'])) for v in pair['views'].values()]
        if any(im is None or (OUT/'failures'/f"{im['pool_id']}.json").exists() for im in views):
            rejected.append(dict(request_id=pair['request_id'],reason='pool_not_available'));continue
        for side,view in pair['views'].items():
            base=lookup[(view['image_id'],view['condition'])]
            if base['pool_id'] not in images:
                im=dict(base);prior=json.load(gzip.open(OUT/'pools'/im['pool_id']/'states.json.gz','rt',encoding='utf-8'))
                im['requested_orders']=[o for o in prior['orders'] if o['kind']!='random' and o['kind']!='same_room']
                images[im['pool_id']]=im
            im=images[base['pool_id']];members={r['worker_id']:r for r in im['records']}
            assert view['reference']['target_id']==im['reference']['target_id']
            assert {r['worker_id'] for r in view['records']}==set(pair['common_workers'])
            for r in view['records']:
                own=members[r['worker_id']]
                assert r['object_id']==own['object_id'] and r['fusion_record']['points']==own['points']
            for replay in pair['replays']:
                assert set(replay['worker_order'])==set(pair['common_workers'])
                im['requested_orders'].append(dict(path_id='room_'+pair['request_id']+'_'+side+'_'+replay['replay_id'],
                    kind='same_room',workers=replay['worker_order'],request_id=pair['request_id'],
                    replay_id=replay['replay_id'],side=side,selection_metric='none',policy='same_room_common_people',policy_has_focus_support=True))
        accepted.append(pair['request_id'])
    shutil.copyfile(path,OUT/'request_inputs/PAIR_PROCESS_REQUESTS.json')
    save(OUT/'same_room_request_status.json',dict(status='validated_for_execution',accepted_pairs=accepted,rejected_pairs=rejected))
    return list(images.values())


def aggregate():
    snap=read(OUT/'input_snapshot.json');finished=[];frames=[];trans=[];swaps=[]
    for im in snap['images']:
        p=OUT/'pools'/im['pool_id']
        if not (p/'DONE.json').exists():continue
        finished.append(read(p/'DONE.json'));frames.append(pd.read_csv(p/'observations.csv'))
        trans.append(pd.read_csv(p/'transitions.csv'));swaps.append(pd.read_csv(p/'same_k.csv'))
    if not frames:return
    f=pd.concat(frames,ignore_index=True);t=pd.concat(trans,ignore_index=True);v=pd.concat(swaps,ignore_index=True)
    for field,default in [('selection_metric','none'),('policy','random'),('focus_support',True)]:
        if field not in f:f[field]=default
        else:f[field]=f[field].where(f[field].notna(),default)
    for name,frame in [('trajectory_scores',f),('transitions',t),('same_k_stability',v)]:frame.to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
    f.drop_duplicates(['pool_id','subset']).to_csv(OUT/'unique_subsets.csv',index=False,encoding='utf-8-sig')
    endpoints=f.sort_values('k').groupby(['pool_id','path_id'],as_index=False).tail(1)
    endpoints.to_csv(OUT/'path_endpoints.csv',index=False,encoding='utf-8-sig')
    summary=[]
    for (pool,k,kind,selection_metric),g in f.groupby(['pool_id','k','path_kind','selection_metric']):
        sv=v[(v.pool_id==pool)&(v.k==k)]
        summary.append(dict(pool_id=pool,image=g.image.iloc[0],condition=g.condition.iloc[0],layer=g.layer.iloc[0],k=k,path_kind=kind,selection_metric=selection_metric,
            path_states=len(g),unique_subsets=g.subset.nunique(),below_four=int(g.below_four.sum()),
            complete_geometry=int(g.complete_evaluable.sum()),connection=int(g.connection_available.sum()),
            full_numeric=int(g.diagnostic_B8L2.notna().sum()),quality_numeric=int(g.B8L2.notna().sum()),
            B8L2_mean=g.B8L2.mean(),D10_mean=g.D10.mean(),R_mean=g.R_union_normalized.mean(),
            same_k_pairs=len(sv) if kind=='random' else 0,
            same_k_valid_pairs=int(sv.floor_jaccard_difference.notna().sum()) if kind=='random' else 0,
            same_k_floor_difference=sv.floor_jaccard_difference.mean() if kind=='random' else None))
    pd.DataFrame(summary).to_csv(OUT/'by_pool_k.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(finished).to_csv(OUT/'completion.csv',index=False,encoding='utf-8-sig')
    failures=[read(p) for p in (OUT/'failures').glob('*.json')] if (OUT/'failures').exists() else []
    save(OUT/'STATUS.json',dict(data_release='v1',planned_pools=len(snap['images']),completed_pools=len(finished),
        completed_images=f.image.nunique(),completed_by_condition=f.groupby('condition').image.nunique().to_dict(),
        failed_pools=len(failures),failures=failures,path_states=len(f),unique_subsets=len(f.drop_duplicates(['pool_id','subset'])),
        new_subsets=sum(r['new_subsets'] for r in finished),reused_subsets=sum(r['reused_subsets'] for r in finished),
        quality_states=int(f.B8L2.notna().sum()),numeric_states=int(f.diagnostic_B8L2.notna().sum()),
        source_manifest=snap['input_manifest'],classification_selection='pending requests handled separately'))
    print(read(OUT/'STATUS.json'),flush=True)


def regate_holdouts():
    """Correct CSV boolean interpretation without touching saved geometry or scores."""
    snapshot=read(OUT/'input_snapshot.json')
    history=OUT/'history/pre_holdout_flag_correction_input.json'
    if not history.exists():save(history,snapshot)
    table=pd.read_csv(QUALITY/'shared_records.csv',keep_default_na=False).set_index('object_id')
    legacy={r['object_id'] for r in read(ROOT/'research/fusion/wall_consensus_b8l2_20261016/member_registry.json') if r['original_holdout']}
    held=set();changes=[]
    for im in snapshot['images']:
        for r in im['records']:
            correct=explicit_true(table.loc[r['object_id'],'original_holdout']) or r['object_id'] in legacy
            if correct!=r['original_holdout']:changes.append(dict(record_id=r['id'],object_id=r['object_id'],previous=r['original_holdout'],corrected=correct))
            r['original_holdout']=correct
            if correct:held.add(r['id'])
    snapshot['analysis_revision']='v1_holdout_flag_parse_corrected_20261017'
    save(OUT/'input_snapshot.json',snapshot)
    def apply(frame):
        frame['main_comparison_allowed']=[bool(row.quality_allowed and row.layer in ('ordinary','doorway_conditional')
             and not held.intersection(row.member_records.split('|'))) for row in frame.itertuples()]
        return frame
    for path in (OUT/'pools').glob('*/observations.csv'):
        apply(pd.read_csv(path,low_memory=False)).to_csv(path,index=False,encoding='utf-8-sig')
    path=OUT/'random_baseline/trajectory_scores.csv'
    if path.exists():apply(pd.read_csv(path,low_memory=False)).to_csv(path,index=False,encoding='utf-8-sig')
    save(OUT/'holdout_flag_correction.json',dict(reason='CSV False is text, not truthy holdout',
        records_corrected=len(changes),actual_legacy_holdout_records=len(held),details=changes,
        geometry_changed=False,score_values_changed=False,data_release='v1'))
    aggregate()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','run','requests','room','aggregate','regate']);parser.add_argument('--jobs',type=int,default=4)
    args=parser.parse_args();OUT.mkdir(exist_ok=True)
    if args.stage=='prepare':prepare();return
    if args.stage=='aggregate':aggregate();return
    if args.stage=='regate':regate_holdouts();return
    images=prepare_worker_requests() if args.stage=='requests' else prepare_room_requests() if args.stage=='room' else read(OUT/'input_snapshot.json')['images']
    todo=images if args.stage in ('requests','room') else [im for im in images if not (OUT/'pools'/im['pool_id']/'DONE.json').exists() and not (OUT/'failures'/f"{im['pool_id']}.json").exists()]
    with ProcessPoolExecutor(max_workers=args.jobs) as executor:
        futures={executor.submit(run_image,im):im['pool_id'] for im in todo}
        for future in as_completed(futures):
            try:result=future.result()
            except Exception as e:
                save(OUT/'failures'/f"{futures[future]}.json",dict(pool_id=futures[future],status='execution_error',reason=repr(e)));result=dict(pool_id=futures[future],status='execution_error',reason=repr(e))
            print(result,flush=True)
    aggregate()


if __name__=='__main__':main()
