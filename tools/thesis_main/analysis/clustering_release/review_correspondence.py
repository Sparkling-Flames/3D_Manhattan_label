#!/usr/bin/env python3
"""Validate supplied endpoint correspondences as a sidecar; NEVER auto-merge clusters.
Example: python code/review_correspondence.py --root . --review reviewed.csv --out review_result
Only status=confirmed rows are evaluated. Point indices are one-based.
A full distance is emitted only when both role mappings cover both submissions bijectively.
"""
from pathlib import Path
import argparse,collections,hashlib,json
import numpy as np,pandas as pd
from .release import prepare,frame,writejson

def pointsha(p):return hashlib.sha256(json.dumps(np.asarray(p).tolist(),separators=(',',':')).encode()).hexdigest()

def validate(root,review,out):
 out.mkdir(parents=True,exist_ok=True);st,rows,rec,elig,_=prepare(root);d=pd.read_csv(review,keep_default_na=False)
 required={'image_id','condition','id_a','id_b','role','point_a_1based','point_b_1based','status','reviewer','evidence_source','point_payload_sha_a','point_payload_sha_b'}
 if not required<=set(d):raise ValueError('Missing review fields: '+str(required-set(d)))
 accepted=[];parent={}
 def find(x):
  parent.setdefault(x,x)
  if parent[x]!=x:parent[x]=find(parent[x])
  return parent[x]
 for _,r in d.iterrows():
  if r.status!='confirmed':continue
  if r.id_a not in rec or r.id_b not in rec:raise ValueError('Unavailable ID; roles must be reviewed upstream')
  a,b=rec[r.id_a],rec[r.id_b]
  if not r.reviewer or not r.evidence_source:raise ValueError('Confirmed rows require author and source')
  if r.point_payload_sha_a!=pointsha(a['p']) or r.point_payload_sha_b!=pointsha(b['p']):raise ValueError('Point version SHA mismatch')
  if any(z['row']['image_id']!=r.image_id or z['row']['raw_condition']!=r.condition for z in [a,b]):raise ValueError('Cross-image/condition correspondence rejected')
  u=int(r.point_a_1based)-1;v=int(r.point_b_1based)-1;role=r.role
  if role not in ['top','bottom']:raise ValueError('role must be top/bottom')
  ix='up' if role=='top' else 'dn'
  if u not in a[ix] or v not in b[ix]:raise ValueError('Role mismatch; record a role review first')
  parent[find((r.id_a,u))]=find((r.id_b,v))
  err=float(st.angular(a['p'][[u]],b['p'][[v]])[0,0]);accepted.append(r.to_dict()|dict(error_deg=err))
 # Detect mutually inconsistent assertions across multiple people; no automatic propagation.
 components=collections.defaultdict(list)
 for x in list(parent):components[find(x)].append(x)
 conflicts=[dict(component=str(k),points=json.dumps(v),reason='same_annotation_multiple_distinct_points_equated') for k,v in components.items() if len({a for a,b in v})<len(v)]
 frame(out,'conflicts.csv',conflicts)
 if conflicts:raise ValueError('Correspondence conflicts; see conflicts.csv. No changes applied.')
 a=pd.DataFrame(accepted);frame(out,'confirmed_endpoint_residuals.csv',a);s=[]
 if not a.empty:
  for (i,j),g in a.groupby(['id_a','id_b']):
   complete=True
   for role,ix in [('top','up'),('bottom','dn')]:
    z=g[g.role==role];left=(z.point_a_1based.astype(int)-1).tolist();right=(z.point_b_1based.astype(int)-1).tolist()
    if len(set(left))!=len(left) or len(set(right))!=len(right):raise ValueError('Non-bijective supplied mapping')
    complete &= set(left)==set(rec[i][ix]) and set(right)==set(rec[j][ix])
   s.append(dict(id_a=i,id_b=j,confirmed_rows=len(g),complete_mapping=complete,max_confirmed_residual=g.error_deg.max(),full_correspondence_distance=g.error_deg.max() if complete else np.nan,original_coordinates_modified=False,cluster_override_applied=False))
 frame(out,'mapping_summary.csv',s);writejson(out/'STATUS.json',{'sidecar_only':True,'automatic_cluster_updates':False,'confirmation_does_not_imply_same_cluster':True})

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--review',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();validate(a.root,a.review,a.out)
