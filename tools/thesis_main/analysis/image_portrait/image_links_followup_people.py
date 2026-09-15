"""Outside-building 16-family person representations and real combinations.

Task-adjusted Q/T within condition; S describes actual scope response direction,
not physical correctness; B uses verified historical Semi payload only. Types
remain exploratory. All group counts are registered; k=2/4 receive replay.
"""
from __future__ import annotations
import itertools,math,time,warnings
from scipy.cluster.hierarchy import linkage,fcluster
from tools.thesis_main.analysis.image_portrait.image_links_followup_common import *
from tools.thesis_main.analysis.image_portrait.history_difficulty_review_v2 import cluster,cluster_static,one_replay,normalize_geometry,dense,dmask
BLOCKS={'Q':['quality'],'T':['log_time'],'S':['scope_reject','scope_accept'],'B':['edit','benefit']}
FAMILIES={''.join(keys):{k:BLOCKS[k]for k in keys}for n in range(1,5)for keys in itertools.combinations(BLOCKS,n)}
FAMILIES['quality_time_edit']={'Q':['quality'],'T':['log_time'],'E':['edit']}

def raw_axes():
 rows=pd.read_csv(V1/'inputs/response_metrics_sanitized.csv.gz');rows=rows[rows.main_worker_included].copy();rows['log_time']=np.log(rows.active_seconds.where(rows.active_seconds>0));audit=pd.read_csv(OUT/'inputs/response_audit.csv.gz').set_index('canonical_annotation_id')
 points=readj(OUT/'inputs/effective_points.json');initial=readj(B/'human/semi_initializations.jsonl.gz');edits={};init_sources=[]
 refs={r['image_id']:r for r in readj(B/'human/references.jsonl.gz')}
 # Reference improvement already has source restrictions in sanitized quality.
 # Recompute initial reference only when a documented old initialization quality exists.
 old_initial={}
 for p in [V1/'B/semi_response_metrics.csv', V1/'B/historical_semi_metrics.csv']:
  if p.exists():
   df=pd.read_csv(p)
   for r in df.to_dict('records'):old_initial[r['canonical_annotation_id']]=r
 for r in initial:
  cid=r['canonical_annotation_id'];p=r.get('initial_points_1024x512');init_sources.append(dict(canonical_annotation_id=cid,image_id=r['image_id'],worker_id=r['worker_id'],source_kind=r.get('initialization_source_kind','unknown'),trace_status=(r.get('trace')or{}).get('initial_import_match_status','unknown')))
  if cid not in points or not p:continue
  a=normalize_geometry(p);b=normalize_geometry(points[cid])
  if not a['valid']or not b['valid']:continue
  edits[cid]=dmask(dense(a['pairs']),dense(b['pairs']))
 rows['edit']=rows.canonical_annotation_id.map(edits)
 # Use exact verified initial geometry + declared usable reference, never current model.
 initials={r['canonical_annotation_id']:r for r in initial};benefit={}
 for r in rows[rows.raw_condition.eq('semi')&rows.quality.notna()].to_dict('records'):
  cid=r['canonical_annotation_id'];ini=initials.get(cid);ref=refs.get(r['image_id'])
  if not ini or not ref or ref.get('current_quality_status')in ['missing','reference_not_geometry_ready','not_evaluable_bad_gt']:continue
  # References in bundle contain explicit normalized pairs; inspect keys and accept only one defined reference.
  rp=ref.get('pairs')
  if not rp:continue
  a=normalize_geometry(ini['initial_points_1024x512']);final=normalize_geometry(points[cid])
  if a['valid'] and final['valid']:
   reference=dense(rp);fq=dmask(dense(final['pairs']),reference)
   if not np.isclose(fq,r['quality'],rtol=1e-5,atol=1e-6):raise ValueError('Reference mismatch with inherited Q: '+cid)
   benefit[cid]=dmask(dense(a['pairs']),reference)-fq
 rows['benefit']=rows.canonical_annotation_id.map(benefit)
 # Supplemental audited original Semi fields may provide initial quality, but no silent substitutes.
 rows['scope_reject']=np.where(rows.raw_condition.eq('oos')&rows.scope.isin(['oos','in_scope']),rows.scope.eq('oos').astype(float),np.nan)
 rows['scope_accept']=np.where(rows.raw_condition.isin(['manual','semi'])&rows.scope.isin(['oos','in_scope']),rows.scope.eq('in_scope').astype(float),np.nan)
 csv('E/semi_initialization_provenance.csv',init_sources);csv('E/person_axis_input_coverage.csv',rows.groupby('raw_condition')[['quality','log_time','scope_reject','scope_accept','edit','benefit']].count().reset_index())
 return rows

