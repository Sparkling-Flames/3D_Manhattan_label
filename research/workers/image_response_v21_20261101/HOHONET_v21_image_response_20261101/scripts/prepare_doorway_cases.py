#!/usr/bin/env python3
"""Freeze two median-response late-stage cases before diagnostic replay."""
from pathlib import Path
import base64,gzip,json,zipfile
import numpy as np
import pandas as pd
from normalize_doorway import PRO,SCREEN,COMMIT

ROOT=Path(__file__).resolve().parents[1]

def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,float) and not np.isfinite(x):return None
    return x

def save(path,x):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2))

def main():
    root=ROOT;out=root/'stage04_doorway_cases';out.mkdir(exist_ok=True)
    normalized=root/'stage02_normalized/doorway_enriched'
    pools={p['pool_id']:p for p in json.loads((root/'source/repo'/SCREEN/'POOLS.json').read_text())}
    with gzip.open(root/'source/repo'/PRO/'stage04_computation/design/FROZEN_RECORDS.json.gz','rt') as f:records=json.load(f)
    refs=json.loads((root/'source/repo'/PRO/'stage04_computation/recovered_reference_scores/FINAL_REFERENCES.json').read_text())
    ledger=json.loads((root/'stage00_doorway_sources/source/research/data/doorway_review_20261030/expanded_visual_review_20261031/FINAL_SCREENING_LEDGER.json').read_text())
    if isinstance(ledger,dict):
        ledger=ledger.get('records',ledger.get('annotations',ledger.get('rows',[])))
    by_id={str(x.get('object_id')):x for x in ledger}
    sources=pd.read_csv(root/'stage02_normalized/doorway/ENDPOINT_SOURCES.csv.gz').set_index('endpoint_source_key')
    z4=zipfile.ZipFile(root/'source/cache/DOORWAY_04_PHYSICAL_GEOMETRY.zip')
    z2=zipfile.ZipFile(root/'source/cache/DOORWAY_02_RESULTS_CURVES_CASES.zip')
    prefix='HOHONET_doorway_v21_20261031/'
    html=z2.read(prefix+'stage06_cases/DOORWAY_ANSWERS_AND_CONSENSUS.html').decode()
    start=html.index('const DATA=')+len('const DATA=')
    visual,_=json.JSONDecoder().raw_decode(html[start:]);visual={x['image']:x for x in visual}
    chosen=[];requests=[];comparisons=[];scope_context=[];minimal_records={};minimal_refs=[]
    for image,lo,hi in [('uNb9QFRL6hY-47',31,32),('jh4fc5c5qoQ-09',23,24)]:
        case=image+f'__after_{lo}_to_{hi}';folder=out/'cases'/case;folder.mkdir(parents=True,exist_ok=True)
        pid=image+'__manual__overall_after_screen';d=pd.read_csv(normalized/(pid+'.csv.gz'))
        a=d[d.k.eq(lo)].set_index('replicate_id');b=d[d.k.eq(hi)].set_index('replicate_id')
        delta=b.B8L2-a.B8L2;median=delta.median();rid=int((delta-median).abs().sort_values(kind='stable').index[0])
        paths=pd.DataFrame({'replicate_id':a.index,'team_low':a.team_key,'source_low':a.endpoint_source_key,
                            'team_high':b.team_key,'source_high':b.endpoint_source_key,'delta_B8':delta,
                            'delta_nodes':b.nodes-a.nodes,'delta_turns':b.turns-a.turns}).reset_index(drop=True)
        unique=paths.drop_duplicates('team_low')
        assert len(unique)==hi,'N-1 exact sensitivity requires every leave-one-out team.'
        paths.to_csv(folder/'ALL_256_FULLTAIL_PATH_CANDIDATES.csv',index=False)
        unique.to_csv(folder/'ALL_EXACT_LEAVE_ONE_OUT_TEAMS.csv',index=False)
        comparisons.append({'image':image,'low_k':lo,'high_k':hi,'path_rows':len(paths),
             'unique_leave_one_out_teams':len(unique),'path_mean_delta_B8':delta.mean(),
             'exact_mean_delta_B8':unique.delta_B8.mean(),'path_nodes_increase':int(paths.delta_nodes.gt(0).sum()),
             'exact_nodes_increase':int(unique.delta_nodes.gt(0).sum()),'path_positive_B8':int(delta.gt(0).sum()),
             'exact_positive_B8':int(unique.delta_B8.gt(0).sum())})
        for family in ['overall_before_screen','overall_after_screen','whole_compatible','space1','space2']:
            poold=pd.read_csv(normalized/(image+'__manual__'+family+'.csv.gz'))
            if poold.empty:scope_context.append({'image':image,'family':family,'N':0});continue
            end=poold[poold.k.eq(poold.N)].iloc[0]
            item={c:end.get(c) for c in ['image','N','target','team_key','endpoint_source_key','B8L2','D10','IoU3D100','nodes','turns','omission','extension','status_class']}
            item['family']=family;scope_context.append(item)
        pair=[a.loc[rid].to_dict(),b.loc[rid].to_dict()]
        pair[0]['replicate_id']=pair[1]['replicate_id']=rid
        meta={'case_id':case,'image':image,'pool_id':pid,'low_k':lo,'high_k':hi,'N':int(pair[1]['N']),
              'base_replicate':rid,'selection_rule':'Among all 256 paired valid paths choose delta B8L2 nearest the path-weighted median; tie lowest saved replicate id.',
              'path_mean_delta_B8':float(delta.mean()),'path_median_delta_B8':float(median),
              'selected_delta_B8':float(delta[rid]),'path_positive_B8':int(delta.gt(0).sum()),
              'path_attempts':len(delta),'new_worker':pair[1]['entry_worker'],
              'low_member_team':pair[0]['team_key'],'high_member_team':pair[1]['team_key'],
              'version':'screen439_final_20261031','target':pair[1]['target'],'target_id':pair[1]['target_id']}
        chosen.append(meta);save(folder/'CASE_DEFINITION_BEFORE_REPLAY.json',meta)
        save(folder/'SELECTED_SCALARS.json',pair)
        pd.DataFrame(pair).to_csv(folder/'SELECTED_SCALARS.csv',index=False)
        p=visual[image]['photo'];kind,b64=p.split(',',1);ext='png' if 'png' in kind else 'jpg'
        (folder/('ORIGINAL_PANORAMA.'+ext)).write_bytes(base64.b64decode(b64))
        ref=next(x for x in refs if x['target_id']==pair[1]['target_id']);minimal_refs.append(ref);save(folder/'FINAL_TARGET_REFERENCE.json',ref)
        before=pools[image+'__manual__overall_before_screen'];raw=[]
        for oid in before['records']:
            record=dict(records[oid]);minimal_records[oid]=dict(records[oid])
            record['current_screen439_ledger']=by_id.get(oid)
            record['in_current_after_pool']=oid in pools[pid]['records']
            raw.append(record)
        save(folder/'ALL_IMAGE_ORIGINAL_ANSWERS.json',raw)
        for label,scalar in zip(['low','high'],pair):
            key=scalar['endpoint_source_key'];source=sources.loc[key];payload=None
            if source.endpoint_source_kind=='pro_shard_key':
                member=prefix+source.endpoint_source_path[len(PRO)+1:]
                with z4.open(member) as raw_file:
                    with gzip.open(raw_file,'rt') as lines:
                        for line in lines:
                            q=json.loads(line)
                            if q['physical_team_key']==key:payload=q;break
                member_ids=payload['member_object_ids']
            else:
                with (root/'source/repo'/source.endpoint_source_path).open() as lines:
                    payload=json.loads(next(line for i,line in enumerate(lines,1) if i==int(source.endpoint_source_line)))
                member_ids=payload['members']
            assert payload is not None
            assert set(member_ids)==set(scalar['member_object_ids'].split('|'))
            save(folder/(label+'_SAVED_ENDPOINT.json'),payload)
            trace_name=prefix+'stage06_cases/mechanism_traces/'+key+'.json.gz'
            cached=trace_name in z2.namelist()
            if cached:
                trace=json.loads(gzip.decompress(z2.read(trace_name)));save(folder/(label+'_CACHED_FULL_TRACE.json'),trace)
                assert trace['comparison_to_saved_endpoint']['all_parity']
                assert set(trace['member_object_ids'])==set(member_ids)
            request={'case_id':case,'side':label,'image':image,'k':int(scalar['k']),'target':scalar['target'],
                     'target_id':scalar['target_id'],'source_key':key,'member_object_ids_in_source_order':member_ids,
                     'member_workers_in_source_order':[records[x]['worker'] for x in member_ids],
                     'saved_endpoint':str((folder/(label+'_SAVED_ENDPOINT.json')).relative_to(root)),
                     'saved_scalar':{k:scalar[k] for k in ['B8L2','D10','IoU3D100','complete_evaluable','nodes','minimum_support']},
                     'cache_full_trace_available':cached,'diagnostic_replay_required':not cached}
            requests.append(request)
    save(out/'CASE_DESIGN_BEFORE_REPLAY.json',{'source_commit':COMMIT,'cases':chosen,
          'main_data':'all 256 saved paths; exact leave-one-out reported as separate finite-pool sensitivity',
          'endpoint_requests':requests,'new_diagnostic_replays':sum(x['diagnostic_replay_required'] for x in requests),
          'unchanged':['members','reference','scope','screen439','gap7.5','MV50 >=50%','coordinate estimate','connection rule','B8L2/D10 engine']})
    save(out/'inputs/FROZEN_CASE_RECORDS.json',minimal_records);save(out/'inputs/FINAL_CASE_REFERENCES.json',minimal_refs)
    pd.DataFrame(comparisons).to_csv(out/'FULLTAIL_PATH_VS_EXACT.csv',index=False)
    pd.DataFrame(scope_context).to_csv(out/'FULL_POOL_SCOPE_CONTEXT.csv',index=False)
    print(json.dumps({'cases':chosen,'diagnostic_replays':sum(x['diagnostic_replay_required'] for x in requests)},ensure_ascii=False))
if __name__=='__main__':main()
