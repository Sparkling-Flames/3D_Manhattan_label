"""Paired corners vs separately x-ordered top/bottom corners.

Read-only, equal-total-count partition experiment. Inputs retain raw/effective points.
Primary: fixed x order, seam x=0, endpoint-wise maximum spherical error.
Sensitivity: cyclic index changes ONLY (no coordinate rotation); free bottleneck matching.
Pair associations: accepted user candidates when supplied; otherwise a retained
legacy association checked for opposite-role endpoints (not semantic confirmation).
A separate sensitivity uses minimum wrapped horizontal assignment with inherited 51.2px bound.
Unconfirmed associations are not physical truth. No worker weights, scale learning or
silently imputed points. Outputs always carry source point indices (one-based).
"""
from __future__ import annotations
import argparse,collections,csv,gzip,hashlib,itertools,json,math,platform
from pathlib import Path
import numpy as np
import pandas as pd
import scipy
from scipy.optimize import linear_sum_assignment
from scipy.cluster.hierarchy import linkage,fcluster
from scipy.spatial.distance import squareform

ROOT=Path(__file__).resolve().parents[4]/'analysis_results/paired_split_research_received_20260920'
CUTS=(3.,6.,9.,12.)
METRICS=('split_fixed','bound_fixed','split_cyclic','bound_cyclic','split_free','bound_free','top_fixed','bottom_fixed')
BLOCK=181.0 # incompatible input signature, never an observed endpoint error

def dump(p,x):
 def clean(v):
  if isinstance(v,dict): return {str(k):clean(a) for k,a in v.items()}
  if isinstance(v,(list,tuple,np.ndarray)): return [clean(a) for a in v]
  if isinstance(v,(np.integer,)):return int(v)
  if isinstance(v,(np.bool_,)):return bool(v)
  if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
  return v
 p.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2),encoding='utf-8')

def angular(a,b):
 a=np.asarray(a,float);b=np.asarray(b,float)
 du=((a[:,None,0]-b[None,:,0]+512.)%1024.-512.)*(2*np.pi/1024.)
 va=((a[:,1]+.5)/512.-.5)*np.pi;vb=((b[:,1]+.5)/512.-.5)*np.pi
 h=np.sin((va[:,None]-vb[None,:])/2.)**2+np.cos(va[:,None])*np.cos(vb[None,:])*np.sin(du/2.)**2
 h=np.clip(h,0.,1.)
 return np.degrees(2*np.arctan2(np.sqrt(h),np.sqrt(1-h)))

def order_indices(p,ix,seam=0.):
 ix=np.asarray(ix,int)
 return ix[np.lexsort((ix,p[ix,1],(p[ix,0]-seam)%1024.))]

def pair_order(p,links,seam=0.):
 links=np.asarray(links,int)
 mids=(p[links[:,0],0]+((p[links[:,1],0]-p[links[:,0],0]+512)%1024-512)/2)%1024
 return links[np.lexsort((links[:,1],links[:,0],(mids-seam)%1024))]

def accepted_map(inp,rows):
 by={r['canonical_annotation_id']:r for r in rows}
 dec=json.loads((inp/'user_six_review.json').read_text(encoding='utf-8-sig'))['decisions']
 ev=json.loads((inp/'pilot_evidence.json').read_text(encoding='utf-8'));out={}
 for e in ev:
  d=dec[e['key']]
  if d['defer']:continue
  for side in ['a','b']:
   if d['Pair'+side.upper()]!='接受当前候选':continue
   cid=e['id_'+side];r=by[cid]
   assert np.array_equal(r['effective_points_1024x512'],e['points_'+side])
   links=np.array(e['candidates_'+side][d[side+'_candidate']]['pairs'],int)-1
   assert sorted(links.flatten())==list(range(r['effective_point_count']))
   out[cid]=links
 return out

