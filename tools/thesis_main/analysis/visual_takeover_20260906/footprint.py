"""Original-adjacency footprint IoU in a common camera-height gauge. Not 3D truth."""
from itertools import combinations
import numpy as np
import pandas as pd
from shapely.geometry import Polygon,Point
import measure as m

def footprint(points):
 p,mp=m.roles(points);r=m.ray(p[1::2])
 if np.any(abs(r[:,1])<1e-5):raise ValueError('floor_near_horizon')
 f=-r/r[:,1,None];poly=Polygon(f[:,[0,2]])
 if not poly.is_valid or poly.area<1e-10:raise ValueError('invalid_original_order_footprint')
 if not poly.contains(Point(0,0)):raise ValueError('camera_not_inside_footprint')
 return poly

def d(a,b):return float(1-a.intersection(b).area/a.union(b).area)
def run():
 a,im,parts,mem,versions,models,refs,raw,norm=m.load();coords={k:r['points_1024x512'] for k,r in raw.items()};coords.update({r['layout_id']:r['points_1024x512'] for r in models+refs});coords.update({'norm|'+k:v for k,v in norm.items()});polys={};audit=[]
 for k,v in coords.items():
  try:polys[k]=footprint(v);z=dict(layout_key=k,footprint_ok=True,reason='',relative_area=polys[k].area)
  except (ValueError,IndexError,TypeError) as e:z=dict(layout_key=k,footprint_ok=False,reason=str(e))
  audit.append(z)
 m.save('measurement/footprint_parse_audit.csv',audit);mb={i:{} for i in im.image_id}
 for r in models:
  if r['source_role']=='offline_dual_prediction':mb[r['image_id']][r['head']]=r['layout_id']
 mr=[]
 for i in im.image_id:
  e=mb[i].get('enclosed','');x=mb[i].get('extended','');mr.append(dict(image_id=i,bi_floor_gap=d(polys[e],polys[x]) if e in polys and x in polys else np.nan))
 mf=pd.DataFrame(mr);m.save('measurement/footprint_models_380.csv',mf);ctx=[];pair=[];resp=[]
 for key,g in a.groupby('context_key',sort=True):
  r=g.iloc[0];ids=[i for i in g.canonical_annotation_id if i in polys];values=[];e=mb[r.image_id].get('enclosed','');x=mb[r.image_id].get('extended','')
  for i,j in combinations(ids,2):
   v=d(polys[i],polys[j]);pair.append(dict(context_key=key,left=i,right=j,d_floor=v));values.append(v)
  ctx.append(dict(context_key=key,image_id=r.image_id,building_id=r.building_id,stage=r.stage,condition=r.raw_condition,raw_count=len(g),floor_count=len(ids),d_human_floor=np.mean(values) if values else np.nan,bi_floor_gap=d(polys[e],polys[x]) if e in polys and x in polys else np.nan))
  for i in g.canonical_annotation_id:resp.append(dict(canonical_annotation_id=i,context_key=key,worker_id=raw[i]['worker_id'],image_id=r.image_id,d_floor_E=d(polys[i],polys[e]) if i in polys and e in polys else np.nan,d_floor_X=d(polys[i],polys[x]) if i in polys and x in polys else np.nan))
 cf=pd.DataFrame(ctx);m.save('analysis/footprint_contexts.csv',cf);m.save('analysis/footprint_pairs.csv.gz',pair);m.save('analysis/footprint_responses.csv',resp)
 cl=[]
 for p in parts[parts.version=='extended73'].to_dict('records'):
  e=mb[p['image_id']].get('enclosed','');x=mb[p['image_id']].get('extended','')
  for cid,g in mem[mem.partition_id==p['partition_id']].groupby('cluster_id',sort=True):
   ids=['norm|'+k for k in g.canonical_annotation_id if 'norm|'+k in polys];z=dict(partition_id=p['partition_id'],cluster_id=cid,context_key=p['context_key'],image_id=p['image_id'],rank=int(g.iloc[0]['rank']),original_support=len(g),floor_support=len(ids),partition_status=p['partition_status'],structure_status=p['structure_status'])
   if ids:
    D=np.zeros((len(ids),len(ids)))
    for ii,jj in combinations(range(len(ids)),2):D[ii,jj]=D[jj,ii]=d(polys[ids[ii]],polys[ids[jj]])
    rep=min(range(len(ids)),key=lambda j:(round(float(D[j].sum()),12),ids[j]));z.update(display_representative_id=ids[rep][5:],representative_status='new_footprint_medoid_not_archived',within_floor=D.sum()/(len(ids)*(len(ids)-1)) if len(ids)>1 else np.nan,medoid_floor_E=d(polys[ids[rep]],polys[e]) if e in polys else np.nan,medoid_floor_X=d(polys[ids[rep]],polys[x]) if x in polys else np.nan)
   cl.append(z)
 clf=pd.DataFrame(cl);m.save('analysis/footprint_cluster_proximity.csv',clf)
 ext=cf.merge(parts[parts.version=='extended73'][['context_key','cluster_count','partition_status','structure_status']],on='context_key');ext.cluster_count=ext.cluster_count.astype(int);prop=m.read(m.P/'facts/proposal_fact.csv.gz');syn=set(prop[prop.initialization_source_kind=='trap_synthetic_disjoint_source'].image_id);ext['synthetic']=ext.image_id.isin(syn);m.save('analysis/footprint_extended73.csv',ext)
 stats=[];rng=np.random.default_rng(20260907)
 for name,df in [('extended73',ext),('without_synthetic',ext[~ext.synthetic]),('all_n3',cf[cf.floor_count>=3])]:
  for st,g in [('all',df)]+[(ss+'|'+cc,gg) for (ss,cc),gg in df.groupby(['stage','condition'])]:
   for yy in ['d_human_floor','cluster_count']:
    if yy not in g:continue
    z=g.dropna(subset=['bi_floor_gap',yy]);bs=sorted(z.building_id.unique());ar=z[['bi_floor_gap',yy]].to_numpy(float);rho=m.rho(ar[:,0],ar[:,1]);dr=[]
    if np.isfinite(rho) and len(bs)>=3:
     ix=[np.flatnonzero(z.building_id.to_numpy()==b) for b in bs]
     for _ in range(500):
      ii=np.concatenate([ix[j] for j in rng.integers(0,len(bs),len(bs))]);v=m.rho(ar[ii,0],ar[ii,1])
      if np.isfinite(v):dr.append(v)
    partial=np.nan
    if len(z)>=10:
     X=np.c_[np.ones(len(z)),pd.Series(z.floor_count.to_numpy()).rank().to_numpy(),pd.get_dummies(z.stage+'|'+z.condition,drop_first=True,dtype=float).to_numpy()];rx=pd.Series(ar[:,0]).rank().to_numpy();ry=pd.Series(ar[:,1]).rank().to_numpy();rx-=X@np.linalg.lstsq(X,rx,rcond=None)[0];ry-=X@np.linalg.lstsq(X,ry,rcond=None)[0]
     if np.std(rx)>1e-9 and np.std(ry)>1e-9:partial=float(np.corrcoef(rx,ry)[0,1])
    bm=z.groupby('building_id')[['bi_floor_gap',yy]].mean();stats.append(dict(scope=name,stratum=st,target=yy,n_contexts=len(z),n_buildings=len(bs),spearman=rho,ci_low=np.quantile(dr,.025) if dr else np.nan,ci_high=np.quantile(dr,.975) if dr else np.nan,building_mean_spearman=m.rho(bm.bi_floor_gap,bm[yy]),support_stage_partial_rank=partial,interval='conditional_historical_workers_not_population_CI'))
 m.save('analysis/footprint_associations.csv',stats)
 pp=pd.DataFrame(pair);wm=a.set_index('canonical_annotation_id').worker_id;pp['wa']=pp.left.map(wm);pp['wb']=pp.right.map(wm);wr=[]
 for w in sorted(a.worker_id.unique()):
  dd=pp[(pp.wa!=w)&(pp.wb!=w)].groupby('context_key').d_floor.mean();z=ext[['context_key','bi_floor_gap']].merge(dd,on='context_key');wr.append(dict(omitted_worker=w,rho=m.rho(z.bi_floor_gap,z.d_floor)))
 m.save('analysis/footprint_worker_sensitivity.csv',wr)
 census=pd.read_csv(m.O/'census/images_380.csv');hh=cf.groupby('image_id').agg(human_floor_mean=('d_human_floor','mean'),raw_floor_count=('floor_count','sum'));census=census.merge(mf,on='image_id').merge(hh,on='image_id',how='left');m.save('census/images_380_enriched.csv',census)
 m.dump('measurement/footprint_QA.json',dict(raw_usable=sum(k in polys for k in raw),normalized_usable=sum('norm|'+k in polys for k in norm),model_dual_comparable=int(mf.bi_floor_gap.notna().sum()),source_coordinates_modified=False,camera_height_gauge=1,absolute_scale_known=False,is_3D_IoU=False))
 print('footprint complete',sum(k in polys for k in raw))
if __name__=='__main__':run()
