"""有限新案例机制与无GT的相容最大组候选；冻结共享融合入口不改。"""
from collections import Counter
import copy
from itertools import combinations
from pathlib import Path
import argparse
import sys

import numpy as np
import pandas as pd

from .fusion_change_mechanisms_20261020 import (
    ROOT, OUT as PREVIOUS, engine, normalized_state, records_from_evidence,
    partition_changed, observations, trace_groups, read, save, csv,
)
from .fixed_identity_location_20261007 import median_pair
from .geometry_cluster_v2 import _maximum_cliques
from .ring_correspondence_20261007 import assemble_fusion
from .paired_split_research.study import angular

OUT=ROOT/'research/fusion/fusion_mechanism_followup_20261021'
EXTERNAL=Path('C:/Users/ASUS/Downloads/HOHONET_personnel_research_20261020/HOHONET_personnel_research_20261020')


def initialization_flag(record):
    """只识别已有错误未改证据；自报与精确绑定不互相替代。"""
    if record['condition']!='semi':return None
    s=record['semi_evidence']
    known=s['known_error_unchanged'] is True
    reported=s['reported_known_error_unchanged'] is True
    if not (known or reported):return None
    if known:
        assert s['exact_initialization_bound']
        initial=np.asarray(s['initialization_points']);final=np.asarray(s['raw_final_points'])
        assert initial.shape==final.shape and np.allclose(initial,final,rtol=0,atol=1e-9)
    return dict(object_id=record['object_id'],worker=record['worker_id'],image=record['image_code'],
        evidence='confirmed_unchanged' if known else 'reported_only',
        error_type=s['correction_evidence']['initialization_error_type'] if known else 'unbound_report',
        edited=s['edited'],current_final_matches_historical=s.get('historical_final_equals_current'),
        pool_analysis_eligible=record['pool_analysis_eligible'],quality_usable=record['quality_usable'],
        is_oos=record['is_oos'],is_doorway=record['is_doorway'])


def initialization_review(evidence):
    """全Semi逐份证据轻量检索，再定位本轮保存团队；不重跑历史部署。"""
    objects={r['object_id']:r for r in evidence}
    flagged=[v for r in evidence if (v:=initialization_flag(r)) is not None]
    flags={r['object_id']:r for r in flagged}
    csv(OUT/'INITIALIZATION_FLAGS.csv',pd.DataFrame(flagged))
    images=[]
    for image in sorted({r['image'] for r in flagged}):
        rows=[r for r in flagged if r['image']==image]
        images.append(dict(image=image,confirmed_historical=sum(r['evidence']=='confirmed_unchanged' for r in rows),
             confirmed_current_pool=sum(r['evidence']=='confirmed_unchanged' and r['pool_analysis_eligible']
                                        and r['current_final_matches_historical'] is True for r in rows),
             reported_only=sum(r['evidence']=='reported_only' for r in rows),
             confirmed_error_types=sorted({r['error_type'] for r in rows if r['evidence']=='confirmed_unchanged'})))
    csv(OUT/'INITIALIZATION_IMAGES.csv',pd.DataFrame(images))
    teams={}
    for path in (OUT/'inputs/pro_cases').glob('*.json'):
        c=read(path)
        if c['meta']['condition']=='semi':
            for p in c['panels']:teams[p['team_key']]=p['object_ids']
    path=pd.read_csv(OUT/'inputs/path_scores.csv')
    for _,r in path[path.condition.eq('semi')].iterrows():teams[r.team_key]=r.member_object_ids.split('|')
    exposures=[]
    for key,ids in teams.items():
        found=[flags[oid] for oid in ids if oid in flags]
        exposures.append(dict(team_key=key,image=objects[ids[0]]['image_code'],n=len(ids),
             confirmed_unchanged_workers=sorted(r['worker'] for r in found if r['evidence']=='confirmed_unchanged'),
             reported_only_workers=sorted(r['worker'] for r in found if r['evidence']=='reported_only'),
             edited_or_other_unknown_workers=sorted(objects[oid]['worker_id'] for oid in ids if oid not in flags)))
    csv(OUT/'INITIALIZATION_TEAM_EXPOSURE.csv',pd.DataFrame(exposures))
    semi=[r for r in evidence if r['condition']=='semi']
    known=[r for r in flagged if r['evidence']=='confirmed_unchanged']
    save(OUT/'INITIALIZATION_COVERAGE.json',dict(scanned_semi_records=len(semi),
         exact_initialization_bound=sum(r['semi_evidence']['exact_initialization_bound'] for r in semi),
         missing_exact_initialization=sum(not r['semi_evidence']['exact_initialization_bound'] for r in semi),
         confirmed_historical_unchanged=len(known),confirmed_images=len({r['image'] for r in known}),
         confirmed_current_pool=sum(r['pool_analysis_eligible'] and r['current_final_matches_historical'] is True for r in known),
         confirmed_duplicate_current_pool=sum(r['pool_analysis_eligible'] and r['current_final_matches_historical'] is True
                                              and r['error_type']=='corner_duplicate' for r in known),
         reported_only=len(flagged)-len(known),reported_images=len({r['image'] for r in flagged if r['evidence']=='reported_only'}),
         saved_semi_teams=len(teams),historical_runtime_audit_replayed=False,eligibility_changed=False))


def support_first_partition(n,edges,cost):
    """先取最多人员的完全相容组，再以原角距离、规范观察ID破同票。"""
    remaining=set(range(n));groups=[];search_nodes=0
    while remaining:
        cliques,truncated,visits=_maximum_cliques(tuple(sorted(remaining)),edges,maximum_search_nodes=10000)
        search_nodes+=visits
        if truncated:raise RuntimeError('clique_search_limit_requires_review')
        chosen=min(cliques,key=lambda c:(cost(c),c))
        groups.append(chosen);remaining.difference_update(chosen)
    return groups,search_nodes


