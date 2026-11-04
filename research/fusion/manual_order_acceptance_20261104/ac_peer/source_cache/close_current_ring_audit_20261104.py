"""Validate the current-only source join and publish diagnostics, without changing outcomes."""
from pathlib import Path
from collections import Counter,defaultdict
import json,gzip
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.audit_current_ring_references_20261104 import ROOT,OUT,REL,read

REASON='no_source_ring_covering_all_selected_nodes'


def ordered_points(record):
    binding=json.loads(record['binding'])
    order=record['order']
    assert sorted(order)==list(range(len(binding['links'])))
    return [binding['points'][i] for pair in order for i in binding['links'][pair]]


def audit_orders():
    orders=read(REL/'analysis_input/final_orders.json.gz')['records']
    records=[]
    for path in [REL/'pools/INPUT_SNAPSHOT.json',REL/'admitted_space_extension/pools/INPUT_SNAPSHOT.json']:
        for pool in read(path)['images']:
            records.extend((pool['pool_id'],r) for r in pool['records'])
    frozen=read(ROOT/'research/fusion/doorway_population_v21_20261031/HOHONET_doorway_v21_20261031/stage04_computation/design/FROZEN_RECORDS.json.gz')
    records.extend(('doorway_frozen_records',r) for r in frozen.values())
    rows=[]
    for pool,r in records:
        oid=r.get('object_id',r['id']);o=orders.get(oid)
        if not o or o['status']!='confirmed':continue
        expected=ordered_points(o)
        ok=np.shape(expected)==np.shape(r['points']) and np.allclose(expected,r['points'],rtol=0,atol=1e-9)
        rows.append(dict(pool_id=pool,object_id=oid,input_order_status=r.get('order_status'),ordered_points_match=bool(ok)))
    d=pd.DataFrame(rows);d.to_csv(OUT/'CURRENT_RAW_ORDER_CHECK.csv',index=False,encoding='utf-8-sig')
    assert d.ordered_points_match.all(),d[~d.ordered_points_match].to_dict('records')
    return d,frozen


def audit_native(frozen):
    gaps=pd.read_csv(OUT/'CURRENT_STATUS_OUTSIDE_INVENTORY.csv')
    base=ROOT/'research/data/doorway_review_20261030'
    byfile=defaultdict(dict)
    for key in gaps.team_key.unique():
        file,line=key.rsplit(':',1)
        assert (base/file).resolve().is_relative_to(base.resolve()) and file.endswith('.jsonl'),key
        byfile[file][int(line)]=key
    rows=[]
    for file,needed in byfile.items():
        with open(base/file,encoding='utf-8') as stream:
            for line,raw in enumerate(stream,1):
                if line not in needed:continue
                r=json.loads(raw);geom=r['geometry']
                assert geom['reason']==REASON,(file,line,geom)
                assert len(r['members'])==r['k'] and len(set(r['members']))==r['k']
                assert all(x in frozen for x in r['members'])
                assert r['nodes']==len(r['node_supports'])
                assert all(v>=r['minimum_support'] for v in r['node_supports'])
                assert r['minimum_support']==int(np.ceil(r['k']/2))
                rows.append(dict(team_key=needed[line],image=r['image'],k=r['k'],nodes=r['nodes'],minimum_support=r['minimum_support'],
                                 member_object_ids='|'.join(sorted(r['members'])),reason=geom['reason'],input_version=r.get('input_version'),
                                 disposition='native_no_source_ring_confirmed',full_node_coordinates_saved=bool(r.get('node_consensus'))))
    d=pd.DataFrame(rows);assert set(d.team_key)==set(gaps.team_key)
    members=d.set_index('team_key').member_object_ids
    for source,g in gaps.groupby('source'):
        current=pd.read_csv(ROOT/source,low_memory=False)
        for r in current[current.endpoint_source_key.isin(g.team_key)].drop_duplicates('endpoint_source_key').itertuples():
            assert set(r.member_object_ids.split('|'))==set(members[r.endpoint_source_key].split('|')),(source,r.endpoint_source_key)
    d.to_csv(OUT/'CURRENT_NATIVE_FAILURES.csv',index=False,encoding='utf-8-sig')
    return d


