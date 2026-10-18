"""验证并比较融合线程实际发布的同房前缀；所有几何距离只在同相机内部。"""
import gzip
import itertools
import json

import numpy as np
import pandas as pd

from .same_room_v1_process_20261017 import ROOT,OUT,VERSION,FUSION_OUT,number_or_none
from .same_room_quality_curves_20261015 import save
from .wall_consensus_population_20261014 import footprint, transition

KEYS=['request_id','replay_id','side','k']


def align_actual(plans,actual):
    joined=plans.merge(actual,on=KEYS,how='outer',validate='one_to_one',indicator=True,suffixes=('_planned',''))
    if joined._merge.eq('right_only').any():raise ValueError('observed prefix outside requested plan')
    joined['execution_status']=np.where(joined._merge.eq('both'),'observed','not_run')
    return joined.drop(columns='_merge')


def within_view_difference(image_a,a,image_b,b):
    if image_a!=image_b:raise ValueError('cross-camera BEV comparison is forbidden')
    pa,pb=[footprint(s['candidate']['footprint']) for s in [a,b]]
    return dict(floor_1_minus_iou=None if pa is None or pb is None else 1-pa.intersection(pb).area/pa.union(pb).area,
        floor_symdiff_h2=None if pa is None or pb is None else pa.symmetric_difference(pb).area,
        node_count_difference=abs(len(a['node_consensus']['nodes'])-len(b['node_consensus']['nodes'])))


