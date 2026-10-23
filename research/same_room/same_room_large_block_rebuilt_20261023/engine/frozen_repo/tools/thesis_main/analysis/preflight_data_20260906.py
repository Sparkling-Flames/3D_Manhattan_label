"""Raw-coordinate, source-audited inputs for retrospective preflight 20260906.
No historical eligibility or current-roster global filter is applied.
"""
from pathlib import Path
from collections import defaultdict
import sys,json,hashlib
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.quality_core.choice_parser import extract_data
from tools.thesis_main.analysis import audit_annotation_research_data_20260905 as old
SUB=ROOT/'analysis_results/uncertainty_substrate_20260823_v1'
OUT=ROOT/'analysis_results/preflight_20260906_v2'
CURRENT=np.array([1,2,6,8,10,11,12,13,15,17,*range(28,38)])
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,rows):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
 (rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)).to_csv(p,index=False,float_format='%.12g',compression={'method':'gzip','mtime':0} if str(p).endswith('.gz') else None)
def read(name): return pd.read_csv(SUB/name,keep_default_na=False)
def distance_matrix(dense):
 tops=np.stack([x[0] for x in dense]);bots=np.stack([x[1] for x in dense])
 n=len(tops); out=np.zeros((n,n))
 for j in range(n):
  inter=np.maximum(0,np.minimum(bots,bots[j])-np.maximum(tops,tops[j])+1).sum(axis=1)
  union=(bots-tops+1).sum(axis=1)+(bots[j]-tops[j]+1).sum()-inter
  out[j]=1-inter/union
 return out

