"""Image-specific geometry dispersion from frozen path-frequency U statistics.

No re-fusion, re-scoring, or reference changes. A small dispersion is not accuracy.
The U statistic compares distinct sampled path indices, retaining repeated teams.
"""
from pathlib import Path
import argparse, json, math, gzip, hashlib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'stage04_geometry' / 'ordinary_cached'
BASE = ROOT / 'source/repo'
OLD = BASE / 'research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/analysis_geometry26/results_stage2'
RULES = {
 'V_floor': {'units':'1 - floor IoU', 'primary': .10, 'grid':[.05,.10,.15,.20], 'range_tolerance':.05},
 'V_centroid_h': {'units':'camera height', 'primary': .05, 'grid':[.025,.05,.10], 'range_tolerance':.025},
 'V_height_h': {'units':'camera height', 'primary': .05, 'grid':[.025,.05,.10], 'range_tolerance':.025},
 'V_turn5': {'units':'absolute turn count difference', 'primary': .5, 'grid':[.25,.5,1.], 'range_tolerance':.25},
 'V_nodes': {'units':'absolute node count difference', 'primary': .5, 'grid':[.25,.5,1.], 'range_tolerance':.25},
}

def write(d, p):
 p.parent.mkdir(parents=True,exist_ok=True)
 raw=d.to_csv(index=False).encode()
 b=gzip.compress(raw,mtime=0) if str(p).endswith('.gz') else raw
 t=p.with_suffix(p.suffix+'.tmp');t.write_bytes(b);t.replace(p)
 if str(p).endswith('.gz'):assert gzip.decompress(p.read_bytes())==raw

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 idx=pd.read_csv(ROOT/'stage02_normalized/manual/POOL_INDEX.csv')
 idx=idx[idx.domain.eq('ordinary_manual_main')].copy()
 old=pd.read_csv(OLD/'GEOMETRY_PATH_PRECISION.csv.gz')
 old=old[old.cohort.eq('pooled256') & old.pool_id.isin(idx.pool_id)].copy()
 old['source_kind']='existing_256_frozen_geometry_U';old['source_table']=str((OLD/'GEOMETRY_PATH_PRECISION.csv.gz').relative_to(ROOT))
 newfile=BASE/'research/data/releases/v2.1/new_space_geometry/NEW_SPACE_GEOMETRY_CURVES.csv.gz'
 new=pd.read_csv(newfile);new=new[new.pool_id.isin(idx.pool_id)].copy()
 new['source_kind']='v21_new_space_256_geometry_U';new['source_table']=str(newfile.relative_to(ROOT))
 assert not set(old.pool_id)&set(new.pool_id),'two competing sources for one pool'
 d=pd.concat([old,new],ignore_index=True)
 assert set(d.pool_id)==set(idx.pool_id),f'missing {set(idx.pool_id)-set(d.pool_id)}'
 assert not d.duplicated(['pool_id','k','metric']).any()
 assert (d.attempted_paths==256).all()
 d=d.rename(columns={'difficulty':'historical_difficulty','building':'historical_building','pool_n':'source_pool_n'})
 meta=idx[['pool_id','image','building','N','difficulty','difficulty_en','ref_turn5','has_short','conditional_short_span']]
 d=d.drop(columns=['image'],errors='ignore').merge(meta,on='pool_id',validate='many_to_one')
 assert (d.N==d.source_pool_n).all()
 d['k_fraction']=d.k/d.N
 d['geometry_valid_fraction']=d.valid_paths/d.attempted_paths
 d['stage']=np.where(d.k==1,'original_answer',np.where(d.k==2,'two_person_legacy','fusion'))
 d['full_team_mechanical_zero']=d.k.eq(d.N)&d['mean'].eq(0)
 write(d,OUT/'GEOMETRY_U_CURVES.csv.gz')
 rows=[];envelopes=[]
 for (pool,metric),g in d[d.k.ge(3)].groupby(['pool_id','metric']):
  md=idx.set_index('pool_id').loc[pool];N=int(md.N);h=max(5,math.ceil(.15*N));rule=RULES[metric]
  a=g.set_index('k').reindex(range(3,N+1));x=a['mean'].to_numpy(float); nv=a.valid_paths.to_numpy(float)
  base={k:md[k] for k in ['image','building','N','difficulty','difficulty_en','ref_turn5','has_short','conditional_short_span']}
  base.update(pool_id=pool,metric=metric,units=rule['units'],required_remaining_people=h)
  er=[]
  for j,k in enumerate(a.index):
   good=np.isfinite(x[j:]).all() and np.isfinite(nv[j:]).all()
   r={**base,'k':k,'k_fraction':k/N,'remaining_people':N-k,'adequate_followup':N-k>=h,
      'all_future_finite':good,'tail_min_valid_paths':float(np.min(nv[j:])) if good else np.nan,
      'tail_max_dispersion':float(np.max(x[j:])) if good else np.nan,
      'tail_range_dispersion':float(np.ptp(x[j:])) if good else np.nan,
      'current_dispersion':x[j],'primary_low_dispersion_tolerance':rule['primary']}
   er.append(r);envelopes.append(r)
  for tol in rule['grid']:
   for minvalid in [32,64,128]:
    cand=[e for e in er if e['all_future_finite'] and e['tail_min_valid_paths']>=minvalid and e['tail_max_dispersion']<=tol+1e-12]
    val=[e for e in cand if e['adequate_followup']]
    first=val[0] if val else None
    if first:reason='sustained_low_dispersion'
    elif N<8:reason='observation_window_too_short'
    elif not np.isfinite(x[-1]):reason='actual_full_geometry_unavailable'
    elif cand:reason='only_near_full_without_required_followup'
    else:reason='persistent_dispersion_or_insufficient_valid_geometry'
    rows.append({**base,'tolerance':tol,'minimum_valid_paths':minvalid,'primary_rule':tol==rule['primary'] and minvalid==64,
                 'onset_k':first['k'] if first else np.nan,'onset_fraction':first['k_fraction'] if first else np.nan,
                 'unconstrained_onset_k':cand[0]['k'] if cand else np.nan,'reason':reason,
                 'near_full':bool(first and first['k_fraction']>=.8)})
 write(pd.DataFrame(envelopes),OUT/'GEOMETRY_TAIL_ENVELOPES.csv.gz')
 write(pd.DataFrame(rows),OUT/'GEOMETRY_LOW_DISPERSION_SENSITIVITY.csv.gz')
 sr=[];windows=[(3,6),(6,10),(10,15),(15,20),(20,30),(30,35),(3,10),(10,20),(3,20),(20,35)]
 piv=d.pivot(index=['pool_id','k'],columns='metric',values='mean')
 for pool,md in idx.set_index('pool_id').iterrows():
  N=int(md.N); pairs=windows+[(3,N),(max(3,N-5),N)]
  for k0,k1 in dict.fromkeys(pairs):
   if k1>N or k0>=k1:continue
   for metric in RULES:
    v0=piv.get(metric,pd.Series(dtype=float)).get((pool,k0),np.nan)
    v1=piv.get(metric,pd.Series(dtype=float)).get((pool,k1),np.nan)
    sr.append(dict(pool_id=pool,image=md.image,building=md.building,difficulty=md.difficulty,difficulty_en=md.difficulty_en,
      N=N,k_from=k0,k_to=k1,k_from_fraction=k0/N,k_to_fraction=k1/N,metric=metric,value_from=v0,value_to=v1,
      delta_dispersion=v1-v0,abs_delta_dispersion=abs(v1-v0),valid=np.isfinite(v0) and np.isfinite(v1)))
 s=pd.DataFrame(sr);write(s,OUT/'GEOMETRY_IMAGE_INTERVALS.csv.gz')
 summ=[]
 for (k0,k1,metric),g in s.groupby(['k_from','k_to','metric']):
  for dl in ['All','Easy','Medium','Hard']:
   q=g if dl=='All' else g[g.difficulty_en.eq(dl)]
   q=q[q.valid]
   if q.empty:continue
   summ.append(dict(k_from=k0,k_to=k1,metric=metric,difficulty_en=dl,images=len(q),buildings=q.building.nunique(),
       mean_delta=q.delta_dispersion.mean(),median_delta=q.delta_dispersion.median(),mean_abs_delta=q.abs_delta_dispersion.mean(),
       decreased_images=int(q.delta_dispersion.lt(-1e-9).sum()),increased_images=int(q.delta_dispersion.gt(1e-9).sum()),
       small_abs_change_images=int(q.abs_delta_dispersion.le(RULES[metric]['range_tolerance']).sum())))
 write(pd.DataFrame(summ),OUT/'GEOMETRY_INTERVAL_SUMMARY.csv')
 panels=[]
 for cap in [10,14,20,30,35]:
  keep=idx[idx.N.ge(cap)]
  for metric in RULES:
   q=d[d.pool_id.isin(keep.pool_id)&d.metric.eq(metric)&d.k.between(3,cap)]
   for k,g in q.groupby('k'):
    x=g['mean'].dropna()
    panels.append(dict(panel_capacity=cap,metric=metric,k=k,capacity_images=len(keep),capacity_buildings=keep.building.nunique(),
      evaluable_images=len(x),mean_image_dispersion=x.mean(),median_image_dispersion=x.median(),
      p10_image_dispersion=x.quantile(.1),p90_image_dispersion=x.quantile(.9),
      mean_k_fraction=(k/keep.N).mean()))
 write(pd.DataFrame(panels),OUT/'GEOMETRY_FIXED_PANEL_CURVES.csv')
 receipt={'ordinary_images':len(idx),'old_geometry_pools':old.pool_id.nunique(),'new_geometry_pools':new.pool_id.nunique(),
  'source_curve_rows':len(d),'new_fusion':0,'new_geometry_distances':0,'new_analysis':True,'rules':RULES,
  'definition':'conditional pairwise U statistic over distinct sampled path indices; repeated exact teams retain frequency',
  'onset':'all future dispersion values <= tolerance with >=max(5,ceil(.15N)) additional people observed; minimum valid paths 64/256',
  'warning':'low dispersion or zero at full pool is not correctness, semantic agreement, or an online stopping rule'}
 (OUT/'CHECKS_AND_RULES.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
 print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()
