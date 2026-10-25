#!/usr/bin/env python3
"""Exact current-pool capacity and held-out original-answer contrasts.

This is a raw-answer use test, separate from fusion exchange evaluation. It does
not select a K or modify labels. It preserves same-corner-count geometry checks.
"""
import argparse,gzip,json,math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from build_condition_response_classes import save_csv,save_json

METRICS=['turn_difference','short_edge_difference','Q_difference','D10_difference',
 'area_log_difference','height_log_difference','azimuth_difference_deg',
 'top_difference_deg','bottom_difference_deg','unmatched_fraction']

def summarize_result(result):
 sums=[]
 for (method,condition,pool_layer,layer,subset,metric),g in result.groupby(['method','condition','pool_layer','image_layer','subset','metric']):
  for level in ['ALL','简单','中等','困难','单列']:
   z=g if level=='ALL' else g[g.difficulty.eq(level)]
   if not len(z):continue
   b=z.groupby('building')[['within','cross','cross_minus_within']].mean()
   sums.append(dict(method=method,condition=condition,pool_layer=pool_layer,image_layer=layer,subset=subset,metric=metric,difficulty=level,
      images=z.image_id.nunique(),buildings=len(b),image_within=z.within.mean(),image_cross=z.cross.mean(),
      image_ratio=z.cross.mean()/z.within.mean() if z.within.mean()>1e-10 else np.nan,
      images_cross_larger=int(z.cross_larger.sum()),image_fraction_cross_larger=z.cross_larger.mean(),
      building_within=b.within.mean(),building_cross=b.cross.mean(),buildings_cross_larger=int(b.cross_minus_within.gt(0).sum())))
 return pd.DataFrame(sums)

def pair_distance(p,q):
 p=np.asarray(p,float);q=np.asarray(q,float)
 az=((p[::2,0,None]-q[None,::2,0]+512)%1024-512)*360/1024
 ii,jj=linear_sum_assignment(np.abs(az));ok=np.abs(az[ii,jj])<=9
 ii,jj=ii[ok],jj[ok]
 out={'unmatched_fraction':1-2*len(ii)/(len(p)/2+len(q)/2)}
 for name,values in [('azimuth_difference_deg',np.abs(az[ii,jj])),
       ('top_difference_deg',np.abs(p[2*ii,1]-q[2*jj,1])*180/512),
       ('bottom_difference_deg',np.abs(p[2*ii+1,1]-q[2*jj+1,1])*180/512)]:
  out[name]=float(np.mean(values)) if len(values) else np.nan
 return out

def build_pairs(snapshot,features):
 lookup=features.set_index('object_id');rows=[]
 for pool in snapshot['images']:
  records=pool['records'];meta=pool['meta'];poolid=pool['pool_id']
  for ia,a in enumerate(records):
   ra=lookup.loc[a['object_id']]
   for b in records[ia+1:]:
    rb=lookup.loc[b['object_id']]
    row=dict(pool_id=poolid,image_id=meta['image_id'],image=meta['image'],condition=meta['condition'],building=meta['building'],
      difficulty=ra.difficulty_coarse,image_layer=ra.image_layer,pool_layer=meta['layer'],
      worker_a=a['worker_id'],worker_b=b['worker_id'],object_a=a['object_id'],object_b=b['object_id'],
      corners_a=len(a['points'])//2,corners_b=len(b['points'])//2,
      same_corner_count=len(a['points'])==len(b['points']))
    row.update(pair_distance(a['points'],b['points']))
    for dst,src in [('turn_difference','turn_n'),('short_edge_difference','short_turn_edges'),
                    ('Q_difference','B8L2'),('D10_difference','D10'),
                    ('area_log_difference','log_area'),('height_log_difference','log_height')]:
     row[dst]=abs(ra[src]-rb[src])
    rows.append(row)
 return pd.DataFrame(rows)

