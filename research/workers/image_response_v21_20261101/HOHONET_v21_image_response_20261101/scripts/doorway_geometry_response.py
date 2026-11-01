"""New distances on existing doorway endpoints; never recomputes fusion or Q.

Two reproducible disjoint matchings at each k retain all sampled path frequencies.
Also measures exact within-path increments and distance to the actual full team.
"""
from pathlib import Path
import sys,json,hashlib,gzip,math
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vendor'))
import shapely
from shapely.geometry import Polygon
OUT=ROOT/'stage04_geometry/doorway'
SEED=20261101

def write(df,path):
 path.parent.mkdir(parents=True,exist_ok=True)
 raw=df.to_csv(index=False).encode();b=gzip.compress(raw,mtime=0) if str(path).endswith('.gz') else raw
 tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_bytes(b);tmp.replace(path)
 if str(path).endswith('.gz'):assert gzip.decompress(path.read_bytes())==raw

def bools(s):
 return s.astype(str).str.lower().isin(['true','1','1.0']).to_numpy()

def load_catalog(image):
 file=ROOT/f'stage02_normalized/doorway_enriched/geometry/{image}.csv.gz'
 cat=pd.read_csv(file,low_memory=False);cat=cat[cat.k.ge(3)].reset_index(drop=True)
 geo=np.empty(len(cat),dtype=object);geo[:]=None
 eligible=bools(cat.geometry_eligible);errors=0
 for i,s in enumerate(cat.footprint_json):
  if not eligible[i] or not isinstance(s,str):continue
  try:
   poly=Polygon(json.loads(s))
   if poly.is_valid and poly.area>0 and not poly.is_empty:geo[i]=poly
   else:errors+=1
  except Exception:errors+=1
 cat['catalog_index']=np.arange(len(cat))
 lookup={}
 for i,r in cat.iterrows():
  for key in str(r.get('all_endpoint_source_keys',r.endpoint_source_key)).split('|'):
   assert key not in lookup or lookup[key]==i,'duplicate source endpoint identity'
   lookup[key]=i
 cat.attrs['source_lookup']=pd.Series(lookup,dtype=int)
 return cat,geo,errors

def distances(cat,geo,ka,kb):
 ix=cat.attrs['source_lookup']
 ia=ix.reindex(ka).fillna(-1).to_numpy(int);ib=ix.reindex(kb).fillna(-1).to_numpy(int)
 assert (ia>=0).all() and (ib>=0).all(),'endpoint identity not present in catalog'
 ga=geo[ia];gb=geo[ib];va=~shapely.is_missing(ga);vb=~shapely.is_missing(gb);both=va&vb
 out={'floor_a_valid':va,'floor_b_valid':vb,'floor_both_valid':both,'same_physical_team':cat.team_key.to_numpy()[ia]==cat.team_key.to_numpy()[ib]}
 floor=np.full(len(ia),np.nan);cent=np.full(len(ia),np.nan)
 if both.any():
  pa=ga[both];pb=gb[both];inter=shapely.area(shapely.intersection(pa,pb));union=shapely.area(pa)+shapely.area(pb)-inter
  floor[both]=np.clip(1-inter/union,0,1)
  cent[both]=shapely.distance(shapely.centroid(pa),shapely.centroid(pb))
 out['floor_distance']=floor;out['centroid_distance_h']=cent
 for src,dest in [('height_mean_h','height_distance_h'),('nodes','node_count_distance'),('turns','turn_count_distance')]:
  vals=pd.to_numeric(cat[src],errors='coerce').to_numpy(dtype=float);v=np.abs(vals[ia]-vals[ib]);v[~both]=np.nan;out[dest]=v
 return out

METRICS=['floor_distance','centroid_distance_h','height_distance_h','node_count_distance','turn_count_distance']

def summarize(df,meta,keys):
 rows=[]
 for key,g in df.groupby(keys,dropna=False):
  key=key if isinstance(key,tuple) else (key,)
  common={**meta,**dict(zip(keys,key)),'attempted_pairs':len(g),'unique_team_pairs':len(g[['team_a','team_b']].drop_duplicates()),
    'same_physical_team_pairs':int(g.same_physical_team.sum()),'both_floor_valid_pairs':int(g.floor_both_valid.sum()),
    'from_only_floor_valid_pairs':int((g.floor_a_valid&~g.floor_b_valid).sum()),'to_only_floor_valid_pairs':int((~g.floor_a_valid&g.floor_b_valid).sum())}
  for m in METRICS:
   x=g[m].dropna();rows.append({**common,'metric':m,'valid_pairs':len(x),'mean':x.mean(),'median':x.median(),
     'p10':x.quantile(.1),'p90':x.quantile(.9),'max':x.max(),
     'gt_0p1_rate':float((x>.1).mean()) if len(x) else np.nan,'gt_0p2_rate':float((x>.2).mean()) if len(x) else np.nan})
 return pd.DataFrame(rows)

