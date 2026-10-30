"""Auditable direct history edges, image prediction errors, complete paired cases.

No fusion, classification fitting, reference changes or team selection is done.
Saved native geometry/trace rows are extracted by their exact archived pointers.
"""
from pathlib import Path
import collections, gzip, hashlib, itertools, json, os, subprocess
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/'source'; OUT=ROOT/'stage02_same_room'; REPO=ROOT.parent/'repo'
ENV={**os.environ, 'GIT_NO_LAZY_FETCH':'1'}

def save(d,p):
    t=p.with_name(p.name+'.tmp'); d.to_csv(t,index=False,compression={'method':'gzip','compresslevel':3,'mtime':0} if str(p).endswith('.gz') else None); t.replace(p)

def gzjson(v,p):
    t=p.with_name(p.name+'.tmp')
    with gzip.open(t,'wt',encoding='utf8') as f: json.dump(v,f,ensure_ascii=False,separators=(',',':'))
    t.replace(p)

def git(*args): return subprocess.check_output(['git','-C',str(REPO),*args],env=ENV)

def main():
    rel=json.loads((SRC/'research/same_room/relation_adoption_20261016/relations.json').read_text()); rm={tuple(sorted([r['image_a'],r['image_b']])):r for r in rel}
    pred=OUT/'prediction'; records=pd.read_csv(pred/'CURRENT_FORMAL_RECORDS.csv.gz'); im=records.drop_duplicates('image_id').set_index('image_id')
    panels=[]; edges=collections.defaultdict(set)
    for scenario in ['v2_frozen','v21_on_v2_records','v21_all']:
        for kind,filename,sourcecol,keys in [
            ('person','PERSON_PREDICTION_VALUES.csv.gz','source_images',['group_id','building','m','N','split_id','target_image','source_images','budget']),
            ('mean','MEAN_HISTORY_VALUES.csv.gz','history',['group_id','building_id','m','N','split_id','target_image','history','panel'])]:
            d=pd.read_csv(pred/scenario/filename,usecols=keys).drop_duplicates()
            for row in d.to_dict('records'):
                sources=row[sourcecol].split('|'); rr=[rm.get(tuple(sorted([row['target_image'],s]))) for s in sources]
                okay=[bool(r and r['physical_adopted'] and r['scope_comparable'] and not r['substantive_conflict']) for r in rr]
                row.update(scenario=scenario,panel_kind=kind,direct_sources=len(sources),valid_direct_sources=sum(okay),all_sources_direct=all(okay),relation_oos_pending=any(r and r['oos_pending'] for r in rr),excluded_sources='|'.join(s for s,ok in zip(sources,okay) if not ok))
                panels.append(row)
                for s in sources: edges[s,row['target_image']].add((scenario,kind,str(row['group_id'])))
    panel=pd.DataFrame(panels); save(panel,pred/'HISTORY_PANEL_DIRECT_EDGE_VALIDATION.csv.gz')
    edge_rows=[]
    for (s,t),uses in edges.items():
        r=rm.get(tuple(sorted([s,t])))
        edge_rows.append(dict(source_image=s,target_image=t,source_code=im.loc[s].image_code,target_code=im.loc[t].image_code,direct_registry_exists=r is not None,physical_adopted=bool(r and r['physical_adopted']),scope_comparable=bool(r and r['scope_comparable']),substantive_conflict=bool(r and r['substantive_conflict']),oos_pending=bool(r and r['oos_pending']),user_group_ids='|'.join(r['user_group_ids']) if r else '',relation_tier=r['tier'] if r else '',uses=';'.join(':'.join(x) for x in sorted(uses))))
    ee=pd.DataFrame(edge_rows); save(ee,pred/'HISTORY_DIRECT_EDGE_VALIDATION.csv'); assert panel.all_sources_direct.all()
    # Target-image prediction errors retain all images, including negative cases.
    image_errors=[]; support_bridge=[]
    oldpairs=None
    for scenario in ['v2_frozen','v21_on_v2_records','v21_all']:
        dp=pd.read_csv(pred/scenario/'DIRECT_PAIRS.csv').drop_duplicates('pair_id').set_index('pair_id'); d=pd.read_csv(pred/scenario/'DIRECT_MEAN_VALUES.csv.gz')
        d['relation_oos_pending']=d.pair_id.map(dp.oos_pending); d['base_abs_error']=(d.external_image_mean-d.actual).abs(); d['source_abs_error']=(d.source_mean-d.actual).abs()
        oldset=set(d.pair_id) if oldpairs is None else oldpairs
        for scope in ['legacy_combined','ordinary_no_relation_oos_pending','relation_oos_pending']:
            z=d if scope=='legacy_combined' else d[d.relation_oos_pending.eq(scope=='relation_oos_pending')]
            v=z.groupby(['metric','building','target_image']).agg(actual=('actual','first'),source_mean_mae=('source_abs_error','mean'),external_image_mean_mae=('base_abs_error','mean'),source_images=('source_image','nunique'),min_common_n=('common_n','min'),target_n=('target_n','first')).reset_index()
            v['gain_source_over_external']=v.external_image_mean_mae-v.source_mean_mae; v['scenario']=scenario; v['scope']=scope
            v['image_code']=v.target_image.map(im.image_code); v['current_difficulty']=v.target_image.map(im.current_class); v['current_reference']=v.target_image.map(im.reference_id); image_errors.append(v)
        for pair,g in d[d.metric.eq('B8L2')].groupby('pair_id'):
            a,b=g.iloc[0].source_image,g.iloc[0].target_image
            support_bridge.append(dict(scenario=scenario,pair_id=pair,image_a=a,image_b=b,code_a=im.loc[a].image_code,code_b=im.loc[b].image_code,building=g.building.iloc[0],relation_oos_pending=bool(g.relation_oos_pending.iloc[0]),present_in_v2_panel=pair in oldset,n_a=int(g.iloc[0].source_n),n_b=int(g.iloc[0].target_n),common_n=int(g.iloc[0].common_n),Q_source_mean_mae=float(g.source_abs_error.mean()),Q_external_mae=float(g.base_abs_error.mean())))
        if oldpairs is None: oldpairs=set(d.pair_id)
    save(pd.concat(image_errors,ignore_index=True),pred/'DIRECT_MEAN_IMAGE_ERRORS.csv'); save(pd.DataFrame(support_bridge),pred/'V2_V21_DIRECT_PAIR_SUPPORT_BRIDGE.csv')

    abc=OUT/'abc'; case=abc/'cases'; case.mkdir(exist_ok=True)
    e=pd.read_csv(abc/'PAIRED_CASE_EVENTS.csv.gz'); native=pd.read_csv(abc/'EXISTING_ENDPOINT_STATUS_COMPONENTS.csv.gz',low_memory=False).set_index('team_key')
    cached_inputs=case/'PAIRED_CASE_INPUTS.json.gz'
    if cached_inputs.exists():snapshots=json.load(gzip.open(cached_inputs,'rt'))['images']
    else:
        packed=OUT/'minimal_inputs/PRIMARY_POOL_INPUT_SNAPSHOT.json.gz'
        snapshots=json.load(gzip.open(packed,'rt'))['images'] if packed.exists() else json.loads((REPO/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json').read_text())['images']
    poolids=set(e.pool_id_a)|set(e.pool_id_b); pp=[p for p in snapshots if p['pool_id'] in poolids]; assert len(pp)==6
    gzjson(dict(data_release='v2.1',purpose='unchanged current original raw answers and formal references for exact existing paired events',images=pp),case/'PAIRED_CASE_INPUTS.json.gz')
    pm={p['pool_id']:p for p in pp}; allkeys={r[c] for r in e.to_dict('records') for c in [f'team_{arm}_{v}' for arm in ['A','B','C'] for v in ['a','b']]}; byshard=collections.defaultdict(list)
    for k in sorted(allkeys):
        p=native.loc[k].geometry_state_pointer; shard,line=p.split('#L'); byshard[shard].append((k,int(line)))
    statefile=case/'PAIRED_CASE_CACHED_GEOMETRY_AND_TRACE.jsonl.gz'
    cached_states={j['team_key']:j for j in map(json.loads,gzip.open(statefile,'rt'))} if statefile.exists() else {}
    cached_receipts=pd.read_csv(case/'CACHED_GEOMETRY_RECEIPT.csv').set_index('team_key').to_dict('index') if (case/'CACHED_GEOMETRY_RECEIPT.csv').exists() else {}
    states={}; receipt=[]
    for shard,wanted in byshard.items():
        if all(k in cached_states and k in cached_receipts for k,line in wanted):
            for k,line in wanted:
                states[k]=cached_states[k];receipt.append(dict(team_key=k,**cached_receipts[k]))
            continue
        path='research/same_room/same_room_large_block_rebuilt_20261023/native_endpoints/'+shard; blob=git('rev-parse','HEAD:'+path).decode().strip(); raw=git('cat-file','blob',blob); lines=gzip.decompress(raw).splitlines()
        for k,line in wanted:
            j=json.loads(lines[line-1]); assert j['team_key']==k
            states[k]=j; receipt.append(dict(team_key=k,git_blob=blob,source_path=path,line_1based=line,shard_sha256=hashlib.sha256(raw).hexdigest(),line_sha256=hashlib.sha256(lines[line-1]).hexdigest(),current_reference_id=native.loc[k].get('reference_id'),current_B8L2=native.loc[k].B8L2,archived_reference_id=j.get('reference_id'),archived_repository_commit=j.get('repository_commit')))
    with gzip.open(case/'PAIRED_CASE_CACHED_GEOMETRY_AND_TRACE.jsonl.gz','wt',encoding='utf8') as f:
        for k in sorted(states): f.write(json.dumps(states[k],ensure_ascii=False,separators=(',',':'))+'\n')
    save(pd.DataFrame(receipt),case/'CACHED_GEOMETRY_RECEIPT.csv')
    nodes=[]; rings=[]; rawcheck=[]; endpoints=[]
    for r in e.to_dict('records'):
        blocks={x:set(r[x+'_members'].split('|')) for x in ['D','X','Y','Z']}
        for v in ['a','b']:
            pool=pm[r['pool_id_'+v]]; answers={a['worker']:a for a in pool['records']}
            for arm,block in [('A','X'),('B','Y'),('C','Z')]:
                k=r[f'team_{arm}_{v}']; j=states[k]; assert set(j['member_workers'])==set(r[arm+'_members'].split('|'))
                fs=j['full_state']; threshold=j['minimum_support']; meta=dict(event_id=r['event_id'],pair_key=r['pair_key'],image=r['image_'+v],view=v,arm=arm,block=block,team_key=k,n=r['n'],m=r['m'],minimum_support=threshold)
                ng=fs['identity_groups']; endpoint={**meta,'B8L2':native.loc[k].B8L2,'D10':native.loc[k].D10,'score_status':native.loc[k].score_status,'selected_nodes':sum(bool(g['selected']) for g in ng),'candidate_nodes':len(ng),'raw_member_identity_verified':True,'ring_reason':fs['ring_diagnostics'].get('reason'),'ring_tied_best':fs['ring_diagnostics'].get('tied_best'),'ring_policy':fs['ring_diagnostics'].get('policy')}
                endpoints.append(endpoint)
                for g in ng:
                    members={x['worker'] for x in g['members']}; ds=members&blocks['D']; bs=members&blocks[block]
                    assert len(ds|bs)==int(g['support']) and not (ds&bs)
                    nodes.append({**meta,'feature_id':g['feature_id'],'selected':g['selected'],'support':g['support'],'D_support':len(ds),'block_support':len(bs),'D_reaches_team_MV50':len(ds)>=threshold,'block_reaches_team_MV50':len(bs)>=threshold,'at_threshold':int(g['support'])==threshold,'D_workers':'|'.join(sorted(ds)),'block_workers':'|'.join(sorted(bs)),'center':json.dumps(g['center']),'max_bottom_angle':g.get('maximum_bottom_angle'),'max_top_angle':g.get('maximum_top_angle'),'bottom_location_clusters':len(g.get('bottom_position_groups_9deg',[])),'top_location_clusters':len(g.get('top_position_groups_9deg',[]))})
                    for a in g['members']:
                        orig=answers[a['worker']]; i=a['pair_index']; pts=orig['points'][2*i:2*i+2]; eq=bool(np.allclose(np.asarray(pts),np.asarray(a['points']),rtol=0,atol=1e-10))
                        rawcheck.append(dict(team_key=k,worker=a['worker'],pair_index=i,current_object_id=orig['object_id'],archive_object_id=a['id'],points_equal=eq))
                diag=fs['ring_diagnostics']
                for kind,key in [('complete_projected_source_ring','alternatives'),('direct_edge','edges')]:
                    for item in diag.get(key,[]):
                        wk=set(item.get('workers',item.get('direct_workers',[]))); d=wk&blocks['D']; b=wk&blocks[block]
                        rings.append({**meta,'evidence_kind':kind,'feature_ids':'|'.join(item['feature_ids']),'support':item.get('support',item.get('direct_support')),'D_support':len(d),'block_support':len(b),'D_workers':'|'.join(sorted(d)),'block_workers':'|'.join(sorted(b)),'interpretation':'diagnostic support; native ring chooses the most-supported complete projected source ring; not a separate per-edge MV50 test'})
    rc=pd.DataFrame(rawcheck).drop_duplicates(); assert rc.points_equal.all()
    save(pd.DataFrame(nodes),case/'CASE_NODE_VOTE_LEDGER.csv.gz'); save(pd.DataFrame(rings),case/'CASE_RING_SUPPORT_DIAGNOSTICS.csv.gz'); save(rc,case/'CASE_RAW_GEOMETRY_IDENTITY_CHECK.csv.gz'); save(pd.DataFrame(endpoints),case/'CASE_ENDPOINT_MECHANISM_INDEX.csv')
    # Worker recurrence is an identity count, not an independent sample count.
    ee=pd.read_csv(abc/'EVENT_IDENTITIES.csv.gz'); z=ee[ee.final_method.eq('TARGET_DSTRUCT_K3')&ee.analysis_scope.eq('ordinary_comparable')&ee.role_direction.eq('2→3')&ee.n.eq(2*ee.m)]
    rr=[]
    for r in z.to_dict('records'):
        for b in ['D','X','Y','Z']:
            for w in r[b+'_members'].split('|'): rr.append(dict(n=r['n'],m=r['m'],role_direction=r['role_direction'],block=b,worker=w,event_id=r['event_id'],pair_key=r['pair_key'],building=r['building']))
    rr=pd.DataFrame(rr); fr=rr.groupby(['n','m','role_direction','block','worker']).agg(event_uses=('event_id','nunique'),pair_uses=('pair_key','nunique'),buildings=('building','nunique')).reset_index(); save(fr,abc/'MAIN_HALF_MEMBER_FREQUENCY.csv')
    checks=dict(direct_panel_rows=len(panel),distinct_direct_edges=len(edge_rows),invalid_source_target_edges=int((~panel.all_sources_direct).sum()),case_events=len(e),case_images=len(pp),case_unique_cached_endpoints=len(states),source_points_checked=len(rc),source_points_all_equal=bool(rc.points_equal.all()),new_fusion_calls=0,new_relation_edges=0,per_node_IDs_are_local_to_endpoint=True,ring_diagnostic_not_per_edge_MV50=True)
    (OUT/'EVIDENCE_COMPLETION_CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)); print(json.dumps(checks,ensure_ascii=False),flush=True)

if __name__=='__main__': main()
