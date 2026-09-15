"""True-person composition changes uncertainty; never assumes mixing is better.
Reuses every recovered old combination but recomputes FUTURE coverage excluding
all its own members. Fixed-future matched contrasts remove changing-holdout bias.
"""
import collections,itertools,json,time
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.convergence_v2_common import *
from tools.thesis_main.analysis.image_portrait.convergence_v2_process import group_replay,partition_stats


def multiplicity(labels):
 sizes=sorted(collections.Counter(labels).values(),reverse=True)
 return ''.join(chr(65+j)*s for j,s in enumerate(sizes))

def recompute():
 old=pd.read_csv(OLD/'E/real_worker_combinations.csv.gz');responses=read_responses();responses=responses[responses.main_worker_included&responses.geometry_valid];dense=boundary_map();rows=[];indexrows=[]
 for ii,((image,arm),g) in enumerate(old.groupby(['image_id','condition'])):
  h=responses[(responses.image_id==image)&(responses.raw_condition==arm)].sort_values('worker_id').reset_index(drop=True);dm,pcs=pairs_for(h,dense);wm={w:j for j,w in enumerate(h.worker_id)};n=len(h)
  indexrows.append(dict(image_id=image,condition=arm,ordered_workers=';'.join(h.worker_id),ordered_canonical_ids=';'.join(h.canonical_annotation_id),n=n))
  for r in g.to_dict('records'):
   w=r['workers'].split(';');assert len(w)==len(set(w));ix=np.array([wm[v]for v in w],int);rest=np.setdiff1d(np.arange(n),ix);subdm=dm[np.ix_(ix,ix)];lab=cluster(subdm,pcs[ix],.1);med=medoids(subdm,lab,2);stats=partition_stats(subdm,pcs[ix],lab)
   cov=(dm[:,ix[med]].min(1)<=.1+1e-12) if len(med) else np.zeros(n,bool)
   singleton_cov=dm[:,ix].min(1)<=.1+1e-12
   subsetmask=sum(1<<int(j)for j in ix);coveredmask=sum(1<<int(j)for j in np.flatnonzero(cov));anymask=sum(1<<int(j)for j in np.flatnonzero(singleton_cov))
   rows.append(dict(combo_id=r['combo_id'],image_id=image,building=image.split('_')[0],condition=arm,people=len(ix),workers=r['workers'],canonical_ids=';'.join(h.canonical_annotation_id.iloc[ix]),future_workers=';'.join(h.worker_id.iloc[rest]),future_n=len(rest),future_coverage=float(cov[rest].mean()) if len(rest)else np.nan,future_coverage_allow_singletons=float(singleton_cov[rest].mean()) if len(rest)else np.nan,future_new_point_count=float((~np.isin(pcs[rest],pcs[ix])).mean())if len(rest)else np.nan,subset_bitmask=subsetmask,covered_worker_bitmask=coveredmask,any_covered_worker_bitmask=anymask,old_self_inclusive_coverage=r['observed_population_coverage'],population_combinations=r['population_combinations'],sampled_combinations=r['sampled_combinations'],**stats))
  if ii%40==0:print('COMBINATION',ii+1,'rows',len(rows),flush=True)
 c=csv('combinations/real_combinations_external_future.csv.gz',rows);csv('combinations/bitmask_worker_index.csv',indexrows)
 return c,pd.DataFrame(indexrows)