def infer_links(p,up,dn):
 if len(up)!=len(dn):return None,'unbalanced_top_bottom',{}
 if len(up)==0:return None,'empty_role',{}
 dx=abs((p[up,None,0]-p[dn,0][None,:]+512)%1024-512)
 cost=np.where(dx<51.2,dx,1e9)
 i,j=linear_sum_assignment(cost)
 if np.max(cost[i,j])>=1e9:return None,'no_pairing_within_inherited_x_bound',{}
 best=float(cost[i,j].sum());second=np.inf
 for u,v in zip(i,j):
  q=cost.copy();q[u,v]=1e9;ii,jj=linear_sum_assignment(q)
  if np.max(q[ii,jj])<1e9:second=min(second,float(q[ii,jj].sum()))
 meta={'pair_cost_px':best,'second_pair_cost_px':second,'pair_margin_px':second-best}
 if second-best<1e-8:return None,'ambiguous_horizontal_assignment',meta
 return np.column_stack([up[i],dn[j]]),'conditional_unique_x_assignment',meta

def prepare(rows,audit,approved,association='legacy_guarded',key39=None):
 rec={};ar=[]
 if association=='legacy_guarded':
  from . import legacy_helpers as legacy
  ns=legacy.legacy_functions(key39 if key39 is not None else json.loads((ROOT/'inputs/key39_source.json').read_text(encoding='utf-8')))
 for r in rows:
  cid=r['canonical_annotation_id'];excluded=r['worker_id'] in {'W019','W026'}
  p=np.asarray(r['effective_points_1024x512'],float)
  good=(not excluded and bool(r['calculation_included']) and p.ndim==2 and p.shape[1:]==(2,) and len(p)>0
    and np.isfinite(p).all() and np.all(p>=0) and np.all(p[:,0]<=1024) and np.all(p[:,1]<512))
  z={'id':cid,'code':audit.loc[cid,'code'],'image_id':r['image_id'],'worker':r['worker_id'],'condition':r['raw_condition'],
   'stage':r['stage'],'block':r['block_index'],'exposure':r['assistance_exposure'],'excluded_worker':excluded,
   'pointset_available':good,'raw_count':r['raw_point_count'],'effective_count':r['effective_point_count'],
   'processing_status':r['processing_status'],'imputed_point':r['imputed_point'],'split_available':False,'bound_available':False}
  if not good:z['role_source']='not_pointset_eligible';ar.append(z);continue
  if cid in approved:
   links=approved[cid];up=links[:,0];dn=links[:,1]
   role='user_confirmed_roles_and_links';status='user_confirmed_links';meta={}
  else:
   up=np.flatnonzero(p[:,1]<255.5);dn=np.flatnonzero(p[:,1]>255.5)
   links=None;role='horizon_255_5_conditional_roles';status='unassigned';meta={}
  split=len(up)>0 and len(dn)>0 and len(up)+len(dn)==len(p)
  if not split:
   z.update(role_source=role,role_status='empty_role_or_point_on_horizon',n_top=len(up),n_bottom=len(dn));ar.append(z);continue
  up=order_indices(p,up);dn=order_indices(p,dn)
  if links is None:
   if association=='min_horizontal':links,status,meta=infer_links(p,up,dn)
   else:
    nn=ns['normalize_geometry'](p.tolist())
    if not nn['valid']:status='legacy_not_normalizable'
    else:
     try:
      pp,pi=legacy.recover_endpoints(p,nn)
      if np.all((pp[:,0,1]<255.5)&(pp[:,1,1]>255.5)):
       links=pi;status='legacy_links_opposite_role_checked_not_human_confirmed'
      else:status='legacy_links_same_side_rejected'
     except ValueError:status='legacy_endpoint_recovery_ambiguous'

  if links is not None:links=pair_order(p,links)
  exact=0;near=0;mingap=np.inf
  for ix in [up,dn]:
   g=np.diff(np.r_[p[ix,0]%1024,(p[ix[0],0]%1024)+1024]);mingap=min(mingap,float(g.min()))
   exact+=int((g<1e-9).sum());near+=int((g<=1.).sum())
  order_inversion=False
  if links is not None:
   # Relative top order and bottom order; a cyclic offset alone is not an inversion.
   t_rank={k:i for i,k in enumerate(up)};b_rank={k:i for i,k in enumerate(dn)}
   seq=[b_rank[b] for a,b in sorted(links.tolist(),key=lambda z:t_rank[z[0]])]
   order_inversion=sum(np.diff(np.r_[seq,seq[0]])<0)>1 if len(seq)>2 else False
  z.update(split_available=True,bound_available=links is not None,role_source=role,role_status='available_conditionally',
   n_top=len(up),n_bottom=len(dn),pairing_source=status,exact_x_ties=exact,near_x_gaps_le1px=near,
   minimum_role_x_gap_px=mingap,paired_role_order_inversion=order_inversion,**meta)
  rr={'id':cid,'p':p,'up':up,'dn':dn,'links':links,'row':r,'audit':z};rec[cid]=rr;ar.append(z)
 return rec,pd.DataFrame(ar)