def fits(rows,arm,b):
 train=rows[rows.building.ne(b)].copy();profiles=[]
 for col in ['quality','log_time','scope_reject','scope_accept','edit','benefit']:
  q=train[train.raw_condition.eq(arm)]if col in ['quality','log_time']else train[train.raw_condition.eq('semi')]if col in ['edit','benefit']else train
  q=q.dropna(subset=[col]).copy();q['residual']=q[col]-q.groupby(['image_id','raw_condition'])[col].transform('median')
  for w,g in q.groupby('worker_id'):
   qualified=len(g)>=6 and g.building.nunique()>=3
   profiles.append(dict(condition=arm,target_building=b,worker_id=w,axis=col,score=g.residual.mean()if qualified else np.nan,qualified=qualified,training_responses=len(g),training_buildings=g.building.nunique(),source_condition=arm if col in ['quality','log_time']else 'semi'if col in ['edit','benefit']else 'scope_direction_sources'))
 return profiles

def subgroup_stats(dm,pc,ix):
 small=dm[np.ix_(ix,ix)];p=pc[ix];l=cluster(small,p,.1);co=collections.Counter(l);tri=np.triu_indices(len(ix),1);same=l[tri[0]]==l[tri[1]]
 return dict(n_people=len(ix),total_clusters=len(co),supported_clusters=sum(v>=2 for v in co.values()),singleton_share=sum(v==1 for v in co.values())/len(ix),point_count_disagreement=np.mean(p[tri[0]]!=p[tri[1]])if len(tri[0])else np.nan,within_mode=md(small[tri][same]),mode_entropy=-sum(v/len(ix)*np.log2(v/len(ix))for v in co.values()))

