"""Read-only projection audit; retains original corner adjacency and raw coordinates."""
from pathlib import Path
import json,hashlib
from itertools import combinations
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
ROOT=Path(__file__).resolve().parents[4]
P=ROOT/'analysis_results/uncertainty_cloud_inputs_20260906_v1'
O=ROOT/'analysis_results/visual_takeover_20260906_v1'
def read(p):return pd.read_csv(p,dtype=str,keep_default_na=False)
def jl(p):return [json.loads(x) for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
def js(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def yes(x):return str(x).lower() in ('true','1')
def save(name,x):
 p=O/name;p.parent.mkdir(parents=True,exist_ok=True);pd.DataFrame(x).to_csv(p,index=False)
def dump(name,x):
 p=O/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def roles(points):
 a=np.asarray(points,float)
 if a.ndim!=2 or a.shape[1]!=2 or len(a)<6 or len(a)%2:raise ValueError('odd_or_insufficient_points')
 if not np.isfinite(a).all() or np.any(a<0) or np.any(a[:,0]>1024) or np.any(a[:,1]>512):raise ValueError('nonfinite_or_out_of_bounds')
 pairs=a.reshape(-1,2,2);mapping=np.arange(len(a)).reshape(-1,2)
 if np.any((pairs[:,0,1]-256)*(pairs[:,1,1]-256)>=0):raise ValueError('same_hemisphere_adjacent_endpoints')
 rev=pairs[:,0,1]>pairs[:,1,1];mapping[rev]=mapping[rev,::-1]
 return a[mapping.ravel()].copy(),mapping.ravel().tolist()
def ray(a):
 a=np.asarray(a,float);u=2*np.pi*(a[...,0]/1024-.5);v=np.pi*(.5-a[...,1]/512)
 return np.stack([np.cos(v)*np.sin(u),np.sin(v),-np.cos(v)*np.cos(u)],axis=-1)
def project(a):
 a=np.asarray(a,float)
 return np.stack([((np.arctan2(a[...,0],-a[...,2])/2/np.pi+.5)*1024)%1024,(.5-np.arctan2(a[...,1],np.hypot(a[...,0],a[...,2]))/np.pi)*512],axis=-1)
def band(points,n=1024,linear=False):
 a,_=roles(points);grid=(np.arange(n)+.5)/n;curves=[]
 for edge in (a[::2],a[1::2]):
  x=edge[:,0]/1024;y=edge[:,1];d=(np.roll(x,-1)-x+.5)%1-.5;v=np.pi*(.5-y/512)
  if np.any(abs(d)<1e-8):raise ValueError('zero_azimuth_edge')
  if not(np.all(d>0) or np.all(d<0)) or abs(abs(d.sum())-1)>1e-6:raise ValueError('non_single_circular_order_or_nonstar_boundary')
  if np.any(abs(v)>=np.pi/2-1e-8):raise ValueError('pole_endpoint')
  z=np.full(n,np.nan)
  for i,di in enumerate(d):
   t=((grid-x[i])%1)/di if di>0 else -((x[i]-grid)%1)/di;good=(t>=0)&(t<1+1e-10);q=t[good];j=(i+1)%len(x)
   if linear:z[good]=(1-q)*y[i]+q*y[j]
   else:
    du=di*2*np.pi
    if abs(np.sin(du))<1e-8:raise ValueError('antipodal_edge')
    tangent=(np.tan(v[i])*np.sin((1-q)*du)+np.tan(v[j])*np.sin(q*du))/np.sin(du)
    z[good]=(.5-np.arctan(tangent)/np.pi)*512
  if not np.isfinite(z).all():raise ValueError('incomplete_coverage')
  curves.append(z)
 return np.array(curves)
def dist(a,b,solid=False):
 if solid:a=-np.sin(np.pi*(.5-a/512));b=-np.sin(np.pi*(.5-b/512))
 inter=np.maximum(0,np.minimum(a[1],b[1])-np.maximum(a[0],b[0])).sum();union=np.diff(a,axis=0).sum()+np.diff(b,axis=0).sum()-inter
 return float(1-inter/union)
def rho(x,y):
 x=np.asarray(x,float);y=np.asarray(y,float);ok=np.isfinite(x)&np.isfinite(y)
 return float(spearmanr(x[ok],y[ok]).statistic) if ok.sum()>=4 and np.ptp(x[ok])>0 and np.ptp(y[ok])>0 else np.nan
def load():
 a=read(P/'annotations.csv.gz');im=read(P/'images.csv');parts=read(P/'clusters/partitions.csv.gz');mem=read(P/'clusters/memberships.csv.gz');versions=jl(P/'raw_annotation_versions.jsonl');models=jl(P/'models/layouts.jsonl');refs=jl(P/'references.jsonl')
 for r in refs:r.setdefault('layout_id',r['reference_id'])
 raw={r['canonical_annotation_id']:r for r in versions if yes(r['selected_canonical_version'])}
 gv=read(P/'facts/geometry_variants.csv.gz');norm={r.canonical_annotation_id:json.loads(r.points_json) for r in gv[gv.variant=='strict_normalized'].itertuples()}
 return a,im,parts,mem,versions,models,refs,raw,norm

def run():
 a,im,parts,mem,versions,models,refs,raw,norm=load();assert not a.duplicated(['context_key','worker_id']).any()
 coords={k:v['points_1024x512'] for k,v in raw.items()};coords.update({r['layout_id']:r['points_1024x512'] for r in models+refs});coords.update({'norm|'+k:v for k,v in norm.items()})
 cache={};lin={};audit=[]
 for key,pts in coords.items():
  row={'layout_key':key,'source_points_unchanged':True,'corner_adjacency_changed':False}
  try:
   arr,mapping=roles(pts);row.update(role_map_json=json.dumps(mapping),role_swaps=sum(i!=j for i,j in enumerate(mapping))//2,pair_dx_max=float(abs((arr[::2,0]-arr[1::2,0]+512)%1024-512).max()))
   cache[key]=band(arr);lin[key]=band(arr,linear=True);row.update(projected_ok=True,reason='')
  except (ValueError,IndexError,TypeError) as e:row.update(projected_ok=False,reason=str(e))
  audit.append(row)
 save('measurement/layout_parse_audit.csv',audit)
 by={i:{} for i in im.image_id};rb={i:[] for i in im.image_id}
 for r in models:by[r['image_id']][r['model_family']+'|'+r['head']+'|'+r['source_role']]=r
 for r in refs:rb[r['image_id']].append(r)
 mrows=[]
 for r in im.to_dict('records'):
  mid=r['image_id'];mm=by[mid];e=mm.get('Bi-Layout|enclosed|offline_dual_prediction');x=mm.get('Bi-Layout|extended|offline_dual_prediction');h=mm.get('HoHoNet|single|offline_ep300_replay');z=dict(image_id=mid,model_count=len(mm),reference_count=len(rb[mid]),reference_projected_count=sum(t['layout_id'] in cache for t in rb[mid]),bi_raw_equal=bool(e and x and len(e['points_1024x512']) and np.array_equal(e['points_1024x512'],x['points_1024x512'])))
  for name,l,r2 in [('bi_gap',e,x),('hoho_bi_enclosed',h,e),('hoho_bi_extended',h,x)]:
   i=l['layout_id'] if l else '';j=r2['layout_id'] if r2 else '';ok=i in cache and j in cache;z[name]=dist(cache[i],cache[j]) if ok else np.nan
   if name=='bi_gap':z['bi_linear']=dist(lin[i],lin[j]) if ok else np.nan;z['bi_solid']=dist(cache[i],cache[j],True) if ok else np.nan
  mrows.append(z)
 mf=pd.DataFrame(mrows).set_index('image_id');save('measurement/model_comparisons_380.csv',mf.reset_index());contexts=[];pairs=[];responses=[]
 prop=read(P/'facts/proposal_fact.csv.gz');pk={(r.base_task_id,r.stage):r.initialization_source_kind for r in prop.itertuples()}
 for ctx,g in a.groupby('context_key',sort=True):
  r=g.iloc[0];mid=r.image_id;ids=[k for k in g.canonical_annotation_id if k in cache];pp=[]
  for i,j in combinations(ids,2):
   q=dict(context_key=ctx,left=i,right=j,d_projected=dist(cache[i],cache[j]),d_linear=dist(lin[i],lin[j]),d_solid=dist(cache[i],cache[j],True));pp.append(q);pairs.append(q)
  z=dict(context_key=ctx,image_id=mid,building_id=r.building_id,stage=r.stage,condition=r.raw_condition,raw_count=len(g),projected_count=len(ids),current20_count=sum(g.current20_member.map(yes)),initialization_source_kind=pk.get((mid,r.stage),'not_recorded_or_manual'))
  for field in ['d_projected','d_linear','d_solid']:z[field]=np.mean([t[field] for t in pp]) if pp else np.nan
  z.update(mf.loc[mid].to_dict());contexts.append(z)
  for k in g.canonical_annotation_id:
   q=dict(canonical_annotation_id=k,context_key=ctx,image_id=mid,worker_id=raw[k]['worker_id'],projected_ok=k in cache)
   for name in ['enclosed','extended']:
    m=by[mid].get('Bi-Layout|'+name+'|offline_dual_prediction');mk=m['layout_id'] if m else '';q['d_'+name]=dist(cache[k],cache[mk]) if k in cache and mk in cache else np.nan
   responses.append(q)
 c=pd.DataFrame(contexts);save('analysis/context_metrics.csv',c);save('analysis/pair_distances.csv.gz',pairs);save('analysis/response_to_bi.csv',responses)
 chk=[];cr=[]
 for p in parts.to_dict('records'):
  mm=mem[mem.partition_id==p['partition_id']];chk.append(dict(partition_id=p['partition_id'],reported=int(p['member_count']),found=len(mm),matches=len(mm)==int(p['member_count']),raw_only=int((mm.mapping_status=='raw_version_only').sum())))
  if p['version']!='extended73':continue
  for cid,g in mm.groupby('cluster_id',sort=True):
   ids=['norm|'+k for k in g.canonical_annotation_id if 'norm|'+k in cache];z=dict(partition_id=p['partition_id'],cluster_id=cid,context_key=p['context_key'],image_id=p['image_id'],rank=int(g.iloc[0]['rank']),original_support=len(g),projected_support=len(ids),partition_status=p['partition_status'],structure_status=p['structure_status'],representative_role='new_display_medoid_in_old_membership_not_archived_medoid',semantic_label='not_assigned')
   if ids:
    D=np.zeros((len(ids),len(ids)))
    for i,j in combinations(range(len(ids)),2):D[i,j]=D[j,i]=dist(cache[ids[i]],cache[ids[j]])
    k=min(range(len(ids)),key=lambda i:(round(float(D[i].sum()),12),ids[i]));z['display_representative_id']=ids[k][5:];z['within_mean']=D.sum()/len(ids)/(len(ids)-1) if len(ids)>1 else np.nan
    for head in ['enclosed','extended']:
     m=by[p['image_id']].get('Bi-Layout|'+head+'|offline_dual_prediction');mk=m['layout_id'] if m else '';z['medoid_d_'+head]=dist(cache[ids[k]],cache[mk]) if mk in cache else np.nan
   cr.append(z)
 save('analysis/membership_checks.csv',chk);cl=pd.DataFrame(cr);save('analysis/existing_cluster_proximity.csv',cl)
 v=cl.dropna(subset=['medoid_d_enclosed','medoid_d_extended']);cover=[]
 for t in [.025,.05,.1]:
  e=v.medoid_d_enclosed<=t;x=v.medoid_d_extended<=t;cover.append(dict(radius=t,clusters=len(v),both=int((e&x).sum()),neither=int((~e&~x).sum()),only_E=int((e&~x).sum()),only_X=int((~e&x).sum()),semantic_classification=False))
 save('analysis/cluster_template_coverage.csv',cover)
 ext=c.merge(parts[parts.version=='extended73'][['context_key','cluster_count','partition_status','structure_status']],on='context_key',validate='one_to_one');ext.cluster_count=ext.cluster_count.astype(int);save('analysis/extended73_metrics.csv',ext)
 stats=[];rng=np.random.default_rng(20260906)
 for scope,df in [('extended73',ext),('without_synthetic',ext[ext.initialization_source_kind!='trap_synthetic_disjoint_source']),('all_n3',c[c.projected_count>=3])]:
  for st,g in [('all',df)]+[(s+'|'+co,gg) for (s,co),gg in df.groupby(['stage','condition'])]:
   for xx,yy in [('bi_gap','d_projected'),('bi_linear','d_linear'),('bi_solid','d_solid'),('bi_gap','cluster_count')]:
    if yy not in g:continue
    d=g.dropna(subset=[xx,yy]);r=rho(d[xx],d[yy]);bs=sorted(d.building_id.unique());draw=[]
    if np.isfinite(r) and len(bs)>=3:
     ar=d[[xx,yy]].to_numpy(float);b=d.building_id.to_numpy();groups=[np.flatnonzero(b==bb) for bb in bs]
     for _ in range(500):
      ii=np.concatenate([groups[j] for j in rng.integers(0,len(bs),len(bs))]);q=rho(ar[ii,0],ar[ii,1])
      if np.isfinite(q):draw.append(q)
    bm=d.groupby('building_id')[[xx,yy]].mean();stats.append(dict(scope=scope,stratum=st,x=xx,y=yy,contexts=len(d),images=d.image_id.nunique(),buildings=len(bs),spearman=r,ci_low=np.quantile(draw,.025) if draw else np.nan,ci_high=np.quantile(draw,.975) if draw else np.nan,building_mean_rho=rho(bm[xx],bm[yy]),interval='conditional_historical_workers_500_building_bootstrap'))
 save('analysis/associations.csv',stats)
 pp=pd.DataFrame(pairs);workers=a.set_index('canonical_annotation_id').worker_id;pp['wa']=pp.left.map(workers);pp['wb']=pp.right.map(workers);wr=[]
 for w in sorted(a.worker_id.unique()):
  target=pp[(pp.wa!=w)&(pp.wb!=w)].groupby('context_key').d_projected.mean();dd=ext[['context_key','bi_gap']].merge(target.rename('target'),on='context_key');wr.append(dict(omitted_worker=w,rho=rho(dd.bi_gap,dd.target),kind='sensitivity_not_CI'))
 save('analysis/worker_dependence_sensitivity.csv',wr)
 h30={r['image_id']:r['review_id'] for r in js(P/'archive/human30.json')['items']};ai={r['image_id']:r.get('review_id','R50-'+str(i+1).zfill(3)) for i,r in enumerate(js(P/'archive/ai50_selection.json')['items'])}
 census=im.merge(mf.reset_index(),on='image_id');ct=a.groupby('image_id').agg(historical_rows=('canonical_annotation_id','size'),historical_workers=('worker_id','nunique'),historical_contexts=('context_key','nunique'));census=census.merge(ct,on='image_id',how='left');census[['historical_rows','historical_workers','historical_contexts']]=census[['historical_rows','historical_workers','historical_contexts']].fillna(0).astype(int)
 hm=c.groupby('image_id').agg(human_projected_mean=('d_projected','mean'),raw_projected_count=('projected_count','sum'));census=census.merge(hm,on='image_id',how='left');census['human30_id']=census.image_id.map(h30).fillna('');census['ai50_id']=census.image_id.map(ai).fillna('')
 for ver in ['extended73','historical42']:census[ver+'_partitions']=census.image_id.map(parts[parts.version==ver].groupby('image_id').size()).fillna(0).astype(int)
 save('census/images_380.csv',census);save('census/by_building.csv',census.groupby(['building_id','population_role']).agg(images=('image_id','size'),annotations=('historical_rows','sum'),bi_equal=('bi_raw_equal','sum'),human30=('human30_id',lambda x:(x!='').sum()),ai50=('ai50_id',lambda x:(x!='').sum())).reset_index())
 floor=np.array([[-3,-1,-3],[3,-1,-3],[3,-1,3],[-3,-1,3]],float)
 def coords_of(f):
  t=f.copy();t[:,1]=.875;q=np.empty((len(f)*2,2));q[::2]=project(t);q[1::2]=project(f);return q
 q=coords_of(floor);p=coords_of(np.insert(floor,1,(floor[0]+floor[1])/2,axis=0));checks=[dict(test='synthetic_collinear_insertion',projected=dist(band(q),band(p)),linear=dist(band(q,linear=True),band(p,linear=True)),is_human_data=False)]
 for name,rr in [('cyclic_shift',np.roll(q,2,axis=0)),('reverse_cycle',q.reshape(-1,2,2)[::-1].reshape(-1,2))]:checks.append(dict(test=name,projected=dist(band(q),band(rr)),is_human_data=False))
 assert max(abs(r['projected']) for r in checks)<1e-10;dump('measurement/math_checks.json',checks)
 qa=dict(source_commit='29f628fd5a9c4d3e2064ffffec32bbffb324776c',images=len(im),historical_images=int((census.historical_rows>0).sum()),buildings=im.building_id.nunique(),canonical_rows=len(a),raw_projectable=sum(k in cache for k in raw),normalized_projectable=sum('norm|'+k in cache for k in norm),partitions=len(parts),membership_count_mismatches=sum(not z['matches'] for z in chk),raw_only_memberships=sum(z['raw_only'] for z in chk),human30=int((census.human30_id!='').sum()),ai50=int((census.ai50_id!='').sum()),raw_data_modified=False)
 dump('ANALYSIS_QA.json',qa);save('census/input_sha256.csv',[dict(path=str(p.relative_to(P)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(P.rglob('*')) if p.is_file()]);print(json.dumps(qa,indent=2))
if __name__=='__main__':run()