def clique_candidate(baseline):
    members=sorted((m for g in baseline['identity_groups'] for m in g['members']),
                   key=lambda m:(m['worker'],m['id'],m['pair_index']))
    lookup={(m['id'],m['pair_index']):i for i,m in enumerate(members)}
    edges={tuple(sorted((lookup[p['a'],a],lookup[p['b'],b]))) for p in baseline['pairwise'] for a,b in p['matches']}
    p=np.asarray([m['points'] for m in members])
    distance=(angular(p[:,0]-.5,p[:,0]-.5)+angular(p[:,1]-.5,p[:,1]-.5))/2
    def cost(c):return sum(distance[a,b] for a,b in combinations(c,2))
    parts,visits=support_first_partition(len(members),edges,cost)
    groups=[];mapping={}
    for i,part in enumerate(parts):
        ms=[members[j] for j in part];fid=f'clique_{i:03d}'
        assert len({m['worker'] for m in ms})==len(ms)
        assert all(tuple(sorted((a,b))) in edges for a,b in combinations(part,2))
        groups.append(dict(feature_id=fid,members=ms,support=len(ms),selected=2*len(ms)>=baseline['n'],center=median_pair(ms)))
        for m in ms:mapping[m['id'],m['pair_index']]=fid
    assignments=copy.deepcopy(baseline['assignments'])
    for r in assignments:r['feature_ids']=[mapping[r['id'],i] for i in range(len(r['feature_ids']))]
    result=dict(n=baseline['n'],minimum_support=baseline['minimum_support'],identity_groups=groups,assignments=assignments,
                method='support_first_pairwise_compatible_cliques_v1',search_nodes=visits,**assemble_fusion(groups,assignments))
    return result


def rescue_candidate(baseline):
    """锁定达票组，仅从原未达票观察中提取完全相容的多数组。"""
    locked=copy.deepcopy([g for g in baseline['identity_groups'] if g['selected']])
    members=sorted((m for g in baseline['identity_groups'] if not g['selected'] for m in g['members']),
                   key=lambda m:(m['worker'],m['id'],m['pair_index']))
    lookup={(m['id'],m['pair_index']):i for i,m in enumerate(members)}
    edges={tuple(sorted((lookup[p['a'],a],lookup[p['b'],b]))) for p in baseline['pairwise'] for a,b in p['matches']
           if (p['a'],a) in lookup and (p['b'],b) in lookup}
    if members:
        p=np.asarray([m['points'] for m in members])
        distance=(angular(p[:,0]-.5,p[:,0]-.5)+angular(p[:,1]-.5,p[:,1]-.5))/2
        parts,visits=support_first_partition(len(members),edges,lambda c:sum(distance[a,b] for a,b in combinations(c,2)))
    else:parts,visits=[],0
    groups=locked;mapping={};used=set()
    for part in parts:
        if len(part)<baseline['minimum_support']:continue
        ms=[members[i] for i in part];fid=f'rescue_{len(groups):03d}'
        assert len({m['worker'] for m in ms})==len(ms)
        assert all(tuple(sorted((a,b))) in edges for a,b in combinations(part,2))
        groups.append(dict(feature_id=fid,members=ms,support=len(ms),selected=True,center=median_pair(ms)))
        for m in ms:
            used.add((m['id'],m['pair_index']));mapping[m['id'],m['pair_index']]=fid
    for g in baseline['identity_groups']:
        if g['selected']:continue
        ms=[m for m in g['members'] if (m['id'],m['pair_index']) not in used]
        if ms:groups.append(dict(feature_id=g['feature_id'],members=ms,support=len(ms),selected=False,center=g['center'] if len(ms)==len(g['members']) else median_pair(ms)))
    assignments=copy.deepcopy(baseline['assignments'])
    for r in assignments:r['feature_ids']=[mapping.get((r['id'],i),fid) for i,fid in enumerate(r['feature_ids'])]
    assert {tuple(sorted((m['id'],m['pair_index']) for m in g['members'])) for g in groups if g['selected'] and not g['feature_id'].startswith('rescue_')}=={tuple(sorted((m['id'],m['pair_index']) for m in g['members'])) for g in baseline['identity_groups'] if g['selected']}
    return dict(n=baseline['n'],minimum_support=baseline['minimum_support'],identity_groups=groups,assignments=assignments,
                method='locked_selected_majority_clique_rescue_v1',search_nodes=visits,**assemble_fusion(groups,assignments))


def mechanism_stage(state,object_ids,focus,objects,score):
    """保留固定来源清单及其去向；未进入清单不推断为没画真实目标。"""
    focal=[g for g in state['identity_groups'] if observations(g)&focus]
    present=set().union(*(observations(g) for g in state['identity_groups']))
    sources=[objects[oid] for oid in object_ids]
    return dict(n=state['n'],threshold=state['minimum_support'],
        team_workers=sorted(r['worker_id'] for r in sources),object_ids=object_ids,
        known_focal_observations_present=sorted(present&focus),
        focal_groups=[dict(feature_id=g['feature_id'],support=g['support'],selected=g['selected'],
             center=g['center'],members=g['members'],
             known_focal_members=sorted(observations(g)&focus)) for g in focal],
        original_answers=[dict(object_id=r['object_id'],worker=r['worker_id'],points=r['points_1024x512']) for r in sources],
        node_count=len(state['node_consensus']['nodes']),output_points=state['candidate']['points'],
        connection_reason=state['candidate'].get('reason'),ring=state['ring_diagnostics'],
        reference_id=sources[0]['reference_id'],reference_version=sources[0]['reference_version'],
        score=score)


