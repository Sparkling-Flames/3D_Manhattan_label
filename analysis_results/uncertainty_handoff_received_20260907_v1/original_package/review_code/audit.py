"""Read-only geometric census: no coordinate changes and no corner adjacency sorting."""
from pathlib import Path
from itertools import combinations
from collections import defaultdict
import json, hashlib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from shapely.geometry import Polygon,Point
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'analysis_results/uncertainty_cloud_inputs_20260906_v1';O=ROOT/'review_results'
def read(p):return pd.read_csv(p,dtype=str,keep_default_na=False)
def js(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def jl(p):return [json.loads(x) for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
def yes(x):return str(x).lower() in ('true','1')
def save(n,r):
 p=O/n;p.parent.mkdir(parents=True,exist_ok=True);pd.DataFrame(r).to_csv(p,index=False)
def dump(n,r):
 p=O/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def roles(points):
 a=np.asarray(points,float)
 if a.ndim!=2 or a.shape[1]!=2 or len(a)<6 or len(a)%2:raise ValueError('odd_or_insufficient')
 if not np.isfinite(a).all() or np.any(a<0) or np.any(a[:,0]>1024) or np.any(a[:,1]>512):raise ValueError('coordinate_invalid')
 pp=a.reshape(-1,2,2);ii=np.arange(len(a)).reshape(-1,2)
 if np.any((pp[:,0,1]-256)*(pp[:,1,1]-256)>=0):raise ValueError('adjacent_pair_same_hemisphere')
 rev=pp[:,0,1]>pp[:,1,1];ii[rev]=ii[rev,::-1]
 return a[ii.ravel()].copy(),ii.ravel().tolist()
def ray(a):
 a=np.asarray(a,float);u=2*np.pi*(a[...,0]/1024-.5);v=np.pi*(.5-a[...,1]/512)
 return np.stack([np.cos(v)*np.sin(u),np.sin(v),-np.cos(v)*np.cos(u)],axis=-1)
def project(a):
 a=np.asarray(a,float)
 return np.stack([((np.arctan2(a[...,0],-a[...,2])/2/np.pi+.5)*1024)%1024,(.5-np.arctan2(a[...,1],np.hypot(a[...,0],a[...,2]))/np.pi)*512],axis=-1)
def lift(points):
 a,mp=roles(points);rf=ray(a[1::2]);rt=ray(a[::2]);den=np.linalg.norm(rt[:,[0,2]],axis=1)
 if np.any(abs(rf[:,1])<1e-5) or np.any(den<1e-8):raise ValueError('near_horizon_or_pole')
 f=-rf/rf[:,1,None];t=rt*(np.linalg.norm(f[:,[0,2]],axis=1)/den)[:,None]
 return f,t,mp

def footprint(points):
 f,_,_=lift(points);p=Polygon(f[:,[0,2]])
 if not p.is_valid or p.area<1e-10:raise ValueError('invalid_original_order_polygon')
 if not p.contains(Point(0,0)):raise ValueError('camera_outside')
 return p

def band(points,n=1024,linear=False):
 a,_=roles(points);grid=(np.arange(n)+.5)/n;curves=[]
 for edge in (a[::2],a[1::2]):
  x=edge[:,0]/1024;y=edge[:,1];d=(np.roll(x,-1)-x+.5)%1-.5;v=np.pi*(.5-y/512)
  if np.any(abs(d)<1e-8):raise ValueError('zero_azimuth_edge')
  if not(np.all(d>0) or np.all(d<0)) or abs(abs(d.sum())-1)>1e-6:raise ValueError('non_single_valued_or_nonstar_boundary')
  if np.any(abs(v)>=np.pi/2-1e-8):raise ValueError('pole_endpoint')
  z=np.full(n,np.nan)
  for i,di in enumerate(d):
   t=((grid-x[i])%1)/di if di>0 else -((x[i]-grid)%1)/di;ok=(t>=0)&(t<1+1e-10);q=t[ok];j=(i+1)%len(x);du=di*2*np.pi
   if linear:z[ok]=(1-q)*y[i]+q*y[j]
   else:
    if abs(np.sin(du))<1e-8:raise ValueError('antipodal_edge')
    tangent=(np.tan(v[i])*np.sin((1-q)*du)+np.tan(v[j])*np.sin(q*du))/np.sin(du);z[ok]=(.5-np.arctan(tangent)/np.pi)*512
  if not np.isfinite(z).all():raise ValueError('incomplete_coverage')
  curves.append(z)
 return np.array(curves)
def dp(a,b):return float(1-a.intersection(b).area/a.union(b).area)
def db(a,b,solid=False):
 if solid:a=-np.sin(np.pi*(.5-a/512));b=-np.sin(np.pi*(.5-b/512))
 inter=np.maximum(0,np.minimum(a[1],b[1])-np.maximum(a[0],b[0])).sum();return float(1-inter/(np.diff(a,axis=0).sum()+np.diff(b,axis=0).sum()-inter))
def rho(x,y):
 x=np.asarray(x,float);y=np.asarray(y,float);ok=np.isfinite(x)&np.isfinite(y)
 return float(spearmanr(x[ok],y[ok]).statistic) if ok.sum()>=4 and np.ptp(x[ok])>0 and np.ptp(y[ok])>0 else np.nan

def load():
 a=read(P/'annotations.csv.gz');im=read(P/'images.csv');pa=read(P/'clusters/partitions.csv.gz');me=read(P/'clusters/memberships.csv.gz');ve=jl(P/'raw_annotation_versions.jsonl');mo=jl(P/'models/layouts.jsonl');re=jl(P/'references.jsonl')
 for r in re:r.setdefault('layout_id',r['reference_id'])
 raw={r['canonical_annotation_id']:r for r in ve if yes(r['selected_canonical_version'])};gv=read(P/'facts/geometry_variants.csv.gz');norm={r.canonical_annotation_id:json.loads(r.points_json) for r in gv[gv.variant=='strict_normalized'].itertuples()}
 return a,im,pa,me,ve,mo,re,raw,norm

def run():
 a,im,pa,me,ve,mo,re,raw,norm=load();assert len(a)==2501 and not a.duplicated(['context_key','worker_id']).any()
 coords={k:r['points_1024x512'] for k,r in raw.items()};coords.update({r['layout_id']:r['points_1024x512'] for r in mo+re});coords.update({'norm|'+k:v for k,v in norm.items()});polys={};bands={};lines={};audit=[]
 for key,p in coords.items():
  z=dict(layout_id=key,corner_adjacency_changed=False,coordinate_values_changed=False)
  try:arr,mp=roles(p);z.update(endpoint_role_map=json.dumps(mp),role_swaps=sum(i!=j for i,j in enumerate(mp))//2,pair_dx_max=float(abs((arr[::2,0]-arr[1::2,0]+512)%1024-512).max()))
  except (ValueError,TypeError) as e:z['role_failure']=str(e)
  for label,cache,fn in [('floor',polys,footprint),('band',bands,band)]:
   try:cache[key]=fn(p);z[label+'_ok']=True;z[label+'_failure']=''
   except (ValueError,IndexError,TypeError) as e:z[label+'_ok']=False;z[label+'_failure']=str(e)
  if key in bands:lines[key]=band(p,linear=True)
  audit.append(z)
 save('measurement/layout_audit.csv',audit);mb=defaultdict(dict);rb=defaultdict(list)
 for r in mo:mb[r['image_id']][r['model_family']+'|'+r['head']+'|'+r['source_role']]=r
 for r in re:rb[r['image_id']].append(r)
 models=[]
 for mid in im.image_id:
  mm=mb[mid];e=mm.get('Bi-Layout|enclosed|offline_dual_prediction');x=mm.get('Bi-Layout|extended|offline_dual_prediction');h=mm.get('HoHoNet|single|offline_ep300_replay');z=dict(image_id=mid,model_count=len(mm),reference_count=len(rb[mid]),reference_floor_available=sum(r['layout_id'] in polys for r in rb[mid]),bi_equal=bool(e and x and len(e['points_1024x512']) and np.array_equal(e['points_1024x512'],x['points_1024x512'])))
  for name,l,r in [('bi',e,x),('hoho_E',h,e),('hoho_X',h,x)]:
   i=l['layout_id'] if l else '';j=r['layout_id'] if r else '';z[name+'_floor']=dp(polys[i],polys[j]) if i in polys and j in polys else np.nan
   if name=='bi':
    ok=i in bands and j in bands;z['bi_band']=db(bands[i],bands[j]) if ok else np.nan;z['bi_linear']=db(lines[i],lines[j]) if ok else np.nan;z['bi_solid']=db(bands[i],bands[j],True) if ok else np.nan
  models.append(z)
 mf=pd.DataFrame(models).set_index('image_id');save('measurement/models.csv',mf.reset_index());prop=read(P/'facts/proposal_fact.csv.gz');pk={(r.base_task_id,r.stage):r.initialization_source_kind for r in prop.itertuples()};ctx=[];prs=[];response=[]
 for key,g in a.groupby('context_key',sort=True):
  r=g.iloc[0];ids=list(g.canonical_annotation_id);pp=[]
  for i,j in combinations(ids,2):
   ok=i in bands and j in bands;z=dict(context_key=key,left=i,right=j,d_floor=dp(polys[i],polys[j]) if i in polys and j in polys else np.nan,d_band=db(bands[i],bands[j]) if ok else np.nan,d_linear=db(lines[i],lines[j]) if ok else np.nan,d_solid=db(bands[i],bands[j],True) if ok else np.nan);pp.append(z);prs.append(z)
  z=dict(context_key=key,image_id=r.image_id,building_id=r.building_id,stage=r.stage,condition=r.raw_condition,raw_count=len(g),floor_count=sum(k in polys for k in ids),band_count=sum(k in bands for k in ids),current20_count=sum(g.current20_member.map(yes)),initialization_source_kind=pk.get((r.image_id,r.stage),'manual_or_not_recorded'))
  for f in ['d_floor','d_band','d_linear','d_solid']:
   vals=[p[f] for p in pp if np.isfinite(p[f])];z[f]=float(np.mean(vals)) if vals else np.nan
  z.update(mf.loc[r.image_id].to_dict());ctx.append(z)
  for k in ids:
   rr=dict(canonical_annotation_id=k,context_key=key,image_id=r.image_id,worker_id=raw[k]['worker_id'])
   for head in ['enclosed','extended']:
    mod=mb[r.image_id].get('Bi-Layout|'+head+'|offline_dual_prediction');mk=mod['layout_id'] if mod else '';rr['d_'+head]=dp(polys[k],polys[mk]) if k in polys and mk in polys else np.nan
   response.append(rr)
 cf=pd.DataFrame(ctx);save('analysis/contexts.csv',cf);save('analysis/pairs.csv.gz',prs);save('analysis/responses_to_bi.csv',response);cr=[];checks=[]
 for p in pa.to_dict('records'):
  mm=me[me.partition_id==p['partition_id']];checks.append(dict(partition_id=p['partition_id'],reported=int(p['member_count']),found=len(mm),matches=int(p['member_count'])==len(mm),raw_only=int((mm.mapping_status=='raw_version_only').sum())))
  if p['version']!='extended73':continue
  for cid,g in mm.groupby('cluster_id',sort=True):
   ids=['norm|'+k for k in g.canonical_annotation_id if 'norm|'+k in polys];z=dict(partition_id=p['partition_id'],cluster_id=cid,context_key=p['context_key'],image_id=p['image_id'],rank=int(g.iloc[0]['rank']),original_support=len(g),floor_support=len(ids),partition_status=p['partition_status'],structure_status=p['structure_status'],semantic_label='',representative_status='new_display_medoid_not_archived')
   if ids:
    D=np.zeros((len(ids),len(ids)))
    for i,j in combinations(range(len(ids)),2):D[i,j]=D[j,i]=dp(polys[ids[i]],polys[ids[j]])
    ri=min(range(len(ids)),key=lambda i:(round(float(D[i].sum()),12),ids[i]));z['representative_id']=ids[ri][5:];z['within_floor']=D.sum()/(len(ids)*(len(ids)-1)) if len(ids)>1 else np.nan
    for head in ['enclosed','extended']:
     mod=mb[p['image_id']].get('Bi-Layout|'+head+'|offline_dual_prediction');mk=mod['layout_id'] if mod else '';z['medoid_'+head]=dp(polys[ids[ri]],polys[mk]) if mk in polys else np.nan
   cr.append(z)
 save('analysis/membership_checks.csv',checks);cl=pd.DataFrame(cr);save('analysis/clusters_to_bi.csv',cl);u=cl.dropna(subset=['medoid_enclosed','medoid_extended']);cover=[]
 for t in [.05,.1,.2]:
  e=u.medoid_enclosed<=t;x=u.medoid_extended<=t;cover.append(dict(radius=t,clusters=len(u),both=int((e&x).sum()),neither=int((~e&~x).sum()),only_E=int((e&~x).sum()),only_X=int((~e&x).sum()),semantic_classification=False))
 save('analysis/template_coverage.csv',cover);ext=cf.merge(pa[pa.version=='extended73'][['context_key','cluster_count','partition_status','structure_status']],on='context_key',validate='one_to_one');ext.cluster_count=ext.cluster_count.astype(int);save('analysis/extended73.csv',ext);stats=[];rng=np.random.default_rng(20260906)
 for scope,df in [('extended73',ext),('without_synthetic',ext[ext.initialization_source_kind!='trap_synthetic_disjoint_source']),('all_n3',cf[cf.floor_count>=3])]:
  for st,g in [('all',df)]+[(s+'|'+c,gg) for (s,c),gg in df.groupby(['stage','condition'])]:
   for xx,yy in [('bi_floor','d_floor'),('bi_band','d_band'),('bi_linear','d_linear'),('bi_solid','d_solid'),('bi_floor','cluster_count')]:
    if yy not in g:continue
    dd=g.dropna(subset=[xx,yy]);r=rho(dd[xx],dd[yy]);bs=sorted(dd.building_id.unique());draw=[]
    if np.isfinite(r) and len(bs)>=3:
     ar=dd[[xx,yy]].to_numpy(float);b=dd.building_id.to_numpy();groups=[np.flatnonzero(b==bb) for bb in bs]
     for _ in range(500):
      ii=np.concatenate([groups[j] for j in rng.integers(0,len(bs),len(bs))]);q=rho(ar[ii,0],ar[ii,1])
      if np.isfinite(q):draw.append(q)
    bm=dd.groupby('building_id')[[xx,yy]].mean();stats.append(dict(scope=scope,stratum=st,x=xx,y=yy,contexts=len(dd),images=dd.image_id.nunique(),buildings=len(bs),rho=r,ci_low=np.quantile(draw,.025) if draw else np.nan,ci_high=np.quantile(draw,.975) if draw else np.nan,building_mean_rho=rho(bm[xx],bm[yy]),interval='500_building_bootstrap_conditional_on_historical_workers'))
 save('analysis/associations.csv',stats);pp=pd.DataFrame(prs);wk=a.set_index('canonical_annotation_id').worker_id;pp['wa']=pp.left.map(wk);pp['wb']=pp.right.map(wk);wr=[]
 for w in sorted(a.worker_id.unique()):
  target=pp[(pp.wa!=w)&(pp.wb!=w)].groupby('context_key').d_floor.mean();z=ext[['context_key','bi_floor']].merge(target.rename('target'),on='context_key');wr.append(dict(omitted_worker=w,rho=rho(z.bi_floor,z.target),kind='sensitivity_not_CI'))
 save('analysis/worker_sensitivity.csv',wr);h30={r['image_id']:r['review_id'] for r in js(P/'archive/human30.json')['items']};ai={r['image_id']:r.get('review_id','R50-'+str(i+1).zfill(3)) for i,r in enumerate(js(P/'archive/ai50_selection.json')['items'])}
 census=im.merge(mf.reset_index(),on='image_id');ct=a.groupby('image_id').agg(historical_rows=('canonical_annotation_id','size'),historical_workers=('worker_id','nunique'),historical_contexts=('context_key','nunique'));census=census.merge(ct,on='image_id',how='left');cols=['historical_rows','historical_workers','historical_contexts'];census[cols]=census[cols].fillna(0).astype(int);hm=cf.groupby('image_id').agg(human_floor_mean=('d_floor','mean'),floor_count=('floor_count','sum'));census=census.merge(hm,on='image_id',how='left');census['human30_id']=census.image_id.map(h30).fillna('');census['ai50_id']=census.image_id.map(ai).fillna('')
 for v in ['extended73','historical42']:census[v+'_partitions']=census.image_id.map(pa[pa.version==v].groupby('image_id').size()).fillna(0).astype(int)
 save('census/images_380.csv',census);save('census/buildings.csv',census.groupby(['building_id','population_role']).agg(images=('image_id','size'),annotations=('historical_rows','sum'),bi_equal=('bi_equal','sum'),human30=('human30_id',lambda s:(s!='').sum()),ai50=('ai50_id',lambda s:(s!='').sum())).reset_index());support=[]
 for key,g in a.groupby('context_key'):
  have=sorted(g[g.current20_member.map(yes)].worker_id,key=int);valid=sorted([r.worker_id for r in g.itertuples() if yes(r.current20_member) and r.canonical_annotation_id in polys],key=int);support.append(dict(context_key=key,observed_current20=len(have),floor_current20=len(valid),workers_json=json.dumps(have),floor_workers_json=json.dumps(valid)))
 save('analysis/current20_support.csv',support)
 square=np.array([[-3,-1,-3],[3,-1,-3],[3,-1,3],[-3,-1,3]],float)
 def coords_of(f):
  t=f.copy();t[:,1]=.875;q=np.empty((len(f)*2,2));q[::2]=project(t);q[1::2]=project(f);return q
 q=coords_of(square);extra=coords_of(np.insert(square,1,(square[0]+square[1])/2,axis=0));tests=[]
 for name,r in [('collinear_insertion',extra),('cyclic_start',np.roll(q,2,axis=0)),('reverse_cycle',q.reshape(-1,2,2)[::-1].reshape(-1,2))]:tests.append(dict(test=name,floor=dp(footprint(q),footprint(r)),projected=db(band(q),band(r)),linear=db(band(q,linear=True),band(r,linear=True)),synthetic=True))
 assert max(abs(t['floor'])+abs(t['projected']) for t in tests)<1e-9;dump('measurement/math_checks.json',tests)
 qa=dict(source_commit='29f628fd5a9c4d3e2064ffffec32bbffb324776c',images=len(im),buildings=im.building_id.nunique(),historical_images=int((census.historical_rows>0).sum()),canonical_rows=len(a),raw_floor_available=sum(k in polys for k in raw),raw_band_available=sum(k in bands for k in raw),models=len(mo),reference_variants=len(re),partitions=len(pa),membership_mismatches=sum(not r['matches'] for r in checks),raw_only_memberships=sum(r['raw_only'] for r in checks),human30=int((census.human30_id!='').sum()),ai50=int((census.ai50_id!='').sum()),raw_data_modified=False);dump('ANALYSIS_QA.json',qa)
 save('census/input_hashes.csv',[dict(path=str(p.relative_to(P)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(P.rglob('*')) if p.is_file()]);print(json.dumps(qa,indent=2))
if __name__=='__main__':run()
