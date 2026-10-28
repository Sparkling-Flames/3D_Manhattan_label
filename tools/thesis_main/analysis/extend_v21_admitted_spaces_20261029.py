"""其它已准入目标分池补充；保留原 current_target 结果及原答身份。"""
import argparse
import copy
import json
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import pandas as pd
from .rebuild_v21_20261028 import OUT, read

TARGET = OUT / 'admitted_space_extension'


def save(name, value):
    path = TARGET / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf8')


def prepare():
    from . import build_v21_pools_20261028 as builder
    inventory = read(OUT / 'quality_inventory.json')
    bindings = {r['object_id']: r for r in read(OUT / 'reference_bindings.json')}
    refs = {r['target_id']: r for r in read(OUT / 'reference_catalog.json')}
    candidates = [copy.deepcopy(r) for r in inventory if r['quality_exclusion_reasons']==['bound_other_admitted_space']]
    assert len(candidates)==236
    counts = Counter((r['reference_id'], r['condition']) for r in candidates)
    admitted = []
    for r in candidates:
        b=bindings[r['object_id']]; ref=refs[r['reference_id']]
        assert b['pool_vote_eligible'] and b['independent_vote_eligible']
        assert b['chosen_target_id']==r['reference_id'] and r['reference_id'] in b['allowed_target_ids']
        assert ref['full_reference_available'] and ref['is_admitted_space_candidate'] and not ref['image_analysis_blocked']
        assert r['score_status']=='complete' and r['diagnostic_B8L2'] is not None
        r['extension_pool_eligible']=counts[r['reference_id'],r['condition']]>=3
        r['analysis_scope']='other_admitted_target'
        r['source_current_target_class']=r['current_class']
        r['current_class']='未分级'
        if r['extension_pool_eligible']:
            r.update(quality_usable=True,quality_use='ordinary_primary' if b['ordinary_difficulty_eligible'] else 'special_conditional_only',B8L2=r['diagnostic_B8L2'],D10=r['diagnostic_D10'])
            admitted.append(r)
    assert len(admitted)==231 and Counter(r['condition'] for r in admitted)=={'manual':227,'semi':4}
    save('CANDIDATE_RECORDS.json', candidates)
    save('ANALYSIS_RECORDS.json', admitted)
    captured={}
    original_read, original_write = builder.read, builder.write
    builder.read=lambda path: admitted if path==OUT/'quality_inventory.json' else original_read(path)
    builder.write=lambda name,value: captured.update({name:value})
    try: builder.main()
    finally: builder.read, builder.write=original_read,original_write
    pools=captured['pools/INPUT_SNAPSHOT.json']['images']
    assert len(pools)==31 and sum(len(p['records']) for p in pools)==231
    oldids={p['pool_id'] for p in read(OUT/'pools/INPUT_SNAPSHOT.json')['images']}
    for i,p in enumerate(pools):
        pid=p['meta']['image']+'__'+p['meta']['condition']+'__other_space_'+str(i)
        assert pid not in oldids
        p['pool_id']=p['meta']['pool_id']=pid
        p['meta'].update(analysis_scope='other_admitted_target',difficulty_aligned=False)
    save('pools/INPUT_SNAPSHOT.json',dict(data_release='v2.1',analysis_scope='other_admitted_target',images=pools))
    pd.DataFrame([p['meta'] for p in pools]).to_csv(TARGET/'POOL_COVERAGE.csv',index=False,encoding='utf-8-sig')
    save('SCOPE_CONTRACT.json',dict(version='admitted_space_extension_v1',candidates=236,admitted_records=231,pools=31,manual_pools=30,semi_pools=1,insufficient_records=5,other_exclusions_preserved=6,original_pools=263,original_quality=8154,combined_quality=8385,
        grouping=['image_id','condition','reference_id'],raw_scores='reuse diagnostic_B8L2 and diagnostic_D10 without measurement',difficulty='current_target label not reassigned to another target; extension marked ungraded',aggregation='within image average across target pools before image/building aggregation',k2='separate actual MV50 supplement; frozen natural analysis retains deferred k2',current_pointer_advanced=False))


def fuse_one(payload):
    from . import fuse_v21_new_pools_20261028 as native
    native.TARGET=TARGET/'new_space_natural256'
    return native.compute(payload)


def analyze_one(path):
    from . import analyze_v21_natural_20261028 as native
    native.TARGET=TARGET/'natural_analysis'
    native.TARGET.mkdir(exist_ok=True)
    return native.process(path)


def two_payloads(pools):
    payloads=[]; links=[]
    for p in pools:
        pid=p['pool_id']; plan=read(TARGET/'new_space_natural256'/pid/'DESIGN.json')
        group=[dict(pool_id=pid,path_id=pid+'__new256_'+str(x['path_index']),stratum='new_space256',first=x['workers'][0],entrant_worker=x['workers'][1],third=x['workers'][2],team_key='',team_key_1='',team_key_3='') for x in plan['paths']]
        links.extend(group);payloads.append((p,group))
    (TARGET/'two_person_natural256').mkdir(exist_ok=True)
    pd.DataFrame(links).to_csv(TARGET/'two_person_natural256/PATH_LINKS.csv.gz',index=False)
    return payloads


def two_one(payload):
    from . import compute_v21_two_person_20261028 as native
    native.TARGET=TARGET/'two_person_natural256'
    return native.compute(payload)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['prepare','fuse','inputs','analyze','two']);ap.add_argument('--jobs',type=int,default=2);args=ap.parse_args()
    if args.stage=='prepare':prepare();return
    pools=read(TARGET/'pools/INPUT_SNAPSHOT.json')['images']
    if args.stage=='fuse':
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            for r in ex.map(fuse_one,[(p,2026102900+i,None) for i,p in enumerate(pools)]):print(r,flush=True)
    elif args.stage=='two':
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            for r in ex.map(two_one,two_payloads(pools)):print(r,flush=True)
    elif args.stage=='inputs':
        from . import prepare_v21_new_space_curves_20261028 as native
        native.OUT=TARGET;native.ENDPOINTS=TARGET/'new_space_natural256';native.TARGET=TARGET/'natural_inputs';native.TARGET.mkdir(exist_ok=True)
        native.main()
    else:
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            for r in ex.map(analyze_one,sorted((TARGET/'natural_inputs').glob('*.csv.gz'))):print(r,flush=True)
        folder=TARGET/'natural_analysis/pool_checkpoints'
        for stem in ['curves','intervals','components','status','curve_bands','curve_band_summary','path_strata']:
            frames=[pd.read_csv(p,low_memory=False) for p in sorted(folder.glob('*__'+stem+'.csv.gz'))]
            pd.concat(frames,ignore_index=True).to_csv(TARGET/'natural_analysis'/('UPDATED_'+stem.upper()+'.csv.gz'),index=False,encoding='utf-8-sig')


if __name__=='__main__':main()
