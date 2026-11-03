"""One affected current legacy-role prefix: exact targeted statistical replay.

Reuses all saved endpoint scalars. Reconstructs the missing late-phase bootstrap
cache only for the affected policy and two versions, in order to update its
actual global intervals without refitting or re-fusing any team.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types
import warnings
import numpy as np
import pandas as pd
from .apply_manual_ring_orders_20261104 import ROOT, BASE_COMMIT

IMPACT=ROOT/'research/fusion/manual_order_impact_20261104'
RELEASE=ROOT/'research/data/releases/v2.1'
SRC=ROOT/'research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/analysis_policy26'
BASE=RELEASE/'current_policy_results/original_common32/analysis_policy26'
PID='x8F5xyUWy9e-08__manual__0b13997fd3'
KEY=PID+'__fb261248c4a2c1b66d0b'
POLICY='structure_dominant_first'
PHASE='late_20_to_Nminus1'


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);sys.modules[name]=m;return m


def check(a,b,keys,label,columns=None):
    a=a.set_index(keys).sort_index();b=b.set_index(keys).sort_index();assert a.index.equals(b.index),(label,a.shape,b.shape)
    checks=[]
    for c in (columns or list(a)):
        if c not in b or not pd.api.types.is_numeric_dtype(a[c]):continue
        x=pd.to_numeric(a[c],errors='coerce').astype(float);y=pd.to_numeric(b[c],errors='coerce').astype(float)
        assert np.array_equal(x.isna(),y.isna()),(label,c,'missing')
        error=float((x-y).abs().max()) if x.notna().any() else 0.
        assert error<1e-7,(label,c,error)
        checks.append(dict(table=label,field=c,rows=len(a),maximum_absolute_error=error))
    return checks


def main():
    out=IMPACT/'policy';out.mkdir(parents=True,exist_ok=True)
    F=module('adopted_policy_functions_20261025',SRC/'adopted_policy_functions_20261025.py')
    native=types.ModuleType('targeted_frozen_policy32');native.__file__=str(SRC/'analyze_policy32.py')
    exec(compile((SRC/'analyze_policy32.py').read_text(),str(SRC/'analyze_policy32.py'),'exec'),native.__dict__)
    blocks=module('policy_frozen_blocks',SRC.parent/'engine26/derive_frozen_blocks.py')
    meta=pd.read_csv(BASE/'COMMON_IMAGES.csv').sort_values('pool_id').reset_index(drop=True)
    target=meta[meta.pool_id.eq(PID)].iloc[0]
    original=pd.read_csv(RELEASE/'current_policy_inputs'/(PID+'.csv.gz'),low_memory=False)
    new=original.copy();end=blocks.add_blocks_frame(pd.read_csv(IMPACT/'endpoints/ENDPOINT_SCORES.csv')).set_index('team_key')
    e=end.loc[KEY];hit=original.team_key.eq(KEY)
    assert hit.sum()==1 and original.loc[hit,'base_batch'].eq('new16').all()
    assert original.loc[hit,'policy'].eq(POLICY).all() and original.loc[hit,'k'].eq(28).all()
    r=original.loc[hit].iloc[0]
    assert (r.reference_id,r.reference_version)==(e.reference_id,e.reference_version)
    assert pd.isna(r.B8L2)
    mutable=[c for c in F.FIELDS if c not in ['source_time_total_seconds','labor_kind_code']]
    mutable+=['complete_evaluable','connection_available','score_status','geometry_status','order_status','order_tied','geometry_reason',
              'floor_evaluable','complete_floor_evaluable','location_unresolved','score_available','below_four',
              'floor_short_edge_03_n','floor_redundant5_n','floor_area_camera_h2','height_mean_h','B8_formula_residual',
              'B8_global_height_block','B8_local_height_block','D10_direction_block']
    for c in set(mutable):
        if c in new and c in e:new.loc[hit,c]=e[c]
    fixed=[c for c in original if c not in mutable]
    pd.testing.assert_frame_equal(original[fixed],new[fixed])
    native.save(new,out/'PREFIX_VALUES_ASSISTED.csv.gz')
    original[hit].assign(connection_version='automatic').to_csv(out/'AFFECTED_PREFIX_AUTOMATIC.csv',index=False)
    new[hit].assign(connection_version='manual_assisted').to_csv(out/'AFFECTED_PREFIX_ASSISTED.csv',index=False)
    support=pd.read_csv(ROOT/'research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/local_audit/policy/FIXED_K_SUPPORT.csv.gz',keep_default_na=False)
    support=support[support.batch.eq('combined16')].set_index(['pool_id','policy','phase','metric'])
    def legal(frame):
        d=frame[frame.base_batch.isin(['old8','prior_new8','new16'])].copy()
        d['analysis_source']=np.where(d.base_batch.eq('new16'),'new16','old16');d['legacy_batch']=d.base_batch
        return native.legalize(d)
    parts={};parity=[]
    for version,frame in [('automatic',original),('manual_assisted',new)]:
        native.input_for_pool=lambda base,pid,df=frame: legal(df)
        destination=out/version
        assert native.analyze_pool(destination,target,support,2000,native.DEFAULT_SEED)
        part=destination/'analysis_policy26/parts'/PID;parts[version]=part
        k=pd.read_csv(part/'POLICY_IMAGE_K.csv.gz');k.loc[k.k.eq(2),F.METRICS]=np.nan
        k['execution_status']=np.where(k.k.eq(2),'not_executed_policy_k2','executed');native.save(k,part/'POLICY_IMAGE_K.csv.gz')
    for name,keys in [('POLICY_IMAGE_K.csv.gz',['pool_id','version','policy','k']),
                      ('POLICY_IMAGE_PHASE.csv',['pool_id','version','policy','phase']),
                      ('FIXED_SUPPORT.csv.gz',['pool_id','version','policy','phase','metric'])]:
        expected=pd.read_csv(BASE/'results'/name);expected=expected[expected.pool_id.eq(PID)]
        parity+=check(pd.read_csv(parts['automatic']/name),expected,keys,'affected_pool/'+name)
    saved_phase=pd.read_csv(BASE/'results/POLICY_IMAGE_PHASE.csv')
    old_support=pd.read_csv(BASE/'results/FIXED_SUPPORT.csv.gz',keep_default_na=False)
    old_support=old_support[(old_support.policy==POLICY)&(old_support.phase==PHASE)].set_index(['pool_id','version','metric'])
    versions=['new16','pooled32'];phase_i=F.PHASES.index(PHASE);policy_i=F.POLICIES.index(POLICY)
    # Read-only recovery of the precise missing Monte Carlo cache. Source files
    # contain existing scored scalars; only the affected late statistics are run.
    cache=out/'LATE_PATH_BOOTSTRAP_AUTOMATIC.npz'
    arrays={}
    if cache.exists():
        with np.load(cache) as z:arrays={k:z[k] for k in z.files}
    else:
        arrays={v:np.full((len(meta),2000,len(F.METRICS)),np.nan,np.float32) for v in versions}
        for pos,row in meta.iterrows():
            if int(row.pool_n)<21:continue
            if row.pool_id==PID:
                with np.load(parts['automatic']/'PATH_BOOTSTRAP_CACHE.npz') as z:
                    for v in versions:arrays[v][pos]=z[POLICY+'__'+v+'__boot'][:,phase_i,:]
                continue
            d=legal(pd.read_csv(RELEASE/'current_policy_inputs'/(row.pool_id+'.csv.gz'),low_memory=False))
            ks=np.arange(1,int(row.pool_n)+1);late=(ks>=20)&(ks<int(row.pool_n));jlate=np.flatnonzero(late)
            stable_pool=int(hashlib.sha256(row.pool_id.encode()).hexdigest()[:8],16)
            for v in versions:
                use=d if v=='pooled32' else d[d.analysis_source.eq(v)]
                bases=sorted(set.intersection(*[set(use.loc[use.policy.eq(p),'base_path_id']) for p in F.POLICIES]))
                n=F.matrices(use[use.policy.eq('natural_random')],bases,ks)
                p=F.matrices(use[use.policy.eq(POLICY)],bases,ks)
                n={c:a[:,late] for c,a in n.items()};p={c:a[:,late] for c,a in p.items()}
                groupmap=use.drop_duplicates('base_path_id').set_index('base_path_id').legacy_batch.to_dict()
                vi=native.VERSIONS.index(v)
                rng=np.random.default_rng(np.random.SeedSequence([native.DEFAULT_SEED,stable_pool,vi]))
                draw=native.resamples(bases,groupmap,rng,2000)
                bvalues=np.concatenate([F.statistics({c:a[ix] for c,a in n.items()},{c:a[ix] for c,a in p.items()}) for ix in np.array_split(draw,10)],axis=0)
                for mi,m in enumerate(F.METRICS):
                    entry=old_support.loc[(row.pool_id,v,m)]
                    keepks={int(x) for x in str(entry.matched_k_list).split('|') if x and x!='nan'}
                    keep=np.array([int(k) in keepks for k in ks[late]])
                    arrays[v][pos,:,mi]=F.fixed_mean(bvalues[:,:,mi],keep,1)
            if pos%10==0:print('recovered affected-policy late bootstrap',pos+1,'/',len(meta),flush=True)
        import io
        buf=io.BytesIO();np.savez_compressed(buf,**arrays);native.atomic_bytes(cache,buf.getvalue())
    original_summary=pd.read_csv(BASE/'results/POLICY_PRECISION_SUMMARY.csv')
    resultrows=[]
    for connection in ['automatic','manual_assisted']:
        for v in versions:
            points=np.full((len(meta),len(F.PHASES),len(F.METRICS)),np.nan)
            s=saved_phase[(saved_phase.policy==POLICY)&(saved_phase.version==v)].set_index(['pool_id','phase'])
            for pi,row in meta.iterrows():
                for ph,phase in enumerate(F.PHASES):points[pi,ph]=s.loc[(row.pool_id,phase),F.METRICS].to_numpy(float)
            lateboots=arrays[v].copy()
            if connection=='manual_assisted':
                pos=int(meta.index[meta.pool_id.eq(PID)][0])
                with np.load(parts[connection]/'PATH_BOOTSTRAP_CACHE.npz') as z:
                    points[pos]=z[POLICY+'__'+v+'__point']
                    lateboots[pos]=z[POLICY+'__'+v+'__boot'][:,phase_i,:]
            # Other phases are not recalculated; their old rows remain untouched.
            boots=np.full((len(meta),2000,len(F.PHASES),len(F.METRICS)),np.nan,np.float32)
            boots[:,:,phase_i,:]=lateboots
            rng=np.random.default_rng(np.random.SeedSequence([native.DEFAULT_SEED,999,policy_i,native.VERSIONS.index(v)]))
            rows=F.aggregate(points,boots,meta,v,POLICY,rng,2000)
            z=pd.DataFrame(rows);z=z[z.phase.eq(PHASE)].rename(columns={'batch':'version'})
            if connection=='automatic':
                expected=original_summary[(original_summary.policy==POLICY)&(original_summary.version==v)&(original_summary.phase==PHASE)]
                parity+=check(z,expected,['policy','version','phase','difficulty','metric','weighting'],'global_original_late/'+v)
            z['connection_version']=connection;resultrows.append(z)
            del boots
    comparison=pd.concat(resultrows,ignore_index=True);native.save(comparison,out/'LATE_GLOBAL_COMPARISON.csv')
    patch=comparison[comparison.connection_version.eq('manual_assisted')].drop(columns='connection_version')
    mask=(original_summary.policy==POLICY)&original_summary.version.isin(versions)&(original_summary.phase==PHASE)
    updated=pd.concat([original_summary[~mask],patch],ignore_index=True)
    native.save(updated,out/'POLICY_PRECISION_SUMMARY_ASSISTED.csv')
    # Replace only one pool in the per-image/per-k consumer, preserving saved
    # counterparts and the all-four-role cohort.
    for name in ['POLICY_IMAGE_K.csv.gz','POLICY_IMAGE_PHASE.csv','FIXED_SUPPORT.csv.gz']:
        d=pd.read_csv(BASE/'results'/name);replace=pd.read_csv(parts['manual_assisted']/name)
        d=pd.concat([d[~d.pool_id.eq(PID)],replace],ignore_index=True);native.save(d,out/('ASSISTED_'+name))
    native.save(pd.DataFrame(parity),out/'BASELINE_REPRODUCTION.csv')
    prior=legal(original);after=legal(new);oldgood=prior.B8L2.notna()
    assert np.array_equal(prior.loc[oldgood,'B8L2'],after.loc[oldgood,'B8L2'],equal_nan=True)
    assert prior.source_time_total_seconds.equals(after.source_time_total_seconds)
    checks=dict(source_commit=BASE_COMMIT,affected_unique_teams=1,affected_prefix_rows=1,affected_k=28,
        affected_base_batch='new16',affected_policy=POLICY,affected_global_versions=versions,affected_phase=PHASE,
        primary_cohort_images=len(meta),primary_cohort_buildings=meta.building.nunique(),
        secondary_original_old8_hit=False,added_reference32_hit=False,
        early_phase_or_full_team_changed=False,current_DSTRUCT_policy_claim=False,
        original_scored_values_changed=0,source_annotation_labor_changed=False,human_order_labor_known=False,
        recovered_missing_path_bootstrap_cache='same existing source rows; affected policy late phase new16/pooled32 only',
        bootstrap_replicates=2000,seed=native.DEFAULT_SEED,
        baseline_parity_max_error=max(p['maximum_absolute_error'] for p in parity),new_fusions=0,new_score_calls=0)
    (out/'CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(checks,ensure_ascii=False,indent=2));print(comparison[(comparison.metric=='paired_Q_delta')&(comparison.difficulty=='全部')].to_string(index=False))


if __name__=='__main__':
    warnings.filterwarnings('ignore',category=RuntimeWarning)
    main()