def closeout_evidence(states,cases,objects):
    stages={};transitions=[]
    def focal(case):
        p=case['panels'][1]
        return set().union(*(observations(g) for g in normalized_state(p['state'])['identity_groups']
                             if g['feature_id'] in p['focus_group_ids']))
    def add(name,key,method,focus):
        d=states[key]
        if method=='assisted':
            h=read(PREVIOUS/'LOCAL_REVIEW_CONTROL.json');state=normalized_state(h['state']);score=h['score']
        else:state=d[method];score=d.get(method+'_score',{})
        stages[name]=dict(team_key=key,method=method,image=d['request']['image'],condition=d['request']['condition'],
                         **mechanism_stage(state,d['request']['object_ids'],focus,objects,score))
    def connect(name,before,after,kind):
        a,b=stages[before],stages[after]
        transitions.append(dict(contrast=name,mechanism=kind,before=before,after=after,image=a['image'],condition=a['condition'],
            members_before=a['team_workers'],members_after=b['team_workers'],
            incoming=sorted(set(b['team_workers'])-set(a['team_workers'])),outgoing=sorted(set(a['team_workers'])-set(b['team_workers'])),
            n_before=a['n'],n_after=b['n'],threshold_before=a['threshold'],threshold_after=b['threshold'],
            known_sources_before=len(a['known_focal_observations_present']),known_sources_after=len(b['known_focal_observations_present']),
            support_before=[g['support'] for g in a['focal_groups']],support_after=[g['support'] for g in b['focal_groups']],
            selected_before=[g['selected'] for g in a['focal_groups']],selected_after=[g['selected'] for g in b['focal_groups']],
            nodes_before=a['node_count'],nodes_after=b['node_count'],B8L2_before=a['score'].get('B8L2'),B8L2_after=b['score'].get('B8L2')))
    e=cases['manual_e9z19_lowQ_complement'];j=cases['manual_jtc26_speed_complement'];u=cases['manual_Uw22_local_dilution']
    for case,prefix in [(e,'e9z'),(j,'jtc'),(u,'Uw')]:
        for i,p in enumerate(case['panels']):add(prefix+str(i),p['team_key'],'baseline',focal(case))
    add('e9z_W107','e9z19_same_source_lowQ_W107','baseline',focal(e))
    for method in ['baseline','candidate']:add('jtc_dropW128_'+method,'jtc26_4F1S_drop_W128',method,focal(j))
    connect('e9z_same_ratio','e9z1','e9z_W107','same_ratio_specific_members')
    connect('e9z_addition','e9z0','e9z1','local_vote_completion')
    connect('e9z_threshold','e9z1','e9z2','unchanged_support_higher_threshold')
    connect('jtc_swap','jtc0','jtc1','local_vote_completion')
    connect('jtc_background','jtc1','jtc_dropW128_baseline','same_ratio_correspondence_splitting')
    connect('jtc_repair','jtc_dropW128_baseline','jtc_dropW128_candidate','same_members_correspondence_control')
    connect('Uw_position','Uw0','Uw1','position_before_node_loss')
    connect('Uw_threshold','Uw1','Uw2','unchanged_support_higher_threshold')
    key=next(k for k,d in states.items() if d['request']['image']=='q9vSo1VnCiC-30' and d['baseline']['n']==17)
    human=read(PREVIOUS/'HUMAN_REVIEW.json')
    focus={(m['worker'],m['source_pair_index']) for g in human['sources'] for m in g['members']}
    for method in ['baseline','assisted','candidate']:add('q9_'+method,key,method,focus)
    connect('q9_human_control','q9_baseline','q9_assisted','same_members_human_identity_control')
    connect('q9_auto_control','q9_baseline','q9_candidate','same_members_automatic_candidate')
    key=next(k for k,d in states.items() if d['request']['condition']=='semi' and d['baseline']['n']==11)
    focus=set().union(*(observations(g) for g in states[key]['candidate']['identity_groups']
                        if g['feature_id']=='node_001' or g['feature_id'].startswith('rescue_')))
    for method in ['baseline','candidate']:add('semi_'+method,key,method,focus)
    connect('semi_duplicate','semi_baseline','semi_candidate','same_target_duplicate_output')
    save(OUT/'MECHANISM_CHAINS.json',dict(schema='fusion_mechanism_chains_v1',
        expression_status='focal source membership is observed; physical absence is not inferred from nonmembership',
        source='METHOD_STATES.json.gz; q9 assisted from previous LOCAL_REVIEW_CONTROL.json',stages=stages,transitions=transitions))
    csv(OUT/'MECHANISM_TRANSITIONS.csv',pd.DataFrame(transitions))


