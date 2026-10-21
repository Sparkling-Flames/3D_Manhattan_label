"""Exact pool/n populations and cached sets, separate from class-cell coverage."""
from pathlib import Path
from collections import Counter
import hashlib,json,math
import pandas as pd

HERE=Path(__file__).resolve().parent
V3=HERE.parent
OLD=V3.parent/'personnel_global_composition_20261021'

def main():
    p=pd.read_csv(V3/'composition/PANELS.csv',dtype={'full_pool_member_sets':str})
    scope=p.drop_duplicates(['pool_id','n']).copy()
    old_sources=[OLD/'composition/TEAMS_SCALARS.csv.gz',HERE/'restored_full_tables/N20_ALL_144642_ENDPOINT_SCALARS.csv.gz']
    old_frames=[pd.read_csv(f,usecols=['team_key','pool_id','k']) for f in old_sources]
    old=pd.concat(old_frames,ignore_index=True).drop_duplicates('team_key')
    new_frames=[]; executions=[]
    for f in sorted((V3/'composition/batches').glob('*/COMPLETION.json')):
        r=json.loads(f.read_text())
        if r.get('status')!='complete':continue
        frame=pd.read_csv(f.parent/'ENDPOINT_SCALARS.csv.gz',usecols=['team_key','pool_id','k'])
        frame['batch_id']=f.parent.name;new_frames.append(frame)
        ef=f.parent/'EXECUTION.json'
        if ef.exists():
            e=json.loads(ef.read_text())
            executions.append(dict(batch_id=f.parent.name,exported=len(frame),native_calls=e.get('new_native',0),seconds=e.get('seconds'),resumed=e.get('resumed',0),reused=e.get('reused',0)))
    new=pd.concat(new_frames,ignore_index=True) if new_frames else pd.DataFrame(columns=['team_key','pool_id','k','batch_id'])
    stage_reference_rows=len(new)
    # A cached endpoint can be exported again for another declared experiment.
    # Count its actual member set once; retain stage references separately.
    duplicated=new[new.team_key.duplicated(False)]
    if len(duplicated):
        assert (duplicated.groupby('team_key')[['pool_id','k']].nunique()<=1).all().all()
    new=new.drop_duplicates('team_key')
    main_keys=set(pd.read_csv(V3/'composition/DESIGN_TEAMS.csv.gz',usecols=['team_key']).team_key)
    registered=set(main_keys)
    for name in ['LARGE_BLOCK_TEAMS.csv.gz','PURE_BLOCK_TEAMS.csv.gz','F01_CAPACITY_TEAMS.csv.gz']:
        registered.update(pd.read_csv(V3/'composition'/name,usecols=['team_key']).team_key)
    old_counts=old.groupby(['pool_id','k']).size().to_dict()
    union=pd.concat([old,new],ignore_index=True).drop_duplicates('team_key')
    union_counts=union.groupby(['pool_id','k']).size().to_dict()
    new_counts=new.groupby(['pool_id','k']).size().to_dict()
    main_counts=new[new.team_key.isin(main_keys)].groupby(['pool_id','k']).size().to_dict()
    rows=[]
    for r in scope.itertuples():
        k=(r.pool_id,int(r.n));N=int(r.eligible_pool_n);total=math.comb(N,int(r.n))
        assert str(total)==r.full_pool_member_sets
        count=int(union_counts.get(k,0));assert count<=total
        rows.append(dict(pool_id=r.pool_id,image=r.image,building=r.building,condition=r.condition,difficulty=r.difficulty,
            formal_pool_n=N,team_n=int(r.n),all_member_sets=str(total),all_ordered_sequences=str(math.perm(N,int(r.n))),
            reusable_phase1_plus_n20_sets=int(old_counts.get(k,0)),v3_finished_sets=int(new_counts.get(k,0)),
            v3_finished_main_panel_sets=int(main_counts.get(k,0)),known_cached_union_sets=count,
            not_in_reusable_union_sets=str(total-count),full_member_census=count==total,
            cache_scope='verified structured phase1+n20 and completed v3; broader historical key-only catalog not silently counted'))
    out=pd.DataFrame(rows);out.to_csv(HERE/'EXACT_FULL_POOL_MEMBER_SCALE.csv',index=False,encoding='utf-8-sig')
    ex=pd.DataFrame(executions);ex.to_csv(HERE/'MEASURED_NATIVE_THROUGHPUT.csv',index=False,encoding='utf-8-sig')
    native=int(ex.native_calls.sum());seconds=float(ex.seconds.sum());rate=native/seconds if seconds else None
    all_registered_complete=registered<=set(new.team_key)
    pilot=json.loads((V3/'composition/PILOT_THROUGHPUT.json').read_text())
    receipt=dict(status='complete_registered_scope' if all_registered_complete else 'checkpoint_incomplete_registered_scope',pool_n_cells=len(out),
        coverage_scope='215 main full-formal pool-by-n cells; supplementary n and all n=1..N separately inventoried',
        all_registered_v3_complete=all_registered_complete,all_registered_v3_unique=len(registered),
        all_member_sets=sum(int(s) for s in out.all_member_sets),known_cached_union_sets=int(out.known_cached_union_sets.sum()),
        uncovered_member_sets=sum(int(s) for s in out.not_in_reusable_union_sets),
        phase1_plus_n20_unique_index_rows=len(old),all_three_stages_structured_unique=len(union),old_v3_exact_overlap=len(set(old.team_key)&set(new.team_key)),v3_export_stage_references=stage_reference_rows,
        v3_duplicate_export_stage_references=stage_reference_rows-len(new),
        v3_completed_unique=len(new),v3_main_completed=len(main_keys&set(new.team_key)),
        main_registered_unique=len(main_keys),conditional_panels=len(p),conditional_member_references=len(p)*924,
        per_panel_full_member_sets=924,full_pool_census=False,ordered_sequences_evaluated=False,
        measured_native_calls=native,measured_batch_wall_seconds=seconds,aggregate_native_per_batch_wall_second=rate,
        pilot_native_calls=int(pilot['new_native']),pilot_seconds=float(pilot['seconds']),
        all_native_calls_including_pilot=native+int(pilot['new_native']),pilot_endpoints_already_in_completed_union=True,
        throughput_note='Executed worker count and image difficulty are preserved per batch; summed batch wall times are compute stages, not total elapsed research time.',
        source_files=[{'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in old_sources])
    (HERE/'EXACT_SCALE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='source_files'},ensure_ascii=False))

if __name__=='__main__':main()
