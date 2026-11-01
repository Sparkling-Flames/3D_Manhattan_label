#!/usr/bin/env python3
"""Affected downstream component/descriptor calculations from saved endpoints.

No new fusion or quality scoring. Missing named loss blocks are algebraic
projections of the frozen score inputs, checked against the retained scores.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, math
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import numpy as np
import pandas as pd
import analyze_response as ar

ROOT=Path(__file__).resolve().parents[1]
FORMULA_FILE=ROOT/'stage00_manual_sources/repo/research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/engine26/derive_frozen_blocks.py'
spec=importlib.util.spec_from_file_location('frozen_blocks',FORMULA_FILE);blocks=importlib.util.module_from_spec(spec);spec.loader.exec_module(blocks)
LOSS=['B8_floor_block','B8_direction_block','B8_global_height_block','B8_local_height_block','B8_height_block','D10_direction_block']
ERRORS=['iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension']
GEOMETRY=['nodes','turns','short_turn_edges','short_edges_03_h','floor_area_h2','height_mean_h','centroid_x_h','centroid_z_h']
METRICS=LOSS+ERRORS+GEOMETRY
STATES=['complete_evaluable','geometry_formed','actual_consensus_failure','output_generated_unscoreable','complete_floor_evaluable']

def worker(args):
 row,mode,out=args;source=ar.input_file(row,ROOT);d=pd.read_csv(source,low_memory=False);meta=ar.get_meta(row,d)
 if not len(d):return {'pool_id':row['pool_id'],'mode':mode,'empty':True,'path_rows':0,'formula_checked_n':0,'max_B8_formula_residual':None,'output_dir':None}
 d=blocks.add_blocks_frame(d,check_existing=True)
 checked=pd.to_numeric(d.get('B8_formula_residual'),errors='coerce');main=d.k.ge(3)
 maxres=float(checked[main].abs().max()) if checked[main].notna().any() else np.nan
 assert not np.isfinite(maxres) or maxres<1e-7,(row['pool_id'],'retained Q disagrees',maxres)
 d=d[main].copy()
 for c in METRICS:
  if c not in d:d[c]=np.nan
  d[c]=pd.to_numeric(d[c],errors='coerce')
 for c in STATES:
  if c not in d:d[c]=np.nan
  d[c]=ar.as_bool(d[c])
 qgate=d.complete_evaluable.eq(1)&np.isfinite(pd.to_numeric(d.B8L2,errors='coerce'))
 gg=ar.as_bool(d.geometry_eligible).eq(1) if 'geometry_eligible' in d else qgate
 d.loc[~qgate,LOSS+ERRORS]=np.nan
 d.loc[~gg,GEOMETRY]=np.nan
 curves=[];states=[];changes=[]
 for k,g in d.groupby('k'):
  r={**meta,'k':int(k),'k_fraction':k/meta['N'],'path_rows':len(g),'unique_teams':g.team_key.nunique()}
  for metric in METRICS:
   st=ar.finite_stats(g[metric]);r.update({metric+'_'+key:value for key,value in st.items()})
  for metric in STATES:
   x=g[metric].dropna();r[metric+'_valid_n']=len(x);r[metric+'_rate']=x.mean() if len(x) else np.nan
  curves.append(r)
  for name,n in g.status_class.fillna('not_classified').value_counts().items():states.append({**meta,'k':k,'status_class':name,'path_n':int(n),'attempted_paths':len(g),'rate':n/len(g)})
 groups={int(k):g.set_index('replicate_id') for k,g in d.groupby('k')}
 for (ka,kb),labels in ar.pair_design(meta['N']).items():
  is_fixed=any(x.startswith('fixed_') or x=='own_last5_to_full' for x in labels)
  if not is_fixed and not (mode=='doorway_enriched' and any(x.startswith('adjacent_') for x in labels)):continue
  if ka not in groups or kb not in groups:continue
  a,b=groups[ka],groups[kb];ids=a.index.intersection(b.index);a,b=a.loc[ids],b.loc[ids]
  for metric in METRICS:
   av=a[metric].to_numpy(float);bv=b[metric].to_numpy(float);both=np.isfinite(av)&np.isfinite(bv);x=bv[both]-av[both]
   changes.append({**meta,'k_from':ka,'k_to':kb,'interval_labels':'|'.join(sorted(labels)),'metric':metric,
     'attempted_path_pairs':len(ids),'both_valid_n':int(both.sum()),'from_only_valid_n':int((np.isfinite(av)&~np.isfinite(bv)).sum()),
     'to_only_valid_n':int((~np.isfinite(av)&np.isfinite(bv)).sum()),'neither_valid_n':int((~np.isfinite(av)&~np.isfinite(bv)).sum()),
     'paired_from_mean':av[both].mean() if len(x) else np.nan,'paired_to_mean':bv[both].mean() if len(x) else np.nan,
     'mean_delta':x.mean() if len(x) else np.nan,'mean_abs_delta':np.abs(x).mean() if len(x) else np.nan,
     'median_delta':np.median(x) if len(x) else np.nan,'positive_paths':int((x>ar.TOL).sum()),'negative_paths':int((x<-ar.TOL).sum()),
     'unchanged_paths':int((np.abs(x)<=ar.TOL).sum()),'metric_semantics':'dimensionless loss; lower better; not additive Q points' if metric in LOSS else 'saved scalar descriptor'})
 dest=out/'by_pool'/row['pool_id'];dest.mkdir(parents=True,exist_ok=True)
 for name,vals in [('COMPONENTS_BY_K.csv.gz',curves),('COMPONENT_PATH_CHANGES.csv.gz',changes),('NATIVE_STATUS_BY_K.csv.gz',states)]:ar.write_csv(pd.DataFrame(vals),dest/name)
 result={**meta,'mode':mode,'empty':False,'path_rows':len(d),'formula_checked_n':int(checked[main].notna().sum()),
   'max_B8_formula_residual':maxres,'output_dir':str(dest.relative_to(ROOT)),
   'source':str(source.relative_to(ROOT)),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
   'new_fusion':False,'new_quality_scores':False}
 (dest/'COMPLETION.json').write_text(json.dumps(ar.json_clean(result),ensure_ascii=False,indent=2,allow_nan=False));return result

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--workers',type=int,default=2);args=ap.parse_args()
 out=ROOT/'stage04_components';out.mkdir(exist_ok=True)
 jobs=[]
 for mode in ['manual','doorway_enriched']:
  idx=pd.read_csv(ROOT/'stage02_normalized'/mode/'POOL_INDEX.csv')
  if mode=='manual':idx=idx[idx.domain.eq('ordinary_manual_main')]
  for row in idx.to_dict('records'):jobs.append((row,mode,out))
 results=[]
 with ProcessPoolExecutor(max_workers=args.workers) as ex:
  futures=[ex.submit(worker,x) for x in jobs]
  for f in as_completed(futures):
   r=f.result();results.append(r)
   if len(results)%20==0:print(json.dumps({'done':len(results),'total':len(jobs)}),flush=True)
 ar.write_csv(pd.DataFrame(results),out/'COMPONENT_INPUT_INDEX.csv')
 for name in ['COMPONENTS_BY_K.csv.gz','COMPONENT_PATH_CHANGES.csv.gz','NATIVE_STATUS_BY_K.csv.gz']:
  parts=[]
  for r in results:
   if r['empty']:continue
   try:d=pd.read_csv(ROOT/r['output_dir']/name,low_memory=False)
   except pd.errors.EmptyDataError:continue
   parts.append(d)
  ar.write_csv(pd.concat(parts,ignore_index=True),out/name)
 method={'formula':'B8L2=100/(1+hypot(F,D8)+Hg+Hl)',
  'F':'1/IoU2D-1+S_bottom_deg^2/32','D8':'1.5*dir_deg^2/(dir_deg^2+64)',
  'Hg':'(Hmean/0.8)^2','Hl':'(Hcenter/0.25)^2','D10_direction':'1.5*dir_deg^2/(dir_deg^2+100)',
  'units':'dimensionless losses, lower is better; block changes are not additive Q points',
  'aggregation':'retain path frequencies; mean of Q not Q of mean blocks',
  'formula_source':str(FORMULA_FILE.relative_to(ROOT)),'formula_source_sha256':hashlib.sha256(FORMULA_FILE.read_bytes()).hexdigest(),
  'pooled_max_B8_formula_residual':max([r['max_B8_formula_residual'] for r in results if r['max_B8_formula_residual'] is not None and np.isfinite(r['max_B8_formula_residual'])]),
  'formula_checked_path_rows':sum(r['formula_checked_n'] for r in results),'source_pools':len(results),
  'quality_component_gate':'complete_evaluable=1 and finite retained B8L2',
  'geometry_gate':'doorway geometry_eligible; ordinary complete_evaluable',
  'empty_pools':sum(r['empty'] for r in results),'new_fusion':False,'new_quality_scores':False}
 (out/'METHOD.json').write_text(json.dumps(ar.json_clean(method),ensure_ascii=False,indent=2,allow_nan=False))
 print(json.dumps(method,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