def composition_analysis(c,indices):
 m=pd.read_csv(OLD/'E/worker_memberships_oof.csv.gz');m=m[(m.panel=='native')&m.k.isin([2,3,4])]
 maps={key:dict(zip(g.worker_id,g.label))for key,g in m.groupby(['heldout_building','information','k'])}
 sums=[];examples=[];failure=[];fixed=[];contrasts=[];growth=[]
 bybuilding=collections.defaultdict(list)
 for key,mp in maps.items():bybuilding[key[0]].append((key,mp))
 for ii,((image,arm),g) in enumerate(c.groupby(['image_id','condition'])):
  b=image.split('_')[0];people_lists=g.workers.str.split(';').tolist();index=indices[(indices.image_id==image)&(indices.condition==arm)].iloc[0];wl=index.ordered_workers.split(';');n=len(wl)
  for (bb,info,kc),mapping in bybuilding[b]:
   pats=[];exact=[]
   for w in people_lists:
    labs=[mapping.get(v) for v in w];pats.append(multiplicity(labs) if all(l is not None for l in labs)else'unknown_not_a_type');exact.append(''.join(sorted(labs))if all(l is not None for l in labs)else'')
   z=g.copy();z['pattern']=pats;z['exact_fold_labels']=exact;valid=z[z.pattern!='unknown_not_a_type']
   for (size,patt),u in valid.groupby(['people','pattern']):
    row=dict(image_id=image,building=b,condition=arm,information=info,k_classes=kc,people=size,pattern=patt,combinations=len(u),available_target_people=sum(w in mapping for w in wl),unknown_target_people=sum(w not in mapping for w in wl),topology_disagreement=u.topology_disagreement.mean(),same_topology_dispersion=u.same_topology_median_d.mean(),mode_entropy=u.mode_entropy.mean(),supported_modes=u.n_supported_modes.mean(),future_coverage=u.future_coverage.mean(),future_new_point_count=u.future_new_point_count.mean())
    sums.append(row)
    for _,e in u.head(1).iterrows():examples.append(dict(**row,combo_id=int(e.combo_id),workers=e.workers,canonical_ids=e.canonical_ids,exact_fold_labels=e.exact_fold_labels,future_workers=e.future_workers))
   if len(z)!=len(valid):failure.append(dict(image_id=image,condition=arm,information=info,k_classes=kc,total_combinations=len(z),untyped_combinations=len(z)-len(valid),reason='missing_outside_building_profile_not_a_real_class'))
   # Fix two future people for matched comparison, then use ONLY disjoint
   # observed combinations. Common future people remove roster-complement bias.
   if n>=6 and (info,kc) in [('Q',2),('T',2),('S',2),('B',2),('QTSB',4),('quality_time_edit',3)]:
    rng=np.random.default_rng(seed_for(image,arm,info,kc,'future'))
    for rep in range(30):
     fi=rng.choice(n,2,replace=False);future_mask=(1<<int(fi[0]))|(1<<int(fi[1]));u=valid[(valid.subset_bitmask.astype(np.int64)&future_mask)==0].copy()
     if not len(u):continue
     cm=u.covered_worker_bitmask.astype(np.int64).to_numpy();u['fixed_future_cov']=(((cm&(1<<int(fi[0])))>0).astype(float)+((cm&(1<<int(fi[1])))>0).astype(float))/2
     groups=u.groupby(['people','pattern']).agg(combinations=('combo_id','size'),coverage=('fixed_future_cov','mean'),topology_disagreement=('topology_disagreement','mean'),entropy=('mode_entropy','mean'),within_geom=('same_topology_median_d','mean')).reset_index()
     for row in groups.to_dict('records'):fixed.append(dict(image_id=image,building=b,condition=arm,information=info,k_classes=kc,replay=rep,future_workers=';'.join(wl[j]for j in fi),**row))
     if kc==2:
      # Match A/B population margins for n2 using AA, BB, AB. All targets share
      # the SAME withheld people. No fused-quality estimand is invented.
      v=u[u.people==2]
      cls={p:h for p,h in v.groupby('exact_fold_labels')}
      if all(p in cls for p in ['AA','AB','BB']):
       for metric in ['fixed_future_cov','topology_disagreement','same_topology_median_d','mode_entropy']:
        a=cls['AB'][metric].mean();base=.5*(cls['AA'][metric].mean()+cls['BB'][metric].mean())
        contrasts.append(dict(image_id=image,building=b,condition=arm,information=info,replay=rep,metric=metric,mixed=a,pure_margin_matched=base,delta=a-base))
  if ii%40==0:print('PATTERNS',ii+1,'summaries',len(sums),'future rows',len(fixed),flush=True)
 csv('combinations/composition_image_summaries.csv.gz',sums);csv('combinations/real_pattern_examples.csv.gz',examples);csv('combinations/profile_coverage_failures.csv',failure);csv('combinations/fixed_future_compositions.csv.gz',fixed)
 if contrasts:
  d=pd.DataFrame(contrasts).groupby(['image_id','building','condition','information','metric'])[['mixed','pure_margin_matched','delta']].mean().reset_index();csv('combinations/fixed_future_paired_image_contrasts.csv',d)
  out=[]
  for keys,g in d.groupby(['condition','information','metric']):out.append(dict(condition=keys[0],information=keys[1],metric=keys[2],mixed=g.mixed.mean(),pure_margin_matched=g.pure_margin_matched.mean(),**paired_interval(g,'delta')))
  csv('combinations/fixed_future_paired_summary.csv',out)
 js('combinations/method.json',dict(real_subsets=len(c),old_results_preserved=True,all_old_subsets_recomputed=True,coverage='strictly excludes all selected combination members; fixed-future contrasts additionally hold future identities constant',information='all16 previous information families, group counts2/3/4 for composition; all counts studied in subgroup route',patterns='exact fold-local letters AND label-invariant multiplicity patterns; unknown not a type',future_replays=30,reference_quality='not analyzed as fused output; old member median remains old descriptive only',short_groups='2-4 people do not establish full convergence',inference_unit='image then building; permutations/combinations do not add independent samples'))

if __name__=='__main__':
 path=OUT/'combinations/real_combinations_external_future.csv.gz'
 if path.exists():c=pd.read_csv(path);idx=pd.read_csv(OUT/'combinations/bitmask_worker_index.csv')
 else:c,idx=recompute()
 composition_analysis(c,idx)
