from pathlib import Path
import argparse,gzip,io,json,zipfile
import numpy as np
import pandas as pd

ap=argparse.ArgumentParser()
ap.add_argument('--input-root',type=Path,default=Path(__file__).resolve().parents[1])
ap.add_argument('--repo',type=Path,required=True)
ap.add_argument('--downloads',type=Path,required=True)
ap.add_argument('--output',type=Path,default=Path(__file__).parent)
args=ap.parse_args();root=args.input_root
out=args.output
out.mkdir(parents=True,exist_ok=True)
c=pd.read_csv(root/'analysis_precision26/results_stage2/NATURAL_CURVES.csv.gz')
meta=c.drop_duplicates('pool_id').set_index('pool_id')
# All doorway pools and the exact 27-image difficult late-population panel,
# plus the large single-image revision example, chosen from stated claims.
pids=set(meta[(meta.layer=='doorway_manual')|((meta.layer=='ordinary_manual')&(meta.difficulty=='\u56f0\u96be')&(meta.pool_n>=30))].index)
pids.update(meta[meta.image.eq('uNb9QFRL6hY-40')].index)
links=[]
with zipfile.ZipFile(args.downloads/'HOHONET_20261026_S01_exact_design.zip') as z:
 for name in z.namelist():
  if '/links_by_pool/' in name and Path(name).name.removesuffix('.csv.gz') in pids:
   d=pd.read_csv(io.BytesIO(gzip.decompress(z.read(name))),usecols=['pool_id','path_id','team_key','k','stage','policy'])
   links.append(d[d.policy=='natural_random'])
links=pd.concat(links,ignore_index=True)
assert not links.duplicated(['pool_id','path_id','k']).any()
needed=set(links.team_key)
cols=['team_key','B8L2','D10','score_status','below_four','connection_available','nodes','policy_deferred']
scalars=[]
for zp in sorted(args.downloads.glob('HOHONET_20261026_DATA_*.zip')):
 with zipfile.ZipFile(zp) as z:
  for name in z.namelist():
   if name.endswith('.scalars.csv.gz') and Path(name).parent.name in pids:
    d=pd.read_csv(io.BytesIO(gzip.decompress(z.read(name))),usecols=cols,low_memory=False)
    scalars.append(d[d.team_key.isin(needed)])
scalars=pd.concat(scalars,ignore_index=True)
assert not scalars.duplicated('team_key').any()
missing=needed-set(scalars.team_key)
base=args.repo/'research/workers/personnel_population_curves_v2_20261023'
old=io.BytesIO(b''.join(p.read_bytes() for p in sorted((base/'results').glob('ENDPOINT_SCALARS.csv.gz.part*'))))
inherited=[]
for src in [old]+sorted((base/'sampling_precision_20261025/new_endpoints/table_shards/NEW_ENDPOINT_SCALARS').glob('part_*.csv.gz')):
 for d in pd.read_csv(src,compression='gzip',usecols=cols,chunksize=50000,low_memory=False):
  inherited.append(d[d.team_key.isin(missing)])
inh=pd.concat(inherited,ignore_index=True)
assert not inh.duplicated('team_key').any()
scalars=pd.concat([scalars,inh],ignore_index=True)
assert set(scalars.team_key)==needed
d=links.merge(scalars,on='team_key',validate='many_to_one')
# Saved status categories are checked directly, not by filling missing Q.
assert set(d.score_status.dropna()) <= {'complete_conditional','below_four','no_connection','invalid_floor','invalid_full_geometry','two_person_deferred'} ,set(d.score_status.dropna())
rows=[]
for cohort,subset in [('stage1_104',d[d.stage==1]),('stage2_104',d[d.stage==2]),('new208',d)]:
 for (pid,k),g in subset.groupby(['pool_id','k']):
  q=g.B8L2.dropna();n=len(g);attempt=g[g.k!=2]
  fail=attempt.score_status.isin(['below_four','no_connection'])
  rows.append(dict(pool_id=pid,k=k,cohort=cohort,paths_attempted=n,quality_valid_paths=len(q),Q_mean=q.mean(),Q_p10=q.quantile(.1),Q_p10_inverse_cdf=np.quantile(q,.1,method='inverted_cdf') if len(q) else np.nan,Q_sd_ddof1=q.std(ddof=1),D10_mean=g.D10.mean(),actual_executed_nondeferred_paths=len(attempt),actual_consensus_failure_paths=int(fail.sum()),actual_consensus_failure_rate=fail.mean() if len(attempt) else np.nan,output_unscoreable_paths=int(attempt.score_status.isin(['invalid_floor','invalid_full_geometry']).sum())))
a=pd.DataFrame(rows)
b=a.merge(c,on=['pool_id','k','cohort'],suffixes=('_ind','_saved'),validate='one_to_one')
checks=[]
for col in [x for x in a if x not in ['pool_id','k','cohort']]:
 x,y=b[col+'_ind'].to_numpy(float),b[col+'_saved'].to_numpy(float)
 assert np.array_equal(np.isnan(x),np.isnan(y)),col
 err=np.nanmax(np.abs(x-y))
 assert err<1e-8,(col,err)
 checks.append(dict(field=col,rows=len(b),max_abs_error=float(err)))
a.to_csv(out/'INDEPENDENT_SELECTED_PREFIX_STATS.csv.gz',index=False,compression='gzip')
(out/'SELECTED_PREFIX_CHECKS.json').write_text(json.dumps(dict(pools=len(pids),natural_prefix_occurrences=len(d),unique_teams=len(needed),new_scalar_records=len(scalars)-len(inh),inherited_scalar_records=len(inh),checks=checks),indent=2),encoding='utf8')
print(json.dumps(dict(pools=len(pids),natural_prefix_occurrences=len(d),unique_teams=len(needed),checks=checks),indent=2))
