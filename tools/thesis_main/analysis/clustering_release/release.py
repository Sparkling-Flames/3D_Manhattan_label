#!/usr/bin/env python3
"""Read-only clustering release candidate. No visual inference or coordinate edits.
Run from package: python code/release.py --root . [--new-responses FILE.jsonl] [--out PATH]
Frozen 2026-09-20 candidate: equal count + top/bottom cyclic order + max endpoint 9deg + complete linkage.
Controls are same measurement at 6/12deg, fixed order, bound cyclic, and old OSPA.
"""
from __future__ import annotations
import argparse,collections,csv,gzip,hashlib,itertools,json,math,sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage,fcluster
from scipy.spatial.distance import squareform
from scipy.optimize import linear_sum_assignment

CONFIG={'release':'RC1-local-20260920-v1','source_commit':'f4a6f4a3b85c08d8873c8a56066219844dc7c88b',
 'primary_metric':'split_cyclic','clustering':'complete','primary_cut_deg':9.0,'sensitivity_cut_deg':[6.0,12.0],
 'equal_total_count_gate':True,'equal_role_counts_gate':True,'coordinate_rotation':False,
 'distance_round_decimals':8,'rounding_is_not_coordinate_edit':True,'exclude_workers':['W019','W026'],
 'pointset_unavailable_is_not_singleton':True,'top_bottom_role_inference':'accepted supplied roles, otherwise horizon255.5 conditional',
 'automatic_correspondence_correction':False,'primary_manual_partial_override':False,
 'population':'frozen canonical independent initial responses per image x original condition',
 'stop_threshold':'NOT_FROZEN','window_tail_n':5,'window_min_total':8,'bootstrap_seed':20260920,
 'primary_scope':'strict equal-count annotation-expression grouping; not physical-room semantics'}

def writejson(p,x):
 def c(v):
  if isinstance(v,dict):return {str(k):c(a) for k,a in v.items()}
  if isinstance(v,(list,tuple,np.ndarray)):return [c(a) for a in v]
  if isinstance(v,(np.bool_,)):return bool(v)
  if isinstance(v,(np.integer,)):return int(v)
  if isinstance(v,(np.floating,float)):return float(v) if np.isfinite(v) else None
  if isinstance(v,Path):return str(v)
  return v
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(c(x),ensure_ascii=False,indent=2),encoding='utf-8')

def frame(out,name,rows):
 d=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
 d.to_csv(out/name,index=False,encoding='utf-8-sig',float_format='%.12g');return d

def cluster(D,t,kind='complete'):
 D=np.round(np.asarray(D,float),CONFIG['distance_round_decimals']);np.fill_diagonal(D,0)
 assert np.isfinite(D).all() and np.allclose(D,D.T)
 if len(D)<=1:return np.ones(len(D),int)
 return fcluster(linkage(squareform(D),method=kind),t,criterion='distance')