def main():
    requests=json.loads((OUT/'PAIR_PROCESS_REQUESTS.json').read_text(encoding='utf-8'))
    provider=ROOT/FUSION_OUT
    manifest=json.loads((provider/'MANIFEST.json').read_text(encoding='utf-8'))
    current=json.loads((provider/'CURRENT.json').read_text(encoding='utf-8'))
    assert current['analysis_revision']==manifest['analysis_revision'] and current['manifest']=='MANIFEST.json'
    snapshot=json.loads((provider/'input_snapshot.json').read_text(encoding='utf-8'))
    assert manifest['data_release']==requests['data_release']=='v1'
    assert snapshot['shared_contract']['version']==requests['common_score_version']
    assert snapshot['shared_contract']['parameters']==requests['metric_parameters']
    input_pools={p['pool_id']:p for p in snapshot['images']}
    for pair in requests['pairs']:
        for view in pair['views'].values():
            saved=input_pools[view['image']+'__manual']
            assert saved['image_id']==view['image_id']
            records={r['id']:r for r in saved['records']}
            for member in view['records']:
                assert all(records[member['record_id']].get(k)==v for k,v in member['fusion_record'].items())
            assert all(saved['reference'].get(k)==v for k,v in view['reference'].items() if k!='evaluation_only')
    plans=pd.read_csv(OUT/'planned_prefixes.csv')
    lookup={r['request_id']:r for r in requests['pairs']}
    orders={(r['request_id'],p['replay_id']):p['worker_order'] for r in requests['pairs'] for p in r['replays']}
    actual=pd.read_csv(provider/manifest['files']['trajectory'],low_memory=False)
    actual=actual[actual.path_kind.eq('same_room')&actual.request_id.isin(lookup)].copy()
    assert actual.B8L2.notna().equals(actual.D10.notna())
    states={};paths={}
    for pair in requests['pairs']:
        for side,view in pair['views'].items():
            pool=view['image']+'__manual';folder=provider/'pools'/pool
            if not (folder/'DONE.json').exists():
                actual=actual[actual.pool_id.ne(pool)]
                continue
            with gzip.open(folder/'states.json.gz','rt',encoding='utf-8') as f:payload=json.load(f)
            wanted=set(actual.loc[actual.pool_id.eq(pool),'subset'])
            states[pool]={s['subset']:s['automatic'] for s in payload['states'] if s['subset'] in wanted}
            paths[pool]=(folder/'states.json.gz').relative_to(ROOT).as_posix()
            saved={o['path_id']:o for o in payload['orders']}
            for replay in pair['replays']:
                key='room_'+pair['request_id']+'_'+side+'_'+replay['replay_id']
                assert saved[key]['workers']==replay['worker_order']
    for row in actual.itertuples():
        pair=lookup[row.request_id];view=pair['views'][row.side];order=orders[row.request_id,row.replay_id]
        prefix=order[:row.k];members={m['worker_id']:m for m in view['records']}
        assert row.pool_id==view['image']+'__manual' and row.image==view['image'] and row.condition==view['condition']
        assert row.reference_id==view['reference']['target_id'] and row.reference_version==view['reference']['reference_version']
        assert set(row.member_workers.split('|'))==set(prefix) and row.added_worker==prefix[-1]
        assert set(row.member_object_ids.split('|'))=={members[w]['object_id'] for w in prefix}
        ids={members[w]['record_id'] for w in prefix}
        assert set(row.member_records.split('|'))==ids
        state=states[row.pool_id][row.subset]
        assert state['n']==row.k
        assert all(m['id'] in ids for g in state['identity_groups'] for m in g['members'])
    actual['geometry_source']=actual.pool_id.map(paths)
    actual['pair_primary_design']=actual.request_id.map(lambda rid:lookup[rid]['reference_quality_primary_eligible'])
    actual['comparison_quality_allowed']=actual.pair_primary_design & actual.main_comparison_allowed
    for metric in ['B8L2','D10']:
        actual['comparison_'+metric]=actual[metric].where(actual.comparison_quality_allowed)
    joined=align_actual(plans,actual)
    observed=joined[joined.execution_status.eq('observed')].copy()
    assert np.allclose(observed.cumulative_source_seconds,observed.source_active_seconds,equal_nan=True,atol=1e-8,rtol=0)
    save(OUT,'process_trace_validated.csv',joined)
    stability=[];adjacent=[]
    for keys,g in observed.groupby(['request_id','side','k']):
        for a,b in itertools.combinations(g.itertuples(),2):
            stability.append(dict(request_id=keys[0],side=keys[1],k=keys[2],replay_a=a.replay_id,replay_b=b.replay_id,
                same_subset=a.subset==b.subset,**within_view_difference(a.image,states[a.pool_id][a.subset],b.image,states[b.pool_id][b.subset])))
    for keys,g in observed.groupby(['request_id','replay_id','side']):
        rows=list(g.sort_values('k').itertuples())
        for a,b in zip(rows,rows[1:]):
            if b.k!=a.k+1:continue
            old,new=states[a.pool_id][a.subset],states[b.pool_id][b.subset]
            adjacent.append(dict(request_id=keys[0],replay_id=keys[1],side=keys[2],k_from=a.k,k_to=b.k,
                **within_view_difference(a.image,old,b.image,new),**transition(old,new)))
    stability=pd.DataFrame(stability);save(OUT,'process_same_k_stability.csv',stability)
    save(OUT,'process_adjacent_changes.csv',pd.DataFrame(adjacent))
    side_summary=[]
    for keys,g in joined.groupby(['request_id','side','k']):
        done=g[g.execution_status.eq('observed')]
        side_summary.append(dict(request_id=keys[0],side=keys[1],k=keys[2],planned=len(g),observed=len(done),not_received=len(g)-len(done),
            complete_geometry=int(done.complete_evaluable.sum()),floor_available=int(done.floor_evaluable.sum()),
            full_numeric=int(done.diagnostic_B8L2.notna().sum()),primary_quality=int(done.comparison_B8L2.notna().sum()),
            primary_B8L2_mean=number_or_none(done.comparison_B8L2.mean()),primary_D10_mean=number_or_none(done.comparison_D10.mean())))
    save(OUT,'process_side_completeness.csv',pd.DataFrame(side_summary))
    pk=['request_id','replay_id','k']
    paired=joined[joined.side.eq('a')].merge(joined[joined.side.eq('b')],on=pk,suffixes=('_a','_b'),validate='one_to_one')
    for side in ['a','b']:
        paired['complete_'+side]=paired['complete_evaluable_'+side].fillna(False)
    paired['both_complete']=paired.complete_a & paired.complete_b
    paired['both_quality']=paired[['comparison_B8L2_a','comparison_B8L2_b','comparison_D10_a','comparison_D10_b']].notna().all(axis=1)
    for metric in ['B8L2','D10']:
        paired[metric+'_b_minus_a']=paired['comparison_'+metric+'_b']-paired['comparison_'+metric+'_a']
        for side in ['a','b']:
            paired=paired.sort_values(pk)
            paired['adjacent_'+metric+'_'+side]=paired.groupby(['request_id','replay_id'])['comparison_'+metric+'_'+side].diff()
    save(OUT,'process_paired_prefixes.csv',paired)
    curves=[]
    for keys,g in paired.groupby(['request_id','k']):
        valid=g[g.both_quality]
        curves.append(dict(request_id=keys[0],k=keys[1],planned_replays=len(g),
            both_received=int((g.execution_status_a.eq('observed')&g.execution_status_b.eq('observed')).sum()),
            both_complete=int(g.both_complete.sum()),both_primary_quality=len(valid),
            B8L2_a=number_or_none(valid.comparison_B8L2_a.mean()),B8L2_b=number_or_none(valid.comparison_B8L2_b.mean()),
            D10_a=number_or_none(valid.comparison_D10_a.mean()),D10_b=number_or_none(valid.comparison_D10_b.mean()),
            primary_mean_absolute_B8L2_gap=number_or_none(valid.B8L2_b_minus_a.abs().mean()),
            primary_mean_absolute_D10_gap=number_or_none(valid.D10_b_minus_a.abs().mean())))
    save(OUT,'process_paired_curves.csv',pd.DataFrame(curves))
    vs=stability.groupby(['request_id','side','k'],as_index=False).agg(
        comparisons=('same_subset','size'),same_subset_comparisons=('same_subset','sum'),
        valid_floor_comparisons=('floor_1_minus_iou','count'),mean_floor_difference=('floor_1_minus_iou','mean'),
        max_floor_difference=('floor_1_minus_iou','max'))
    save(OUT,'process_same_k_summary.csv',vs)
    endpoints=[]
    for request_id,pair in lookup.items():
        n=pair['n_common_process'];end=paired[paired.request_id.eq(request_id)&paired.k.eq(n)]
        row=dict(request_id=request_id,building=pair['building'],user_group_ids=pair['user_group_ids'],N=n,
            reference_primary_design=pair['reference_quality_primary_eligible'],planned_replays=len(pair['replays']),
            both_received=int((end.execution_status_a.eq('observed')&end.execution_status_b.eq('observed')).sum()),
            both_complete=int(end.both_complete.sum()),both_primary_quality=int(end.both_quality.sum()))
        for side in ['a','b']:
            part=end[end['execution_status_'+side].eq('observed')]
            row['unique_full_sets_'+side]=int(part['subset_'+side].nunique())
            row['full_B8L2_'+side]=number_or_none(part['comparison_B8L2_'+side].mean())
            row['full_D10_'+side]=number_or_none(part['comparison_D10_'+side].mean())
        endpoints.append(row)
    save(OUT,'common_pool_full_endpoints.csv',pd.DataFrame(endpoints))
    observed_complete=len(observed)==len(plans)
    result=dict(data_release='v1',analysis_revision=VERSION,producer_version=manifest['version'],
        producer_analysis_revision=manifest['analysis_revision'],producer_current=FUSION_OUT+'/CURRENT.json',
        planned_side_prefixes=len(plans),validated_side_prefixes=len(observed),not_received=len(plans)-len(observed),
        pairs=len(lookup),buildings=len({r['building'] for r in lookup.values()}),
        paired_prefixes=len(paired),both_complete=int(paired.both_complete.sum()),both_primary_quality=int(paired.both_quality.sum()),
        same_k_comparisons=len(stability),same_k_valid_floor=int(stability.floor_1_minus_iou.notna().sum()),
        adjacent_comparisons=len(adjacent),all_requested_traces_received=observed_complete,
        complete_side_prefixes=int(observed.complete_evaluable.sum()),
        sorting_deferred_side_prefixes=int(observed.order_status.eq('two_person_sorting_deferred').sum()),
        manual_order_pending_side_prefixes=int(observed.order_status.eq('needs_manual_order').sum()),
        known_full_source_time_prefixes=int(observed.cumulative_source_seconds.notna().sum()),
        known_full_target_time_prefixes=int(observed.cumulative_target_seconds.notna().sum()),
        geometry_owner=FUSION_OUT,reference_primary_pairs=sum(r['reference_quality_primary_eligible'] for r in lookup.values()),
        no_cross_camera_BEV=True,no_interpolation=True,new_fusion_executed_here=False,
        mixed_scope_mask='B6 missing full reference and G202 mixed admitted targets remain diagnostic across whole pair, including prefixes producer marked eligible')
    save(OUT,'PROCESS_RESULTS.json',result)
    summary=json.loads((OUT/'SUMMARY.json').read_text(encoding='utf-8'))
    summary.pop('complete_paired_trajectory_conclusions',None)
    summary.update(process_comparison_status='completed_real_paired_process' if observed_complete else 'partial_real_paired_process',
        validated_side_prefixes=len(observed),all_planned_prefixes_received=observed_complete,
        every_prefix_has_both_primary_quality=bool(paired.both_quality.all()))
    save(OUT,'SUMMARY.json',summary)
    contract=json.loads((OUT/'FIELD_CONTRACT.json').read_text(encoding='utf-8'))
    contract.update(tables={p.name:list(pd.read_csv(p,nrows=0).columns) for p in OUT.glob('*.csv')},
        real_processes='provider saved states verified against exact canonical prefixes/aliases/references; no full-pool future members in prefix identities',
        stability='within same image only; same-k pairs and adjacent k computed from saved automatic states, no new fusion',
        quality_curve='both metrics and both views use identical successful replay intersection; complete rate and missing counts remain separate',
        whole_pair_mask='two diagnostic designs never promoted using favorable prefix qualification; provider raw scores preserved separately',
        full_end='all common-pool members, not whole original image pool; one unique set per side, zero replay variation is mechanical')
    save(OUT,'FIELD_CONTRACT.json',contract)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
