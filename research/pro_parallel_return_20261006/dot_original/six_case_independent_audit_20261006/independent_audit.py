"""Independent bounded audit; never imports study code or alters the source.
Usage: python independent_audit.py --study extracted/panorama_parallel_results_20261006 --out independent
The consensus check is an at-least-j coverage recurrence, independent of author's tile polygonization.
"""
import argparse,json,hashlib,math,csv,time
from pathlib import Path
from itertools import combinations
from collections import Counter
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import Polygon,GeometryCollection,shape,LineString
from shapely.ops import unary_union
from shapely.affinity import rotate

CODES=['x8F5xyUWy9e-01','x8F5xyUWy9e-09','uNb9QFRL6hY-47','jtcxE69GiFV-12','rPc6DW4iMge-06','yqstnuAEVhm-32']
def write_json(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2))
def metric(a,g):
 o=g.difference(a).area;e=a.difference(g).area;i=a.intersection(g).area
 return dict(iou=i/a.union(g).area,omission_h2=o,extension_h2=e,omission_ref=o/g.area,extension_ref=e/g.area,error_ref=(o+e)/g.area,ref_area_h2=g.area,area_h2=a.area)
def at_least_coverage(polys):
 layers=[]
 for p in polys:
  old=layers
  layers=[old[0].union(p) if old else p]
  for j in range(1,len(old)+1):
   inherited=old[j] if j<len(old) else GeometryCollection()
   layers.append(inherited.union(old[j-1].intersection(p)))
 return layers