def main():
    raw,frozen=audit_orders();native=audit_native(frozen)
    checks=pd.read_csv(OUT/'CURRENT_LINKED_DIAGNOSTIC_CHECKS.csv')
    links=pd.read_csv(OUT/'CURRENT_INVENTORY_LINKS.csv.gz',low_memory=False)
    unprepared=pd.read_csv(OUT/'CURRENT_UNPREPARED.csv')
    # Historical deferral does not override the subsequently executed two-person supplement.
    k2keys=set(unprepared[unprepared.reason.isin(['historical_deferred','actual_k2_no_source_ring_replayed'])].team_key)
    k2=[]
    if k2keys:
        from tools.thesis_main.analysis.ring_correspondence_20261007 import build
        from tools.thesis_main.analysis.consensus_delivery_20261008 import WORKING_GAP
        objects={r['id']:r for p in read(REL/'pools/INPUT_SNAPSHOT.json')['images'] for r in p['records']}
        for r in links[links.team_key.isin(k2keys)].drop_duplicates('team_key').itertuples():
            state=build([objects[oid] for oid in r.member_object_ids.split('|')],gap=WORKING_GAP)
            assert r.score_status=='no_connection' and state['ring_diagnostics']['reason']==REASON
            nodes=state['node_consensus']['nodes']
            k2.append(dict(team_key=r.team_key,nodes=len(nodes),reason=state['candidate']['reason'],node_locations_ready=all(n['points'] is not None for n in nodes)))
        pd.DataFrame(k2).to_csv(OUT/'ACTUAL_K2_PREVIOUSLY_DEFERRED_CHECK.csv',index=False,encoding='utf-8-sig')
        unprepared.loc[unprepared.team_key.isin(k2keys),'reason']='actual_k2_no_source_ring_replayed'
        unprepared.to_csv(OUT/'CURRENT_UNPREPARED.csv',index=False,encoding='utf-8-sig')
    checks['disposition']=checks.disposition.replace({'current_status_requires_resolution:capacity_only':'capacity_only_not_executed'})
    assert not checks.disposition.str.contains('mismatch|requires_resolution|source_coverage|existing_').any(),checks[checks.disposition.str.contains('mismatch|requires_resolution|source_coverage|existing_')].disposition.value_counts().to_dict()
    checks['disposition']=checks.disposition.replace({'candidate_pending_current_reference_identity':'current_no_source_ring_nodes_ready'})
    checks.to_csv(OUT/'CURRENT_LINKED_DIAGNOSTIC_CHECKS.csv',index=False,encoding='utf-8-sig')
    joined=links.merge(checks[['team_key','disposition']],on='team_key',how='left',validate='many_to_one')
    rows=[]
    for module,g in joined.groupby('module'):
        good=g[g.disposition.eq('current_no_source_ring_nodes_ready')]
        rows.append(dict(module=module,current_linked_teams=g.team_key.nunique(),node_ready_no_ring_teams=good.team_key.nunique(),
                         affected_source_rows=len(good[['source','source_row']].drop_duplicates()),affected_images=checks[checks.team_key.isin(good.team_key)].image.nunique(),
                         below_four_teams=g[g.disposition.eq('below_four_nodes')].team_key.nunique(),
                         unprepared_current_keys=g[g.disposition.isna()].team_key.nunique()))
    pd.DataFrame(rows).to_csv(OUT/'CURRENT_MODULE_IMPACT.csv',index=False,encoding='utf-8-sig')
    # Only explicit current main examples are assigned. The census is not a human-work quota.
    room=pd.read_csv(REL/'admitted_space_extension/image_difficulty_20261030/SAME_ROOM_HALF_EVENTS.csv.gz')
    main_room_rows=set(room.index[room.method_updated.eq('TARGET_DSTRUCT_K3') & room.updated_direction.eq('C2→C3') & room.n.isin([10,14])])
    targeted=joined[joined.disposition.eq('current_no_source_ring_nodes_ready') & (
        joined.module.isin(['current_half','current_same_room_half','q_only','changed_alliances']) |
        (joined.module.eq('natural_ordinary_manual_main') & pd.to_numeric(joined.k,errors='coerce').eq(pd.to_numeric(joined.N,errors='coerce'))))]
    targeted=targeted[~targeted.module.eq('current_same_room_half') | targeted.source_row.isin(main_room_rows)]
    groups=pd.read_csv(OUT/'EXACT_GEOMETRY_CANDIDATE_GROUPS.csv')
    gl=pd.read_csv(OUT/'EXACT_GEOMETRY_CANDIDATE_LINKS.csv')
    ids=set(gl[gl.team_key.isin(targeted.team_key)].group_id)
    selected=groups[groups.group_id.isin(ids)].copy()
    selected.to_csv(OUT/'TARGETED_MANUAL_CASES.csv',index=False,encoding='utf-8-sig')
    gl[gl.group_id.isin(ids)].merge(links,on='team_key',how='inner').to_csv(OUT/'TARGETED_MANUAL_ALL_REFERENCES.csv.gz',index=False,encoding='utf-8-sig')
    (OUT/'VALIDATED_REVIEW_IDS.json').write_text(json.dumps(selected.representative_review_id.tolist()),encoding='utf-8')
    effects=[];ready=set(checks[checks.disposition.eq('current_no_source_ring_nodes_ready')].team_key)
    half=pd.read_csv(REL/'admitted_space_extension/image_difficulty_20261030/HALF_EVENT_LEGALITY.csv.gz')
    half=half[half.updated_class_legal]
    for n,g in half.groupby('n'):
        hit=g[['A_team_key','B_team_key','C_team_key']].isin(ready).any(axis=1)
        effects.append(dict(experiment='TARGET_DSTRUCT_K3_C2_to_C3',n=int(n),m=7,events=len(g),no_ring_events=int(hit.sum()),no_ring_images=g[hit].image.nunique(),scored_events=int(g.ABC_scored.sum()),GS_image_mean=g.groupby('image').gap_sym.mean().mean(),CB_image_mean=g.groupby('image').CB.mean().mean()))
    for (method,n,m,direction),g in room.groupby(['method_updated','n','m','updated_direction']):
        hit=g[[c for c in g if c.startswith('team_key_')]].isin(ready).any(axis=1)
        effects.append(dict(experiment='same_room_'+method+'_'+direction,n=int(n),m=int(m),events=len(g),no_ring_events=int(hit.sum()),no_ring_images=len(set(g.loc[hit,'image_a'])|set(g.loc[hit,'image_b'])),scored_events=int(g[['GS_a','GS_b','CB_a','CB_b']].notna().all(axis=1).sum())))
    pd.DataFrame(effects).to_csv(OUT/'CURRENT_MAIN_EVENT_IMPACT.csv',index=False,encoding='utf-8-sig')
    result=dict(raw_confirmed_input_occurrences=len(raw),raw_confirmed_unique_objects=raw.object_id.nunique(),raw_order_matches=int(raw.ordered_points_match.sum()),
                current_prepared_unique_teams=len(checks),dispositions=checks.disposition.value_counts().to_dict(),
                current_native_keys=len(native),native_images=native.image.nunique(),targeted_geometry_cases=len(selected),targeted_images=selected.image.nunique(),
                exact_existing_fusion_orders=int(checks.coordinate_existing_orders.sum()),formal_outcomes_changed=False,
                previously_deferred_actual_k2_replayed=len(k2),
                manual_purpose='diagnose connectability of adopted examples; separate assisted sensitivity, not automatic result repair',
                native_scope='current screen439 pool references to native and reused supplement files; not independent samples across modules')
    (OUT/'FINAL_AUDIT_CHECKS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    discovery=read(OUT/'CURRENT_REFERENCE_CHECKS.json')
    discovery.update(stage='reference_discovery_closed_by_FINAL_AUDIT_CHECKS',human_queue_released=True,human_queue_scope=f'{len(selected)} targeted geometry groups, never the inventory',final_receipt='FINAL_AUDIT_CHECKS.json')
    (OUT/'CURRENT_REFERENCE_CHECKS.json').write_text(json.dumps(discovery,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