def bottleneck(C):
 assert len(C)==C.shape[1] and len(C)>0
 v=np.unique(C);lo=0;hi=len(v)-1
 while lo<hi:
  mid=(lo+hi)//2;i,j=linear_sum_assignment((C>v[mid]).astype(int))
  if np.all(C[i,j]<=v[mid]):hi=mid
  else:lo=mid+1
 i,j=linear_sum_assignment((C>v[lo]).astype(int));return float(v[lo]),j

def cyclic(C):
 n=len(C);v=np.array([np.max(C[np.arange(n),(np.arange(n)+s)%n]) for s in range(n)])
 best=int(np.argmin(v));svals=np.sort(v)
 return float(v[best]),best,float(svals[1]-svals[0]) if n>1 else np.inf

def compare(a,b):
 p,q=a['p'],b['p'];out={};maps={}
 if len(p)!=len(q):return {'status':'different_total_count'},{}
 if len(a['up'])!=len(b['up']) or len(a['dn'])!=len(b['dn']):return {'status':'different_role_counts'},{}
 T=angular(p[a['up']],q[b['up']]);B=angular(p[a['dn']],q[b['dn']])
 out['status']='split_available'
 mt=np.diag(T);mb=np.diag(B)
 out.update(top_fixed=float(mt.max()),bottom_fixed=float(mb.max()),split_fixed=float(max(mt.max(),mb.max())),
            split_fixed_mean=float(np.r_[mt,mb].mean()))
 for role,C in [('top',T),('bottom',B)]:
  cv,shift,margin=cyclic(C);fv,ind=bottleneck(C)
  out[role+'_cyclic']=cv;out[role+'_shift']=shift;out[role+'_shift_margin_deg']=margin;out[role+'_free']=fv
  aix=a['up' if role=='top' else 'dn'];bix=b['up' if role=='top' else 'dn']
  maps['split_fixed_'+role]=(aix,bix)
  maps['split_cyclic_'+role]=(aix,bix[(np.arange(len(bix))+shift)%len(bix)])
  maps['split_free_'+role]=(aix,bix[ind])
 out['split_cyclic']=max(out['top_cyclic'],out['bottom_cyclic']);out['split_free']=max(out['top_free'],out['bottom_free'])
 if a['links'] is None or b['links'] is None:return out,maps
 L=a['links'];R=b['links'];T2=angular(p[L[:,0]],q[R[:,0]]);B2=angular(p[L[:,1]],q[R[:,1]])
 C=np.maximum(T2,B2);v,shift,margin=cyclic(C);fv,ind=bottleneck(C)
 out.update(status='both_available',bound_fixed=float(np.diag(C).max()),bound_cyclic=v,bound_free=fv,
            bound_shift=shift,bound_shift_margin_deg=margin,bound_fixed_mean=float(np.r_[np.diag(T2),np.diag(B2)].mean()))
 for j,role in enumerate(['top','bottom']):
  maps['bound_fixed_'+role]=(L[:,j],R[:,j]);maps['bound_cyclic_'+role]=(L[:,j],R[(np.arange(len(R))+shift)%len(R),j])
  maps['bound_free_'+role]=(L[:,j],R[ind,j])
 out['same_fixed_correspondence']=all(set(zip(*maps['split_fixed_'+r]))==set(zip(*maps['bound_fixed_'+r])) for r in ['top','bottom'])
 out['same_cyclic_correspondence']=all(set(zip(*maps['split_cyclic_'+r]))==set(zip(*maps['bound_cyclic_'+r])) for r in ['top','bottom'])
 return out,maps

