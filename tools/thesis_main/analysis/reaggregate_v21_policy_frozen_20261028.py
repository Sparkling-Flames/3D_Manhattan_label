"""Reaggregate the registered historical policy paths with v2.1 endpoint scores."""
import argparse
import gzip
import importlib.util
import json
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pandas as pd
from .rebuild_v21_20261028 import ROOT, OUT, read
from .prepare_v21_natural_inputs_20261028 import BASE, PRIOR, EXT

TARGET=OUT/'policy_frozen_design'
OLD=EXT/'analysis_policy26'
RAW=['nodes','floor_turn5_n','iou_2d','S_bottom_deg','dir','Hmean','Hcenter']
BLOCKS=['B8_floor_block','B8_direction_block','B8_height_block']
_MODULE=None


def load_module():
    global _MODULE
    if _MODULE is not None:return _MODULE
    sys.path.insert(0,str(OLD))
    spec=importlib.util.spec_from_file_location('frozen_policy32',OLD/'analyze_policy32.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    def atomic_bytes(path,payload):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        temp=path.with_name(path.name+'.writing');temp.write_bytes(payload);temp.replace(path)
    module.atomic_bytes=atomic_bytes
    _MODULE=module
    return module


def scalars(wanted):
    sources=[(BASE/'results/ENDPOINT_SCALARS.csv.gz',None)]
    sources += [(p,None) for p in sorted((PRIOR/'new_endpoints/table_shards/NEW_ENDPOINT_SCALARS').glob('*.csv.gz'))]
    idx=pd.read_csv(EXT/'new_endpoints26/COMPLETE_NEW_ENDPOINT_SHARD_INDEX.csv.gz')
    pool_ids={k.rsplit('__',1)[0] for k in wanted}
    sources += [(EXT/r.scalar_file,r.pool_id) for r in idx.loc[idx.stage.eq(1)&idx.pool_id.isin(pool_ids)].itertuples()]
    found={};remaining=set(wanted)
    by_pool={pid:set() for pid in pool_ids}
    for key in wanted:by_pool[key.rsplit('__',1)[0]].add(key)
    for path,pid in sources:
        candidates=remaining if pid is None else by_pool[pid] & remaining
        if not candidates:continue
        for d in pd.read_csv(path,usecols=lambda c:c in RAW+BLOCKS+['team_key'],chunksize=50000,low_memory=False):
            assert set(RAW+['team_key'])<=set(d.columns),(str(path),'missing required scalar field')
            for r in d[d.team_key.isin(candidates)].to_dict('records'):
                found[r['team_key']]=r;remaining.discard(r['team_key'])
        if not remaining:break
    missing=remaining
    assert not missing,('missing required scalar teams',len(missing),list(missing)[:5])
    return pd.DataFrame(found.values()).set_index('team_key').rename(columns={c:c+'_scalar' for c in BLOCKS})


def patches(wanted):
    result={}
    for root in [OUT/'historical_population_rescore',OUT/'population256_rescore']:
        for path in root.rglob('*.jsonl.gz'):
            with gzip.open(path,'rt',encoding='utf8') as f:
                for line in f:
                    r=json.loads(line);key=r['team_key']
                    if key in wanted:
                        score=r.get('result') or {}
                        result[key]={c:score.get(c) for c in ['B8L2','D10','iou_2d','S_bottom_deg','dir','Hmean','Hcenter']}
                        result[key]['score_status']=score.get('score_status') or r.get('original_score_status') or r.get('original_endpoint_state')
    return pd.DataFrame.from_dict(result,orient='index')


def frame_for_pool(events, scalar, patch, affected, module, prior, new):
    pieces=[]
    for arm in ['natural','policy']:
        common=['pool_id','base_path_id','k','version','policy']
        cols=[c for c in events if c.endswith('_'+arm)]
        d=events[common+cols].copy();d=d.rename(columns={c:c.removesuffix('_'+arm) for c in cols})
        if arm=='natural':
            d=d.drop(columns='policy').drop_duplicates(['pool_id','base_path_id','k','version'])
            d['policy']='natural_random'
        d['analysis_source']=d.version
        d['legacy_batch']=np.where(d.version.eq('new16'),'new16',np.where(d.base_path_id.str.contains('__precision_20261025__',regex=False),'prior_new8','old8'))
        d=d.join(scalar,on='team_key',rsuffix='_scalar',validate='many_to_one')
        for c in BLOCKS:d[c]=d[c+'_scalar'] if c+'_scalar' in d else np.nan
        old_prior=d.legacy_batch.eq('prior_new8')
        if old_prior.any():
            keys=pd.MultiIndex.from_frame(d.loc[old_prior,['pool_id','base_path_id','policy','k']])
            prior_values=prior.reindex(keys)
            assert len(prior_values)==int(old_prior.sum()) and prior_values.team_key.notna().all()
            assert (prior_values.team_key.to_numpy()==d.loc[old_prior,'team_key'].to_numpy()).all()
            for c in RAW:
                d.loc[old_prior,c]=prior_values[c].to_numpy()
            for c in BLOCKS:
                values=prior_values[c].to_numpy();fallback=d.loc[old_prior,c+'_scalar'].to_numpy() if c+'_scalar' in d else np.full(len(values),np.nan)
                d.loc[old_prior,c]=np.where(pd.notna(values),values,fallback)
        if new and d.pool_id.iloc[0] in affected:
            mask=d.k.ne(2);missing=set(d.loc[mask,'team_key'])-set(patch.index)
            assert not missing,('missing v2.1 score',len(missing),list(missing)[:3])
            available={c:d[c].notna() for c in RAW[2:]+BLOCKS}
            for c in ['B8L2','D10']+RAW[2:]:
                values=d.team_key.map(patch[c]);d.loc[mask,c]=values[mask] if c in ('B8L2','D10') else values[mask].where(available[c][mask])
            status=d.team_key.map(patch.score_status); d.loc[mask,'score_status']=status[mask].fillna(d.loc[mask,'score_status'])
            v=d.dir;valid=(d.iou_2d>0)&d[['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']].notna().all(axis=1)
            derived={'B8_floor_block':1/d.iou_2d-1+d.S_bottom_deg**2/32,'B8_direction_block':1.5*v*v/(v*v+64),'B8_height_block':(d.Hmean/.8)**2+(d.Hcenter/.25)**2}
            for c in BLOCKS:d.loc[mask,c]=derived[c][mask].where(valid[mask]&available[c][mask])
        d['score_failure_nonpolicy']=(d.k.ne(2)&d.B8L2.isna()).astype(float)
        d['incomplete_nonpolicy']=(d.k.ne(2)&~d.complete_evaluable.fillna(False).astype(bool)).astype(float)
        status=d.score_status.fillna('');active=d.k.ne(2)&d.B8L2.isna()
        d['actual_consensus_failure']=active & status.isin(['fusion_exception','below_four','no_connection'])
        d['output_generated_unscorable']=active & status.isin(['measurement_exception','invalid_floor','invalid_full_geometry'])
        d['reference_unavailable']=active & status.isin(['floor_only_reference','missing_reference'])
        d['other_unscored']=active & ~(d.actual_consensus_failure|d.output_generated_unscorable|d.reference_unavailable)
        pieces.append(d)
    data=pd.concat(pieces,ignore_index=True)
    data['labor_kind_code']=pd.Categorical(data.labor_kind.fillna('')).codes
    for c in module.F.FIELDS:data[c]=pd.to_numeric(data[c],errors='raise')
    return data


def process_pool(payload):
    row,e,scalar,patch,affected,prior,support,old_k=payload
    module=load_module();pid=row.pool_id
    old=frame_for_pool(e,scalar,patch,affected,module,prior,False)
    for policy in module.F.POLICIES:
        for version in ['old16','new16','pooled32']:
            use=old if version=='pooled32' else old[old.analysis_source.eq(version)]
            bases=sorted(set(use.loc[use.policy.eq(policy),'base_path_id']));ks=np.arange(1,int(row.pool_n)+1)
            n=module.F.matrices(use[use.policy.eq('natural_random')],bases,ks);p=module.F.matrices(use[use.policy.eq(policy)],bases,ks)
            values=module.F.statistics({c:a[None] for c,a in n.items()},{c:a[None] for c,a in p.items()})[0]
            saved=old_k.loc[[(pid,policy,version,int(k)) for k in ks]]
            for col in module.F.METRICS:
                x=values[:,module.F.METRICS.index(col)];y=pd.to_numeric(saved[col],errors='coerce').to_numpy()
                bad=~np.isclose(x,y,atol=1e-8,rtol=0,equal_nan=True)
                assert not bad.any(),(pid,policy,version,col,[(int(ks[j]),x[j],y[j]) for j in np.flatnonzero(bad)[:3]])
    updated=frame_for_pool(e,scalar,patch,affected,module,prior,True)
    module.input_for_pool=lambda base,pool_id:updated
    module.analyze_pool(TARGET,row,support,2000,module.DEFAULT_SEED)
    return pid


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pool');ap.add_argument('--jobs',type=int,default=3);args=ap.parse_args()
    module=load_module(); TARGET.mkdir(parents=True,exist_ok=True)
    meta=pd.read_csv(OLD/'COMMON_IMAGES.csv');assert len(meta)==157 and meta.building.nunique()==22
    events=pd.read_csv(OLD/'results/EXACT_PAIRED_EVENTS.csv.gz',low_memory=False)
    if args.pool:
        meta=meta[meta.pool_id.eq(args.pool)];assert len(meta)==1
        events=events[events.pool_id.eq(args.pool)].copy()
    wanted=set(events.team_key_natural)|set(events.team_key_policy)
    scalar=scalars(wanted); patch=patches(wanted)
    prior_parts=[]
    for path in sorted((PRIOR/'new_endpoints/table_shards/NEW_PREFIX_VALUES_COMPACT').glob('*.csv.gz')):
        for d in pd.read_csv(path,usecols=['pool_id','base_path_id','policy','k','team_key']+RAW+BLOCKS,chunksize=50000,low_memory=False):
            prior_parts.append(d[d.pool_id.isin(set(meta.pool_id))])
    prior=pd.concat(prior_parts,ignore_index=True).set_index(['pool_id','base_path_id','policy','k'])
    assert prior.index.is_unique
    affected={r['pool_id'] for r in read(OUT/'pools/DEPENDENCIES.json') if r['action']=='reuse_geometry_rescore'}
    support=pd.read_csv(PRIOR/'local_audit/policy/FIXED_K_SUPPORT.csv.gz',keep_default_na=False)
    support=support[support.batch.eq('combined16')].set_index(['pool_id','policy','phase','metric']);assert support.index.is_unique
    old_k=pd.read_csv(OLD/'results/POLICY_IMAGE_K.csv.gz',low_memory=False).set_index(['pool_id','policy','version','k'])
    groups={pid:g for pid,g in events.groupby('pool_id',sort=False)}
    payloads=[]
    for i,row in meta.iterrows():
        pid=row.pool_id; e=groups[pid]
        keys=pd.Index(set(e.team_key_natural)|set(e.team_key_policy))
        ix=lambda frame:frame.index.get_level_values('pool_id')==pid
        payloads.append((row,e,scalar.loc[keys],patch.loc[patch.index.intersection(keys)],affected,prior[ix(prior)],support[ix(support)],old_k[ix(old_k)]))
    results=[]
    with ProcessPoolExecutor(max_workers=args.jobs) as executor:
        for pid in executor.map(process_pool,payloads):
            results.append(pid);print('policy',len(results),'/',len(meta),pid,flush=True)
    if args.pool:return
    module.aggregate(TARGET,meta,2000,module.DEFAULT_SEED)
    (TARGET/'CHECKS.json').write_text(json.dumps(dict(images=len(results),buildings=int(meta.building.nunique()),old_metric_parity=True,missing_original_endpoints=0,affected_pools=len(set(results)&affected),historical_roles_and_paths=True,new_fusion=False,bootstraps=2000),indent=2)+'\n',encoding='utf8')


if __name__=='__main__':main()
