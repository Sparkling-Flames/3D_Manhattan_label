#!/usr/bin/env python3
"""Aggregate shared-target and shared-worker contrasts; no distances recomputed."""
from pathlib import Path
import pandas as pd, numpy as np
R=Path(__file__).resolve().parents[1]
d=pd.read_csv(R/'COMMON45_BASELINE_PAIRED_BY_POOL.csv.gz')
key=['method','baseline','condition','layer','subset','metric']
cols=['candidate_within','candidate_cross','candidate_gap','baseline_within','baseline_cross','baseline_gap','gap_gain']
rows=[]
for scope in ['ALL_TARGETS','primary','other_admitted']:
 a=d if scope=='ALL_TARGETS' else d[d.scope.eq(scope)]
 a=a.dropna(subset=['candidate_within','candidate_cross','baseline_within','baseline_cross'])
 im=a.groupby(key+['image_id','building'],dropna=False)[cols].mean().reset_index()
 for keys,g in im.groupby(key,dropna=False):
  b=g.groupby('building')[cols].mean()
  r=dict(zip(key,keys));r.update(scope_summary=scope,images=len(g),buildings=len(b),candidate_gap_positive_images=int(g.candidate_gap.gt(1e-12).sum()),baseline_gap_positive_images=int(g.baseline_gap.gt(1e-12).sum()),candidate_gap_larger_images=int(g.gap_gain.gt(1e-12).sum()),candidate_gap_larger_buildings=int(b.gap_gain.gt(1e-12).sum()))
  r.update({c+'_image_mean':float(g[c].mean())for c in cols});r.update({c+'_building_mean':float(b[c].mean())for c in cols});rows.append(r)
out=pd.DataFrame(rows);path=R/'COMMON45_BASELINE_PAIRED_SUMMARY.csv';tmp=path.with_name(path.name+'.writing');out.to_csv(tmp,index=False,encoding='utf-8-sig');tmp.replace(path)
print('saved',len(out),'paired aggregate rows')
view=out[(out.condition=='manual')&(out.layer=='ordinary_manual')&(out.subset=='same_corner_count')&(out.metric=='geometry_pair_angle')&(out.scope_summary=='ALL_TARGETS')&(out.method.isin(['DSTRUCT_K3','TARGET_DSTRUCT_K3','OPPSTRUCT_K3','OPPGEOM_K3','RFUSE_GEOM_K2']))]
print(view[['method','baseline','images','candidate_gap_image_mean','baseline_gap_image_mean','gap_gain_image_mean','candidate_gap_larger_images','candidate_gap_larger_buildings']].to_string(index=False))
