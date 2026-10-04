from pathlib import Path
import json, sys, hashlib, csv
import numpy as np
from arc_consensus import *
ROOT=Path(__file__).resolve().parents[1]

def main():
 out=ROOT/'results/construction';out.mkdir(parents=True,exist_ok=True)
 rows=[];checks=[]
 expected={'2t7WUuJeko7-06':'ca532c9a723ac6f2d6e0338d272de535528a8558','7y3sRwLe3Va-04':'1e03b76d492c33c7c764156fb4ac5556d150cdf9','rPc6DW4iMge-06':'7db75a7bd2066e1753d8475b8f0a43949d7fbf52','uNb9QFRL6hY-67':'3527a7335389336bc0bc16805f4a4dfe89e65285'}
 for image,sha in expected.items():
  b=(ROOT/'inputs'/f'{image}.json').read_bytes(); got=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest(); assert got==sha
  p=json.loads(b);records=p['records'];result=fuse(records)
  (out/f'{image}_exact.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
  diagnostics=[]
  for r in records:
   status='ok';reason=None
   try: rr=Ring(r)
   except Unsupported as e:status='unsupported';reason=str(e)
   f,A=footprint(r)
   q=np.asarray(r['points']).reshape(-1,2,2);x=q[:,0,0]%W; d=(np.roll(x,-1)-x+W/2)%W-W/2
   signs=np.sign(d);orientation=int(np.sign(d.sum()))
   back=[dict(pair_indices=[i,(i+1)%len(q)],x_start=float(x[i]),x_end=float(x[(i+1)%len(q)]),signed_short_span_px=float(d[i]),source_pair_indices=[r['source_pair_indices'][i],r['source_pair_indices'][(i+1)%len(q)]]) for i in range(len(q)) if signs[i]!=orientation]
   diagnostics.append(dict(id=r['id'],worker=r['worker'],ring_confirmed=r['ring_confirmed'],pair_count=len(q),arc_status=status,reason=reason,bev_valid=A.is_valid,bev_area=A.area,backtracking_edges=back))
  L=tile_vote(records,(len(records)+1)//2)
  from shapely.geometry import mapping
  (out/f'{image}_lee.json').write_text(json.dumps(dict(image=image,n=len(records),threshold=(len(records)+1)//2,geometry=mapping(L),area=L.area,valid=L.is_valid,geometry_type=L.geom_type,gt_used=False)))
  diag=dict(image=image,n=len(records),record_ids=[r['id'] for r in records],workers=[r['worker'] for r in records],diagnostics=diagnostics,arc_status=result['status'],lee_status='ok',method_failures_are_not_exclusions=True)
  (out/f'{image}_domain.json').write_text(json.dumps(diag,ensure_ascii=False,indent=2))
  check=dict(image=image,n=len(records),blob_matches_current_handoff=True,arc_status=result['status'],arc_individual_pass=sum(d['arc_status']=='ok' for d in diagnostics),failures=result['failures'],lee_status='ok',lee_area=L.area)
  if result.get('methods'):
   exact=result['methods'][result['bev_mv50_complete_method']];_,A=footprint(exact)
   check.update(exact_pairs=exact['pair_count'],lee_symmetric_difference_h2=A.symmetric_difference(L).area,serialization_error_px=exact['max_serialization_error_px'])
  checks.append(check); rows.extend(dict(image=image,**r) for r in diagnostics)
  print(image,check,flush=True)
 (ROOT/'results/input_and_domain_checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
 with (ROOT/'results/complete_roster.csv').open('w',newline='') as f:
  fields=['image','id','worker','ring_confirmed','pair_count','arc_status','reason','bev_valid','bev_area']
  w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
if __name__=='__main__':main()
