"""Bind current experiment references before inspecting historical diagnostic material."""
from pathlib import Path
from collections import Counter,defaultdict
import gzip,json
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/fusion/missing_ring_review_20261104'
REL=ROOT/'research/data/releases/v2.1'
IMG=ROOT/'research/workers/image_response_v21_20261101/HOHONET_v21_image_response_20261101'


def read(p):
    with (gzip.open(p,'rt',encoding='utf-8') if str(p).endswith('.gz') else open(p,encoding='utf-8')) as f:return json.load(f)


def main():
    screen=pd.read_csv(OUT/'V21_INVENTORY_SCREEN.csv').set_index('team_key')
    preparation=read(OUT/'PREPARE.json')
    candidates=set(screen.index)|set(preparation['deferred'])|{r['team_key'] for r in preparation['errors']}
    links=[];summaries=[];status_gaps=[]
    def ingest(name,path,filter_fn=None):
        header=pd.read_csv(path,nrows=0).columns
        keys=([ 'endpoint_source_key'] if 'endpoint_source_key' in header else [c for c in header if c=='team_key' or c.endswith('_team_key') or c.startswith('team_key_')])
        if not keys:raise ValueError((name,str(path),'no explicit team key'))
        total=0;unique=set();eventids=set();matched=set();status=Counter()
        for d in pd.read_csv(path,chunksize=20000,low_memory=False):
            if filter_fn:d=filter_fn(d)
            total+=len(d)
            if 'score_status' in d and len(keys)==1:
                failed=d[d.score_status.eq('no_connection') & ~d[keys[0]].isin(candidates)]
                for _,r in failed.drop_duplicates(keys[0]).iterrows():
                    status_gaps.append(dict(module=name,source=str(path.relative_to(ROOT)),team_key=r[keys[0]],nodes=r.get('nodes'),geometry_status=r.get('geometry_status')))
            for c in keys:
                unique.update(d[c].dropna().astype(str))
                hit=d[d[c].isin(candidates)]
                for ix,r in hit.iterrows():
                    key=r[c];matched.add(key)
                    event=str(r.get('event_id',r.get('replicate_id',r.get('panel_id',ix))))
                    eventids.add(event)
                    links.append(dict(module=name,source=str(path.relative_to(ROOT)),source_row=int(ix),event_id=event,arm=c,team_key=key,image=r.get('image',''),pool_id=r.get('pool_id',''),reference_id=r.get('reference_id',''),reference_version=r.get('reference_version',''),score_status=r.get('score_status',r.get('output_status',r.get('status',r.get('status_class','')))),k=r.get('k',r.get('n','')),member_object_ids=r.get('member_object_ids',''),member_workers=r.get('member_workers','')))
                    links[-1]['N']=r.get('N','')
                    if c not in ('team_key','endpoint_source_key'):
                        # A comparison row's primary-arm status and members do not describe its other arms.
                        links[-1].update(score_status='',member_object_ids='',member_workers='')
            if 'score_status' in d:status.update(d.score_status.fillna('missing'))
        summaries.append(dict(module=name,source=str(path.relative_to(ROOT)),rows=total,unique_teams=len(unique),inventory_matched_teams=len(matched),matched_events=len(eventids),statuses=json.dumps(status)))
    idx=pd.read_csv(IMG/'stage03_response/manual/ANALYSIS_POOL_INDEX.csv')
    for r in idx.itertuples():
        ingest('natural_'+r.domain,IMG/r.source_file,lambda d:d[d.k.ne(2)])
    idx=pd.read_csv(IMG/'stage02_normalized/doorway_enriched/POOL_INDEX.csv')
    for r in idx.itertuples():ingest('natural_'+r.domain,IMG/r.path)
    idx=pd.read_csv(IMG/'stage02_normalized/manual/K2_OVERLAY_INDEX.csv')
    for r in idx.itertuples():ingest('actual_k2_supplement',IMG/r.normalized_file)
    print('natural and actual k2 references complete',flush=True)
    up=REL/'admitted_space_extension/image_difficulty_20261030'
    ingest('current_half',up/'HALF_EVENT_LEGALITY.csv.gz',lambda d:d[d.updated_class_legal])
    ingest('current_same_room_half',up/'SAME_ROOM_HALF_EVENTS.csv.gz')
    for name,file in [
        ('q_only','q_only_exchange_20261031/DESIGN_LINKS.csv'),
        ('same_room_finite','same_room_current_extended_design/PANEL_TEAM_LINKS.csv.gz'),
        ('same_room_large_registered','same_room_current_large_design/STRICT_ABC_EVENTS.csv.gz'),
        ('fusion_baseline','fusion_common_panel/METHOD_ENDPOINTS.csv'),
        ('changed_alliances','closeout_20261030/alliance_completion_20261031/ALLIANCE_RESULTS.csv')]:
        ingest(name,REL/file,(lambda d:d[d.method=='wall_auto']) if name=='fusion_baseline' else None)
    ac=ROOT/'research/workers/personnel_ac_v21_20261030'
    for name,file in [('ac_registered','stage01_registered/AC_EVENTS.csv.gz'),('ac_semi','stage01b_semi/AC_EVENTS.csv.gz')]:
        ingest(name,ac/file)
    packages=ROOT/'research/workers/personnel_v21_reselection_20261029/additional_delivery/packages'
    for name,folder in [('composition_manual','03B_core/composition/primary_panel_inputs'),('composition_semi','03C/composition/primary_semi_inputs'),('composition_other','03A/composition/other_targets_design')]:
        ingest(name,packages/folder/'PANEL_TEAMS.csv.gz')
    ingest('legacy_role_policy',REL/'current_policy_design/PREFIX_LINKS.csv.gz',lambda d:d[d.k.ge(3)])
    selection=ROOT/'research/workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030/stage05_selection_stop'
    ingest('same_room_q_qt',selection/'selection/POLICY_EVENT_RESULTS.csv.gz')
    ingest('stopping_endpoints',selection/'endpoints/STOPPING_SCALARS.csv.gz')
    pd.DataFrame(summaries).to_csv(OUT/'CURRENT_REFERENCE_SOURCES.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(status_gaps,columns=['module','source','team_key','nodes','geometry_status']).drop_duplicates().to_csv(OUT/'CURRENT_STATUS_OUTSIDE_INVENTORY.csv',index=False,encoding='utf-8-sig')
    l=pd.DataFrame(links);l.to_csv(OUT/'CURRENT_INVENTORY_LINKS.csv.gz',index=False,encoding='utf-8-sig')
    wanted=set(l.team_key);bykey=defaultdict(list)
    for r in l.to_dict('records'):bykey[r['team_key']].append(r)
    accepted=read(ROOT/'analysis_results/consensus_delivery_20261008/order_import.json')['accepted']
    orders=defaultdict(list)
    for r in accepted:orders[r['image']].append(r)
    objects=defaultdict(list)
    for path in [REL/'pools/INPUT_SNAPSHOT.json',REL/'admitted_space_extension/pools/INPUT_SNAPSHOT.json']:
        for pool in read(path)['images']:
            for raw in pool['records']:objects[raw.get('object_id',raw['id'])].append(raw)
    door=ROOT/'research/fusion/doorway_population_v21_20261031/HOHONET_doorway_v21_20261031/stage04_computation/design/FROZEN_RECORDS.json.gz'
    for oid,raw in read(door).items():objects[oid].append(raw)
    checks=[];groups={};group_links=[];unprepared=[]
    for key in sorted(wanted):
        if key not in screen.index:
            reason=next((r['reason'] for r in preparation['errors'] if r['team_key']==key),'historical_deferred')
            unprepared.append(dict(team_key=key,reason=reason,modules='|'.join(sorted({r['module'] for r in bykey[key]}))))
            continue
        rows=screen.loc[[key]]
        if len(rows)!=1:raise ValueError(('duplicate screen key',key))
        rid=rows.iloc[0].review_id
        p=OUT/'prepared'/(rid+'.json.gz')
        if not p.exists():continue
        c=read(p);key=c['team_key'];nodes=c['nodes'];reasons=[]
        scr=rows.iloc[0]['screen']
        if scr!='eligible_members_only_not_yet_current_experiment_verified':reasons.append(str(scr))
        current=bykey[key]
        statuses={str(x['score_status']) for x in current if pd.notna(x['score_status']) and str(x['score_status'])}
        if statuses & {'complete_conditional','scoreable','raw_original_scoreable','capacity_only','two_person_deferred','policy_deferred'}:reasons.append('current_status_requires_resolution:'+','.join(sorted(statuses)))
        if len(nodes)<4:reasons.append('below_four_nodes')
        if any(n['points'] is None for n in nodes):reasons.append('unresolved_location')
        selected={n['feature_id'] for n in nodes}
        coverage=defaultdict(set)
        for n in nodes:
            for m in n['members']:coverage[m['worker']].add(n['feature_id'])
        covering=sum(s==selected for s in coverage.values())
        if len(nodes)>=3 and covering:reasons.append('source_coverage_requires_recheck')
        binding={n['feature_id']:n['points'] for n in nodes}
        exact=[o for o in orders[c['image']] if {n['feature_id']:n['points'] for n in o['order_binding']}==binding]
        coordinate_matches=[o for o in orders[c['image']] if sorted(n['points'] for n in o['order_binding'])==sorted(n['points'] for n in nodes)]
        if exact:reasons.append('existing_exact_manual_order')
        elif coordinate_matches:reasons.append('existing_coordinate_bound_order')
        raw_mismatches=[r['id'] for r in c['records'] if not any(v['points']==r['points'] and v.get('worker_id',v.get('worker'))==r['worker'] for v in objects[r['id']])]
        if raw_mismatches:reasons.append('current_raw_input_mismatch')
        expected_ids={r['id'] for r in c['records']}
        member_mismatches=[r for r in current if pd.notna(r['member_object_ids']) and r['member_object_ids'] and set(r['member_object_ids'].split('|'))!=expected_ids]
        if member_mismatches:reasons.append('current_team_member_mismatch')
        # Exact coordinates only; no near-geometry answer propagation.
        signature=json.dumps([c['image_id'],c['reference_id'],c['reference_version'],sorted([n['points'] for n in nodes])],sort_keys=True,separators=(',',':'))
        if not reasons:
            if signature not in groups:groups[signature]=dict(group_id=f'R{len(groups)+1:06}',representative_review_id=rid,image=c['image'],nodes=len(nodes))
            group_links.append(dict(group_id=groups[signature]['group_id'],review_id=rid,team_key=key))
        checks.append(dict(review_id=rid,team_key=key,image=c['image'],k=c['k'],nodes=len(nodes),covering_sources=covering,exact_existing_orders=len(exact),coordinate_existing_orders=len(coordinate_matches),raw_input_mismatches='|'.join(raw_mismatches),disposition=';'.join(reasons) or 'candidate_pending_current_reference_identity',modules='|'.join(sorted({r['module'] for r in current}))))
        if len(checks)%2000==0:print('checked current-linked diagnostic',len(checks),flush=True)
    pd.DataFrame(checks).to_csv(OUT/'CURRENT_LINKED_DIAGNOSTIC_CHECKS.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(list(groups.values())).to_csv(OUT/'EXACT_GEOMETRY_CANDIDATE_GROUPS.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(group_links).to_csv(OUT/'EXACT_GEOMETRY_CANDIDATE_LINKS.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(unprepared).to_csv(OUT/'CURRENT_UNPREPARED.csv',index=False,encoding='utf-8-sig')
    result=dict(reference_sources=len(summaries),matched_unique_keys=len(wanted),prepared_checked=len(checks),missing_prepared=sorted(wanted-{r['team_key'] for r in checks}),dispositions=dict(Counter(r['disposition'] for r in checks)),candidate_geometry_groups=len(groups),human_queue_released=False)
    (OUT/'CURRENT_REFERENCE_CHECKS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='missing_prepared'},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