def prepare(root,new_path=None,restore_borrowed=False):
 src=root/'input/source'
 from tools.thesis_main.analysis.paired_split_research import study as st
 studyroot=src/'analysis_results/paired_split_research_received_20260920'
 inp=root/'inputs'
 rows=[json.loads(l) for l in gzip.open(inp/'responses.jsonl.gz','rt',encoding='utf-8')]
 audit=pd.read_csv(inp/'prior_response_audit.csv').set_index('id')
 approved=st.accepted_map(inp,rows)
 if new_path:
  op=gzip.open if str(new_path).endswith('.gz') else open
  with op(new_path,'rt',encoding='utf-8-sig') as f:new=[json.loads(l) for l in f if l.strip()]
  required={'canonical_annotation_id','image_id','worker_id','raw_condition','raw_points_1024x512','effective_points_1024x512','calculation_included','stage','block_index','assistance_exposure','processing_status','imputed_point','raw_point_count','effective_point_count','building_id','coordinate_width','coordinate_height','record_type'}
  for r in new:
   if not required<=r.keys():raise ValueError('Missing fields '+str(sorted(required-r.keys())))
   if not isinstance(r['worker_id'],str) or not __import__('re').fullmatch(r'W[0-9]{3,}',r['worker_id']):raise ValueError('worker_id must be a W-prefixed stable person identifier')
   if (r['coordinate_width'],r['coordinate_height'])!=(1024,512):raise ValueError('Coordinates must be explicitly converted upstream to 1024x512; retain raw export separately')
   if r['raw_condition'] not in ['manual','semi','oos']:raise ValueError('Unknown original condition; version the analysis contract')
   if not isinstance(r['calculation_included'],bool):raise ValueError('calculation_included must be boolean')
   if r['worker_id'] in CONFIG['exclude_workers']:pass # retains excluded record in audit
   if r.get('parent_annotation_id') or r.get('record_type','independent_initial')!='independent_initial':
    raise ValueError('Revisions cannot be added as independent votes; keep a separate revision file.')
   if r['canonical_annotation_id'] in {z['canonical_annotation_id'] for z in rows}:raise ValueError('Duplicate canonical ID; no overwrite allowed')
   pts=r['effective_points_1024x512'];npnt=None if pts is None else len(pts)
   if npnt!=r['effective_point_count']:raise ValueError('effective count disagrees with payload')
   if len(r['raw_points_1024x512'])!=r['raw_point_count']:raise ValueError('raw count mismatch')
   code=r.get('image_code') or next((z['code'] for z in audit.to_dict('records') if z['image_id']==r['image_id']),r['image_id'])
   audit.loc[r['canonical_annotation_id'],'code']=code
   rows.append(r)
 keys=[(r['image_id'],r['raw_condition'],r['worker_id']) for r in rows if r['worker_id'] not in CONFIG['exclude_workers']]
 if len(keys)!=len(set(keys)):raise ValueError('Repeated person/image/condition: explicitly resolve first independent response upstream; do not count twice')
 if restore_borrowed:
  rows=__import__('copy').deepcopy(rows)
  for row in rows:
   if row.get('imputed_point'):
    row['effective_points_1024x512']=row['raw_points_1024x512']
    row['effective_point_count']=row['raw_point_count']
 rec,elig=st.prepare(rows,audit,approved,'legacy_guarded',json.loads((inp/'key39_source.json').read_text()))
 # New explicit complete role arrays can be supplied upstream. No inference of individual links from cross-person anchors.
 for r in rows:
  if 'point_roles' not in r:continue
  cid=r['canonical_annotation_id']
  if cid not in rec:raise ValueError('Explicit roles currently require otherwise eligible payload; audit upstream')
  roles=r['point_roles'];p=rec[cid]['p']
  if len(roles)!=len(p) or set(roles)-{'top','bottom'}:raise ValueError('point_roles must be complete top/bottom array')
  up=np.where(np.array(roles)=='top')[0];dn=np.where(np.array(roles)=='bottom')[0]
  if not len(up) or not len(dn):raise ValueError('empty explicit role')
  rec[cid]['up']=st.order_indices(p,up);rec[cid]['dn']=st.order_indices(p,dn);rec[cid]['links']=None
  m=elig.id.eq(cid);elig.loc[m,['n_top','n_bottom']]=[len(up),len(dn)];elig.loc[m,'role_source']='upstream_explicit_role';elig.loc[m,'bound_available']=False
 for cid,a in rec.items():
  L=a['links']
  if L is not None:
   x=a['p'][L[:,0],0];y=a['p'][L[:,1],0];mid=(x+((y-x+512)%1024-512)/2)%1024
   if len(np.unique(np.round(mid,10)))<len(mid):
    a['links']=None;elig.loc[elig.id.eq(cid),'bound_available']=False;elig.loc[elig.id.eq(cid),'pairing_source']='pair_midpoint_tie_requires_review'
 return st,rows,rec,elig,studyroot