def run():
    OUT.mkdir(parents=True,exist_ok=True)
    evidence=read(ROOT/'research/statistics/v2_evidence_audit_20261019/records.json.gz')['records']
    objects={r['object_id']:r for r in evidence}
    fe=engine();pools={p['pool_id']:p for p in fe.load_pools()}
    cases=[]
    case_dir=OUT/'inputs/pro_cases'
    case_files=sorted(case_dir.glob('*.json')) if case_dir.exists() else sorted((EXTERNAL/'mechanisms/cases').glob('*.json'))
    for path in case_files:
        case=read(path)
        if 'panels' not in case:continue
        if path.parent!=case_dir:save(case_dir/path.name,case)
        cases.append(case)
    # 保留新包已有完整路径与票账，不重跑其团队。
    for name in ['path_scores.csv','path_node_support.csv','path_transitions.json']:
        (OUT/'inputs').mkdir(exist_ok=True)
        if not (OUT/'inputs'/name).exists():(OUT/'inputs'/name).write_bytes((EXTERNAL/'mechanisms'/name).read_bytes())
    ledger=[];node_rows=[];transition_rows=[]
    for case in cases:
        history=case['history_groups']
        assert all(objects[r['object_id']]['points_1024x512']==r['points_1024x512'] for r in case['records'])
        previous=None
        for panel in case['panels']:
            state=normalized_state(panel['state']);score=panel['score']
            focus=set(panel.get('focus_group_ids',[]))
            if not focus:focus={g['feature_id'] for g in state['identity_groups'] if g['support'] in [state['minimum_support']-1,state['minimum_support']]}
            for g in state['identity_groups']:
                if g['feature_id'] not in focus:continue
                support=Counter(history.get(m['worker'],'unknown') for m in g['members'])
                incident=[e for e in state['ring_diagnostics']['edges'] if g['feature_id'] in e['feature_ids']]
                node_rows.append(dict(case=case['case_id'],image=case['meta']['image'],condition=case['meta']['condition'],
                      team_key=panel['team_key'],n=state['n'],group=g['feature_id'],support=g['support'],threshold=state['minimum_support'],
                      selected=g['selected'],support_by_history=dict(support),workers='|'.join(sorted(m['worker'] for m in g['members'])),
                      direct_edges=[e['direct_support'] for e in incident],projected_edges=[e['projected_support'] for e in incident],
                      full_projected_ring_support=max((a['support'] for a in state['ring_diagnostics']['alternatives']),default=0)))
            ledger.append(dict(case=case['case_id'],image=case['meta']['image'],condition=case['meta']['condition'],team_key=panel['team_key'],label=panel['label'],
                   n=state['n'],threshold=state['minimum_support'],nodes=len(state['node_consensus']['nodes']),B8L2=score['B8L2'],D10=score['D10'],
                   iou_2d=score.get('iou_2d'),omission=score.get('omission'),extension=score.get('extension'),
                   member_workers=score['member_workers'],reference_id=case['reference']['target_id'] if 'target_id' in case['reference'] else case['meta']['reference_id']))
            if previous:
                oldpanel,old=previous
                retained=set(oldpanel['score']['member_workers'])&set(score['member_workers'])
                for row in trace_groups(old['identity_groups'],state['identity_groups'],retained):
                    transition_rows.append(dict(case=case['case_id'],before=oldpanel['team_key'],after=panel['team_key'],n_before=old['n'],n_after=state['n'],
                          threshold_before=old['minimum_support'],threshold_after=state['minimum_support'],retained_partition_changed=partition_changed(old['identity_groups'],state['identity_groups'],retained),**row))
            previous=panel,state
    csv(OUT/'CASE_TEAMS.csv',pd.DataFrame(ledger));csv(OUT/'FOCUS_SUPPORT.csv',pd.DataFrame(node_rows));csv(OUT/'CASE_TRANSITIONS.csv',pd.DataFrame(transition_rows))

    # 独立方法候选只运行有限的已保存团队及既有人审关系，不接入生产入口。
    previous_design=read(PREVIOUS/'DESIGN.json');previous_teams=read(PREVIOUS/'TEAMS.json.gz')
    previous_states=read(PREVIOUS/'STATES.json.gz');requests=[]
    for case in cases:
        for panel in case['panels']:
            requests.append(dict(key=panel['team_key'],image=case['meta']['image'],condition=case['meta']['condition'],
                                 object_ids=panel['object_ids'],pool_id=case['pool_id'],expected=panel['state']['candidate']['points'],role='new_package_case'))
    # 固定同一低Q/慢者，只更换它接入的具体背景；不是重新搜索人群。
    jtc=next(c for c in cases if c['case_id']=='manual_jtc26_speed_complement')
    fast=jtc['panels'][0]['object_ids'];slow=next(r['object_id'] for r in jtc['records'] if r['worker_id']=='W106')
    existing={tuple(sorted(r['object_ids'])):r['key'] for r in requests}
    for dropped in fast:
        ids=sorted((set(fast)-{dropped})|{slow})
        if tuple(ids) in existing:continue
        requests.append(dict(key='jtc26_4F1S_drop_'+objects[dropped]['worker_id'],image=jtc['meta']['image'],condition='manual',object_ids=ids,
                             pool_id=jtc['pool_id'],role='same_ratio_slow_swap',dropped_worker=objects[dropped]['worker_id']))
    requests.append(dict(key='jtc26_5F_add_W106',image=jtc['meta']['image'],condition='manual',object_ids=sorted(set(fast)|{slow}),
                         pool_id=jtc['pool_id'],role='fixed_core_addition'))
    e9z=next(c for c in cases if c['case_id']=='manual_e9z19_lowQ_complement')
    entrant=next(r['object_id'] for r in e9z['records'] if r['worker_id']=='W031')
    requests.append(dict(key='e9z19_5H5L_alternative_W031',image=e9z['meta']['image'],condition='manual',
                         object_ids=sorted(e9z['panels'][0]['object_ids']+[entrant]),pool_id=e9z['pool_id'],role='same_ratio_lowQ_entrant'))
    available={r['worker_id']:r for r in pools[e9z['pool_id']]['records']}
    excluded={objects[oid]['worker_id'] for oid in e9z['panels'][1]['object_ids']}
    selection_path=OUT/'inputs/LOWQ_SELECTION.json'
    if not selection_path.exists():
        historical_features=pd.read_csv(EXTERNAL/'tables/profiles/lobo_features.csv')
        eligible=historical_features[(historical_features.target_building=='e9zR4mvMWw7') & historical_features.condition.eq('manual')
                  & historical_features.origin.eq('new') & historical_features.panel.eq('ordinary')
                  & historical_features.Q_supported_8images_3buildings & (historical_features.Q_peer<0)
                  & historical_features.worker_id.isin(set(available)-excluded)].sort_values('worker_id')
        save(selection_path,dict(selected_worker=eligible.iloc[0].worker_id,
             source='HOHONET_personnel_research_20261020/tables/profiles/lobo_features.csv',
             eligible=eligible[['worker_id','Q_peer','Q_mean','n_quality_images','n_quality_buildings']].to_dict('records'),
             selection='first eligible canonical worker ID; same source, condition and negative supported LOBO Q; no target outcomes'))
    selection=read(selection_path)
    comparison=next(r for r in selection['eligible'] if r['worker_id']==selection['selected_worker'])
    # 只追加一个按人员ID预选、同来源且有楼外Q支持的对照，不看目标几何或分数挑结果。
    worker=comparison['worker_id']
    requests.append(dict(key='e9z19_same_source_lowQ_'+worker,image=e9z['meta']['image'],condition='manual',pool_id=e9z['pool_id'],
                         object_ids=sorted(e9z['panels'][0]['object_ids']+[available[worker]['object_id']]),role='same_source_lowQ_entrant',
                         incoming_worker=worker,historical_Q_peer=float(comparison['Q_peer']),selection=selection['selection']))
    for row in pd.read_csv(PREVIOUS/'NESTED_STEPS.csv').to_dict('records'):
        if row['image']=='q9vSo1VnCiC-30' and row['arm']=='B' and row['n_to'] in [17,18]:
            for key in [row['team_before'],row['team_after']]:
                t=previous_teams[key]
                requests.append(dict(key=key,image=t['image'],condition='manual',object_ids=t['object_ids'],pool_id=t['pool_id'],
                                     expected=previous_states[key]['candidate']['points'],role='reviewed_split'))
    # 使用同一29图面板中已出现旧观察重分的另外两个例子，不依据候选得分选例。
    event_table=pd.read_csv(PREVIOUS/'PRIMARY_EVENTS.csv')
    for image in ['UwV83HsGsw3-22','B6ByNegPMKs-47']:
        matches=event_table[(event_table.image==image)&event_table.retained_partition_changed]
        if matches.empty:continue
        selected=matches.iloc[0];event=next(e for e in previous_design['primary_events'] if e['event_id']==selected.event_id)
        for arm in ['A',selected.arm]:
            key=event[arm+'_team_key'];t=previous_teams[key]
            requests.append(dict(key=key,image=image,condition='manual',object_ids=t['object_ids'],pool_id=t['pool_id'],expected=previous_states[key]['candidate']['points'],role='other_regrouping'))

    # 旧人工关系只作固定对照；坐标仍读取当前v2，不恢复旧资格或评分。
    from .consensus_delivery_20261008 import cases as human_cases
    historical={im['image']:im for im in read(ROOT/'analysis_results/direct_fusion_20261007/gap_sweep/population/inputs.json')['images']}
    control_images={'B6ByNegPMKs-11','q9vSo1VnCiC-32','7y3sRwLe3Va-23','q9vSo1VnCiC-03','zsNo4HB9uLZ-05','yqstnuAEVhm-25'}
    controls=[]
    for case in human_cases()[0]:
        image=case['image']
        if image not in control_images or case['kind']!='partition':continue
        old={r['id']:r for r in historical[image]['records']};groups=[]
        for group in case['groups']:
            mapped=[]
            for rid,index in group:
                r=old[rid];oid=r['object_id']
                if oid not in objects:continue
                source_index=r['source_pair_indices'][index]
                indices=objects[oid]['coordinate_evidence'].get('ordered_source_pair_indices')
                if indices is not None and source_index not in indices:continue
                mapped.append([objects[oid]['worker_id'],source_index])
            groups.append(mapped)
        controls.append(dict(case=case['case'],image=image,groups=groups,original_sizes=list(map(len,case['groups'])),mapped_sizes=list(map(len,groups)),
                             kind='different_targets' if len(groups)>1 else 'same_target'))
    save(OUT/'HUMAN_CONTROLS.json',controls)
    for image in sorted(control_images):
        old=historical[image]['records'];ids=[r['object_id'] for r in old if r['object_id'] in objects and objects[r['object_id']]['points_1024x512']]
        requests.append(dict(key='current_v2_legacy_panel__'+image,image=image,condition='manual',object_ids=ids,pool_id=None,role='human_identity_control'))
    requests={r['key']:r for r in requests}
    save(OUT/'REQUESTS.json',list(requests.values()))
    results={};rows=[];checks=[]
    with fe.cached_matching(),fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (scorer,models):
        for i,r in enumerate(requests.values()):
            selected=[objects[oid] for oid in r['object_ids']]
            baseline=fe.fuse(records_from_evidence(selected),gap=fe.WORKING_GAP)['automatic']
            if 'expected' in r:assert baseline['candidate']['points']==r['expected']
            unrestricted=clique_candidate(baseline)
            candidate=rescue_candidate(baseline)
            a,b=normalized_state(fe.compact(baseline)),normalized_state(candidate)
            u=normalized_state(unrestricted)
            results[r['key']]=dict(request=r,baseline=a,candidate=b,unrestricted=u)
            row=dict(key=r['key'],image=r['image'],condition=r['condition'],role=r['role'],n=baseline['n'],threshold=baseline['minimum_support'],
                     baseline_nodes=len(a['node_consensus']['nodes']),candidate_nodes=len(b['node_consensus']['nodes']),
                     partition_changed=partition_changed(a['identity_groups'],b['identity_groups'],{x['worker_id'] for x in selected}),
                     baseline_connection=bool(a['candidate']['points']),candidate_connection=bool(b['candidate']['points']),search_nodes=candidate['search_nodes'],
                     unrestricted_nodes=len(u['node_consensus']['nodes']))
            if r['pool_id']:
                for label,state in [('baseline',a),('candidate',b),('unrestricted',u)]:
                    score=fe.compute_score(state,pools[r['pool_id']],scorer,models)
                    results[r['key']][label+'_score']=score
                    row[label+'_B8L2']=score['B8L2'];row[label+'_D10']=score['D10']
            for c in (c for c in controls if c['image']==r['image'] and r['role']=='human_identity_control'):
                for label,state in [('baseline',a),('candidate',b),('unrestricted',u)]:
                    assignment={(m['worker'],m['source_pair_index']):g['feature_id'] for g in state['identity_groups'] for m in g['members']}
                    ids=[{assignment[tuple(o)] for o in group if tuple(o) in assignment} for group in c['groups']]
                    checks.append(dict(case=c['case'],image=c['image'],method=label,kind=c['kind'],complete_mapping=c['mapped_sizes']==c['original_sizes'],
                          same_target_split=any(len(x)>1 for x in ids),different_targets_merged=any(x&y for j,x in enumerate(ids) for y in ids[j+1:])))
            rows.append(row);print(i+1,len(requests),r['image'],row['baseline_nodes'],row['candidate_nodes'],flush=True)
    save(OUT/'METHOD_STATES.json.gz',results);csv(OUT/'METHOD_COMPARISONS.csv',pd.DataFrame(rows));csv(OUT/'HUMAN_RELATION_RESULTS.csv',pd.DataFrame(checks))


