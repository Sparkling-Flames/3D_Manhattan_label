"""Readable per-image result index and cross-metric comparisons."""
from pathlib import Path
import json,math,gzip
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'stage07_summary/integrated'

def write(d,p):
 p.parent.mkdir(parents=True,exist_ok=True);b=d.to_csv(index=False).encode('utf-8-sig');p.write_bytes(gzip.compress(b,mtime=0) if str(p).endswith('.gz') else b)

def main():
 idx=pd.read_csv(ROOT/'stage02_normalized/manual/POOL_INDEX.csv');idx=idx[idx.domain.eq('ordinary_manual_main')].copy()
 c=pd.read_csv(ROOT/'stage03_response/manual/POOL_K_STATISTICS.csv.gz',low_memory=False);c=c[c.domain.eq('ordinary_manual_main')]
 o=pd.read_csv(ROOT/'stage03_response/manual/PLATEAU_SENSITIVITY.csv.gz');o=o[o.domain.eq('ordinary_manual_main')&o.primary_rule]
 e=pd.read_csv(ROOT/'stage03_response/manual/TAIL_ENVELOPES.csv.gz');e=e[e.domain.eq('ordinary_manual_main')]
 geo=pd.read_csv(ROOT/'stage04_geometry/ordinary_cached/GEOMETRY_U_CURVES.csv.gz',low_memory=False)
 go=pd.read_csv(ROOT/'stage04_geometry/ordinary_cached/GEOMETRY_LOW_DISPERSION_SENSITIVITY.csv.gz');go=go[go.primary_rule]
 ge=pd.read_csv(ROOT/'stage04_geometry/ordinary_cached/GEOMETRY_TAIL_ENVELOPES.csv.gz')
 mc=pd.read_csv(ROOT/'stage07_summary/manual/MC_ONSET_BRACKETS.csv');mc=mc[(mc.tolerance==2)&(mc.minimum_valid_paths==64)]
 cols=['pool_id','image','building','N','difficulty','difficulty_en','has_short','ref_turn5','ref_vertices','conditional_short_span','target_id','reference_id','reference_version','sampling_scheme']
 rows=[];cross=[]
 for _,r in idx.iterrows():
  b={x:r[x] for x in cols};p=c[c.pool_id.eq(r.pool_id)].set_index('k');op=o[o.pool_id.eq(r.pool_id)].set_index('metric')
  b['required_remaining_people']=max(5,math.ceil(.15*r.N))
  for m in ['B8L2_mean','B8L2_p10','B8L2_sd','complete_evaluable_rate','D10_mean','IoU3D100_mean']:
   q=op.loc[m];b[m+'_onset_k']=q.onset_k;b[m+'_onset_fraction']=q.onset_k_fraction;b[m+'_onset_reason']=q.reason
  for m in ['B8L2_mean','B8L2_p10']:
   q=mc[mc.pool_id.eq(r.pool_id)&mc.metric.eq(m)];b[m+'_MC_confirmed_k']=q.earliest_MC_upper_within_k.iloc[0] if len(q) else np.nan
  for m in ['V_floor','V_centroid_h','V_height_h','V_turn5','V_nodes']:
   q=go[go.pool_id.eq(r.pool_id)&go.metric.eq(m)].iloc[0];b[m+'_low_dispersion_onset_k']=q.onset_k;b[m+'_onset_reason']=q.reason
  for k,label in [(3,'k3'),(6,'k6'),(10,'k10'),(20,'k20'),(30,'k30'),(35,'k35'),(int(r.N),'full')]:
   if k not in p.index:continue
   b[f'{label}_k']=k;b[f'{label}_k_fraction']=k/r.N
   for m in ['B8L2_mean','B8L2_p10','B8L2_sd','B8L2_valid_n','D10_mean','IoU3D100_mean','complete_evaluable_rate','nodes_mean','turns_mean','floor_area_h2_mean','height_mean_h_mean']:
    b[f'{label}_{m}']=p.loc[k,m]
   gp=geo[geo.pool_id.eq(r.pool_id)&geo.k.eq(k)]
   for _,gr in gp.iterrows():
    b[f'{label}_{gr.metric}']=gr['mean'];b[f'{label}_{gr.metric}_valid_paths']=gr.valid_paths
  for k in [10,20,30]:
   if r.N-k<b['required_remaining_people']:continue
   z=e[e.pool_id.eq(r.pool_id)&e.k.eq(k)].set_index('metric');gz=ge[ge.pool_id.eq(r.pool_id)&ge.k.eq(k)].set_index('metric')
   cr={x:b[x] for x in ['pool_id','image','building','N','difficulty','difficulty_en','has_short']};cr.update(k=k,k_fraction=k/r.N)
   for m,lim in [('B8L2_mean',2),('B8L2_p10',2),('B8L2_sd',1),('complete_evaluable_rate',.05)]:
    v=z.loc[m,'tail_range'];ok=bool(z.loc[m,'all_future_metric_values_finite']) and z.loc[m,'tail_min_valid_paths']>=64
    cr[m+'_remaining_range']=v;cr[m+'_small']=bool(ok and v<=lim+1e-12)
   for m,lim in [('V_floor',.1),('V_centroid_h',.05),('V_height_h',.05)]:
    v=gz.loc[m,'tail_max_dispersion'];cr[m+'_remaining_max']=v;cr[m+'_low']=bool(np.isfinite(v) and v<=lim+1e-12)
   cross.append(cr)
  rows.append(b)
 d=pd.DataFrame(rows);write(d,OUT/'MANUAL_206_IMAGE_RESULTS.csv');z=pd.DataFrame(cross);write(z,OUT/'CROSS_METRIC_AT_FIXED_COUNTS.csv')
 facts=[]
 for (k,dl),g in z.groupby(['k','difficulty_en']):
  facts.append(dict(k=int(k),difficulty=dl,images=len(g),buildings=g.building.nunique(),meanQ_small=int(g.B8L2_mean_small.sum()),
   P10_small=int(g.B8L2_p10_small.sum()),SD_small=int(g.B8L2_sd_small.sum()),floor_low=int(g.V_floor_low.sum()),centroid_low=int(g.V_centroid_h_low.sum()),
   meanQ_small_but_P10_not=int((g.B8L2_mean_small&~g.B8L2_p10_small).sum()),meanQ_small_but_SD_not=int((g.B8L2_mean_small&~g.B8L2_sd_small).sum()),
   meanQ_small_but_floor_not_low=int((g.B8L2_mean_small&~g.V_floor_low).sum())))
 write(pd.DataFrame(facts),OUT/'CROSS_METRIC_SUMMARY.csv')
 # Doorway wide table uses its actual pool and target, including empty capacities.
 di=pd.read_csv(ROOT/'stage02_normalized/doorway/POOL_INDEX.csv');dc=pd.read_csv(ROOT/'stage03_response/doorway/POOL_K_STATISTICS.csv.gz');do=pd.read_csv(ROOT/'stage03_response/doorway/PLATEAU_SENSITIVITY.csv.gz');do=do[do.primary_rule]
 dg=pd.read_csv(ROOT/'stage04_geometry/doorway_exact_U/GEOMETRY_U_CURVES.csv.gz')
 rr=[]
 for _,r in di.iterrows():
  b={x:r[x] for x in ['pool_id','image','building','family','target','N','capacity_status','target_id','reference_version']};op=do[do.pool_id.eq(r.pool_id)].set_index('metric');p=dc[dc.pool_id.eq(r.pool_id)].set_index('k')
  for m in ['B8L2_mean','B8L2_p10','B8L2_sd','complete_evaluable_rate']:
   if m in op.index:b[m+'_onset_k']=op.loc[m,'onset_k'];b[m+'_onset_reason']=op.loc[m,'reason']
  for k,label in [(3,'k3'),(6,'k6'),(10,'k10'),(14,'k14'),(20,'k20'),(30,'k30'),(int(r.N),'full')]:
   if k not in p.index:continue
   b[label+'_k']=k;b[label+'_k_fraction']=k/r.N
   for m in ['B8L2_mean','B8L2_p10','B8L2_sd','B8L2_valid_n','D10_mean','IoU3D100_mean','complete_evaluable_rate']:b[label+'_'+m]=p.loc[k,m]
   gp=dg[dg.pool_id.eq(r.pool_id)&dg.k.eq(k)]
   for _,gr in gp.iterrows():
    b[f'{label}_{gr.ordinary_U_metric}']=gr['mean'];b[f'{label}_{gr.ordinary_U_metric}_valid_paths']=gr.valid_paths
  rr.append(b)
 write(pd.DataFrame(rr),OUT/'DOORWAY_85_POOL_RESULTS.csv')
 # Matching approximation is separate from Monte Carlo precision of personnel paths.
 ms=pd.read_csv(ROOT/'stage04_geometry/doorway/MATCHING_SENSITIVITY.csv.gz');mp=ms.pivot(index=['pool_id','image','domain','N','k_from','metric'],columns='matching',values='mean').reset_index();mp['absolute_matching_difference']=abs(mp[0]-mp[1]);write(mp,OUT/'DOORWAY_MATCHING_APPROXIMATION.csv.gz')
 mq=mp[mp.metric.eq('floor_distance')];summary={'manual_images':len(d),'doorway_pool_definitions':len(rr),'same_team_not_same_expression_claim':False,
  'doorway_primary_geometry_source':'stage04_geometry/doorway_exact_U/GEOMETRY_U_CURVES.csv.gz',
  'doorway_primary_geometry_method':'exact multiplicity-weighted U over all distinct saved path-index pairs, not all possible teams',
  'doorway_primary_geometry_pool_k_cells':int(dg[['pool_id','k']].drop_duplicates().shape[0]),
  'doorway_matching_diagnostics_role':'superseded approximation; retained only to explain the precision-driven all-pool exact U calculation',
  'doorway_matching_floor_cells':int(mq.absolute_matching_difference.notna().sum()),'doorway_matching_floor_difference_median':float(mq.absolute_matching_difference.median()),
  'doorway_matching_floor_difference_p90':float(mq.absolute_matching_difference.quantile(.9)),'doorway_matching_floor_difference_max':float(mq.absolute_matching_difference.max()),
  'manual_finite_geometry_cells_under_64_valid_paths':int(((geo.k>=3)&(geo.valid_paths<64)&geo['mean'].notna()).sum()),
  'cross_metric':facts}
 (OUT/'RESULT_FACTS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':main()
