"""Exact finite leave-one-out sensitivity, when every omission team is cached.

The main 256-prefix weighting is not changed. This is a separate exhaustive
uniform-team distribution at N-1, possible only when all N teams are present.
"""
from pathlib import Path
import pandas as pd, numpy as np, json, gzip
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'stage07_summary/finite_tail'

def write(df,path):
 path.parent.mkdir(parents=True,exist_ok=True);raw=df.to_csv(index=False).encode();b=gzip.compress(raw,mtime=0) if str(path).endswith('.gz') else raw
 tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_bytes(b);tmp.replace(path)

def stat(x):
 x=np.asarray(x,float);a=x[np.isfinite(x)]
 return dict(valid_n=len(a),mean=float(a.mean()) if len(a) else np.nan,p10_linear=float(np.quantile(a,.1)) if len(a) else np.nan,
 p10_inverse_cdf=float(np.quantile(a,.1,method='inverted_cdf')) if len(a) else np.nan,
 sd_population=float(a.std(ddof=0)) if len(a) else np.nan,quality_available_rate=float(np.isfinite(x).mean()))

def main():
 mi=pd.read_csv(ROOT/'stage02_normalized/manual/POOL_INDEX.csv');mi=mi[mi.domain.eq('ordinary_manual_main')].copy();mi['file']=mi.normalized_file
 di=pd.read_csv(ROOT/'stage02_normalized/doorway/POOL_INDEX.csv');di=di[di.domain.isin(['doorway_before','doorway_after','doorway_whole'])].copy();di['file']=di.path
 idx=pd.concat([mi,di],ignore_index=True);rows=[];teams=[]
 for _,r in idx.iterrows():
  N=int(r.N)
  if N<4:continue
  d=pd.read_csv(ROOT/r.file,usecols=['k','team_key','replicate_id','B8L2','D10','IoU3D100','member_workers','member_object_ids','complete_evaluable'])
  a=d[d.k.eq(N-1)];f=d[d.k.eq(N)];u=a.drop_duplicates('team_key');complete=len(u)==N
  base={k:r[k] for k in ['pool_id','image','building','domain','N']};base.update(k=N-1,k_fraction=(N-1)/N,observed_distinct_teams=len(u),possible_teams=N,exact_support_complete=complete)
  if f.empty:raise RuntimeError('missing full endpoint')
  for q in ['B8L2','D10','IoU3D100']:
   pstat=stat(a[q]);exact=stat(u[q]) if complete else {x:np.nan for x in pstat};full=float(f[q].iloc[0]);pv=pd.to_numeric(a[q],errors='coerce').dropna();ev=pd.to_numeric(u[q],errors='coerce').dropna()
   out={**base,'metric':q,'full_value':full,**{f'path_{k}':v for k,v in pstat.items()},**{f'exact_{k}':v for k,v in exact.items()}}
   out['path_minus_exact_mean']=pstat['mean']-exact['mean'];out['path_minus_exact_p10_linear']=pstat['p10_linear']-exact['p10_linear']
   out['path_delta_to_full']=full-pstat['mean'];out['exact_delta_to_full']=full-exact['mean']
   out['path_gain_to_full_rate']=float((full>pv+1e-9).mean()) if len(pv) and np.isfinite(full) else np.nan
   out['exact_gain_to_full_rate']=float((full>ev+1e-9).mean()) if complete and len(ev) and np.isfinite(full) else np.nan
   rows.append(out)
  if complete:
   freq=a.team_key.value_counts()
   for _,t in u.iterrows():teams.append({**base,**t.to_dict(),'path_frequency':int(freq[t.team_key]),'exact_uniform_team_weight':1/N,'full_B8L2':f.B8L2.iloc[0]})
 d=pd.DataFrame(rows);write(d,OUT/'LEAVE_ONE_OUT_PATH_VS_EXACT.csv.gz');write(pd.DataFrame(teams),OUT/'EXACT_COMPLETE_TEAMS.csv.gz')
 summ=[]
 for (domain,q),g in d.groupby(['domain','metric']):
  v=g[g.exact_support_complete];good=v[v.path_minus_exact_mean.notna()]
  majority_valid=v[v.path_gain_to_full_rate.notna()&v.exact_gain_to_full_rate.notna()]
  summ.append(dict(domain=domain,metric=q,images=len(g),complete_enumeration_images=len(v),evaluable_comparisons=len(good),
   mean_absolute_MC_mean_error=good.path_minus_exact_mean.abs().mean(),max_absolute_MC_mean_error=good.path_minus_exact_mean.abs().max(),
   mean_error_above_one_images=int(good.path_minus_exact_mean.abs().gt(1).sum()),p10_linear_error_above_two_images=int(v.path_minus_exact_p10_linear.abs().gt(2).sum()),
   gain_majority_evaluable_images=len(majority_valid),gain_majority_unavailable_images=len(v)-len(majority_valid),
   same_gain_majority=int(((majority_valid.path_gain_to_full_rate>.5)==(majority_valid.exact_gain_to_full_rate>.5)).sum())))
 write(pd.DataFrame(summ),OUT/'EXACT_TAIL_PRECISION_SUMMARY.csv')
 (OUT/'METHOD.json').write_text(json.dumps({'main_path_weighting_unchanged':True,'exact_comparison':'uniform distribution over all N observed omission teams at k=N-1; used only when all N distinct teams present','quality_missing':'not zero; conditional distribution plus quality availability fraction (not claimed as pure complete-output rate)','P10':'Both linear and inverse empirical CDF saved explicitly. Existing finite exact convention is inverse CDF. Linear-to-linear comparison is an estimator sensitivity only, not a replacement for adopted exact P10.','SD':'population SD for the exact finite distribution, separate from sample SD in the main 256-path table','new_fusion':0,'new_paths':0},indent=2))
 print(pd.DataFrame(summ).to_string(index=False))

if __name__=='__main__':main()