def process_pool(row,cat,geo):
 pool=row.pool_id;N=int(row.N);dest=OUT/'by_pool'/pool;marker=dest/'CHECKS.json'
 if marker.exists():return json.loads(marker.read_text())
 d=pd.read_csv(ROOT/row.path);d=d[d.k.ge(3)].copy()
 if d.empty:
  return {'pool_id':pool,'N':N,'capacity_status':'no_fusion_main_capacity','rows':0}
 groups={int(k):g.sort_values('replicate_id').reset_index(drop=True) for k,g in d.groupby('k')}
 rows=[];meta={c:row[c] for c in ['pool_id','image','building','domain','family','target','N']}
 for k,g in groups.items():
  for matching in [0,1]:
   seed=int(hashlib.sha256(f'{SEED}|{pool}|{k}|{matching}'.encode()).hexdigest()[:16],16)
   perm=np.random.default_rng(seed).permutation(len(g));a=g.iloc[perm[::2]];b=g.iloc[perm[1::2]]
   assert len(a)==len(b)
   e=pd.DataFrame({'kind':'same_k_matching','k_from':k,'k_to':k,'k_fraction':k/N,'matching':matching,'seed':str(seed),
      'path_a':a.replicate_id.to_numpy(),'path_b':b.replicate_id.to_numpy(),'team_a':a.team_key.to_numpy(),'team_b':b.team_key.to_numpy(),
      'endpoint_a':a.endpoint_source_key.to_numpy(),'endpoint_b':b.endpoint_source_key.to_numpy(),
      **distances(cat,geo,a.endpoint_source_key.to_numpy(),b.endpoint_source_key.to_numpy())});rows.append(e)
 for step in [1,2]:
  for k in range(3,N-step+1):
   if k not in groups or k+step not in groups:continue
   a=groups[k].set_index('replicate_id');b=groups[k+step].set_index('replicate_id');ids=a.index.intersection(b.index);a=a.loc[ids];b=b.loc[ids]
   rows.append(pd.DataFrame({'kind':f'adjacent_{step}','k_from':k,'k_to':k+step,'k_fraction':k/N,'matching':-1,'seed':'frozen_existing_path',
    'path_a':ids,'path_b':ids,'team_a':a.team_key.to_numpy(),'team_b':b.team_key.to_numpy(),
    'endpoint_a':a.endpoint_source_key.to_numpy(),'endpoint_b':b.endpoint_source_key.to_numpy(),
    **distances(cat,geo,a.endpoint_source_key.to_numpy(),b.endpoint_source_key.to_numpy())}))
 full=groups.get(N)
 if full is not None:
  assert full.team_key.nunique()==1
  for k,a in groups.items():
   if k==N:continue
   kb=np.repeat(full.endpoint_source_key.iloc[0],len(a));ka=a.endpoint_source_key.to_numpy()
   rows.append(pd.DataFrame({'kind':'to_actual_full','k_from':k,'k_to':N,'k_fraction':k/N,'matching':-1,'seed':'frozen_existing_path',
    'path_a':a.replicate_id.to_numpy(),'path_b':a.replicate_id.to_numpy(),'team_a':a.team_key.to_numpy(),'team_b':np.repeat(full.team_key.iloc[0],len(a)),
    'endpoint_a':ka,'endpoint_b':kb,**distances(cat,geo,ka,kb)}))
 e=pd.concat(rows,ignore_index=True);e.insert(0,'pool_id',pool)
 s=summarize(e,meta,['kind','k_from','k_to'])
 match=summarize(e[e.kind.eq('same_k_matching')],meta,['kind','k_from','k_to','matching'])
 write(e,dest/'GEOMETRY_PAIR_EVENTS.csv.gz');write(s,dest/'GEOMETRY_PAIR_SUMMARY.csv.gz');write(match,dest/'MATCHING_SENSITIVITY.csv.gz')
 rr={'pool_id':pool,'N':N,'path_rows':len(d),'geometry_pairs':len(e),'output_dir':str(dest.relative_to(ROOT)),
   'new_fusion':0,'new_geometry_distances':len(e),'sampling_seed':SEED,'same_k_pairings':2,'source':'existing frozen endpoint geometry',
   'pair_identity_complete':True,'duplicate_teams_keep_path_frequency':True,'geometry_pairing_is_not_new_person_paths':True}
 marker.write_text(json.dumps(rr,indent=2));print(json.dumps(rr),flush=True);return rr

def main():
 OUT.mkdir(parents=True,exist_ok=True);idx=pd.read_csv(ROOT/'stage02_normalized/doorway/POOL_INDEX.csv');account=[];invalid=[]
 for image,group in idx.groupby('image'):
  path=ROOT/f'stage02_normalized/doorway_enriched/geometry/{image}.csv.gz'
  if not path.exists():continue
  cat,geo,errors=load_catalog(image);invalid.append({'image':image,'catalog_teams':len(cat),'source_eligible_but_shapely_invalid':errors})
  for _,row in group.iterrows():account.append(process_pool(row,cat,geo))
 write(pd.DataFrame(account),OUT/'COMPUTE_ACCOUNTING.csv');write(pd.DataFrame(invalid),OUT/'CATALOG_GEOMETRY_CHECK.csv')
 for name in ['GEOMETRY_PAIR_SUMMARY.csv.gz','MATCHING_SENSITIVITY.csv.gz']:
  parts=[pd.read_csv(ROOT/r['output_dir']/name) for r in account if 'output_dir' in r]
  write(pd.concat(parts,ignore_index=True) if parts else pd.DataFrame(),OUT/name)
 config={'seed':SEED,'same_k':'two independent deterministic random perfect matchings of the 256 existing path indices; all path occurrences retained',
  'same_k_estimator':'conditional mean over valid sampled pairs; matching 0/1 saved separately to assess matching approximation',
  'nested_path_steps':[1,2],'actual_full':'distance to single actual full team, not to truth; unavailable if full floor invalid',
  'distance':'1-floor IoU; centroid Euclidean distance in camera-height units; absolute height/count differences',
  'no_geometry_repair':True,'no_reference_or_fusion_changes':True,'new_person_paths':0,'new_fusion':0}
 (OUT/'METHOD.json').write_text(json.dumps(config,indent=2))
 print('DONE',len(account),len(idx),flush=True)

if __name__=='__main__':main()
