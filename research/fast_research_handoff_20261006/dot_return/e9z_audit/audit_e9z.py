"""Read-only independent e9z audit. Writes only to its own output directory.
Run: python oct6-e9z-audit/audit_e9z.py
Geometry and clustering independently implemented from the declared formulas.
"""
import json, math, hashlib, argparse
from pathlib import Path
from itertools import combinations
import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
from shapely.geometry import Polygon

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--handoff',type=Path,default=Path(__file__).resolve().parent.parent/'oct6-handoff-intake')
parser.add_argument('--out',type=Path,default=Path(__file__).resolve().parent)
args=parser.parse_args()
ROOT=args.handoff.resolve(); OUT=args.out.resolve(); OUT.mkdir(parents=True,exist_ok=True)
D=json.loads((ROOT/'inputs.json').read_text())
image=next(im for im in D['images'] if im['image']=='e9zR4mvMWw7-15')
records=image['records']
initial=json.dumps(records,sort_keys=True)

def ray(points):
 p=np.asarray(points,float)
 lon=2*np.pi*(p[...,0]/1024-.5); lat=np.pi*(.5-p[...,1]/512)
 return np.stack([np.cos(lat)*np.sin(lon),np.sin(lat),-np.cos(lat)*np.cos(lon)],axis=-1)
def angle(points):
 r=ray(points); return np.rad2deg(np.arccos(np.clip(r@r.T,-1,1)))
def floor(points):
 p=np.asarray(points,float).reshape(-1,2,2)[:,1]; lon=2*np.pi*(p[:,0]/1024-.5)
 radius=1/np.tan(np.pi*(p[:,1]/512-.5))
 return np.stack([radius*np.sin(lon),-radius*np.cos(lon)],axis=1)
def scores(points,ref):
 a,b=Polygon(floor(points)),Polygon(floor(ref))
 return dict(iou=a.intersection(b).area/a.union(b).area,omission_h2=b.difference(a).area,extension_h2=a.difference(b).area,candidate_area_h2=a.area,reference_area_h2=b.area,centroid_distance_h=a.centroid.distance(b.centroid))
def cluster(rs,t,side='paired'):
 nodes=[dict(id=r['id'],worker=r['worker'],pair_index=i,source_pair_index=r['source_pair_indices'][i],points=p) for r in rs for i,p in enumerate(np.asarray(r['points']).reshape(-1,2,2).tolist())]
 nodes.sort(key=lambda v:(str(v['worker']),str(v['id']),v['points'][0][0]%1024,v['points'][0][1],v['points'][1][1],v['pair_index']))
 p=np.array([v['points'] for v in nodes]); td=angle(p[:,0]); bd=angle(p[:,1]); pd=np.maximum(td,bd)
 ds=(pd if side=='paired' else td if side=='top' else bd).copy()
 for i,a in enumerate(nodes):
  for j,b in enumerate(nodes):
   if a['worker']==b['worker']: ds[i,j]=181
 np.fill_diagonal(ds,0)
 labels=fcluster(linkage(squareform(ds,checks=False),method='complete'),t,criterion='distance')
 groups=[]
 for lab in sorted(set(labels),key=lambda l:np.flatnonzero(labels==l)[0]):
  inds=np.flatnonzero(labels==lab); medoid=int(inds[np.argmin(pd[np.ix_(inds,inds)].sum(axis=1))]); x0=p[medoid,0,0]
  x=float((x0+np.median((p[inds,0,0]-x0+512)%1024-512))%1024)
  center=[[x,float(np.median(p[inds,0,1]))],[x,float(np.median(p[inds,1,1]))]]
  groups.append(dict(members=[nodes[i] for i in inds],support=len(inds),selected=len(inds)>=math.ceil(len(rs)/2),center=center,diameter_paired_deg=float(pd[np.ix_(inds,inds)].max()),diameter_top_deg=float(td[np.ix_(inds,inds)].max()),diameter_bottom_deg=float(bd[np.ix_(inds,inds)].max())))
 selected=sorted([g for g in groups if g['selected']],key=lambda g:g['center'][0][0]); points=[p for g in selected for p in g['center']]
 return dict(groups=groups,selected_groups=selected,points=points,pair_count=len(selected),minimum_support=math.ceil(len(rs)/2))

right=[];left=[]
for r in records:
 for i,p in enumerate(np.array(r['points']).reshape(-1,2,2)):
  if p[0,0]>1000: right.append(dict(id=r['id'],worker=r['worker'],pair_index=i,source_pair_index=r['source_pair_indices'][i],points=p.tolist()))
  if p[0,0]<10: left.append(dict(id=r['id'],worker=r['worker'],pair_index=i,source_pair_index=r['source_pair_indices'][i],points=p.tolist()))