def cluster(D,t):
 assert np.isfinite(D).all() and np.allclose(D,D.T) and np.allclose(np.diag(D),0.)
 if len(D)<2:return np.ones(len(D),int)
 return fcluster(linkage(squareform(D,checks=True),method='complete'),t,criterion='distance')

def stats(l):
 c=np.array(list(collections.Counter(l).values()));n=len(l)
 return {'N':n,'clusters':len(c),'singletons':int((c==1).sum()),'singleton_mass':float((c==1).sum()/n),
         'supported':int((c>=2).sum()),'largest_share':float(c.max()/n),'sizes':';'.join(map(str,sorted(c,reverse=True)))}

def run(root=ROOT,association='legacy_guarded',output=None):
 root=Path(root);inp=root/'inputs';out=Path(output) if output is not None else root/'results';out.mkdir(parents=True,exist_ok=True)
 inputsha=hashlib.sha256((inp/'responses.jsonl.gz').read_bytes()).hexdigest()
 rows=[json.loads(l) for l in gzip.open(inp/'responses.jsonl.gz','rt',encoding='utf-8')]
 audit=pd.read_csv(inp/'prior_response_audit.csv').set_index('id');approved=accepted_map(inp,rows)
 rec,ad=prepare(rows,audit,approved,association,json.loads((inp/'key39_source.json').read_text(encoding='utf-8')));ad.to_csv(out/'response_eligibility.csv',index=False)
 ords=[]
 for a in rec.values():
  for role in ['top','bottom']:
   for i,k in enumerate(a['up' if role=='top' else 'dn']):
    ords.append(dict(id=a['id'],code=a['audit']['code'],worker=a['audit']['worker'],condition=a['audit']['condition'],route='split',role=role,ordinal=i+1,point_index=int(k)+1,x=a['p'][k,0],y=a['p'][k,1]))
  if a['links'] is not None:
   for i,(t,b) in enumerate(a['links']):
    for role,k in [('top',t),('bottom',b)]:ords.append(dict(id=a['id'],code=a['audit']['code'],worker=a['audit']['worker'],condition=a['audit']['condition'],route='bound',role=role,ordinal=i+1,point_index=int(k)+1,x=a['p'][k,0],y=a['p'][k,1]))
 pd.DataFrame(ords).to_csv(out/'point_ordinals.csv',index=False)
 groups=collections.defaultdict(list)
 for a in rec.values():groups[a['row']['image_id'],a['row']['raw_condition']].append(a)
 pr=[];gs=[];members=[];diag=[];diffs=[];cache={};point_path=out/'all_fixed_endpoint_comparisons.csv.gz'
 fields=['image_id','condition','id_a','id_b','route','role','ordinal','point_a','point_b','dx_wrapped_px','dy_px','angular_deg']
 with gzip.open(point_path,'wt',newline='',encoding='utf-8') as fh:
  writer=csv.DictWriter(fh,fieldnames=fields);writer.writeheader()
  for gn,((iid,cond),rr) in enumerate(sorted(groups.items())):
   rr=sorted(rr,key=lambda a:a['audit']['worker']);ids=[a['id'] for a in rr];n=len(rr);code=rr[0]['audit']['code']
   Ds={k:np.full((n,n),BLOCK) for k in METRICS}
   for D in Ds.values():np.fill_diagonal(D,0.)
   counts=np.array([len(a['p']) for a in rr]);Dc=(counts[:,None]!=counts[None,:]).astype(float)
   for i,j in itertools.combinations(range(n),2):
    a,b=rr[i],rr[j];v,maps=compare(a,b)
    base=dict(image_id=iid,code=code,condition=cond,id_a=a['id'],id_b=b['id'],worker_a=a['audit']['worker'],worker_b=b['audit']['worker'],count_a=len(a['p']),count_b=len(b['p']),
              role_source_a=a['audit']['role_source'],role_source_b=b['audit']['role_source'])
    pr.append(dict(**base,**v))
    for key in METRICS:
     if key in v:Ds[key][i,j]=Ds[key][j,i]=v[key]
    for route in ['split_fixed','bound_fixed']:
     for role in ['top','bottom']:
      if route+'_'+role not in maps:continue
      aa,bb=maps[route+'_'+role];errs=np.diag(angular(a['p'][aa],b['p'][bb]))
      for k,(pa,pb,e) in enumerate(zip(aa,bb,errs)):
       writer.writerow(dict(image_id=iid,condition=cond,id_a=a['id'],id_b=b['id'],route=route,role=role,ordinal=k+1,point_a=int(pa)+1,point_b=int(pb)+1,
           dx_wrapped_px=float((a['p'][pa,0]-b['p'][pb,0]+512)%1024-512),dy_px=float(a['p'][pa,1]-b['p'][pb,1]),angular_deg=float(e)))
   ixbound=np.array([i for i,a in enumerate(rr) if a['links'] is not None],int)
   groupcache={'code':code,'ids':ids,'workers':[a['audit']['worker'] for a in rr],'counts':counts.tolist(),'bound_indices':ixbound.tolist(),'matrices':{k:D.tolist() for k,D in Ds.items()},'labels':{}}
   # Full available sets: paired eligibility must not become an artificial singleton.
   for key in ['count_only']+list(METRICS):
    ix=ixbound if key.startswith('bound') else np.arange(n)
    if not len(ix):continue
    D=(Dc if key=='count_only' else Ds[key])[np.ix_(ix,ix)]
    for t in ((0.,) if key=='count_only' else CUTS):
     lab=cluster(D,t);tag=f'{key}_{int(t)}';groupcache['labels'][tag]={'ids':[ids[i] for i in ix],'labels':lab.tolist()}
     gs.append(dict(code=code,image_id=iid,condition=cond,view=key,cut=t,**stats(lab)))
     c=collections.Counter(lab);A=D<=t;np.fill_diagonal(A,False);eq=lab[:,None]==lab[None,:]
     diag.append(dict(code=code,image_id=iid,condition=cond,view=key,cut=t,N=len(ix),compatible_pairs=int(A.sum()//2),compatible_pairs_split=int((A&~eq).sum()//2)))
     for k,i in enumerate(ix):
      a=rr[i];members.append(dict(code=code,image_id=iid,condition=cond,stage=a['row']['stage'],id=ids[i],worker=a['audit']['worker'],count=len(a['p']),view=key,cut=t,cluster=int(lab[k]),cluster_size=c[lab[k]],N=len(ix),
              n_same_count_others=int((counts[ix]==counts[i]).sum()-1),close_neighbors=int(A[k].sum()),pair_source=a['audit']['pairing_source']))
   # Compare rules only on the COMMON paired-eligible set.
   if len(ixbound):
    common={k:D[np.ix_(ixbound,ixbound)] for k,D in Ds.items()}
    for t in CUTS:
     l={k:cluster(D,t) for k,D in common.items()}
     for x,y in [('split_fixed','bound_fixed'),('split_fixed','split_cyclic'),('bound_fixed','bound_cyclic'),('split_cyclic','split_free'),('bound_cyclic','bound_free')]:
      aa=l[x][:,None]==l[x][None,:];bb=l[y][:,None]==l[y][None,:]
      e1=common[x]<=t;e2=common[y]<=t
      diffs.append(dict(code=code,image_id=iid,condition=cond,N=len(ixbound),cut=t,view_a=x,view_b=y,
                       count_a=len(set(l[x])),count_b=len(set(l[y])),different_membership_pairs=int((aa!=bb).sum()//2),different_threshold_pairs=int((e1!=e2).sum()//2)))
     # Separately clustering top and bottom then intersecting is NOT generally
     # identical to clustering their maximum distance.
     tt=l['top_fixed'];bb=l['bottom_fixed'];lab=np.array([list(zip(tt,bb)).index(z)+1 for z in zip(tt,bb)])
     aa=l['split_fixed'][:,None]==l['split_fixed'][None,:];cc=lab[:,None]==lab[None,:]
     diffs.append(dict(code=code,image_id=iid,condition=cond,N=len(ixbound),cut=t,view_a='split_fixed',view_b='top_bottom_partition_intersection',
                 count_a=len(set(l['split_fixed'])),count_b=len(set(lab)),different_membership_pairs=int((aa!=cc).sum()//2),different_threshold_pairs=0))
     for key in ['split_fixed','bound_fixed','split_cyclic','bound_cyclic','split_free','bound_free']:
      gs.append(dict(code=code,image_id=iid,condition=cond,view=key+'_common',cut=t,**stats(l[key])))
   cache[iid+'|'+cond]=groupcache
   if gn%60==0:print('group',gn,code,flush=True)
 pdf=pd.DataFrame(pr);pdf.to_csv(out/'pairwise_rules.csv',index=False)
 for file,data in [('group_summary',gs),('memberships',members),('pairwise_to_partition',diag),('common_partition_comparisons',diffs)]:pd.DataFrame(data).to_csv(out/(file+'.csv'),index=False)
 (out/'cache.json').write_text(json.dumps(cache,separators=(',',':')),encoding='utf-8')
 evidence={'association_policy':association,'raw_records':len(rows),'retained_excluding_W019_W026':int((~ad.excluded_worker).sum()),'pointset_eligible':int(ad.pointset_available.sum()),'split_eligible':len(rec),
 'bound_eligible':int(ad.bound_available.sum()),'user_confirmed_bound_responses':len(approved),'groups_split':len(groups),
 'compared_same_count_pairs_split':int(pdf.status.isin(['split_available','both_available']).sum()),'compared_pairs_both':int(pdf.status.eq('both_available').sum()),
 'same_total_different_role_counts_pairs':int(pdf.status.eq('different_role_counts').sum()),'different_total_count_pairs':int(pdf.status.eq('different_total_count').sum()),
 'bound_sources':ad.loc[ad.split_available,'pairing_source'].value_counts().to_dict(),
 'source_responses_sha256':inputsha,'raw_points_changed':False,'coordinate_rotation_used':False,'synthetic_people_used':False,
 'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__,'python':platform.python_version()}
 assert inputsha==hashlib.sha256((inp/'responses.jsonl.gz').read_bytes()).hexdigest()
 dump(out/'SCOPE.json',evidence);print(json.dumps(evidence,ensure_ascii=False,indent=2))
 print(pd.DataFrame(gs).query('cut==9').groupby('view')[['N','clusters','singletons']].sum().to_string())
 return rec,ad,pdf,cache

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=ROOT);ap.add_argument('--association',choices=['legacy_guarded','min_horizontal'],default='legacy_guarded');ap.add_argument('--output-dir',type=Path,default=None);args=ap.parse_args();run(args.root,args.association,args.output_dir)
