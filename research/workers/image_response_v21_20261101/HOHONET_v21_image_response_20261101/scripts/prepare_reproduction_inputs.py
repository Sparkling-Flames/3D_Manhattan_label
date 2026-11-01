"""Lossless analysis-column projection of normalized paths; sources stay intact."""
from pathlib import Path
import pandas as pd,numpy as np,gzip,hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reproduction_inputs'
KEEP=['pool_id','image','building','condition','domain','family','target','target_id','reference_id','reference_version','N','difficulty','difficulty_en',
 'k','k_fraction','replicate_id','origin_stratum','team_key','member_object_ids','member_workers','endpoint_source_key','endpoint_source_path','endpoint_source_line','endpoint_source_kind',
 'B8L2','D10','IoU3D100','complete_output','complete_evaluable','status_class','quality_valid','geometry_formed','complete_floor_evaluable',
 'actual_consensus_failure','output_generated_unscoreable','nodes','turns','short_turn_edges','short_edges_03_h','floor_area_h2','height_mean_h',
 'centroid_x_h','centroid_z_h','S_bottom_deg','dir','Hmean','Hcenter','omission','extension','iou_2d','B8_floor_block','B8_direction_block',
 'B8_global_height_block','B8_local_height_block','B8_height_block','D10_direction_block','geometry_eligible','geometry_key','minimum_support',
 'node_supports','node_supports_json','below_four','connection_available','score_status','geometry_status','policy_deferred']

def write(d,p):
 p.parent.mkdir(parents=True,exist_ok=True);b=d.to_csv(index=False).encode('utf-8-sig');p.write_bytes(gzip.compress(b,compresslevel=6,mtime=0) if str(p).endswith('.gz') else b)
 if str(p).endswith('.gz'):assert gzip.decompress(p.read_bytes())==b

def main():
 receipts=[]
 for mode,base in [('manual','stage02_normalized/manual'),('doorway','stage02_normalized/doorway'),('doorway_enriched','stage02_normalized/doorway_enriched')]:
  index=pd.read_csv(ROOT/base/'POOL_INDEX.csv');index=index.drop(columns=['absolute_file','absolute_path'],errors='ignore')
  for i,r in index.iterrows():
   rel=r.get('normalized_file',r.get('path'))
   if not isinstance(rel,str):raise RuntimeError('no portable input path')
   src=ROOT/rel;d=pd.read_csv(src,low_memory=False);d=d[[c for c in KEEP if c in d]];dest=OUT/rel;write(d,dest)
   newsha=hashlib.sha256(dest.read_bytes()).hexdigest();oldsha=hashlib.sha256(src.read_bytes()).hexdigest()
   receipts.append(dict(domain=mode,pool_id=r.pool_id,path=rel,rows=len(d),columns=len(d.columns),bytes=dest.stat().st_size,sha256=newsha,upstream_normalized_sha256=oldsha,projection='kept required analysis columns and all exact member identities'))
   if 'normalization_sha256' in index:index.loc[i,'upstream_normalization_sha256']=r.normalization_sha256;index.loc[i,'normalization_sha256']=newsha
  write(index,OUT/base/'POOL_INDEX.csv')
  print(mode,len(index),flush=True)
 # Necessary compact frozen metadata and existing precision/geometry inputs.
 selected=[
 'source/repo/research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json',
 'source/repo/research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json',
 'source/repo/research/data/releases/v2.1/natural_results/NATURAL_CURVE_BANDS.csv.gz',
 'source/repo/research/data/releases/v2.1/new_space_geometry/NEW_SPACE_GEOMETRY_CURVES.csv.gz',
 'source/repo/research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/analysis_geometry26/results_stage2/GEOMETRY_PATH_PRECISION.csv.gz',
 'source/repo/research/data/doorway_review_20261030/screen439_results_20261031/BASE_256_ORDERS.csv.gz']
 for rel in selected:
  s=ROOT/rel
  if s.exists():(OUT/rel).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(s,OUT/rel)
 write(pd.DataFrame(receipts),OUT/'INPUT_PROJECTION_MANIFEST.csv')
 (OUT/'INPUT_SCOPE.json').write_text(json.dumps({'purpose':'reproduce statistics from frozen existing endpoints; no claim to bundle all raw panorama images or all full fusion states','columns':'redundant aliases and source-history columns omitted; exact team identities and all used numbers/states preserved','frozen_source_commit':'e1873bfadc1d0e61499809c91fba9dc39c717f83','endpoint_table_files':len(receipts),'rows':sum(r['rows'] for r in receipts),'bytes':sum(r['bytes'] for r in receipts),'inner_gzip_complete_readback':True},indent=2))
 print(json.dumps({'files':len(receipts),'rows':sum(r['rows'] for r in receipts),'bytes':sum(r['bytes'] for r in receipts)}),flush=True)

if __name__=='__main__':main()
