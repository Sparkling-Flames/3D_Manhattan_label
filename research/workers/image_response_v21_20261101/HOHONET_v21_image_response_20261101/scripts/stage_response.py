"""Locate each image's response stages, preserving direction and oscillations."""
from pathlib import Path
import pandas as pd,numpy as np,json,gzip
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'stage07_summary/response_stages'

def write(d,n):
 OUT.mkdir(parents=True,exist_ok=True);raw=d.to_csv(index=False).encode('utf-8-sig');p=OUT/n;p.write_bytes(gzip.compress(raw,mtime=0) if n.endswith('.gz') else raw)

def main():
 idx=pd.read_csv(ROOT/'stage02_normalized/manual/POOL_INDEX.csv');idx=idx[idx.domain.eq('ordinary_manual_main')]
 cols=['pool_id','image','building','domain','N','difficulty_en','k_from','k_to','interval_labels','metric','both_valid_n','mean_delta','mean_abs_delta','positive_paths','negative_paths','absolute_jump_gt5_rate']
 d=pd.read_csv(ROOT/'stage03_response/manual/PATH_CHANGE_SUMMARY.csv.gz',usecols=cols);d=d[d.domain.eq('ordinary_manual_main') & d.k_to.eq(d.k_from+1)]
 c=pd.read_csv(ROOT/'stage03_response/manual/POOL_K_STATISTICS.csv.gz',usecols=['pool_id','k','B8L2_mean','B8L2_p10','B8L2_sd','complete_evaluable_rate']);rows=[]
 for _,r in idx.iterrows():
  p=d[d.pool_id.eq(r.pool_id)];q=c[c.pool_id.eq(r.pool_id)].set_index('k')
  windows=[(3,6),(6,10),(10,20),(20,30),(30,35)]
  for a,b in windows:
   end=min(b,int(r.N))
   if end<=a:continue
   for metric in ['B8L2','D10','IoU3D100','nodes','turns','floor_area_h2','complete_evaluable']:
    g=p[p.metric.eq(metric)&p.k_from.ge(a)&p.k_to.le(end)];v=g[g.both_valid_n.ge(64)&g.mean_abs_delta.notna()]
    base={k:r[k] for k in ['pool_id','image','building','N','difficulty_en','has_short']};base.update(stage=f'{a}-{b}',k_from=a,k_to=end,planned_end=b,observed_steps=end-a,complete_fixed_stage=end==b,metric=metric,
      valid_step_n=len(v),paired_valid_path_transitions=int(v.both_valid_n.sum()),
      mean_absolute_per_addition=float(v.mean_abs_delta.mean()) if len(v) else np.nan,
      mean_signed_per_addition=float(v.mean_delta.mean()) if len(v) else np.nan,
      path_weighted_absolute_per_addition=float(np.average(v.mean_abs_delta,weights=v.both_valid_n)) if len(v) else np.nan,
      mean_jump_gt5_rate=float(v.absolute_jump_gt5_rate.mean()) if len(v) else np.nan)
    if metric=='B8L2':
     s=q.reindex(range(a,end+1)).B8L2_mean;de=s.diff().dropna();base['mean_curve_net_change']=s.iloc[-1]-s.iloc[0]
     base['mean_curve_total_variation']=de.abs().sum() if len(de)==end-a else np.nan;base['mean_curve_abs_per_addition']=de.abs().mean() if len(de) else np.nan
    rows.append(base)
 out=pd.DataFrame(rows);write(out,'IMAGE_STAGE_RESPONSES.csv.gz')
 q=out[out.metric.eq('B8L2')&out.N.ge(30)&out.planned_end.le(30)&out.complete_fixed_stage & out.valid_step_n.eq(out.observed_steps)]
 peaks=[]
 for pool,g in q.groupby('pool_id'):
  if len(g)!=4:continue
  z=g.loc[g.mean_absolute_per_addition.idxmax()];peaks.append(dict(pool_id=pool,image=z.image,building=z.building,difficulty_en=z.difficulty_en,N=z.N,dominant_stage_by_per_addition_path_change=z.stage,peak_absolute_change=z.mean_absolute_per_addition))
 peak=pd.DataFrame(peaks);write(peak,'COMMON171_DOMINANT_RESPONSE_STAGE.csv')
 agg=q.groupby(['difficulty_en','stage']).agg(images=('pool_id','size'),buildings=('building','nunique'),mean_absolute_per_addition=('mean_absolute_per_addition','mean'),median_absolute_per_addition=('mean_absolute_per_addition','median'),mean_signed_per_addition=('mean_signed_per_addition','mean'),mean_jump_gt5_rate=('mean_jump_gt5_rate','mean'),mean_curve_net_change=('mean_curve_net_change','mean'),mean_curve_total_variation=('mean_curve_total_variation','mean')).reset_index();write(agg,'COMMON171_STAGE_SUMMARY.csv')
 facts={'complete_four_stage_images':len(peak),'dominant_stage_counts':peak.dominant_stage_by_per_addition_path_change.value_counts().to_dict(),
  'definition':'stage score is mean of per-step conditional absolute within-path Q changes; equal weight to additions, not to stage length; fixed stages 3-6,6-10,10-20,20-30 on N>=30 images',
  'Q_unavailable':'separate output-state changes; no zero substitution', 'new_fusion':0}
 (OUT/'METHOD_AND_FACTS.json').write_text(json.dumps(facts,ensure_ascii=False,indent=2));print(json.dumps(facts,ensure_ascii=False))

if __name__=='__main__':main()
