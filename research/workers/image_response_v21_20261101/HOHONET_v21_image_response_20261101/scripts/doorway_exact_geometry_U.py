#!/usr/bin/env python3
"""Exact same-k U statistics over the 256 saved doorway path indices.

Not exhaustive finite-person-team enumeration. Saved repeated teams keep their
path multiplicities; distinct stored geometry states are not merged by member ID.
No new team, fusion, reference, or quality score is generated.
"""
from __future__ import annotations
import argparse,functools,gzip,hashlib,json,math,time
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import numpy as np
import pandas as pd
import doorway_geometry_response as dg
import analyze_response as ar

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'stage04_geometry/doorway_exact_U'
METRICS={'floor_distance':('1-floor IoU','V_floor'),
 'centroid_distance_h':('camera-height units','V_centroid_h'),
 'height_distance_h':('camera-height units','V_height_h'),
 'node_count_distance':('absolute node count difference','V_nodes'),
 'turn_count_distance':('absolute effective-turn count difference','V_turn5')}

@functools.lru_cache(maxsize=2)
def catalog(image):
 cat,geo,errors=dg.load_catalog(image)
 valid=~dg.shapely.is_missing(geo)
 centers=np.full((len(cat),2),np.nan)
 if valid.any():centers[valid]=dg.shapely.get_coordinates(dg.shapely.centroid(geo[valid]))
 return cat,geo,valid,centers,errors

def weighted_stats(dist,weights,zero_within,denominator):
 if denominator<=0:return dict(mean=np.nan,p10=np.nan,median=np.nan,p90=np.nan,maximum=np.nan,pair_sd_population=np.nan,zero_pair_count=0)
 d=np.r_[0.,dist];w=np.r_[zero_within,weights].astype(np.int64)
 keep=(w>0)&np.isfinite(d);d,w=d[keep],w[keep]
 assert int(w.sum())==int(denominator),(w.sum(),denominator)
 mean=float(np.dot(d,w)/denominator);s2=float(np.dot(d*d,w)/denominator)
 order=np.argsort(d);ds,ws=d[order],w[order];cw=np.cumsum(ws)
 def quantile(p):return float(ds[np.searchsorted(cw,max(1,math.ceil(p*denominator)),side='left')])
 return dict(mean=mean,p10=quantile(.1),median=quantile(.5),p90=quantile(.9),maximum=float(ds[-1]),
   pair_sd_population=math.sqrt(max(0.,s2-mean*mean)),zero_pair_count=int(w[np.abs(d)<=1e-12].sum()))