def main(root,out,new_path=None):
 out.mkdir(parents=True,exist_ok=True)
 if (root/'input')==out or (root/'input') in out.parents:raise ValueError('Output cannot overwrite inputs')
 writejson(out/'CONFIG.json',CONFIG)
 st,rows,rec,elig,sroot=prepare(root,new_path);frame(out,'eligibility.csv',elig)
 allby=collections.defaultdict(list)
 for r in rows:
  if r['worker_id'] not in CONFIG['exclude_workers']:allby[r['image_id'],r['raw_condition']].append(r)
 met=['split_cyclic','split_fixed','bound_cyclic','split_free','ospa_gate']
 pairs=[];ends=[];ords=[];members=[];summary=[];cache={};rowmap={r['canonical_annotation_id']:r for r in rows}
 # Previous OSPA is recomputed from original endpoints and checked, not silently reused as a different metric.
 for key,fullrows in sorted(allby.items()):
  rr=sorted([rec[r['canonical_annotation_id']] for r in fullrows if r['canonical_annotation_id'] in rec],key=lambda x:(x['row']['worker_id'],x['id']))
  if not rr:continue
  code=rr[0]['audit']['code'];ids=[a['id'] for a in rr];n=len(rr);D={m:np.full((n,n),181.) for m in met}
  for d in D.values():np.fill_diagonal(d,0.)
  for a in rr:
   for role,ix in [('top',a['up']),('bottom',a['dn'])]:
    for k,j in enumerate(ix):ords.append(dict(id=a['id'],code=code,condition=key[1],worker=a['row']['worker_id'],role=role,ordinal=k+1,point_index_1based=j+1,x=a['p'][j,0],y=a['p'][j,1]))
  for i,j in itertools.combinations(range(n),2):
   a,b=rr[i],rr[j];v,maps=st.compare(a,b)
   c=st.angular(a['p'],b['p']);u,w=linear_sum_assignment(np.minimum(c,30.));m1,n1=sorted(c.shape)
   ospa=(np.minimum(c,30.)[u,w].sum()+30*(n1-m1))/n1
   base=dict(code=code,image_id=key[0],condition=key[1],id_a=a['id'],id_b=b['id'],worker_a=a['row']['worker_id'],worker_b=b['row']['worker_id'],count_a=len(a['p']),count_b=len(b['p']))
   p={**base,**v,'ospa1':ospa,'ospa_gate':ospa if len(a['p'])==len(b['p']) else 181.}
   for m in met:
    val=p.get(m)
    if val is not None:D[m][i,j]=D[m][j,i]=val
   pairs.append(p)
   for m in ['split_cyclic','split_fixed','bound_cyclic','split_free']:
    for role in ['top','bottom']:
     if m+'_'+role not in maps:continue
     aa,bb=maps[m+'_'+role];es=np.diag(st.angular(a['p'][aa],b['p'][bb]))
     for k,(u,v1,e) in enumerate(zip(aa,bb,es)):
      ends.append(dict(**base,metric=m,role=role,ordinal_a=k+1,point_a=int(u)+1,point_b=int(v1)+1,error_deg=float(e),x_a=a['p'][u,0],y_a=a['p'][u,1],x_b=b['p'][v1,0],y_b=b['p'][v1,1]))
  for m in met:
   ix=np.array([i for i,a in enumerate(rr) if a['links'] is not None],int) if m=='bound_cyclic' else np.arange(n)
   if not len(ix):continue
   dm=D[m][np.ix_(ix,ix)];kk=[6.] if m=='ospa_gate' else ([9.] if m in ['split_free','bound_cyclic'] else [6.,9.,12.])
   for t in kk:
    lab=cluster(dm,t);near=np.round(dm,8)<=t;same=lab[:,None]==lab[None,:];tri=np.triu_indices(len(lab),1)
    s=st.stats(lab);groups=collections.Counter(lab)
    summary.append(dict(code=code,image_id=key[0],condition=key[1],metric=m,cut=t,N_record=len(fullrows),N_eligible=len(ix),N_unavailable=len(fullrows)-len(ix),**s,
     near_pairs=int(near[tri].sum()),near_separated=int((near[tri]&~same[tri]).sum()),within_incompatible=int((same[tri]&~near[tri]).sum())))
    reps={l:int(z[np.argmin(np.round(dm[np.ix_(z,z)].sum(1),8))]) for l in groups for z in [np.flatnonzero(lab==l)]}
    for k,i in enumerate(ix):
     l=lab[k];gidx=np.where(lab==l)[0];signature=hashlib.sha256('|'.join(sorted(ids[ix[z]] for z in gidx)).encode()).hexdigest()[:12]
     members.append(dict(code=code,image_id=key[0],condition=key[1],stage=rr[i]['row']['stage'],id=ids[i],worker=rr[i]['row']['worker_id'],metric=m,cut=t,cluster=int(l),cluster_version_hash=signature,cluster_size=int(groups[l]),count=len(rr[i]['p']),close_neighbors=int(near[k].sum()-1),representative_id=ids[ix[reps[l]]]))
  cache['|'.join(key)]={'code':code,'ids':ids,'workers':[a['row']['worker_id'] for a in rr],'building':fullrows[0].get('building_id',key[0].split('_')[0]),'N_record':len(fullrows),'counts':[len(a['p']) for a in rr],'bound_indices':[i for i,a in enumerate(rr) if a['links'] is not None],'matrices':{m:d.tolist() for m,d in D.items()}}
 frame(out,'pairwise.csv',pairs);frame(out,'point_ordinals.csv',ords);frame(out,'memberships.csv',members);frame(out,'group_summary.csv',summary)
 pd.DataFrame(ends).to_csv(out/'endpoint_correspondences.csv.gz',index=False,compression={'method':'gzip','mtime':0},float_format='%.12g')
 writejson(out/'cache.json',cache)
 # Direct paired vs primary common cohort diagnostic and parameter/tie sensitivity.
 cc=[]
 for key,g in cache.items():
  ix=g['bound_indices'];A=np.array(g['matrices']['split_cyclic'])[np.ix_(ix,ix)];B=np.array(g['matrices']['bound_cyclic'])[np.ix_(ix,ix)]
  if not len(ix):continue
  la=cluster(A,9);lb=cluster(B,9);tri=np.triu_indices(len(ix),1)
  cc.append(dict(key=key,code=g['code'],N=len(ix),different_scores=int((np.abs(A-B)>1e-7)[tri].sum()),relations_changed=int(((la[:,None]==la[None,:])!=(lb[:,None]==lb[None,:]))[tri].sum())))
 frame(out,'binding_common_comparison.csv',cc)
 # Snapshot provenance and comparability; new datasets are not forced to match old counts.
 writejson(out/'SCOPE.json',{'raw_records':len(rows),'excluded':int(elig.excluded_worker.sum()),'eligible_split':int(elig.split_available.sum()),'eligible_bound':int(elig.bound_available.sum()),'units':len(cache),'images':len({k.split('|')[0] for k in cache}),'pair_rows':len(pairs),'endpoint_rows':len(ends),'no_new_visual_review':True,'original_coordinates_modified':False,'input_sha256':hashlib.sha256((root/'inputs/responses.jsonl.gz').read_bytes()).hexdigest(),'new_responses_path':str(new_path) if new_path else None})
 return st,rows,rec,elig,cache

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--out',type=Path);ap.add_argument('--new-responses',type=Path);a=ap.parse_args();main(a.root.resolve(),a.out or a.root/'results/release',a.new_responses)
