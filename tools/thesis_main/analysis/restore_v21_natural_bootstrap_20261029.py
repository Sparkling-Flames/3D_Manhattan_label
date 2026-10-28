"""Restore missing whole-path bootstrap caches from frozen endpoint/path tables."""
import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import pandas as pd
from .rebuild_v21_20261028 import OUT, ROOT, read
from .prepare_v21_natural_inputs_20261028 import BASE, PRIOR, EXT, selected

TARGET=OUT/'natural_analysis_restored'


def prepare(only=None):
    pools={p['pool_id']:p for p in read(OUT/'pools/INPUT_SNAPSHOT.json')['images']}
    curves=pd.read_csv(OUT/'natural_results/HYBRID_DISPLAY_CURVES.csv.gz',usecols=['pool_id','layer'])
    ids=set(curves.loc[curves.layer.isin(['ordinary_manual','doorway_manual']),'pool_id'])
    cached={p.stem for p in (OUT/'natural_analysis/bootstrap_cache').glob('*.npz')}
    ids-=cached;assert len(ids)==159
    if only:assert only in ids;ids={only}
    TARGET.mkdir(parents=True,exist_ok=True);input_dir=TARGET/'inputs';input_dir.mkdir(exist_ok=True)
    if all((input_dir/(pid+'.csv.gz')).exists() for pid in ids):return sorted(ids)
    old=selected(BASE/'results/ENDPOINT_SCALARS.csv.gz',ids)
    prior=pd.concat([selected(p,ids) for p in sorted((PRIOR/'new_endpoints/table_shards/NEW_ENDPOINT_SCALARS').glob('*.gz'))],ignore_index=True)
    endpoints=pd.concat([old,prior],ignore_index=True).drop_duplicates('team_key',keep='last')
    links=pd.read_csv(BASE/'results/PREFIX_TEAM_LINKS.csv.gz',low_memory=False)
    links=links[links.pool_id.isin(ids)&links.policy.eq('natural_random')].copy();links['stratum']='old24'
    extra=pd.read_csv(PRIOR/'design/NEW_PREFIX_TEAM_LINKS.csv.gz',dtype={'seed':str,'master_seed':str},low_memory=False)
    extra=extra[extra.pool_id.isin(ids)&extra.policy.eq('natural_random')].copy()
    extra['stratum']=extra.batch.map({'balanced_new24':'prior_new24','focus_new48':'prior_focus48'});assert extra.stratum.notna().all()
    links=pd.concat([links,extra],ignore_index=True)
    index=pd.read_csv(EXT/'new_endpoints26/COMPLETE_NEW_ENDPOINT_SHARD_INDEX.csv.gz')
    for i,pid in enumerate(sorted(ids),1):
        parts=[endpoints[endpoints.pool_id.eq(pid)]];requests=[links[links.pool_id.eq(pid)]]
        for r in index[index.pool_id.eq(pid)].itertuples():parts.append(selected(EXT/r.scalar_file,{pid}))
        for stage in (1,2):
            path=EXT/f'design26/links_by_pool/stage{stage}'/(pid+'.csv.gz')
            d=pd.read_csv(path,dtype={'seed':str,'master_seed':str},low_memory=False)
            d=d[d.policy.eq('natural_random')].copy();d['stratum']='new104A' if stage==1 else 'new104B';requests.append(d)
        e=pd.concat(parts,ignore_index=True);assert e.team_key.is_unique,pid
        q=pd.concat(requests,ignore_index=True);assert not q.duplicated(['stratum','path_id','k']).any()
        q=q[['team_key','path_id','k','stratum','policy']].merge(e.drop(columns='k'),on='team_key',how='left',validate='many_to_one',indicator=True)
        assert q._merge.eq('both').all(),(pid,q.loc[q._merge.ne('both'),'team_key'].tolist()[:5]);q=q.drop(columns='_merge')
        for c in ['image','image_id','building','condition','layer','difficulty','pool_n','reference_id','reference_version']:
            q[c]=pools[pid]['meta'].get(c)
        q['pool_n']=len(pools[pid]['records']);q.to_csv(input_dir/(pid+'.csv.gz'),index=False)
        if i%20==0:print('prepared',i,'/',len(ids),flush=True)
    return sorted(ids)


def process(pid):
    import sys,importlib.util,numpy as np
    sys.path.insert(0,str(EXT/'analysis_precision26'))
    import precision_core as core
    import analyze_natural as native
    from .analyze_v21_natural_20261028 import save_csv
    spec=importlib.util.spec_from_file_location('frozen_blocks_restore',EXT/'engine26/derive_frozen_blocks.py')
    blocks=importlib.util.module_from_spec(spec);spec.loader.exec_module(blocks);core._FROZEN_BLOCKS=blocks
    native.bootstrap_weights=core.bootstrap_weights
    native.save_csv=save_csv;native.save_json=lambda obj,p:p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')
    done=TARGET/'pool_checkpoints'/(pid+'__DONE.json')
    if not (done.exists() and (TARGET/'bootstrap_cache'/(pid+'.npz')).exists()):
        d=pd.read_csv(TARGET/'inputs'/(pid+'.csv.gz'),low_memory=False)
        d['score_failure_nonpolicy']=d.B8L2.isna()&d.k.ne(2)
        d['incomplete_nonpolicy']=~d.complete_evaluable.fillna(False).astype(bool)&d.k.ne(2)
        for c in set(core.RAW+core.COMP+core.BOOL).intersection(d.columns):d[c]=core.numeric(d[c])
        exact=pd.read_csv(PRIOR/'analysis_precision/new_results/EXACT_FINITE_MARGINAL_STATISTICS.csv')
        exact_keys=set(map(tuple,exact[exact.exact_complete.eq(True)&exact.k.ne(2)][['pool_id','k']].to_numpy()))
        native.per_pool(pid,d,TARGET,2000,2026102607,2,exact_keys)
    output=pd.read_csv(TARGET/'pool_checkpoints'/(pid+'__curves.csv.gz'))
    original=pd.read_csv(EXT/'analysis_precision26/results_stage2/NATURAL_CURVES.csv.gz',low_memory=False)
    original=original[original.pool_id.eq(pid)];m=output.merge(original,on=['pool_id','cohort','k'],suffixes=('_new','_old'),validate='one_to_one')
    assert len(m)==len(original)==len(output),(pid,'curve rows')
    for metric in core.METRICS:
        assert np.allclose(m[metric+'_new'],m[metric+'_old'],atol=1e-8,rtol=0,equal_nan=True),(pid,metric)
    return pid


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pool');ap.add_argument('--jobs',type=int,default=3);args=ap.parse_args()
    ids=prepare(args.pool)
    with ProcessPoolExecutor(max_workers=args.jobs) as ex:
        for i,pid in enumerate(ex.map(process,ids),1):print('restored',i,'/',len(ids),pid,flush=True)
    if not args.pool:(TARGET/'RESTORE_CHECKS.json').write_text(json.dumps(dict(pools=len(ids),old_curve_parity=True,bootstrap=2000,new_fusion=False,new_scoring=False),indent=2)+'\n',encoding='utf8')


if __name__=='__main__':main()