def figures():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    sys.path.insert(0,str(ROOT/'research/workers/personnel_interchangeability_20261020/analysis/composition'))
    import case_visuals as visual
    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','DejaVu Sans'],'axes.unicode_minus':False})
    evidence=read(ROOT/'research/statistics/v2_evidence_audit_20261019/records.json.gz')['records']
    initialization_review(evidence)
    objects={x['object_id']:x for x in evidence}
    states=read(OUT/'METHOD_STATES.json.gz')
    cases={c['case_id']:c for c in [read(p) for p in (OUT/'inputs/pro_cases').glob('*.json')]}
    closeout_evidence(states,cases,objects)
    jtc=cases['manual_jtc26_speed_complement'];e9z=cases['manual_e9z19_lowQ_complement']

    def target(case,panel_index=1):
        panel=case['panels'][panel_index]
        return set().union(*(observations(g) for g in normalized_state(panel['state'])['identity_groups'] if g['feature_id'] in panel['focus_group_ids']))

    jtc_target=target(jtc);e9z_target=target(e9z)
    human=read(PREVIOUS/'HUMAN_REVIEW.json')
    q9_target={(m['worker'],m['source_pair_index']) for g in human['sources'] for m in g['members']}
    panels=[]

    def plot(name,selection,focus,bounds,title,reference=True):
        fig,axes=plt.subplots(3,len(selection),figsize=(5.2*len(selection),9.3),squeeze=False,
                              gridspec_kw={'height_ratios':[1,1.4,.8]})
        for j,(key,method,label) in enumerate(selection):
            data=states[key];state=data[method];req=data['request'];score=data.get(method+'_score',{})
            sources=[objects[oid] for oid in req['object_ids']]
            iid=sources[0]['image_id'];photo=np.asarray(Image.open(next(ROOT.glob('data/mp3d_layout/*/img/'+iid+'.png'))).convert('RGB'))
            ref=sources[0]['reference_evidence']['points_1024x512']
            focal=[g for g in state['identity_groups'] if observations(g)&focus]
            if not focal:focal=[g for g in state['identity_groups'] if g['feature_id'].startswith('rescue_')]
            for i in [0,1]:
                ax=axes[i,j];visual._erp_background(ax,photo)
                if i==0:
                    for source in sources:visual._erp_edges(ax,source['points_1024x512'],'#23caff',linewidth=.7,alpha=.35)
                else:
                    for g in focal:
                        for m in g['members']:
                            p=np.asarray(m['points']);ax.plot(p[:,0],p[:,1],color='#ffb32b',lw=.8,alpha=.6)
                if reference and ref:visual._erp_edges(ax,ref,'#b3ff8c',linewidth=1.1,reference=True)
                if state['candidate']['points']:visual._erp_edges(ax,state['candidate']['points'],'#ff357c',linewidth=2,markers=True)
                if i==1:
                    ax.set_xlim(bounds[:2]);ax.set_ylim(bounds[3],bounds[2])
                    for gi,g in enumerate(focal[:4]):
                        mid=np.asarray(g['center']).mean(axis=0)
                        ax.annotate(f"{g['support']}票／{'保留' if g['selected'] else '未选'}",xy=mid,xytext=(.04,.88-gi*.19),textcoords='axes fraction',fontsize=9,
                                    color='white',bbox=dict(facecolor='#1a2234',alpha=.85,edgecolor='none',pad=2),
                                    arrowprops=dict(arrowstyle='-',color='white',lw=.6))
                else:
                    q=score.get('B8L2');qs=f'{q:.2f}' if q is not None else '未评分'
                    ax.set_title(label+f"\nn={state['n']}，{len(state['node_consensus']['nodes'])}节点，B8L2={qs}",fontsize=11)
                ax.set_xticks([]);ax.set_yticks([])
            ax=axes[2,j];ax.axis('off')
            lines=[f"门槛 {state['minimum_support']}；节点支持："+'、'.join(str(g['support']) for g in focal)]
            for g in focal[:3]:
                incident=[e for e in state['ring_diagnostics']['edges'] if g['feature_id'] in e['feature_ids']]
                lines.append(f"{g['support']}票组相邻边："+'；'.join(f"{e['direct_support']}/{e['projected_support']}" for e in incident))
            ring=max((a['support'] for a in state['ring_diagnostics']['alternatives']),default=0)
            lines.append(f'完整来源投影环支持：{ring}人')
            lines.append('连接状态：'+str(state['candidate'].get('geometry_status',state['candidate']['reason'])))
            if score.get('B8L2') is None and score:lines.append('评分状态：'+str(score.get('score_status')))
            ax.text(.02,.98,'\n'.join(lines),va='top',fontsize=9,linespacing=1.7)
            panels.append(dict(figure=name,key=key,method=method,n=state['n'],threshold=state['minimum_support'],nodes=len(state['node_consensus']['nodes']),
                               focus_support=[g['support'] for g in focal],B8L2=score.get('B8L2'),source_ring_support=ring))
        fig.suptitle(title+'\n上：原答与完整输出；中：同图局部；下：节点及连接账本',fontsize=14,y=.98)
        fig.text(.03,.035,'蓝：人员原答；橙：焦点组来源；玫红：融合；浅绿：固定参考。边票格式=直接邻接／删点后的投影邻接。\n参考和得分不参与自动归属；图内每个输出使用全部声明成员。',fontsize=9)
        fig.subplots_adjust(left=.025,right=.98,top=.88,bottom=.12,wspace=.12,hspace=.1)
        fig.savefig(OUT/(name+'.png'),dpi=150);plt.close(fig)

    paired_key=next(k for k,v in states.items() if v['request']['role']=='same_source_lowQ_entrant')
    paired_worker=states[paired_key]['request']['incoming_worker']
    for case,workers,title in [(e9z,['W101',paired_worker],'e9z-19：相同背景下，具体新成员的原答不同'),
                               (jtc,['W113','W106'],'jtc-26：原被替换者与补入者的原答')]:
        p=case['panels'][1];focus=target(case)
        fig,axes=plt.subplots(2,2,figsize=(12,7.2),gridspec_kw={'height_ratios':[1,1.1]})
        for col,worker in enumerate(workers):
            source=next(r for r in objects.values() if r['image_code']==case['meta']['image']
                        and r['worker_id']==worker and r['condition']==case['meta']['condition'])
            photo=np.asarray(Image.open(next(ROOT.glob('data/mp3d_layout/*/img/'+source['image_id']+'.png'))).convert('RGB'))
            highlighted=[m for g in normalized_state(p['state'])['identity_groups'] for m in g['members']
                         if (m['worker'],m['source_pair_index']) in focus and m['worker']==worker]
            for row in range(2):
                ax=axes[row,col];visual._erp_background(ax,photo)
                visual._erp_edges(ax,source['points_1024x512'],'#23d6ff',linewidth=1.7,markers=True)
                for m in highlighted:
                    pair=np.asarray(m['points']);ax.plot(pair[:,0],pair[:,1],color='#ff8b27',lw=3)
                if row:
                    bounds=case['zoom_bounds'];ax.set_xlim(bounds[:2]);ax.set_ylim(bounds[3],bounds[2])
                    indices=source['coordinate_evidence'].get('ordered_source_pair_indices')
                    if indices is None:indices=range(len(source['points_1024x512'])//2)
                    label_n=0
                    for index,pair in zip(indices,np.asarray(source['points_1024x512']).reshape(-1,2,2)):
                        if bounds[0]<=pair[0,0]<=bounds[1]:
                            ax.annotate(f'P{index}: x={pair[0,0]:.1f}',xy=pair.mean(axis=0),xytext=(.03,.9-label_n*.16),textcoords='axes fraction',
                                        fontsize=8,color='white',bbox=dict(facecolor='#142637',alpha=.8,edgecolor='none'),
                                        arrowprops=dict(arrowstyle='-',color='white',lw=.7))
                            label_n+=1
                ax.set_xticks([]);ax.set_yticks([])
            axes[0,col].set_title(worker+'完整当前处理作答：'+str(len(source['points_1024x512'])//2)+'对点',fontsize=11)
            axes[1,col].set_title('固定焦点来源清单中'+str(len(highlighted))+'份观察；局部放大',fontsize=10)
        fig.suptitle(title,fontsize=14)
        fig.text(.03,.025,'青色=该人员全部原答连接；橙色=固定焦点清单内的点对。原答按当前处理点位及环序展示。\n未进入清单不自动证明没画真实目标；结合完整路径判断局部表达，不把算法身份组直接当物理真值。',fontsize=9)
        fig.tight_layout(rect=(0,.10,1,.94));fig.savefig(OUT/('e9z_source_compare.png' if case is e9z else 'jtc_source_compare.png'),dpi=155);plt.close(fig)
    plot('e9z_same_ratio',[(e9z['panels'][1]['team_key'],'baseline','5H5L：加入W101'),
          (paired_key,'baseline','同来源、同5H5L：改加入'+paired_worker),
          (e9z['panels'][2]['team_key'],'baseline','原W101路径再加W031：5H6L')],e9z_target,e9z['zoom_bounds'],
          'e9z-19：同为较低历史Q成员，是否补到本图缺的那一票不同')
    plot('jtc_same_ratio',[(jtc['panels'][1]['team_key'],'baseline','4F1S：换出W113'),
          ('jtc26_4F1S_drop_W128','baseline','同4F1S：换出W128'),
          ('jtc26_4F1S_drop_W128','candidate','同一团队：仅修正对应')],jtc_target,jtc['zoom_bounds'],
          'jtc-26：同一慢者、同配比，三份局部来源能否被算法汇成三票')
    q9=next(k for k,v in states.items() if v['request']['role']=='reviewed_split' and v['baseline']['n']==17)
    plot('q9_automatic_candidate',[(q9,'baseline','冻结原算法'),(q9,'candidate','锁定达票组，仅救回未达票碎片')],
         q9_target,[348,410,190,365],'q9-30：自动候选恢复15票组，包含已审的全部13份同角观察')
    z6=next(k for k,v in states.items() if v['request']['image']=='Z6MFQCViBuw-10' and v['baseline']['n']==11)
    focus=set().union(*(observations(g) for g in states[z6]['candidate']['identity_groups'] if g['feature_id']=='node_001' or g['feature_id'].startswith('rescue_')))
    plot('semi_boundary',[(z6,'baseline','Semi：原算法4节点'),(z6,'candidate','Semi：候选增加近邻节点')],focus,[325,395,125,335],
         'Z6-10已审负例：同一墙角被重复输出；来源含未改的角点重复trap')
    existing=next(g for g in states[z6]['candidate']['identity_groups'] if g['feature_id']=='node_001')
    extra=next(g for g in states[z6]['candidate']['identity_groups'] if g['feature_id'].startswith('rescue_'))
    both={m['worker'] for m in existing['members']}&{m['worker'] for m in extra['members']}
    worker=sorted(both)[0];member=next(m for m in existing['members'] if m['worker']==worker);source=objects[member['id']]
    photo=np.asarray(Image.open(next(ROOT.glob('data/mp3d_layout/*/img/'+source['image_id']+'.png'))).convert('RGB'))
    fig,axes=plt.subplots(1,2,figsize=(12,5),gridspec_kw={'width_ratios':[1.8,1]})
    for j,ax in enumerate(axes):
        visual._erp_background(ax,photo)
        if j==0:visual._erp_edges(ax,source['points_1024x512'],'#ffe35b',linewidth=1.1)
        for g,color in [(existing,'#20d8ff'),(extra,'#ff8f20')]:
            ms=[m for m in g['members'] if m['worker']==worker] if j==0 else g['members']
            for m in ms:
                p=np.asarray(m['points']);ax.plot(p[:,0],p[:,1],color=color,lw=2 if j==0 else 1.1,alpha=.95 if j==0 else .7)
        if j==1:ax.set_xlim(300,430);ax.set_ylim(335,125)
        ax.set_xticks([]);ax.set_yticks([])
    axes[0].set_title(worker+'一份完整原答：同时画了蓝、橙两处',fontsize=11)
    axes[1].set_title('蓝8人组、橙6人组的全部局部来源',fontsize=11)
    fig.suptitle('Z6-10已审：蓝橙想标同一墙角；W017原样保留重复trap',fontsize=14)
    fig.text(.03,.04,'两组共享4名人员，不能相加当14人。W017已证实未改trap；其余共享成员的初始化证据另列，不能一并推定。',fontsize=10)
    fig.tight_layout(rect=(0,.12,1,.91));fig.savefig(OUT/'semi_target_review.png',dpi=155);plt.close(fig)
    if not (OUT/'HUMAN_REVIEW.json').exists():
        save(OUT/'HUMAN_REVIEW.json',dict(status='pending',image='Z6MFQCViBuw-10',question='蓝8人组与橙6人组是同一墙角定位差异，还是不同边界目标？',
             shared_workers=sorted(both),representative_worker=worker,representative_object_id=source['object_id'],
             existing_observations=sorted(observations(existing)),rescued_observations=sorted(observations(extra))))
    zs='current_v2_legacy_panel__zsNo4HB9uLZ-05'
    controls=read(OUT/'HUMAN_CONTROLS.json');control=next(c for c in controls if c['case']=='zs05_corrected_fourth')
    focus={tuple(o) for group in control['groups'] for o in group}
    # 用户已确认是不同墙角；三法同图同人员，显示首次候选的误合及收窄后的保留。
    centers=[m['points'] for g in states[zs]['baseline']['identity_groups'] for m in g['members'] if (m['worker'],m['source_pair_index']) in focus]
    ps=np.asarray(centers);bounds=[float(ps[:,:,0].min()-35),float(ps[:,:,0].max()+35),max(0,float(ps[:,:,1].min()-30)),min(512,float(ps[:,:,1].max()+30))]
    plot('adjacent_negative',[(zs,'baseline','已确认不同墙角：原分组'),(zs,'unrestricted','失败：全局优先最大相容组'),(zs,'candidate','收窄：锁定达票组')],focus,bounds,
         'zs-05负对照：相容票多不保证同一实体，不能重排已有达票角点',reference=False)
    csv(OUT/'FIGURE_PANELS.csv',pd.DataFrame(panels))

    fig,axes=plt.subplots(2,2,figsize=(12,7),gridspec_kw={'width_ratios':[2.4,1]})
    for i,(image,worker,bounds) in enumerate([('Z6MFQCViBuw-10','W017',[325,400,130,330]),
                                            ('e9zR4mvMWw7-32','W006',[250,330,185,355])]):
        source=next(r for r in evidence if r['image_code']==image and r['worker_id']==worker and r['condition']=='semi')
        s=source['semi_evidence']
        photo=np.asarray(Image.open(next(ROOT.glob('data/mp3d_layout/*/img/'+source['image_id']+'.png'))).convert('RGB'))
        for j,ax in enumerate(axes[i]):
            visual._erp_background(ax,photo)
            visual._erp_edges(ax,s['initialization_points'],'#18d9ff',linewidth=3)
            visual._erp_edges(ax,s['raw_final_points'],'#ff3a97',linewidth=1)
            if j:ax.set_xlim(bounds[:2]);ax.set_ylim(bounds[3],bounds[2])
            ax.set_xticks([]);ax.set_yticks([])
        axes[i,0].set_title(image+'／'+worker+'：初始与提交坐标重合',fontsize=11)
        axes[i,1].set_title('重复角点局部',fontsize=11)
    fig.suptitle('已确认的角点重复trap：Z6-10之外，e9z-32也有原样保留来源',fontsize=13)
    fig.text(.03,.035,'青色粗线=已绑定初始化；玫红细线=原始提交。叠图重合；不是两批独立观察。其它人员及缺初始几何者另列。',fontsize=9)
    fig.tight_layout(rect=(0,.08,1,.95));fig.savefig(OUT/'semi_initialization_examples.png',dpi=155);plt.close(fig)

    local=[]
    for key,data in states.items():
        req=data['request']
        if req['image'] not in ['jtcxE69GiFV-26','e9zR4mvMWw7-19'] or req['role']=='human_identity_control':continue
        focus=jtc_target if req['image']=='jtcxE69GiFV-26' else e9z_target
        current_obs=set().union(*(observations(g) for g in data['baseline']['identity_groups']))
        for method in ['baseline','candidate']:
            focal=[g for g in data[method]['identity_groups'] if observations(g)&focus]
            local.append(dict(key=key,image=req['image'],method=method,n=data[method]['n'],threshold=data[method]['minimum_support'],
                         known_target_observations_present=len(focus&current_obs),largest_known_subset=max((len(observations(g)&focus) for g in focal),default=0),
                         group_total_support=[g['support'] for g in focal],group_selected=[g['selected'] for g in focal],
                         B8L2=data[method+'_score']['B8L2'],D10=data[method+'_score']['D10'],nodes=len(data[method]['node_consensus']['nodes']),
                         complete_evaluable=data[method+'_score'].get('score_status'),
                         geometry_status=data[method]['candidate'].get('geometry_status'),geometry_reason=data[method]['candidate'].get('reason')))
    csv(OUT/'BACKGROUND_LOCAL_SUPPORT.csv',pd.DataFrame(local))
    path=pd.read_csv(OUT/'inputs/path_scores.csv')
    fig,axes=plt.subplots(2,2,figsize=(12,7.4),layout='constrained')
    for ax,(pid,g) in zip(axes.flat,path.groupby('path_id')):
        g=g.sort_values('n');ax.plot(g.n,g.B8L2,'-o',color='#168fa4',ms=4)
        changed=g.nodes.ne(g.nodes.shift())
        for _,r in g[changed].iterrows():ax.annotate(f'{r.nodes}点',(r.n,r.B8L2),xytext=(3,8),textcoords='offset points',fontsize=9)
        ax.margins(y=.18)
        ax.set_title(pid.split('__')[0]+' / '+g.condition.iloc[0]+' / '+pid.split('__')[-1]);ax.grid(alpha=.2)
        ax.set_xlabel('固定核心后逐人追加L（既有顺序）');ax.set_ylabel('B8L2：相对固定参考');ax.set_xticks(range(int(g.n.min()),int(g.n.max())+1,2))
    fig.suptitle('复用新包44支保存团队：配比路径并非单调，结构跳变与位置变化分别解释',fontsize=13)
    fig.savefig(OUT/'saved_growth_paths.png',dpi=155);plt.close(fig)
    methods=pd.read_csv(OUT/'METHOD_COMPARISONS.csv')
    save(OUT/'COVERAGE.json',dict(existing_package_cases=len(cases),existing_package_teams=12,stored_growth_rows=len(path),stored_growth_paths=path.path_id.nunique(),
         explicit_requested_teams=len(states),new_control_design_teams=7,human_relation_controls=len(controls),
         different_target_controls=sum(c['kind']=='different_targets' for c in controls),
         q9_known13_in_rescued_group=max(len(observations(g)&q9_target) for g in states[q9]['candidate']['identity_groups']),
         q9_rescue_support=max(g['support'] for g in states[q9]['candidate']['identity_groups'] if g['feature_id'].startswith('rescue_')),
         method='locked_selected_majority_clique_rescue_v1',search_or_score_used_to_choose_correspondence=False,
         cases_are_not_independent_validation=True,shared_fusion_entry_modified=False,
         candidate_changed_selected_node_count=int(methods.baseline_nodes.ne(methods.candidate_nodes).sum())))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--figures-only',action='store_true');args=ap.parse_args()
    if not args.figures_only:run()
    figures()
