#!/usr/bin/env python3
"""Saved reference short-span values kept continuous, no outcome-based bins."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
import analyze_response as ar

ROOT=Path(__file__).resolve().parents[1]

def main():
 out=ROOT/'stage07_summary/manual';removed=[]
 # Targeted migration of an initial display grouping. Other strata, estimates,
 # and all individual values are unchanged. Future summaries use corrected code.
 for name in ['FIXED_PANEL_CURVES.csv.gz','FIXED_PANEL_CHANGE_SUMMARY.csv.gz','ONSET_STRATA.csv']:
  p=out/name;d=pd.read_csv(p);bad=d.stratum_dimension.eq('conditional_short_span')
  if bad.any():
   removed.append(dict(table=name,prior_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),removed_rows=int(bad.sum()),retained_rows=int((~bad).sum())))
   ar.write_csv(d[~bad],p)
 idx=pd.read_csv(ROOT/'stage02_normalized/manual/POOL_INDEX.csv');idx=idx[idx.domain.eq('ordinary_manual_main')]
 fields=['pool_id','image','building','N','difficulty_en','has_short','conditional_short_span','ref_short_min_horizontal_deg','ref_turn5']
 ar.write_csv(idx[fields],out/'CONTINUOUS_STRUCTURE_INPUT.csv')
 changes=pd.read_csv(out/'PER_IMAGE_MARGINAL_CHANGES.csv.gz');changes=changes[changes.pool_id.isin(idx.pool_id)]
 changes=changes.merge(idx[['pool_id','has_short','conditional_short_span']],on='pool_id',validate='many_to_one')
 # Restrict span association to images with a short edge; 0 for no-short is an
 # encoding of structural absence, not an actual zero angular span.
 short=changes[changes.has_short.eq(1)&changes.conditional_short_span.notna()]
 rows=[];image_rows=[]
 for panelN,windows in [(20,['fixed_3_to_6','fixed_6_to_10','fixed_10_to_20']),(30,['fixed_3_to_6','fixed_6_to_10','fixed_10_to_20','fixed_20_to_30']),(35,['fixed_20_to_30','fixed_30_to_35'])]:
  dd=short[short.N.ge(panelN)&short.window.isin(windows)&short.metric.isin(['B8L2_mean','B8L2_p10','B8L2_sd','complete_evaluable_rate'])]
  for (window,metric),g in dd.groupby(['window','metric']):
   g=g[g.delta.notna()].copy()
   for c in ['delta','abs_delta']:
    leave=[]
    for b in g.building.unique():
     x=g[g.building.ne(b)]
     if len(x)>=3 and x[c].nunique()>1 and x.conditional_short_span.nunique()>1:leave.append(x.conditional_short_span.corr(x[c],method='spearman'))
    rho=g.conditional_short_span.corr(g[c],method='spearman') if len(g)>=3 and g[c].nunique()>1 else np.nan
    rows.append(dict(panel_min_N=panelN,window=window,metric=metric,response=c,images=len(g),buildings=g.building.nunique(),
       spearman_rho=rho,leave_one_building_rho_min=min(leave) if leave else np.nan,leave_one_building_rho_max=max(leave) if leave else np.nan,
       span_min=g.conditional_short_span.min(),span_max=g.conditional_short_span.max(),
       interpretation='within has_short=1; descriptive association of frozen angle with response, no new difficulty categories'))
   z=g.copy();z['panel_min_N']=panelN;image_rows.append(z)
 ar.write_csv(pd.DataFrame(rows),out/'CONTINUOUS_SHORT_SPAN_ASSOCIATION.csv')
 ar.write_csv(pd.concat(image_rows,ignore_index=True),out/'CONTINUOUS_SHORT_SPAN_IMAGE_VALUES.csv.gz')
 method={'feature':'conditional_short_span=ref_short_min_horizontal_deg.fillna(0)',
  'source':'frozen v2.1 computable geometry; angular degrees, not a binary category',
  'has_short':'ref_short_edges>0; used separately as a binary structural condition',
  'continuous_association':'Spearman correlation only among has_short=1, fixed capacity panels; leave-one-building ranges are sensitivity, not confidence intervals',
  'no_difficulty_relabeling':True,'corrected_initial_categorical_display_rows':removed,'new_fusion':False}
 (out/'CONTINUOUS_STRUCTURE_METHOD.json').write_text(json.dumps(method,ensure_ascii=False,indent=2))
 print(json.dumps({'short_images':int(idx.has_short.eq(1).sum()),'association_rows':len(rows),'migrated_tables':len(removed)}),flush=True)

if __name__=='__main__':main()
