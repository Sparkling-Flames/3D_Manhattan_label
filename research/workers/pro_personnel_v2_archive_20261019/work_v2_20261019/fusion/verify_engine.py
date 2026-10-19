"""Meaningful frozen-input/order checks, independent of unordered-team caches."""
from collections import defaultdict
from pathlib import Path
import time
import numpy as np
from pool_io import OUT,ROOT,load_pools,read,save,csv,digest,sha
from fusion_engine import fuse,compact,WORKING_GAP,scoring_engine,ENGINE,compute_score

SEED=2026101904
def normalized_groups(state,id_to_object):
    return sorted((tuple(sorted((id_to_object[m['id']],m['pair_index']) for m in g['members'])),g['support'],g['selected'],g['center']) for g in state['identity_groups'])
def difference(a,b):
    if a is None or b is None:return 0. if a is b else float('inf')
    if np.asarray(a).shape!=np.asarray(b).shape:return float('inf')
    return float(np.max(np.abs(np.asarray(a,float)-np.asarray(b,float)))) if len(a) else 0.
def main():
    pools=load_pools();selected=[];buildings=set()
    for p in sorted((p for p in pools if p['meta']['layer']=='ordinary_manual' and len(p['records'])>=24),key=lambda p:digest([SEED,p['pool_id']])):
        if p['meta']['building'] in buildings:continue
        selected.append(p);buildings.add(p['meta']['building'])
        if len(selected)==12:break
    trials=[]
    for p in selected:
        for k in (8,16,24):
            rng=np.random.default_rng(int(digest([SEED,p['pool_id'],k])[:16],16));records=[p['records'][i] for i in rng.choice(len(p['records']),k,replace=False)]
            for repeat in range(3):
                order=rng.permutation(len(records)).tolist();trials.append(dict(pool_id=p['pool_id'],k=k,repeat=repeat,object_order=[records[i]['object_id'] for i in order]))
    save(OUT/'ORDER_CHECK_REGISTRATION.json',dict(seed=SEED,pool_count=len(selected),trials=trials,
        independent_calls='Every input permutation calls main fuse directly, without unordered-team state cache or cached_matching. Native core may sort internally by stable worker id; this is tested rather than imposed by caller cache.',
        tolerance=1e-6,engine_parameters_unchanged=True))
    results=[];by_pool={p['pool_id']:p for p in pools};baseline={};t0=time.monotonic()
    for t in trials:
        p=by_pool[t['pool_id']];lookup={r['object_id']:r for r in p['records']};tstart=time.monotonic()
        state=compact(fuse([lookup[oid] for oid in t['object_order']],gap=WORKING_GAP)['automatic']);key=(t['pool_id'],t['k'])
        if key not in baseline:baseline[key]=state
        previous=baseline[key];eq=state==previous
        row=dict(**t,complete_compact_state_exact_equal=eq,point_max_abs_difference=difference(state['candidate']['points'],previous['candidate']['points']),
            footprint_max_abs_difference=difference(state['candidate']['footprint'],previous['candidate']['footprint']),seconds=time.monotonic()-tstart)
        assert eq and row['point_max_abs_difference']<=1e-6,'native_order_dependence_observed'
        results.append(row)
    csv(OUT/'ORDER_INDEPENDENCE_CHECKS.csv',results)
    # Same frozen v1 objects: local previous computation is a checked comparison input, not assumed correct.
    legacy=ROOT/'work_20261018/fusion/INPUT_SNAPSHOT.json';legacy_results=[]
    fixture_path=OUT/'V1_PARITY_INPUT_FIXTURE.json.gz'
    fixtures=read(fixture_path)['inputs'] if fixture_path.exists() else []
    fixtures_by_pool={x['pool']['pool_id']:x for x in fixtures}
    if legacy.exists() or fixtures:
        old_pools=read(legacy)['images'] if legacy.exists() else [x['pool'] for x in fixtures]
        current={(p['meta']['image'],p['meta']['condition']):p for p in pools};used=set()
        for old in sorted(old_pools,key=lambda p:digest([SEED,'legacy',p['pool_id']])):
            p=current.get((old['image'],old['condition']))
            if not p or p['meta']['layer']!='ordinary_manual' or p['meta']['building'] in used:continue
            target=ROOT/'work_20261018/fusion/pools'/old['pool_id'];statefile=target/'states.json.gz'
            fixture=fixtures_by_pool.get(old['pool_id'])
            if not statefile.exists() and fixture is None:continue
            lookup={r['id']:r for r in old['records']};now={r['object_id']:r for r in p['records']}
            saved_states=read(statefile)['states'] if statefile.exists() else fixture['cached_states']
            candidates=[x for x in saved_states if x['automatic'] is not None and len(x['subset'].split('|')) in (4,8,12,16)]
            for cached in sorted(candidates,key=lambda x:digest([SEED,x['subset']])):
                old_rows=[lookup[x] for x in cached['subset'].split('|')]
                if not all(r['object_id'] in now and r['points']==now[r['object_id']]['points'] for r in old_rows):continue
                if old['reference']!=p['reference']:
                    keys=('target_id','reference_version','points_1024x512','floor_xz_h','full_reference_available')
                    if any(old['reference'][k]!=p['reference'][k] for k in keys):continue
                old_new_engine=compact(fuse(old_rows,gap=WORKING_GAP)['automatic'])
                now_rows=[now[r['object_id']] for r in old_rows];new_ids=compact(fuse(now_rows,gap=WORKING_GAP)['automatic'])
                oldmap={r['id']:r['object_id'] for r in old_rows};newmap={r['id']:r['object_id'] for r in now_rows}
                a=old_new_engine['candidate'];b=new_ids['candidate'];cached_a=cached['automatic']['candidate']
                row=dict(pool_id=p['pool_id'],image=p['meta']['image'],building=p['meta']['building'],k=len(old_rows),
                    old_state_file=str(statefile.relative_to(ROOT)) if statefile.exists() else fixture['original_state_path'],
                    old_state_file_sha256=sha(statefile) if statefile.exists() else fixture['original_state_sha256'],old_subset=cached['subset'],
                    object_ids='|'.join(sorted(r['object_id'] for r in old_rows)),
                    cached_vs_main_point_max_abs=difference(cached_a['points'],a['points']),
                    cached_vs_main_floor_max_abs=difference(cached_a['footprint'],a['footprint']),
                    renamed_identity_point_max_abs=difference(a['points'],b['points']),
                    renamed_identity_floor_max_abs=difference(a['footprint'],b['footprint']),
                    physical_identity_groups_exact_equal=normalized_groups(old_new_engine,oldmap)==normalized_groups(new_ids,newmap))
                assert max(row[x] for x in ('cached_vs_main_point_max_abs','cached_vs_main_floor_max_abs','renamed_identity_point_max_abs','renamed_identity_floor_max_abs'))<=1e-6 and row['physical_identity_groups_exact_equal']
                legacy_results.append(row);used.add(p['meta']['building']);break
            if len(used)>=12:break
        csv(OUT/'V1_FROZEN_TEAM_PARITY.csv',legacy_results)
    save(OUT/'ENGINE_VERIFICATION.json',dict(independent_order_trials=len(results),same_members_unique_sets=len(baseline),
        order_exact_state_agreement=sum(r['complete_compact_state_exact_equal'] for r in results),v1_frozen_team_parity_trials=len(legacy_results),
        v1_local_history_available=legacy.exists(),v1_selected_fixture_available=bool(fixtures),
        v1_selected_fixture_used=not legacy.exists() and bool(fixtures),all_checks_passed=True,tolerance=1e-6,seconds=time.monotonic()-t0,
        limits='Limited keyed cross-building numerical checks, not semantic certification of source rings or visual annotation quality. Legacy cache result claims independently tested only for saved selected teams.'))
    print(read(OUT/'ENGINE_VERIFICATION.json'),flush=True)

if __name__=='__main__':main()