assert len(right)==8 and len({r['id'] for r in right})==8
rp=np.array([r['points'] for r in right])
outputs={f'{side}_{t}':cluster(records,t,side) for side in ('paired','top') for t in (5,9,12)}
# Independently created candidates serialized before loading evaluation references.
(OUT/'e9z_candidates_before_evaluation.json').write_text(json.dumps(outputs,indent=2))
refdata=json.loads((ROOT/'evaluation/references.json').read_text())
ref=next(r for im in refdata['images'] if im['image']==image['image'] for r in im['references'] if r['version']=='original')
p12=outputs['paired_12']['points']; deleted=np.array(p12).reshape(-1,2,2)[1:].reshape(-1,2).tolist()
rscores={k:scores(v['points'],ref['points']) for k,v in outputs.items()}
rscores['paired_12_delete_user_rejected_left']=scores(deleted,ref['points'])
A,B=Polygon(floor(p12)),Polygon(floor(deleted)); GT=Polygon(floor(ref['points']))
removed=A.difference(B);added=B.difference(A)
comp=dict(removed_area_h2=removed.area,added_area_h2=added.area,removed_inside_reference_h2=removed.intersection(GT).area,removed_outside_reference_h2=removed.difference(GT).area,removed_inside_reference_fraction=removed.intersection(GT).area/removed.area)
subsets=[]
for omitted in records:
 c=cluster([r for r in records if r['id']!=omitted['id']],5)
 subsets.append(dict(omitted=omitted['id'],pair_count=c['pair_count'],minimum_support=c['minimum_support'],selected_member_ids=[[m['id'] for m in g['members']] for g in c['selected_groups']]))
assert all(s['pair_count']==3 for s in subsets)
# Verify independent members and centers against frozen baseline, not execution of source code.
baselines=json.loads((ROOT/'baselines.json').read_text())['states'];checks=[]
for key,v in outputs.items():
 side,t=key.split('_');route='top_anchor' if side=='top' else 'paired'
 b=next(s['result'] for s in baselines if s['image']==image['image'] and s['route']==route and s['threshold_deg']==int(t))
 def sig(g):return tuple(sorted((m['id'],m['pair_index']) for m in g['members']))
 obs={sig(g):g for g in v['groups']};frozen={sig(g):g for g in b['identity_groups']}
 assert set(obs)==set(frozen)
 err=max(np.max(np.abs(np.array(obs[s]['center'])-frozen[s]['center'])) for s in obs)
 assert err<1e-9
 checks.append(dict(route=route,threshold_deg=int(t),independent_memberships_equal=True,max_center_error_px=float(err)))
# Vertical range is conditional on shared x and camera-height-one floor model.
range_examples=[]
for label,points in [('reference',ref['points']),('paired_12',p12),('top_5',outputs['top_5']['points'])]:
 p=next(p for p in np.array(points).reshape(-1,2,2) if p[0,0]>1000)
 b=p[1]; r=1/np.tan(np.pi*(b[1]/512-.5))
 range_examples.append(dict(label=label,x=float(b[0]),bottom_y=float(b[1]),floor_radius_h=float(r),floor_xz=floor(p).tolist()[0]))
assert json.dumps(records,sort_keys=True)==initial
result=dict(schema='independent_e9z_audit_v1',source=str(ROOT),input_sha256=hashlib.sha256((ROOT/'inputs.json').read_bytes()).hexdigest(),source_unmodified=True,threshold_policy='existing comparison thresholds, not calibrated',right_observations=right,left_observations=left,right_angle_max_deg=dict(top=float(angle(rp[:,0]).max()),bottom=float(angle(rp[:,1]).max())),right_group_support_5=[g['support'] for g in outputs['paired_5']['groups'] if any(m['points'][0][0]>1000 for m in g['members'])],all_seven_person_subsets=subsets,independent_baseline_checks=checks,range_scores=rscores,compensation=comp,range_examples=range_examples,manual_delete_points=deleted,reference=ref)
(OUT/'e9z_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({k:result[k] for k in ('right_angle_max_deg','right_group_support_5','independent_baseline_checks','range_scores','compensation','range_examples')},indent=2))
print('Right and left seam memberships:')
for k,v in outputs.items():
 print(k,[(g['support'],g['center'],[(m['id'],m['pair_index'],'R' if m['points'][0][0]>1000 else 'L') for m in g['members']]) for g in v['groups'] if any(m['points'][0][0]>1000 or m['points'][0][0]<10 for m in g['members'])])