def load():
 OUT.mkdir(parents=True,exist_ok=True)
 spine=read('annotation_spine.csv'); geometries=read('geometry_variants.csv')
 raw=geometries[geometries.variant=='raw'].set_index('canonical_annotation_id')
 normalized=geometries[geometries.variant=='strict_normalized'].set_index('canonical_annotation_id')
 sources={}; indices={}; audits=[]; rows=[]
 for path,group in spine.groupby('raw_export_path'):
  p=ROOT/path;digest=sha(p)
  assert set(group.raw_export_sha256)=={digest},f'source SHA mismatch {path}'
  data=json.loads(p.read_text(encoding='utf-8-sig'));index={}
  for t in data:
   for a in t.get('annotations',[]):
    w=a.get('completed_by');w=w.get('id',w.get('pk')) if isinstance(w,dict) else w
    key=(int(a.get('task',t['id'])),int(w),int(a['id']))
    assert key not in index, f'duplicate raw identity {path} {key}'
    index[key]=(t,a)
  indices[path]=index;sources[path]=digest
 for s in spine.to_dict('records'):
  key=(int(s['runtime_task_id']),int(s['worker_id']),int(s['raw_annotation_id']))
  t,a=indices[s['raw_export_path']][key]
  points,*_=extract_data(a.get('result',[]));points=np.asarray(points,dtype=float).reshape(-1,2)
  canonical=s['canonical_annotation_id']; archived=np.asarray(json.loads(raw.loc[canonical,'points_json']),dtype=float).reshape(-1,2)
  assert points.shape==archived.shape and np.allclose(points,archived,atol=1e-8,rtol=0),canonical
  first=normalize_geometry(points)
  # Match the published strict geometry pairwise path: canonical serialization is reparsed.
  norm=normalize_geometry(first['canonical_points']) if first['valid'] else first
  published_valid=str(normalized.loc[canonical,'strict_valid']).lower()=='true'
  audits.append(dict(canonical_annotation_id=canonical,source=s['raw_export_path'],raw_coordinates_match=True,
                     first_strict_valid=first['valid'],second_strict_valid=norm['valid'],archived_strict_valid=published_valid,
                     reason=norm['reason']))
  row=dict(s);row.update(context='|'.join(map(str,[s['stage'],s['block_index'],s['raw_condition'],s['base_task_id']])),condition=s['raw_condition'],
                        valid=bool(norm['valid']),first_valid=bool(first['valid']),corners=norm['n_pairs'] if norm['valid'] else np.nan)
  if norm['valid']:
   row['dense']=old._dense_boundaries(norm['pairs']);row['pairs']=norm['pairs'];row['points']=norm['canonical_points']
  rows.append(row)
 evidence=pd.read_csv(ROOT/'analysis_results/annotation_research_prework_20260905_v2/evidence/record_evidence.csv',keep_default_na=False).set_index('canonical_annotation_id')
 refs=old._load_gt_pairs()
 for row in rows:
  e=evidence.loc[row['canonical_annotation_id']];row['time_status']=e.active_time_owner_valid_status
  row['time']=float(e.active_time_seconds) if str(e.active_time_seconds) not in ('','nan') else np.nan
  row['reference_status']=refs.get(row['base_task_id'],{}).get('reference_status','missing')
  row['reference_source']=refs.get(row['base_task_id'],{}).get('source','')
  row['reference_distance']=np.nan
  if row['valid'] and row['base_task_id'] in refs:
   row['reference_distance']=old._d_mask(row['dense'],old._dense_boundaries(refs[row['base_task_id']]['pairs']))
 groups={}
 for key,group in pd.DataFrame(rows).groupby('context',sort=True):
  group=group.sort_values('worker_id');valid=group[group.valid]
  assert valid.worker_id.nunique()==len(valid),(key,'duplicate worker in context')
  if len(valid)<2:continue
  rr=valid.to_dict('records');first=rr[0];D=distance_matrix([r['dense'] for r in rr]);n=len(rr)
  groups[key]=dict(context=key,image=first['base_task_id'],building=first['building_id'],stage=first['stage'],condition=first['condition'],
                   n=n,workers=np.array([int(r['worker_id']) for r in rr]),corners=np.array([r['corners'] for r in rr]),
                   D=D,rows=rr,reference=np.array([r['reference_distance'] for r in rr]),
                   n_raw=len(group),D_mean=D.sum()/(n*(n-1)))
 save('raw_coordinate_audit.csv',audits);save('source_manifest.csv',[dict(path=k,sha256=v) for k,v in sources.items()])
 save('record_inventory.csv',[{k:v for k,v in r.items() if k not in ('dense','pairs','points')} for r in rows])
 modelpath=ROOT/'analysis_results/annotation_research_decision_audit_20260905_v1/data_audit/geometry_comparisons.csv'
 comparisons=pd.read_csv(modelpath,keep_default_na=False)
 model_names=['bilayout_enclosed_extended','hohonet_bilayout_enclosed','hohonet_bilayout_extended']
 model=comparisons[comparisons.comparison.isin(model_names)].pivot_table(index='base_task_id',columns='comparison',values='d_mask',aggfunc='first')
 for g in groups.values():
  g['models']=[float(model.loc[g['image'],c]) if g['image'] in model.index and c in model.columns else np.nan for c in model_names]
 save('model_feature_source.csv',[dict(path=str(modelpath.relative_to(ROOT)),sha256=sha(modelpath),role='archived_machine_only_distances_not_rerun_inference')])
 save('task_inventory.csv',[{k:v for k,v in g.items() if k not in ('rows','D','corners','workers','reference','models')} | dict(n_current20=int(np.isin(g['workers'],CURRENT).sum())) for g in groups.values()])
 (OUT/'RAW_QA.json').write_text(json.dumps(dict(input_rows=len(rows),first_strict=sum(r['first_valid'] for r in rows),strict_rows=sum(r['valid'] for r in rows),
  images=spine.base_task_id.nunique(),workers=spine.worker_id.nunique(),source_count=len(sources),raw_matched=len(audits),
  dense20=sum(g['n']>=20 for g in groups.values()),source_commit='851a54694483bd73bacff228bb8cec18ff161c13',
  mode='fresh_recomputation_reuses_existing_normalizer',eligibility_global_filter=False),indent=2))
 return rows,groups,refs
if __name__=='__main__':
 r,g,f=load();print((OUT/'RAW_QA.json').read_text())