def run_pool(payload):
 row,max_k,force=payload;pid=row['pool_id'];dest=OUT/'by_pool'/pid;marker=dest/'CHECKS.json'
 path=ar.input_file(row,ROOT);source_hash=hashlib.sha256(path.read_bytes()).hexdigest()
 code_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 if not force and marker.exists():
  old=json.loads(marker.read_text())
  if old.get('source_sha256')==source_hash and old.get('code_sha256')==code_hash and old.get('maximum_k_limit')==max_k:return old
 start=time.monotonic();d=pd.read_csv(path);d=d[d.k.ge(3)]
 if max_k is not None:d=d[d.k.le(max_k)]
 meta={c:row.get(c) for c in ['pool_id','image','building','domain','family','target','N']}
 if not len(d):
  dest.mkdir(parents=True,exist_ok=True);r={**meta,'capacity_status':'no_requested_main_fusion_cells','cells':0,'rows':0,'unique_polygon_pair_evaluations':0,'elapsed_seconds':time.monotonic()-start}
  marker.write_text(json.dumps(ar.json_clean(r),ensure_ascii=False,indent=2));return r
 cat,geo,valid,centers,invalid_catalog=catalog(row['image']);lookup=cat.attrs['source_lookup']
 d['catalog_index']=lookup.reindex(d.endpoint_source_key).to_numpy();assert d.catalog_index.notna().all()
 d['catalog_index']=d.catalog_index.astype(int);rows=[];weights_saved=[];newpairs=0;cellchecks=[]
 for k,g in d.groupby('k',sort=True):
  counts=g.catalog_index.value_counts().sort_index();allids=counts.index.to_numpy(int);allw=counts.to_numpy(np.int64)
  assert int(allw.sum())==len(g)==256,(pid,k,len(g))
  for ix,w in zip(allids,allw):
   rr=cat.iloc[ix]
   weights_saved.append({**meta,'k':int(k),'catalog_index':int(ix),'geometry_key':rr.get('geometry_key'),
    'physical_team_key':rr.get('team_key'),'endpoint_source_keys':rr.get('all_endpoint_source_keys',rr.get('endpoint_source_key')),
    'path_multiplicity':int(w),'floor_valid_for_pair':bool(valid[ix])})
  keep=valid[allids];ids=allids[keep];w=allw[keep];nv=int(w.sum());i,j=np.triu_indices(len(ids),1)
  pairw=w[i]*w[j];zero=int(np.sum(w*(w-1)//2));denom=nv*(nv-1)//2
  assert int(pairw.sum())+zero==denom
  dd=np.full(len(i),np.nan)
  for lo in range(0,len(i),8192):
   hi=min(lo+8192,len(i));a=geo[ids[i[lo:hi]]];b=geo[ids[j[lo:hi]]]
   inter=dg.shapely.area(dg.shapely.intersection(a,b));union=dg.shapely.area(a)+dg.shapely.area(b)-inter
   dd[lo:hi]=np.clip(1-inter/union,0,1)
  if len(dd):assert np.isfinite(dd).all()
  newpairs+=len(i)
  metrics={'floor_distance':(dd,np.ones(len(ids),dtype=bool)),
    'centroid_distance_h':(np.linalg.norm(centers[ids[i]]-centers[ids[j]],axis=1),np.ones(len(ids),dtype=bool))}
  for src,name in [('height_mean_h','height_distance_h'),('nodes','node_count_distance'),('turns','turn_count_distance')]:
   values=pd.to_numeric(cat.iloc[ids][src],errors='coerce').to_numpy(float)
   metrics[name]=(np.abs(values[i]-values[j]),np.isfinite(values))
  for name,(dist,mvalid) in metrics.items():
   vp=int(w[mvalid].sum());metric_denom=vp*(vp-1)//2
   pw=pairw[mvalid[i]&mvalid[j]];xd=dist[mvalid[i]&mvalid[j]]
   within=int(np.sum(w[mvalid]*(w[mvalid]-1)//2));st=weighted_stats(xd,pw,within,metric_denom)
   rows.append({**meta,'k':int(k),'k_fraction':int(k)/int(row['N']),'metric':name,'ordinary_U_metric':METRICS[name][1],
     'units':METRICS[name][0],'attempted_paths':len(g),'valid_paths':vp,'valid_fraction':vp/len(g),
     'attempted_path_pairs':len(g)*(len(g)-1)//2,'valid_path_pairs':metric_denom,
     'unique_geometry_states':int(mvalid.sum()),'unique_physical_teams':cat.iloc[ids[mvalid]].team_key.nunique(),
     'within_identical_state_zero_pairs':within,'cross_distinct_state_pairs_evaluated':len(pw),
     'full_pool':int(k)==int(row['N']),'full_pool_one_physical_team':g.team_key.nunique()==1 if int(k)==int(row['N']) else False,
     'mcse':np.nan,'estimation':'exact all valid distinct saved path-index pairs; multiplicity weighted',**st})
  samephysical=cat.iloc[ids].team_key.to_numpy()[i]==cat.iloc[ids].team_key.to_numpy()[j]
  cellchecks.append(dict(k=int(k),valid_paths=nv,within_state_zero_pairs=zero,cross_state_path_pair_weight=int(pairw.sum()),
    total_valid_path_pairs=denom,unique_polygon_pairs=len(i),same_physical_team_distinct_states=int(samephysical.sum()),
    same_physical_team_nonzero_geometry_pairs=int((samephysical&(dd>1e-12)).sum())))
 dest.mkdir(parents=True,exist_ok=True)
 ar.write_csv(pd.DataFrame(rows),dest/'GEOMETRY_U_CURVES.csv.gz')
 ar.write_csv(pd.DataFrame(weights_saved),dest/'PATH_STATE_MULTIPLICITIES.csv.gz')
 ar.write_csv(pd.DataFrame(cellchecks),dest/'PAIR_DENOMINATOR_CHECKS.csv')
 r={**meta,'source':str(path.relative_to(ROOT)),'source_sha256':source_hash,'code_sha256':code_hash,'maximum_k_limit':max_k,
  'cells':int(d.k.nunique()),'rows':len(rows),'path_rows':len(d),'unique_polygon_pair_evaluations':newpairs,
  'source_eligible_but_invalid_catalog_geometries':invalid_catalog,'output_dir':str(dest.relative_to(ROOT)),
  'elapsed_seconds':time.monotonic()-start,'new_fusion':0,'new_quality_scores':0,'new_person_paths':0,
  'same_physical_team_distinct_state_nonzero_pairs':sum(x['same_physical_team_nonzero_geometry_pairs'] for x in cellchecks)}
 marker.write_text(json.dumps(ar.json_clean(r),ensure_ascii=False,indent=2,allow_nan=False));return r

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--workers',type=int,default=4);ap.add_argument('--pool-id',action='append');ap.add_argument('--max-k',type=int);ap.add_argument('--force',action='store_true');args=ap.parse_args()
 OUT.mkdir(parents=True,exist_ok=True);idx=pd.read_csv(ROOT/'stage02_normalized/doorway/POOL_INDEX.csv')
 if args.pool_id:idx=idx[idx.pool_id.isin(args.pool_id)]
 begin=time.monotonic();results=[]
 with ProcessPoolExecutor(max_workers=args.workers) as ex:
  fs=[ex.submit(run_pool,(r,args.max_k,args.force)) for r in idx.to_dict('records')]
  for f in as_completed(fs):
   r=f.result();results.append(r);print(json.dumps({k:r[k] for k in ['pool_id','cells','unique_polygon_pair_evaluations','elapsed_seconds']},ensure_ascii=False),flush=True)
 ar.write_csv(pd.DataFrame(results),OUT/'COMPUTE_ACCOUNTING.csv')
 for name in ['GEOMETRY_U_CURVES.csv.gz','PATH_STATE_MULTIPLICITIES.csv.gz']:
  parts=[pd.read_csv(ROOT/r['output_dir']/name) for r in results if r.get('output_dir')]
  ar.write_csv(pd.concat(parts,ignore_index=True) if parts else pd.DataFrame(),OUT/name)
 method={'scope':'exact U over existing 256 saved path indices for each pool/k, not exhaustive all worker-team combinations',
  'weight':'cross-state multiplicity m_i*m_j; identical-state choose(m_i,2) zero distances included',
  'denominator':'choose(metric-valid saved path count,2); no valid pair => missing, not zero',
  'geometry_identity':'catalog geometry/source state; preserve variants even if physical members match',
  'quality_geometry_missing':'geometry-valid pair denominator separate from Q availability',
  'same_k_pair_sd':'dispersion of saved path-pair distances, not a standard error; pair observations are dependent',
  'mc_precision':'no new path-Monte-Carlo interval; two prior matching runs only diagnose pairing approximation',
  'full_pool':'one physical team makes path-pair dispersion zero if geometry valid; not correctness',
  'metric_quantiles':'inverse weighted empirical CDF over all valid saved path-index pairs',
  'new_fusion':0,'new_quality_scores':0,'new_person_paths':0,'pools':len(results),'pool_k_cells':sum(r['cells'] for r in results),
  'unique_polygon_pair_evaluations':sum(r['unique_polygon_pair_evaluations'] for r in results),'elapsed_seconds':time.monotonic()-begin,
  'all_pool_run':not args.pool_id and args.max_k is None,'workers':args.workers,
  'same_physical_team_distinct_state_nonzero_pairs':sum(r.get('same_physical_team_distinct_state_nonzero_pairs',0) for r in results)}
 (OUT/'METHOD.json').write_text(json.dumps(method,ensure_ascii=False,indent=2));print('DONE '+json.dumps(method),flush=True)

if __name__=='__main__':main()
