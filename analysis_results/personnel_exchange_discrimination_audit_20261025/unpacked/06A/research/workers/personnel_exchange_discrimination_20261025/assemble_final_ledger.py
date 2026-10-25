"""Join actual saved phases without duplicating the large endpoint caches."""
import collections,hashlib,json
from pathlib import Path
import pandas as pd
from run_native import ROOT,REPO,csv,save

STAGES=['screen','confirm','reverse_screen','reverse_confirm','target_omissions','size_paths','large_team_ac_tail']
OUT=ROOT/'final';OUT.mkdir(exist_ok=True)
events=[];usage=[];coverage=[];labels=[]
for stage in STAGES:
    design=ROOT/'design'/stage
    e=pd.read_csv(design/'EVENTS_EXACT.csv.gz',dtype=str,keep_default_na=False)
    complete=json.loads((ROOT/'results'/stage/'COMPLETION.json').read_text())
    assert complete['complete'] and complete['measured_events']==len(e)
    e['stage']=stage;e['condition']='manual';e['layer']='ordinary_manual'
    e['source_team_seats_before']=pd.to_numeric(e.background_source_n)+pd.to_numeric(e.m)
    e['replaced_fraction_of_original_source_seats']=pd.to_numeric(e.m)/e.source_team_seats_before
    e['replaced_fraction_of_source_pool']=pd.to_numeric(e.m)/pd.to_numeric(e.source_capacity)
    e['replaced_fraction_of_team']=pd.to_numeric(e.m)/pd.to_numeric(e.n)
    e['same_class_comparison_available']=stage!='large_team_ac_tail'
    e['event_metrics_file']='results/'+stage+'/EVENT_METRICS.csv.gz'
    e['exact_original_design_file']='design/'+stage+'/EVENTS_EXACT.csv.gz'
    events.append(e)
    arms=['A','C'] if stage=='large_team_ac_tail' else ['A','B','C']
    for arm in arms:
        u=e[['event_id','stage','method','phase','pool_id','image','building','n','m',arm+'_team_key']].rename(columns={arm+'_team_key':'team_key'})
        u['arm']=arm;usage.append(u)
    for phase,g in e.groupby('phase'):
        keys=set(g[[x+'_team_key' for x in arms]].to_numpy().ravel())
        coverage.append(dict(stage=stage,phase=phase,design='direct_AC' if stage=='large_team_ac_tail' else 'strict_ABC',events=len(g),images=g.pool_id.nunique(),buildings=g.building.nunique(),methods=g.method.nunique(),unique_endpoints=len(keys),registered_events_all_computed=True,n_min=pd.to_numeric(g.n).min(),n_max=pd.to_numeric(g.n).max(),m_min=pd.to_numeric(g.m).min(),m_max=pd.to_numeric(g.m).max()))
    p=design/'FROZEN_LABELS.csv.gz'
    if p.exists():labels.append(pd.read_csv(p,dtype=str,keep_default_na=False))

all_events=pd.concat(events,ignore_index=True).fillna('')
assert all_events.event_id.is_unique
csv(OUT/'ALL_EVENTS_EXACT.csv.gz',all_events)
links=pd.concat(usage,ignore_index=True);csv(OUT/'EVENT_ENDPOINT_LINKS.csv.gz',links)
csv(OUT/'STAGE_PHASE_COVERAGE.csv',pd.DataFrame(coverage))
lab=pd.concat(labels,ignore_index=True).drop_duplicates()
# Prior population experiments saved LOBO labels only. Recover the descriptive
# ALL counterparts from their real original archive, never infer them by voting
# across folds or equate numeric class IDs between folds.
historical_dir=REPO/'research/workers/personnel_effective_exchange_conditions_20261022/cross_condition_taxonomy'
old_all_path=historical_dir/'OLD_METHOD_LABELS_ALL.csv'
old_all=pd.read_csv(old_all_path,dtype=str,keep_default_na=False)
old_all=old_all[(old_all.condition=='manual')&old_all.method.isin(['V3_BEHAVIOR','V3_JOINT_QT'])].copy()
old_all['method']=old_all.method+'_'+old_all.tier
old_all['candidate_origin']='historical_original_ALL_20261022'
old_all['label_source']=str(old_all_path.relative_to(REPO))
cross_path=historical_dir/'CROSS_LABELS_ALL.csv'
cross=pd.read_csv(cross_path,dtype=str,keep_default_na=False)
cross=cross[(cross.condition=='manual')&cross.method.isin(['XCOND_GEOM','XCOND_GEOM_QT','XCOND_PAIRED'])].copy()
cross=cross[['worker_id','heldout_building','method','coarse_label','known','missing_reason','input_conditions','condition']].rename(columns={'coarse_label':'class_id'})
cross['method']=cross.method+'_coarse';cross['tier']='coarse'
cross['candidate_origin']='historical_original_ALL_20261022';cross['label_source']=str(cross_path.relative_to(REPO))
lab=pd.concat([lab,old_all,cross],ignore_index=True).fillna('')
key=['worker_id','heldout_building','method']
assert not lab.duplicated(key).any()
csv(OUT/'LABELS_ALL.csv',lab[lab.heldout_building=='ALL'])
csv(OUT/'LABELS_LOBO.csv.gz',lab[lab.heldout_building!='ALL'])

