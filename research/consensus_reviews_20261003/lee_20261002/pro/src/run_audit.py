"""Recompute one complete 8-person group, exhaust its subsets, and diagnose sampling.
No subjects are resampled as extra votes. Monte Carlo batches assess estimator error only.
"""
from pathlib import Path
import csv,json,sys,warnings,zlib,platform
from itertools import combinations
import numpy as np
import scipy,shapely
from shapely.geometry import Polygon, mapping
from shapely.ops import unary_union
from core import region_mesh,tile_consensus,region_iou,replay_group,METHODS
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'results'; OUT.mkdir(exist_ok=True)
def write_json(name,obj):
 (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def write_csv(name,rows):
 with (OUT/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def run():
 data=json.loads((ROOT/'inputs/subset.json').read_text());g=data['groups'][0]
 identity=dict(image=g['code'],condition=g['condition'],gate=g['gate'])
 seed=data['seed']+zlib.crc32('|'.join(identity.values()).encode())
 replay=replay_group(g,permutations=16,seed=seed)
 write_csv('replayed_16_summary.csv',replay['summary']); write_csv('replayed_16_rows.csv',replay['rows'])
 rec=sorted(g['records'],key=lambda r:r['id']);N=len(rec);gt=Polygon(g['references']['original'])
 ps=[Polygon(r['footprint']) for r in rec]; mesh=region_mesh(ps); a=mesh['area']; V=mesh['votes']; I=np.array([t.intersection(gt).area for t in mesh['tiles']])
 allstates={}; subset_rows=[]; exceptions=[]; refinement_max=0.
 # All 2^8-1 subsets, each re-tiled only from its current members.
 for k in range(1,N+1):
  for inds in combinations(range(N),k):
   with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always',RuntimeWarning)
    r=tile_consensus([rec[i] for i in inds]);counts=V[list(inds)].sum(0)
    for method in METHODS:
     geom=r['regions'][method]; selected=2*counts>=k if method=='mv50' else 2*counts>k
     fixed=unary_union([t for t,keep in zip(mesh['tiles'],selected) if keep])
     err=geom.symmetric_difference(fixed).area;refinement_max=max(refinement_max,err)
     inter=geom.intersection(gt).area;loss=(gt.area-inter)/gt.area;extra=(geom.area-inter)/gt.area
     stat=dict(method=method,k=k,members='|'.join(rec[i]['id'] for i in inds),iou=region_iou(geom,gt),area=geom.area,undercoverage_gt=loss,overcoverage_gt=extra,
               components=len(geom.geoms) if geom.geom_type=='MultiPolygon' else int(not geom.is_empty),holes=sum(len(p.interiors) for p in geom.geoms) if geom.geom_type=='MultiPolygon' else len(geom.interiors) if geom.geom_type=='Polygon' else 0)
     allstates[method,inds]=(geom,stat,selected);subset_rows.append(stat)
   exceptions.extend(str(w.message) for w in caught)
 summary=[]
 for method in METHODS:
  for k in range(1,N+1):
   states=[(key,v) for key,v in allstates.items() if key[0]==method and len(key[1])==k]
   vals=np.array([s[1][1]['iou'] for s in states]); d=[]; changes=[]
   with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always',RuntimeWarning)
    for (_,v),(_,u) in combinations(states,2): d.append(1-region_iou(v[0],u[0]))
    if k>1:
     for (meth,inds),v in states:
      for removed in inds:
       before=tuple(i for i in inds if i!=removed)
       changes.append(1-region_iou(v[0],allstates[method,before][0]))
   exceptions.extend(str(w.message) for w in caught)
   original=next(r for r in replay['summary'] if r['method']==method and r['k']==k)
   summary.append(dict(method=method,k=k,all_subsets=len(states),sampled_subsets=original['unique_subsets'],exact_mean=float(vals.mean()),sample16_mean=original['original_mean'],mean_error=original['original_mean']-float(vals.mean()),
       exact_p10=float(np.quantile(vals,.1)),exact_p90=float(np.quantile(vals,.9)),exact_member_distance=float(np.mean(d)) if d else 0.,sample16_member_distance=original['member_distance_mean'],
       exact_adjacent_change=float(np.mean(changes)) if changes else None,sample16_adjacent_change=original['change_mean']))
 write_csv('all_subsets.csv',subset_rows);write_csv('exact_vs_16.csv',summary)
 # Draw 2000 independent batches of 16 random permutations; compare the same unique-subset estimator.
 rng=np.random.default_rng(120261002);mc={key:[] for key in [(m,k) for m in METHODS for k in range(1,N+1)]}
 for batch in range(2000):
  orders=[rng.permutation(N).tolist() for _ in range(16)]
  for k in range(1,N+1):
   inds=set(tuple(sorted(o[:k])) for o in orders)
   for method in METHODS:mc[method,k].append(float(np.mean([allstates[method,x][1]['iou'] for x in inds])))
 mcrows=[]
 for (method,k),vals in mc.items():
  expected=next(s['exact_mean'] for s in summary if s['method']==method and s['k']==k)
  mcrows.append(dict(method=method,k=k,exact_mean=expected,batches=2000,mc_mean=float(np.mean(vals)),mc_sd=float(np.std(vals,ddof=1)),mc_q025=float(np.quantile(vals,.025)),mc_q975=float(np.quantile(vals,.975))))
 write_csv('sampling_error_batches.csv',mcrows)
 # Support-field squared-loss identity in the fixed GT-area normalization. This is descriptive, not a posterior.
 p=V.mean(0); sg=gt.area
 soft=(np.dot(a,p*p)-2*np.dot(I,p)+sg)/sg
 disagreement=np.dot(a,p*(1-p))/sg
 mean_hard=np.mean([(poly.symmetric_difference(gt).area)/sg for poly in ps])
 allregion={m:allstates[m,tuple(range(N))][0] for m in METHODS}
 profiles=[]
 for k in range(1,N+1):
  l=[];w=[]
  for inds in combinations(range(N),k):
   q=V[list(inds)].mean(0);l.append((np.dot(a,q*q)-2*np.dot(I,q)+sg)/sg);w.append(np.dot(a,q*(1-q))/sg)
  analytic=soft+(N-k)/(k*(N-1))*disagreement
  profiles.append(dict(k=k,expected_soft_loss=float(np.mean(l)),analytic_soft_loss=float(analytic),expected_within_prefix_disagreement=float(np.mean(w)),full_pool_disagreement=float(disagreement),finite_pool_factor=(N-k)/(k*(N-1)),expected_original_pair_disagreement=float(2*k/(k-1)*np.mean(w)) if k>1 else None))
 write_csv('support_field_finite_population.csv',profiles)
 write_json('support_field.json',dict(n=N,reference='original R02503, retained as a descriptive reference only',full_soft_squared_loss=float(soft),full_disagreement=float(disagreement),mean_individual_symmetric_difference=float(mean_hard),identity_error=float(mean_hard-soft-disagreement),full_masks={m:dict(iou=region_iou(poly,gt),undercoverage_gt=gt.difference(poly).area/sg,overcoverage_gt=poly.difference(gt).area/sg) for m,poly in allregion.items()},reference_area=sg,
      cells=[dict(area_h2=float(ar),gt_overlap_h2=float(ii),support=int(s)) for ar,ii,s in zip(a,I,V.sum(0))]))
 write_json('full_geometry.geojson',dict(type='FeatureCollection',coordinate_note='Common camera-height coordinates, not geographic coordinates',features=[dict(type='Feature',geometry=mapping(poly),properties={'method':m}) for m,poly in allregion.items()]))
 write_json('checks.json',dict(group=g['code'],records=N,reference_count=1,subsets=2**N-1,method_subsets=len(subset_rows),full_tiles=len(mesh['tiles']),refinement_max_symmetric_difference_h2=float(refinement_max),warnings_all_subset_and_pairs=exceptions,warnings_16=replay['warnings'],summary_rows=len(replay['summary']),replay_rows=len(replay['rows']),no_original_repository_test_claim=True,environment=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,shapely=shapely.__version__,geos=shapely.geos_version_string,platform=platform.platform())))
 print(json.dumps({'exact_vs16':summary,'support_field':{'soft':soft,'disagreement':disagreement,'hard_mean':mean_hard},'max_refinement':refinement_max,'warnings':len(exceptions)},indent=2))
if __name__=='__main__':run()
