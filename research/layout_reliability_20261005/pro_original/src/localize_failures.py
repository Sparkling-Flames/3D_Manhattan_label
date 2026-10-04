"""Diagnostic only: keep every declared edge and report longitude multiplicity.
No envelope is selected and no missing part is interpolated into a full output.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from arc_consensus import pairs,TAU,W,EPS,unique_angles
from compression_study import dump
ROOT=Path(__file__).resolve().parents[1]

def branches(record):
 q=pairs(record);u=q[:,0,0]%W/W*TAU;d=(np.roll(u,-1)-u+np.pi)%TAU-np.pi;parts=[]
 for i,s in enumerate(d):
  if abs(s)<EPS or abs(s)>=np.pi-EPS:raise ValueError('degenerate_edge')
  j=(i+1)%len(q);lo,hi=(u[i],u[j]) if s>0 else (u[j],u[i])
  src={'id':record['id'],'worker':record['worker'],'pair_indices':[i,j],'source_pair_indices':[record['source_pair_indices'][i],record['source_pair_indices'][j]],'ring_confirmed':record['ring_confirmed']}
  if lo<hi:parts.append((lo,hi,src))
  else:
   parts.append((lo,TAU,src))
   if hi>0:parts.append((0.,hi,src))
 return parts

def diagnostic(records):
 parts=[branches(r) for r in records];cuts=unique_angles([0,TAU]+[v for ps in parts for lo,hi,_ in ps for v in (lo,hi)])
 bad=[];loss={r['id']:0. for r in records}
 for lo,hi in zip(cuts[:-1],cuts[1:]):
  mid=(lo+hi)/2;multi=[]
  for r,ps in zip(records,parts):
   active=[p[2] for p in ps if p[0]<=mid<p[1]]
   if len(active)!=1:
    multi.append({'id':r['id'],'worker':r['worker'],'branch_count':len(active),'declared_edges':active});loss[r['id']]+=(hi-lo)/TAU
  if multi:bad.append({'x_lo':lo/TAU*W,'x_hi':hi/TAU*W,'records':multi})
 merge=[]
 for p in bad:
  ids=[v['id'] for v in p['records']]
  if merge and abs(merge[-1]['x_hi']-p['x_lo'])<1e-8 and ids==merge[-1]['record_ids']:merge[-1]['x_hi']=p['x_hi']
  else:merge.append({'x_lo':p['x_lo'],'x_hi':p['x_hi'],'record_ids':ids})
 return dict(n=len(records),role='all-roster failure-location diagnostic only; not partial or complete fused layout',non_single_valued_longitude_share=sum((x['x_hi']-x['x_lo'])/W for x in bad),individual_shares=loss,merged_locations=merge,all_branch_intervals=bad)
if __name__=='__main__':
 rows=[]
 for p in sorted((ROOT/'inputs').glob('*.json')):
  r=json.loads(p.read_text());d=diagnostic(r['records']);dump(ROOT/'results/domain_locations'/p.name,d)
  rows.append(dict(image=r['image'],n=d['n'],non_single_valued_longitude_share=d['non_single_valued_longitude_share'],locations=json.dumps(d['merged_locations'])))
 pd.DataFrame(rows).to_csv(ROOT/'results/domain_locations/summary.csv',index=False)
 print(pd.DataFrame(rows).to_string(index=False))