def main(study,out):
 out.mkdir(parents=True,exist_ok=True);t=time.time()
 src=study/'inputs';rd=study/'results';data=json.loads((src/'cases.json').read_text());ims={x['code']:x for x in data['images']}
 saved={(f['properties']['image'],f['properties']['method']):f for f in json.loads((rd/'full_consensus.geojson').read_text())['features']}
 ends=pd.read_csv(rd/'endpoint_metrics.csv');published_pairs=pd.read_csv(rd/'pairwise_distances.csv');published_local=pd.read_csv(rd/'local_diagnostics.csv')
 result={'methods':'independent >=j coverage recurrence, direct set area, direct projection equations, exact all-pair enumeration; no imported study code','source_cases_sha256':hashlib.sha256((src/'cases.json').read_bytes()).hexdigest(),'versions':{'numpy':np.__version__,'shapely':shapely.__version__,'pandas':pd.__version__},'images':[]};allworkers=set();preserved=included=0;geocheck=[];metcheck=[];localcheck=[];person=[];projection=[];paircheck=[];sampling=[];countstats=[]
 specs=json.loads((study/'evidence/local_spec.json').read_text())
 for code in CODES:
  im=ims[code];gate='stable_nonorthogonal_separate' if code.startswith('x8') else 'main_candidate'
  recs=[r for r in im['annotations'] if r['condition']=='manual' and r['independent'] and r['consensus_eligible'] and r['main_consensus_gate']['status']==gate]
  n=len(recs);preserved+=len(im['annotations']);included+=n;allworkers.update(r['worker'] for r in recs)
  assert len({r['worker'] for r in recs})==n and len({r['id'] for r in recs})==n
  polys=[Polygon(r['footprint']) for r in recs];U=unary_union(polys)
  assert all(p.is_valid and p.area>0 for p in polys)
  for r in recs+im['references']:
   q=np.asarray(r['points']).reshape(-1,2,2);theta=2*np.pi*(q[:,1,0]/1024-.5);phi=np.pi*(.5-q[:,1,1]/512)
   f=np.c_[-np.cos(phi)*np.sin(theta)/np.sin(phi),np.cos(phi)*np.cos(theta)/np.sin(phi)]
   delta=np.max(abs(f-np.asarray(r['footprint'])));dx=np.max(abs((q[:,0,0]-q[:,1,0]+512)%1024-512))
   projection.append(dict(image=code,record=r['id'],max_coordinate_error_h=float(delta),max_shared_x_difference_C=float(dx),ring_confirmed=r['ring_confirmed'],order_used=r['order_used']))
  layers=at_least_coverage(polys)
  mean_d=[];ious=[];max_pair_err=0
  for i,j in combinations(range(n),2):
   a,b=polys[i],polys[j];d=a.symmetric_difference(b).area;mean_d.append(d/U.area);ious.append(a.intersection(b).area/a.union(b).area)
   p=published_pairs[(published_pairs.image==code)&(published_pairs.worker_a==recs[i]['worker'])&(published_pairs.worker_b==recs[j]['worker'])]
   if len(p)==0:p=published_pairs[(published_pairs.image==code)&(published_pairs.worker_b==recs[i]['worker'])&(published_pairs.worker_a==recs[j]['worker'])]
   assert len(p)==1
   for k,v in [('distance_h2',d),('distance_union',d/U.area)]:max_pair_err=max(max_pair_err,abs(float(p.iloc[0][k])-v))
  paircheck.append(dict(image=code,n=n,pairs=len(mean_d),union_area_h2=U.area,R=float(np.mean(mean_d)),pair_iou_median=float(np.median(ious)),max_published_pair_error=max_pair_err))
  result['images'].append(dict(image=code,n=n,preserved=len(im['annotations']),room=im['room'],building=im['building'],ring_status=dict(Counter(r['order_used'] for r in recs)),ring_confirmed_count=sum(r['ring_confirmed'] for r in recs),primary_quality_status=dict(Counter(r['main_quality_gate']['status'] for r in recs))))
  for method,k in [('mv50',(n+1)//2),('mv_strict',n//2+1)]:
   g=layers[k-1];f=saved[code,method];s=shape(f['geometry']);props=f['properties']
   assert props['records']==[r['id'] for r in recs] and props['workers']==[r['worker'] for r in recs] and props['n']==n and props['threshold']==k
   geocheck.append(dict(image=code,method=method,n=n,threshold=k,area_h2=g.area,geom_type=g.geom_type,valid=g.is_valid,holes=len(g.interiors) if g.geom_type=='Polygon' else None,symdiff_h2=g.symmetric_difference(s).area,hausdorff_h=g.hausdorff_distance(s)))
   for ref in im['references']:
    G=Polygon(ref['footprint']);m=metric(g,G);r=ends[(ends.image==code)&(ends.method==method)&(ends.version==ref['version'])];assert len(r)==1
    err=max(abs(float(r.iloc[0][name])-v) for name,v in m.items());ind=[metric(a,G) for a in polys]
    metcheck.append(dict(image=code,method=method,version=ref['version'],n=n,**m,individual_mean_omission_ref=float(np.mean([x['omission_ref'] for x in ind])),individual_mean_extension_ref=float(np.mean([x['extension_ref'] for x in ind])),individual_mean_error_ref=float(np.mean([x['error_ref'] for x in ind])),published_endpoint_max_abs_error=err,published_individual_D_abs_error=abs(np.mean([x['error_ref'] for x in ind])-r.iloc[0].individual_mean_error_ref)))
   if code in specs:
    sp=specs[code];r=next(r for r in recs if r['id']==sp['id']);points=np.asarray(r['footprint']);pinds=sp['indices'] if code.startswith('rPc') else [10,11,12];patch=Polygon(points[pinds]);A=Polygon(points);path=LineString(points[sp['indices']])
    for name,h in [(method,g)]+([(ref['version'],Polygon(ref['footprint'])) for ref in im['references']] if method=='mv50' else []):
     pp=published_local[(published_local.image==code)&(published_local.object==name)].iloc[0];c=patch.intersection(h).area/patch.area
     localcheck.append(dict(image=code,object=name,source_record=r['id'],patch_area_h2=patch.area,patch_gt_fraction=patch.area/Polygon(im['references'][0]['footprint']).area,source_covers_fraction=patch.intersection(A).area/patch.area,coverage_fraction=c,published_coverage_abs_error=abs(c-pp.patch_covered_fraction),local_omission_h2=patch.intersection(A).difference(h).area,local_extension_h2=patch.intersection(h).difference(A).area))
     for q in [512,8192]:
      dd=[path.interpolate((i+.5)/q,normalized=True).distance(h.boundary) for i in range(q)]
      sampling.append(dict(image=code,object=name,n=q,mean_h=float(np.mean(dd)),p95_h=float(np.quantile(dd,.95)),sampled_max_h=float(max(dd)),error_bound_max_h=path.length/(2*q)))
    if method=='mv50':
     fs=[]
     for rr,a in zip(recs,polys):
      c=patch.intersection(a).area/patch.area;fs.append(c);person.append(dict(image=code,record=rr['id'],patch_fraction=c))
     countstats.append(dict(image=code,n=n,near_zero=sum(x<.05 for x in fs),intermediate=sum(.05<=x<=.95 for x in fs),near_one=sum(x>.95 for x in fs),warning='Coverage fractions are not votes for matched structural identity'))
  print('DONE',code,'n',n,'elapsed',time.time()-t,flush=True)
 a,b=[Polygon(r['footprint']) for r in ims['uNb9QFRL6hY-47']['references']];m=shape(saved['uNb9QFRL6hY-47','mv50']['geometry'])
 ii=lambda x,y:x.intersection(y).area/x.union(y).area
 result['uNb_fixed_90_diagnostic']={'raw_original_vs_revision':ii(a,b),'rotated_original_vs_revision':ii(rotate(a,90,origin=(0,0)),b),'raw_original_vs_mv50':ii(a,m),'rotated_original_vs_mv50':ii(rotate(a,90,origin=(0,0)),m),'not_used_as_reference':True}
 result.update(preserved_records=preserved,included_records=included,unique_people=len(allworkers),all_pair_count=sum(r['pairs'] for r in paircheck),four_special_pair_count=sum(r['pairs'] for r in paircheck[:4]),six_images_five_buildings=len({ims[c]['building'] for c in CODES}),elapsed_seconds=time.time()-t)
 for name,rows in [('consensus_checks',geocheck),('endpoint_checks',metcheck),('projection_checks',projection),('pair_checks',paircheck),('local_checks',localcheck),('local_person',person),('path_sampling',sampling),('local_coverage_summary',countstats)]:pd.DataFrame(rows).to_csv(out/(name+'.csv'),index=False)
 result['checks']={'max_consensus_symdiff_h2':max(x['symdiff_h2'] for x in geocheck),'max_endpoint_error':max(x['published_endpoint_max_abs_error'] for x in metcheck),'max_individual_D_error':max(x['published_individual_D_abs_error'] for x in metcheck),'max_projection_coordinate_error_h':max(x['max_coordinate_error_h'] for x in projection),'max_pair_error':max(x['max_published_pair_error'] for x in paircheck),'max_local_fraction_error':max(x['published_coverage_abs_error'] for x in localcheck)}
 assert preserved == 118 and included == 109 and len(allworkers) == 24
 assert result['all_pair_count'] == 1127 and result['four_special_pair_count'] == 575
 assert all(v < 1e-9 for v in result['checks'].values()), result['checks']
 result['all_assertions_passed'] = True
 write_json(out/'audit_summary.json',result)
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--study',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.study,a.out)