def main(a):
 root=Path(a.classifications);fea=Path(a.features);inp=Path(a.inputs)
 label_files=[root/'NEW_METHOD_LABELS_ALL_LOBO.csv.gz',root/'AXIS_METHOD_LABELS_ALL_LOBO.csv.gz',root/'SCOPE_INCREMENT_LABELS_ALL_LOBO.csv.gz']
 labels=pd.concat([pd.read_csv(p) for p in label_files],ignore_index=True)
 assert not labels.duplicated(['method','heldout_building','worker_id']).any()
 save_csv(labels,root/'CANDIDATE_LABELS_COMPLETE_ALL_LOBO.csv.gz')
 snapshot=json.load(gzip.open(inp/'INPUT_SNAPSHOT.json.gz','rt'))
 raw=pd.read_csv(fea/'RAW_CONDITION_RESPONSE_RECORDS.csv.gz')
 parts=[];caps=[]
 for (method,building),labs in labels[labels.heldout_building.ne('ALL')&labels.known].groupby(['method','heldout_building']):
  lm=labs.set_index('worker_id').class_id.to_dict()
  for pool in snapshot['images']:
   meta=pool['meta']
   if meta['building']!=building:continue
   workers=[r['worker_id'] for r in pool['records']]
   counts=pd.Series([lm[w] for w in workers if w in lm]).value_counts().to_dict();N=sum(counts.values())
   for cl,num in counts.items():
    parts.append(dict(method=method,pool_id=pool['pool_id'],image_id=meta['image_id'],condition=meta['condition'],building=building,
      image=meta['image'],difficulty=meta['difficulty'],layer=meta['layer'],actual_pool_n=len(workers),known_pool_n=N,
      class_id=cl,class_n=num,members='|'.join(w for w in workers if lm.get(w)==cl)))
   for source,ns in counts.items():
    for target,nt in counts.items():
     if source==target:continue
     for n in [8,10,12,14,16,18,20,22,24,26,28,30]:
      if n>N:continue
      mmax=max(0,min(ns//2,nt,(N-n)//2,n));mmaxall=max(0,min(ns//2,nt,(len(workers)-n)//2,n))
      acmax=max(0,min(ns,nt,len(workers)-n,n))
      if mmaxall<2:continue
      caps.append(dict(method=method,pool_id=pool['pool_id'],image_id=meta['image_id'],condition=meta['condition'],building=building,
       difficulty=meta['difficulty'],layer=meta['layer'],actual_pool_n=len(workers),known_pool_n=N,
       source_class=source,target_class=target,source_n=ns,target_n=nt,n=n,
       max_strict_m_known_background=mmax,max_strict_m_allow_unknown_background=mmaxall,max_direct_ac_m=acmax,
       strict_definition='D,X,Y,Z pairwise disjoint; |D|=n-m; |X|=|Y|=|Z|=m; X/Y source; Z target',
       actual_swaps_not_seat_change='All strict swaps have m actual persons; complete team target seats increase by m.'))
 save_csv(pd.DataFrame(parts),root/'CURRENT_POOL_CLASS_CAPACITY.csv.gz')
 capacity=pd.DataFrame(caps);save_csv(capacity,root/'STRICT_ABC_CAPACITY_BY_N.csv.gz')
 rows=[]
 for (method,condition,n),g in capacity.groupby(['method','condition','n']):
  for m in [4,5,6,7,8,9,10,12,14]:
   z=g[g.max_strict_m_known_background.ge(m)]
   if len(z):rows.append(dict(method=method,condition=condition,n=n,m=m,pools=z.pool_id.nunique(),buildings=z.building.nunique(),directions=len(z)))
 save_csv(pd.DataFrame(rows),root/'STRICT_ABC_CAPACITY_SUMMARY.csv')
 pairpath=fea/'RAW_ORIGINAL_PAIR_DISTANCES.csv.gz'
 if pairpath.exists():pairs=pd.read_csv(pairpath)
 else:
  pairs=build_pairs(snapshot,raw);save_csv(pairs,pairpath)
 out=[]
 for (method,building),labs in labels[labels.heldout_building.ne('ALL')&labels.known].groupby(['method','heldout_building']):
  lm=labs.set_index('worker_id').class_id.to_dict();d=pairs[pairs.building.eq(building)].copy()
  d['class_a']=d.worker_a.map(lm);d['class_b']=d.worker_b.map(lm);d=d[d.class_a.notna()&d.class_b.notna()]
  for pool_id,g in d.groupby('pool_id'):
   base={k:g.iloc[0][k] for k in ['pool_id','image_id','image','condition','building','difficulty','image_layer','pool_layer']};base['method']=method
   for subset,gg in [('all_pairs',g),('same_corner_count',g[g.same_corner_count])]:
    within=gg[gg.class_a.eq(gg.class_b)];cross=gg[gg.class_a.ne(gg.class_b)]
    if len(within)<4 or len(cross)<4:continue
    # Equal-weight within-class means avoid the largest class alone defining
    # the within distance. Cross is equal-weight unordered class-pair means.
    within=within.copy();cross=cross.copy()
    cross['class_pair']=['|'.join(sorted(x)) for x in zip(cross.class_a,cross.class_b)]
    for metric in METRICS:
     w=within.groupby('class_a')[metric].mean();c=cross.groupby('class_pair')[metric].mean()
     wm=float(w.mean());cm=float(c.mean())
     if not np.isfinite(wm) or not np.isfinite(cm):continue
     out.append(dict(**base,subset=subset,metric=metric,within_pair_n=int(within[metric].notna().sum()),
        cross_pair_n=int(cross[metric].notna().sum()),within_classes=len(w),cross_class_pairs=len(c),
        within=wm,cross=cm,cross_minus_within=cm-wm,ratio=cm/wm if wm>1e-10 else np.nan,
        cross_larger=cm>wm))
 result=pd.DataFrame(out);save_csv(result,root/'HELDOUT_RAW_DISTANCE_BY_IMAGE.csv.gz')
 save_csv(summarize_result(result),root/'HELDOUT_RAW_DISTANCE_SUMMARY.csv')
 save_json(dict(methods=labels.method.nunique(),all_labels=len(labels),raw_pairs=len(pairs),raw_image_comparisons=len(result),
    no_new_fusion=True,raw_test_scope='All current formal pools; ordinary_manual, special_manual, doorway_manual, ordinary_semi and special_semi separated using snapshot pool_layer.',
    same_count='Exact raw corner-pair count equality; still compares top/bottom azimuth and scale, not just corner number.',
    pairing='One-to-one Hungarian azimuth matching within 9 degrees; unmatched fraction reported separately.',
    aggregation='Equal class means within; equal unordered class-pair means across; then image and building means.',
    qualification='Historical labels fitted excluding target building; no target fusion score used for candidates.',
    full_combination_note='Capacity is a mathematical feasibility bound, not a claim that endpoints or permutations were computed.'),root/'CAPACITY_RAW_USE_RECEIPT.json')
 print('saved',labels.method.nunique(),'methods;',len(pairs),'raw pairs;',len(result),'image contrasts')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--classifications',required=True);p.add_argument('--features',required=True);p.add_argument('--inputs',required=True);main(p.parse_args())
