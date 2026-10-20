"""Frozen endpoint-library recategorization, separate from class-specific ABC curves."""
import os
for k in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[k]='1'
import argparse,collections,gzip,json,hashlib,time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import numpy as np,pandas as pd
from corner_distance import corner_compare
CONT=['bev_mean_h','bev_max_h','top_mean_h','top_max_h','bev_mean_pairscale','top_mean_pairscale','bev_max_pairscale','top_max_pairscale','bev_max_local_radius_fraction','top_max_local_radius_fraction','bev_mean_h_angle9','bev_mean_h_angle12']
RISK=['valid_distance','different_count','count_not_verified_equal','missing_geometry','noncomplete','high_angle']
def read(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def work(job):
 native,anchors,labels=job;pool=anchors[0]['pool_id'];teams={x['team_key']:x for x in read(Path(native)/'pools'/(pool+'.json.gz'))['teams']};rows=[]
 for anchor in anchors:
  blocks=anchor['blocks'];core=set(anchor['core_workers']);m=anchor['m'];n=anchor['n']
  for i,j in anchor['disjoint_block_pairs']:
   left,right=blocks[i],blocks[j];wa,wb=set(left['workers']),set(right['workers'])
   assert len(wa)==len(wb)==m and not wa&wb and not core&(wa|wb)
   a,b=teams[left['team_key']],teams[right['team_key']]
   assert set(a['member_workers'])==core|wa and set(b['member_workers'])==core|wb and len(a['member_workers'])==n
   assert a['image_id']==b['image_id']==anchor['image_id']
   v,_=corner_compare(a,b)
   row={k:anchor[k] for k in ['anchor_id','pool_id','image','image_id','building','n','m','replicate']};row.update(pair_id=f"{anchor['anchor_id']}__{i}_{j}",left_block=i,right_block=j,A_team_key=a['team_key'],B_team_key=b['team_key'],left_workers='|'.join(sorted(wa)),right_workers='|'.join(sorted(wb)),**v)
   for mid,labs in labels.items():
    unknown=any(w not in labs or labs[w] in ['unknown',None] for w in wa|wb)
    ca=collections.Counter(labs[w] for w in wa) if not unknown else {};cb=collections.Counter(labs[w] for w in wb) if not unknown else {}
    row[mid+'__arm']='unknown' if unknown else 'within' if ca==cb else 'between'
    row[mid+'__pure']=not unknown and len(ca)==len(cb)==1
    row[mid+'__left_vector']=json.dumps(dict(sorted(ca.items())),separators=(',',':'))
    row[mid+'__right_vector']=json.dumps(dict(sorted(cb.items())),separators=(',',':'))
   rows.append(row)
 return rows

def main():
 p=argparse.ArgumentParser();p.add_argument('--requests',type=Path,required=True);p.add_argument('--native',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--jobs',type=int,default=2);p.add_argument('--pairs-only',action='store_true');p.add_argument('--reuse-pairs',type=Path);p.add_argument('--labels-json',type=Path);p.add_argument('--phase',default='discovery_nominated_exploratory_block_probe');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);t=time.perf_counter();q=read(a.requests);by=collections.defaultdict(list)
 for z in q['common_anchors']:by[z['pool_id']].append(z)
 labels=q.get('label_maps',{});primary=q['spec'].get('primary_method')
 if a.labels_json:
  override=json.loads(a.labels_json.read_text());labels=override['label_maps'];primary=override['primary_method'];labels={primary:labels[primary],**{k:v for k,v in labels.items() if k!=primary}}
 methods=list(labels)
 if not a.pairs_only:
  assert len(methods)==2
  assert methods[0]==primary
 rows=[]
 if a.reuse_pairs:
  f=pd.read_csv(a.reuse_pairs)
  assert set(f.anchor_id)=={v['anchor_id'] for v in q['common_anchors']}
  assert len(f)==sum(len(v['disjoint_block_pairs']) for v in q['common_anchors'])
  oldcols=[c for c in f if c.endswith(('__arm','__pure','__left_vector','__right_vector'))];f=f.drop(columns=oldcols)
  blocks={}
  for workers in set(f.left_workers)|set(f.right_workers):blocks[workers]=workers.split('|')
  for mid,labs in labels.items():
   vectors={w:None if any(p not in labs or labs[p] in ['unknown',None] for p in ps) else dict(sorted(collections.Counter(labs[p] for p in ps).items())) for w,ps in blocks.items()}
   av=f.left_workers.map(vectors);bv=f.right_workers.map(vectors);known=av.notna()&bv.notna()
   f[mid+'__arm']=['unknown' if not k else 'within' if x==y else 'between' for x,y,k in zip(av,bv,known)]
   f[mid+'__pure']=[bool(k and len(x)==len(y)==1) for x,y,k in zip(av,bv,known)]
   f[mid+'__left_vector']=[json.dumps(x or {},separators=(',',':')) for x in av];f[mid+'__right_vector']=[json.dumps(x or {},separators=(',',':')) for x in bv]
 else:
  with ProcessPoolExecutor(max_workers=a.jobs) as e:
   for part in e.map(work,[(a.native,x,labels) for x in by.values()]):rows.extend(part);print('pairs',len(rows),flush=True)
  f=pd.DataFrame(rows)
 assert f.pair_id.is_unique;f['valid_distance']=f.status.eq('unique_cyclic_candidate').astype(float);f['different_count']=f.status.eq('different_corner_count').astype(float);f['count_not_verified_equal']=(~f.same_count).astype(float);f['missing_geometry']=f.status.eq('missing_connected_geometry').astype(float);f['noncomplete']=(~f.complete).astype(float);f['high_angle']=(f.angle_deg>12).astype(float)
 for angle in [9,12]:f['bev_mean_h_angle'+str(angle)]=f.bev_mean_h.where(f.angle_deg<=angle)
 f.to_csv(a.out/'COMMON_ENDPOINT_PAIRS.csv.gz',index=False)
 if a.pairs_only:
  receipt=dict(request_sha256=hashlib.sha256(a.requests.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),frozen_anchors=len(q['common_anchors']),endpoint_pairs=len(f),pools=f.pool_id.nunique(),images=f.image_id.nunique(),buildings=f.building.nunique(),elapsed_seconds=time.perf_counter()-t,mode='pairs_only_no_learning_or_class_ranking',failures=f.status.value_counts().to_dict())
  (a.out/'COMMON_LIBRARY_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt));return
 meta=['anchor_id','pool_id','image_id','building','n','m'];allagg=[];support=[]
 for mid in methods:
  for pure in [False,True]:
   v=f[f[mid+'__arm'].ne('unknown')].copy()
   if pure:v=v[v[mid+'__pure']]
   v['arm']=v[mid+'__arm'];keys=meta+['arm']
   z=v.groupby(keys)[CONT+RISK].mean().reset_index();z['method_id']=mid;z['subset']='pure_class_only' if pure else 'all_count_vectors';allagg.append(z)
   sup=v.groupby(keys).agg(attempted_pairs=('pair_id','size'),valid_pairs=('valid_distance','sum')).reset_index();sup['method_id']=mid;sup['subset']='pure_class_only' if pure else 'all_count_vectors';support.append(sup)
 agg=pd.concat(allagg,ignore_index=True);agg.to_csv(a.out/'COMMON_ANCHOR_ARM_VALUES.csv.gz',index=False);pd.concat(support).to_csv(a.out/'COMMON_ANCHOR_SUPPORT.csv.gz',index=False)
 bs=[];ss=[];commonrows=[]
 for subset,part in agg.groupby('subset'):
  for (n,m),g in part.groupby(['n','m']):
   for metric in CONT+RISK:
    pivot=g.pivot(index=meta,columns=['method_id','arm'],values=metric)
    cols=[(mid,arm) for mid in methods for arm in ['within','between']]
    pivot=pivot.reindex(columns=pd.MultiIndex.from_tuples(cols));common=pivot.dropna();count=len(common)
    for ix in common.index:commonrows.append(dict(zip(meta,ix),subset=subset,metric=metric))
    # Equal anchors per true image, equal images per building.
    buildings=common.groupby(level=['building','image_id']).mean().groupby(level='building').mean()
    for building,row in buildings.iterrows():
     vals={}
     for k,mid in enumerate(methods):
      prefix='candidate' if k==0 else 'baseline';vals[prefix+'_within']=row[(mid,'within')];vals[prefix+'_between']=row[(mid,'between')];vals[prefix+'_gap']=row[(mid,'between')]-row[(mid,'within')]
     vals['delta_within']=vals['candidate_within']-vals['baseline_within'];vals['delta_gap']=vals['candidate_gap']-vals['baseline_gap']
     bs.append(dict(subset=subset,n=n,m=m,metric=metric,building=building,candidate=methods[0],baseline=methods[1],common_anchors=count,**vals))
    rec=dict(subset=subset,n=n,m=m,metric=metric,candidate=methods[0],baseline=methods[1],common_anchors=count,images=common.index.get_level_values('image_id').nunique(),buildings=len(buildings))
    if len(buildings):
     x=pd.DataFrame([b for b in bs if b['subset']==subset and b['n']==n and b['m']==m and b['metric']==metric]);rec.update({c:x[c].mean() for c in ['candidate_within','candidate_between','candidate_gap','baseline_within','baseline_between','baseline_gap','delta_within','delta_gap']})
    ss.append(rec)
 pd.DataFrame(bs).to_csv(a.out/'COMMON_LIBRARY_BUILDINGS.csv',index=False);pd.DataFrame(ss).to_csv(a.out/'COMMON_LIBRARY_SUMMARY.csv',index=False);pd.DataFrame(commonrows).to_csv(a.out/'COMMON_MATCHED_ANCHORS.csv.gz',index=False)
 receipt=dict(request_sha256=hashlib.sha256(a.requests.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),frozen_anchors=len(q['common_anchors']),endpoint_pairs=len(f),methods=methods,pools=f.pool_id.nunique(),images=f.image_id.nunique(),buildings=f.building.nunique(),elapsed_seconds=time.perf_counter()-t,phase=a.phase,reused_pair_sha256=hashlib.sha256(a.reuse_pairs.read_bytes()).hexdigest() if a.reuse_pairs else None,labels_override_sha256=hashlib.sha256(a.labels_json.read_bytes()).hexdigest() if a.labels_json else None,classification='equal exchanged-block full class-count vectors; shared raw endpoints; metric-specific common anchors across both methods and both arms',failures=f.status.value_counts().to_dict())
 (a.out/'COMMON_LIBRARY_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
if __name__=='__main__':main()