sources=[('screen','results/screen/NATIVE_ENDPOINT_SCALARS.csv.gz','results/screen/NATIVE_ENDPOINT_GEOMETRY.json.gz'),('batch02','results/batch02/ENDPOINT_SCALARS.csv.gz','results/batch02/ENDPOINT_GEOMETRY.json.gz'),('size_paths','results/size_paths/NATIVE_ENDPOINT_SCALARS.csv.gz','results/size_paths/NATIVE_ENDPOINT_GEOMETRY.json.gz'),('large_team_ac_tail','results/large_team_ac_tail/NATIVE_ENDPOINT_SCALARS.csv.gz','results/large_team_ac_tail/NATIVE_ENDPOINT_GEOMETRY.json.gz')]
needed=set(links.team_key);seen=set();inventory=[]
keep=['team_key','pool_id','image','building','condition','layer','k','score_available','B8L2','D10','geometry_available','geometry_status','score_status','below_four','endpoint_origin','member_workers']
for batch,scalar,geo in sources:
    for chunk in pd.read_csv(ROOT/scalar,low_memory=False,chunksize=20000):
        chunk=chunk[chunk.team_key.isin(needed-seen)]
        if len(chunk)==0:continue
        frame=chunk[[x for x in keep if x in chunk]].copy();frame['scalar_source']=scalar;frame['geometry_source']=geo;frame['first_delivery_batch']=batch
        inventory.append(frame);seen.update(frame.team_key)
assert seen==needed,(len(seen),len(needed))
inv=pd.concat(inventory,ignore_index=True)
csv(OUT/'UNIQUE_ENDPOINT_INVENTORY.csv.gz',inv)
teamuse=links.groupby('team_key').agg(event_appearances=('event_id','size'),distinct_events=('event_id','nunique'),stages=('stage',lambda x:'|'.join(sorted(set(x))))).reset_index()
csv(OUT/'ENDPOINT_REUSE_COUNTS.csv.gz',teamuse)
receipt=dict(data='real_v2',calculation_source_commit='972857b2b3f548316be215400e42d6ef6e639250',latest_main_read='e88d1d443f4000715a50475e085a773661be9c04',events=len(all_events),strict_ABC_events=int((all_events.stage!='large_team_ac_tail').sum()),direct_AC_events=int((all_events.stage=='large_team_ac_tail').sum()),endpoint_occurrences=len(links),unique_endpoints=len(inv),images=all_events.pool_id.nunique(),buildings=all_events.building.nunique(),methods=all_events.method.nunique(),historical_origin_counts=inv.endpoint_origin.value_counts(dropna=False).to_dict(),endpoint_first_batch_counts=inv.first_delivery_batch.value_counts().to_dict(),score_available_counts=inv.score_available.value_counts(dropna=False).astype(int).to_dict(),ALL_label_rows=int((lab.heldout_building=='ALL').sum()),LOBO_label_rows=int((lab.heldout_building!='ALL').sum()),no_recomputed_fusion_for_this_join=True)
save(OUT/'FINAL_LEDGER_RECEIPT.json',receipt)
print(json.dumps(receipt,ensure_ascii=False,indent=2))