def run():
 start=time.monotonic();rows=raw_axes();pools=groups();meta=pd.read_csv(OUT/'inputs/image_metadata_whitelist.csv',keep_default_na=False).set_index('image_id');profiles=[]
 for arm in ['manual','semi']:
  for b in sorted(rows[rows.raw_condition.eq(arm)].building.unique()):profiles+=fits(rows,arm,b)
 pr=csv('E/outside_building_axis_profiles.csv',profiles);typing=[];capacity=[];parts={}
 for (arm,b),g in pr.groupby(['condition','target_building']):
  wide=g[g.qualified].pivot(index='worker_id',columns='axis',values='score')
  for fam,blocks in FAMILIES.items():
   cols=sum(blocks.values(),[]);w=wide.reindex(columns=cols).dropna().sort_index();n=len(w)
   if n<4:capacity.append(dict(condition=arm,building=b,family=fam,qualified_workers=n,requested_groups=2,actual_groups=0,status='insufficient_complete_axis_panel'));continue
   X=w.to_numpy(float);sd=X.std(0);Z=(X-X.mean(0))/np.where(sd>1e-10,sd,1.);offset=0
   for block,cs in blocks.items():Z[:,offset:offset+len(cs)]/=np.sqrt(len(cs));offset+=len(cs)
   tree=linkage(Z,method='ward')
   for k in range(2,n//2+1):
    lab=fcluster(tree,k,criterion='maxclust');co=collections.Counter(lab);capacity.append(dict(condition=arm,building=b,family=fam,qualified_workers=n,requested_groups=k,actual_groups=len(co),singleton_types=sum(v==1 for v in co.values()),status='fitted_exploratory'))
    if k not in [2,4]:continue
    parts[arm,b,fam,k]=dict(zip(w.index,lab));
    for worker,l in zip(w.index,lab):typing.append(dict(condition=arm,target_building=b,family=fam,requested_groups=k,worker_id=worker,type_id=int(l),training_type_size=co[l],supported_type=co[l]>=2))
 csv('E/information_family_group_capacity.csv',capacity);csv('E/training_only_memberships.csv.gz',typing)
 static_cache={};growth_cache={};combinations=[];growth=[];targetcap=[];raw_groups=[];continuous=[];testids=[]
 def stat(i,arm,dm,pc,ix):
  key=(i,arm,tuple(ix))
  if key not in static_cache:static_cache[key]=subgroup_stats(dm,pc,ix)
  return static_cache[key]
 def gr(i,arm,dm,pc,ix,workers):
  key=(i,arm,tuple(ix))
  if key not in growth_cache:
   if len(ix)<4:r={}
   else:
    ss,_,_=one_replay(dm[np.ix_(ix,ix)],pc[ix],.1,24,i,arm+'|'+','.join(workers[ix]),False);x=pd.DataFrame(ss);r=dict(full_by8=np.mean(x.full_onset_no_gate<=8),core_by19=np.mean(x.core_onset_10<=19),full_tail=x.full_tail_no_gate.mean(),core_tail=x.core_tail_10.mean(),late_quarter_new=x.late_quarter_new.mean(),half_tv=x.half_tv_all.mean(),orders=24)
   growth_cache[key]=r
  return growth_cache[key]
 for num,((i,arm),(r,dm,pc,workers,cids))in enumerate(pools.items()):
  if arm not in ['manual','semi']or len(workers)<4:continue
  b=i.split('_')[0];n=len(workers);rng=np.random.default_rng(seed(i,arm,'shared_actual_future2'));held=np.sort(rng.choice(n,2,replace=False));trainix=np.array([j for j in range(n)if j not in held]);testids.append(dict(image_id=i,condition=arm,future_workers=';'.join(workers[held]),future_canonical_ids=';'.join(cids[held]),observed_n=n))
  proposals=[]
  for m in [2,3,4]:
   if len(trainix)<m:continue
   cap=300 if m==2 else 48
   if math.comb(len(trainix),m)<=cap:ss=list(itertools.combinations(trainix,m))
   else:
    seen=set()
    while len(seen)<cap:seen.add(tuple(sorted(rng.choice(trainix,m,replace=False))))
    ss=sorted(seen)
   for ix0 in ss:
    ix=np.array(ix0,int);st=stat(i,arm,dm,pc,ix);st=dict(st,heldout_geometry_coverage=np.mean(np.min(dm[np.ix_(held,ix)],axis=1)<=.1))
    proposals.append((ix,st))
  for (aa,bb,fam,k),mapping in parts.items():
   if aa!=arm or bb!=b:continue
   known=np.array([j for j,w in enumerate(workers)if w in mapping],int);labs={j:mapping[workers[j]]for j in known}
   targetcap.append(dict(image_id=i,condition=arm,building=b,family=fam,requested_groups=k,observed_n=n,typed_target_n=len(known),unclassified_n=n-len(known)))
   for ix,st in proposals:
    if any(j not in labs for j in ix):continue
    vals=[labs[j]for j in ix];occup=sorted(collections.Counter(vals).values(),reverse=True);sig=''.join(chr(65+j)*v for j,v in enumerate(occup));actual=''.join(chr(64+v)for v in sorted(vals))
    combinations.append(dict(image_id=i,building=b,condition=arm,family=fam,requested_groups=k,signature=sig,actual_types=actual,all_types_training_supported=all(sum(v==mapping[workers[j]]for v in mapping.values())>=2 for j in ix),workers=';'.join(workers[ix]),future_workers=';'.join(workers[held]),**st))
   # Actual group sizes, not duplicated annotators; n>=10 pools only for growth comparisons.
   for lab in sorted(set(labs.values())):
    ix=np.array([j for j in known if labs[j]==lab]);st=stat(i,arm,dm,pc,ix);row=dict(image_id=i,condition=arm,building=b,family=fam,requested_groups=k,type_id=int(lab),workers=';'.join(workers[ix]),**st)
    if n>=10 and len(ix)>=4:row.update(gr(i,arm,dm,pc,ix,workers));growth.append(row)
    raw_groups.append(row)
   if n>=10 and len(known)>=4:
    growth.append(dict(image_id=i,condition=arm,building=b,family=fam,requested_groups=k,type_id=0,workers=';'.join(workers[known]),**stat(i,arm,dm,pc,known),**gr(i,arm,dm,pc,known,workers)))
  # Continuous axis comparator, same n, same targets, independently trained scores.
  for axis in ['quality','log_time']:
   p=pr[pr.condition.eq(arm)&pr.target_building.eq(b)&pr.axis.eq(axis)&pr.qualified].set_index('worker_id').score
   rank=sorted([j for j in trainix if workers[j]in p.index],key=lambda j:(p[workers[j]],workers[j]))
   for m in [4,6,8]:
    if len(rank)<2*m:continue
    for kind,ix0 in [('lower',rank[:m]),('higher',rank[-m:]),('mixed',rank[:m//2]+rank[-(m-m//2):])]:
     ix=np.array(sorted(ix0),int);continuous.append(dict(image_id=i,condition=arm,building=b,axis=axis,composition=kind,workers=';'.join(workers[ix]),future_workers=';'.join(workers[held]),**stat(i,arm,dm,pc,ix),**gr(i,arm,dm,pc,ix,workers),heldout_geometry_coverage=np.mean(np.min(dm[np.ix_(held,ix)],axis=1)<=.1)))
  if num%20==0:print('PERSON',num,'combination rows',len(combinations),'unique growth',len(growth_cache),'seconds',round(time.monotonic()-start),flush=True)
 c=csv('E/real_combinations_fixed_future2.csv.gz',combinations);g=csv('E/actual_type_growth.csv.gz',growth);csv('E/actual_type_distributions.csv.gz',raw_groups);csv('E/per_image_family_support.csv',targetcap);csv('E/shared_future_person_ids.csv',testids);co=csv('E/continuous_equal_count_compositions.csv',continuous)
 measures=['total_clusters','supported_clusters','singleton_share','point_count_disagreement','heldout_geometry_coverage','mode_entropy'];csv('E/combination_summary.csv',c.groupby(['condition','family','requested_groups','n_people','signature'])[measures].mean().reset_index())
 contrasts=[]
 for (arm,fam,k),z in c[c.requested_groups.eq(2)&c.n_people.eq(2)].groupby(['condition','family','requested_groups']):
  av=z.groupby(['image_id','building','actual_types'])[measures].mean().reset_index();a=av[av.actual_types.eq('AB')].merge(av[av.actual_types.eq('AA')],on=['image_id','building'],suffixes=('_ab','_aa')).merge(av[av.actual_types.eq('BB')],on=['image_id','building'])
  for m in measures:
   if len(a):a['delta']=a[m+'_ab']-.5*(a[m+'_aa']+a[m]);contrasts.append(dict(condition=arm,family=fam,comparison='AB minus marginal-matched (AA+BB)/2',metric=m,**paired(a)))
 csv('E/marginal_matched_pair_compositions.csv',contrasts)
 effects=[]
 for (arm,axis,n),z in co.groupby(['condition','axis','n_people']):
  a=z[z.composition.eq('lower')].merge(z[z.composition.eq('higher')],on=['image_id','building'],suffixes=('_low','_high'))
  for m in measures+['full_by8','core_by19','late_quarter_new']:
   a['delta']=a[m+'_low']-a[m+'_high'];effects.append(dict(condition=arm,axis=axis,n_people=n,metric=m,**paired(a)))
 csv('E/continuous_axis_paired_differences.csv',effects)
 js('E/execution.json',dict(families=list(FAMILIES),all_counts='2..floor(eligible/2) capacity; actual k2/k4 replay',axis_minimum='6 source responses,3 buildings per axis; complete block intersection',raw_combinations=len(c),growth_rows=len(g),unique_subgroup_growth=len(growth_cache),actual_images=c.image_id.nunique(),new_participants=0,outside_target_building=True,target_conditions_separated=True,unknown_is_not_type=True,future_evaluation='same fixed two real people excluded from every tested combination',subgroup_growth='24 within-pool permutations; cannot infer new-person population convergence',no_fixed_type_truth=True,elapsed=time.monotonic()-start))
 print('E DONE',len(c),len(g),flush=True)
if __name__=='__main__':run()
