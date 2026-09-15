"""Recompute historical uncertainty before expert-adjudicated coarse grading.

Only verified effective geometry is used; no legacy difficulty, reference score,
model feature or expert grade enters geometry or replay. Singleton statistics are
not errors. All permutations reuse distinct observed people and are not new data.
"""
from __future__ import annotations
import argparse,collections,gzip,hashlib,itertools,json,math,time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage,fcluster
from scipy.spatial.distance import squareform
from scipy.optimize import linear_sum_assignment
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_people import dense,dmask
ROOT=Path(__file__).resolve().parents[4]
B=ROOT/'analysis_results/image_portrait_20260914_v1'
PREV=B/'cloud/history_difficulty_20260915_v1/run_13859d59'
OUT=B/'cloud/history_difficulty_review_20260915_v2/run_c0069628'
EXCLUDE={'W019','W026'}
CUTS=(.05,.075,.10,.125,.15,.20)

def js(name,obj):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
 def clean(x):
  if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
  if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
  if isinstance(x,(np.integer,)):return int(x)
  if isinstance(x,(np.bool_,)):return bool(x)
  if isinstance(x,(float,np.floating)):return float(x)if np.isfinite(x)else None
  return x
 p.write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def csv(name,rows):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);df=rows if isinstance(rows,pd.DataFrame)else pd.DataFrame(rows)
 if not len(df.columns):df=pd.DataFrame(columns=['status'])
 df.to_csv(p,index=False,float_format='%.12g',compression={'method':'gzip','mtime':0} if p.suffix=='.gz'else 'infer');return df

def readj(p):
 with (gzip.open(p,'rt',encoding='utf-8-sig') if str(p).endswith('.gz') else open(p,encoding='utf-8-sig'))as f:return [json.loads(x)for x in f if x.strip()]

def sd(*s):return int(hashlib.sha256('|'.join(map(str,s)).encode()).hexdigest()[:8],16)
def med(a):return float(np.median(a))if len(a)else np.nan

def cluster(dm,pcs,cut):
 labels=np.empty(len(pcs),int);offset=0
 for pc in sorted(set(pcs)):
  ix=np.flatnonzero(pcs==pc)
  labs=np.ones(len(ix),int)if len(ix)<2 else fcluster(linkage(squareform(dm[np.ix_(ix,ix)],checks=True),method='complete'),cut,criterion='distance')
  labels[ix]=labs+offset;offset=int(labels[ix].max())
 return labels

def groups_from_raw():
 raw=readj(B/'human/responses.jsonl.gz');rows=[];bd={};points={}
 for r in raw:
  # Explicit whitelist. Never read old difficulty choices or old risk fields.
  row={k:r.get(k)for k in ('canonical_annotation_id','image_id','worker_id','raw_condition','stage','context_key','processing_status','confirmation_source','imputed_point','raw_point_count','effective_point_count')}
  row['main_worker']=row['worker_id']not in EXCLUDE
  row['raw_odd']=bool(row['raw_point_count']%2)
  row['reviewed_repair']=row['processing_status']in ('confirmed_point_removed','confirmed_point_added') and bool(row['confirmation_source'])
  pts=r.get('effective_points_1024x512')
  if row['reviewed_repair']:
   assert pts is not None and len(pts)%2==0
   if r['processing_status']=='confirmed_point_added':assert r.get('review_decision')and r['review_decision']['user_decision']['action']=='add_confirmed_point'
  if row['raw_condition']not in ('manual','semi'):reason='oos_rule_task_separate'
  elif not row['main_worker']:reason='excluded_worker'
  elif row['raw_odd']and not row['reviewed_repair']:reason='unconfirmed_odd_or_ambiguous'
  elif pts is None:reason='missing_effective_geometry'
  elif not r.get('calculation_included',True):reason='explicit_review_excluded'
  else:
   norm=normalize_geometry(pts);reason=''if norm['valid']else 'geometry_'+norm['reason']
   if not reason:
    bd[row['canonical_annotation_id']]=dense(norm['pairs']);points[row['canonical_annotation_id']]=pts
    row['effective_point_count']=len(pts)
  row['analysis_valid']=not reason;row['exclusion_reason']=reason
  # Scope only; all OOS variants are a single direction, not difficulty.
  scope=[c for c in r.get('choices',[])if str(c.get('from_name','')).lower()=='scope']
  vals=[str(v)for c in scope for v in c.get('choices',[])]
  row['scope']='oos'if any(v.lower().startswith('oos')for v in vals)else 'in_scope'if any(v.lower() in ('normal','in_scope','in-scope')for v in vals)else 'unknown'
  rows.append(row)
 df=csv('audit/response_inclusion.csv.gz',rows)
 csv('audit/reviewed_repairs.csv',df[df.reviewed_repair & df.main_worker & df.raw_condition.isin(['manual','semi'])])
 csv('audit/excluded_responses.csv',df[df.main_worker&df.raw_condition.isin(['manual','semi'])&~df.analysis_valid])
 js('audit/coverage.json',dict(raw_canonical=len(df),main_manual=int(((df.raw_condition=='manual')&df.main_worker).sum()),main_semi=int(((df.raw_condition=='semi')&df.main_worker).sum()),valid_manual=int(((df.raw_condition=='manual')&df.analysis_valid).sum()),valid_semi=int(((df.raw_condition=='semi')&df.analysis_valid).sum()),raw_odd_main=int(df[df.main_worker&df.raw_condition.isin(['manual','semi'])].raw_odd.sum()),reviewed_retained=int((df.reviewed_repair&df.analysis_valid).sum()),worker_policy=sorted(EXCLUDE),invalid_not_clusters=True,invalid_image_not_whole_excluded=True))
 groups={}
 for (i,c),g in df[df.main_worker&df.raw_condition.isin(['manual','semi'])].groupby(['image_id','raw_condition']):
  assert g.worker_id.nunique()==len(g),'Repeated person is not an independent vote'
  v=g[g.analysis_valid].sort_values('worker_id').reset_index(drop=True);n=len(v);pcs=v.effective_point_count.to_numpy(int);dm=np.zeros((n,n))
  for a,z in itertools.combinations(range(n),2):dm[a,z]=dm[z,a]=dmask(bd[v.canonical_annotation_id[a]],bd[v.canonical_annotation_id[z]])if pcs[a]==pcs[z]else 2.
  groups[i,c]=(g,v,dm,pcs)
 # portable cache contains only sanitized geometry and actual identities
 (OUT/'cache').mkdir(exist_ok=True)
 arrays={};index=[]
 for no,((i,c),(g,v,dm,pcs)) in enumerate(groups.items()):
  key=f'g{no:03d}';arrays[key+'_dm']=dm;arrays[key+'_pcs']=pcs
  arrays[key+'_workers']=v.worker_id.to_numpy(str);arrays[key+'_ids']=v.canonical_annotation_id.to_numpy(str)
  index.append(dict(key=key,image_id=i,condition=c,n_observed=len(g),n_valid=len(v),n_excluded=len(g)-len(v),repaired_ids=v.loc[v.reviewed_repair,'canonical_annotation_id'].tolist()))
 np.savez_compressed(OUT/'cache/pairwise_geometry.npz',**arrays);js('cache/group_index.json',index)
 js('cache/effective_points.json',points)
 return groups

def cluster_static(dm,pcs,cut):
 n=len(pcs)
 if n==0:return dict(n_valid=0,total_clusters=0,supported_clusters=0,singletons=0),[],[],np.array([],int)
 lab=cluster(dm,pcs,cut);co=collections.Counter(lab);f1=sum(v==1 for v in co.values());f2=sum(v==2 for v in co.values());supp=[l for l,v in co.items()if v>=2]
 p=np.array(list(co.values()))/n;tri=np.triu_indices(n,1);within=dm[tri][(lab[:,None]==lab[None,:])[tri]]
 stat=dict(n_valid=n,total_clusters=len(co),supported_clusters=len(supp),singletons=f1,doubletons=f2,singleton_share=f1/n,supported_share=1-f1/n,largest_share=max(co.values())/n,effective_modes_simpson=1/np.sum(p*p),entropy_bits=-float(np.sum(p*np.log2(p))),point_count_disagreement=float((pcs[tri[0]]!=pcs[tri[1]]).mean())if len(tri[0])else np.nan,within_cluster_median=med(within),sizes_descending=';'.join(map(str,sorted(co.values(),reverse=True))),good_turing_missing_mass_proxy=f1/n)
 # Coverage estimator is a descriptive analogy only: modes learned from data,
 # finite heterogeneous humans violate fixed-species/iid assumptions.
 A=((n-1)*f1)/((n-1)*f1+2*f2)if f2>0 else ((n-1)*(f1-1))/((n-1)*(f1-1)+2)if f1>1 else 0.
 stat['chao_coverage_proxy']=1-(f1/n)*A
 isolated=0
 for l,size in co.items():
  if size==1:
   a=np.flatnonzero(lab==l)[0];other=np.flatnonzero(lab!=l)
   isolated+=int(len(other)==0 or dm[a,other].min()>cut+1e-12)
 stat['isolated_singletons']=isolated;stat['assignment_singletons_with_compatible_peer']=f1-isolated
 recovery=collections.defaultdict(list);rec_cond=collections.defaultdict(list)
 for omit in range(n):
  ix=np.delete(np.arange(n),omit);ll=cluster(dm[np.ix_(ix,ix)],pcs[ix],cut)
  for l in supp:
   original=set(np.flatnonzero(lab==l))-{omit}
   if not original:continue
   candidates=[set(ix[ll==x])for x in np.unique(ll)]
   best=max(len(original&s)/len(original|s)for s in candidates)if candidates else 0
   recovery[l].append(best)
   if len(original)>=2:rec_cond[l].append(best)
 cl=[];pairs=[]
 for l,size in co.items():
  ix=np.flatnonzero(lab==l);wm=med(dm[np.ix_(ix,ix)][np.triu_indices(size,1)])
  cl.append(dict(cluster=int(l),people=size,point_count=int(pcs[ix[0]]),medoid_index=int(ix[np.argmin(dm[np.ix_(ix,ix)].sum(1))]),within_median=wm,loo_mean_jaccard=np.mean(recovery[l])if recovery[l]else np.nan,loo_conditional_mean_jaccard=np.mean(rec_cond[l])if rec_cond[l]else np.nan,loo_pass75=float(np.mean(np.asarray(rec_cond[l])>=.75))if rec_cond[l]else np.nan,loo_evaluable=len(rec_cond[l])))
 for a,z in itertools.combinations(supp,2):
  ia=np.flatnonzero(lab==a);iz=np.flatnonzero(lab==z);same=pcs[ia[0]]==pcs[iz[0]];v=dm[np.ix_(ia,iz)]
  pairs.append(dict(cluster_a=int(a),cluster_b=int(z),people_a=len(ia),people_b=len(iz),point_count_a=int(pcs[ia[0]]),point_count_b=int(pcs[iz[0]]),same_point_count=same,cross_compatible_share=float(np.mean(v<=cut+1e-12))if same else 0.,cross_median=med(v.ravel())if same else np.nan))
 stat['min_supported_loo_jaccard']=min((r['loo_conditional_mean_jaccard']for r in cl if r['people']>=2 and np.isfinite(r['loo_conditional_mean_jaccard'])),default=np.nan)
 stat['max_cross_compatible_share']=max((r['cross_compatible_share']for r in pairs),default=0.)
 stat['weakly_separated_supported_pair']=any(r['cross_compatible_share']>.5 for r in pairs)
 stat['supported_point_counts']=len(set(pcs[np.isin(lab,supp)]))
 return stat,cl,pairs,lab

def rarefy(sizes,m):
 n=sum(sizes)
 if m>n or m<1:return dict(expected_clusters=np.nan,expected_supported=np.nan,expected_singletons=np.nan)
 den=math.comb(n,m);p0=[];p1=[]
 for a in sizes:
  p0.append(math.comb(n-a,m)/den if n-a>=m else 0.)
  p1.append(a*math.comb(n-a,m-1)/den if n-a>=m-1 else 0.)
 return dict(expected_clusters=sum(1-np.array(p0)),expected_supported=sum(1-np.array(p0)-np.array(p1)),expected_singletons=sum(p1))

def one_replay(dm,pcs,cut,orders,i,c,record_trace=False):
 n=len(pcs)
 if n<4:return [],[],[]
 full=cluster(dm,pcs,cut);co=collections.Counter(full);supp=sorted(l for l,s in co.items()if s>=2);ns=sum(co[l]for l in supp);core_final=np.array([co[l]/ns for l in supp]) if ns else np.array([])
 final_med={l:med(dm[np.ix_(np.flatnonzero(full==l),np.flatnonzero(full==l))][np.triu_indices(co[l],1)])for l in supp}
 rng=np.random.default_rng(sd(i,c,'review_v2',cut));cache={};summaries=[];allcurves=[];traces=[]
 for rep in range(orders):
  order=rng.permutation(n);seq=[];prior_ix=None;prior_lab=None
  for k in range(1,n+1):
   ix=np.sort(order[:k]);key=tuple(ix)
   if key not in cache:
    small=dm[np.ix_(ix,ix)];ll=cluster(small,pcs[ix],cut);sc=collections.Counter(ll);ss=sorted(l for l,v in sc.items()if v>=2)
    maxmed=max((med(small[np.ix_(np.flatnonzero(ll==l),np.flatnonzero(ll==l))][np.triu_indices(sc[l],1)])for l in ss),default=np.nan)
    counts=collections.Counter(full[ix]);tv_all=.5*sum(abs(counts[l]/k-co[l]/n)for l in co)
    core_count=np.array([counts[l]for l in supp]);tv_core=.5*np.abs(core_count/core_count.sum()-core_final).sum()if core_count.sum() else 1.
    J=np.zeros((len(supp),len(ss)))
    for a,l in enumerate(supp):
     gold=set(ix[full[ix]==l])
     for b,h in enumerate(ss):
      pred=set(ix[ll==h]);J[a,b]=len(gold&pred)/len(gold|pred)if gold|pred else 0.
    amin,bmin=linear_sum_assignment(-J)if J.size else (np.array([],int),np.array([],int))
    matches=dict(zip(amin,bmin));recovered=len(supp)>0 and len(ss)==len(supp)and len(matches)==len(supp) and all(core_count>=2)
    jmin=min((J[a,matches[a]] for a in matches),default=0.)
    drift=max((abs(med(small[np.ix_(np.flatnonzero(ll==ss[b]),np.flatnonzero(ll==ss[b]))][np.triu_indices(sc[ss[b]],1)])-final_med[supp[a]])for a,b in matches.items()),default=np.nan)
    s=dict(k=k,total_clusters=len(sc),supported_clusters=len(ss),singletons=sum(z==1 for z in sc.values()),tv_all=tv_all,tv_core=float(tv_core),core_all_represented=recovered,core_min_jaccard=jmin,core_geometry_deviation=drift,within_max_median=maxmed)
    cache[key]=(s,ll)
   s,ll=cache[key];s=s.copy();s['new_geometry']=0.;s['new_structure']=0.;s['repartition']=0.
   if prior_ix is not None:
    new=order[k-1];s['new_geometry']=float(dm[new,prior_ix].min()>cut+1e-12);s['new_structure']=float(pcs[new]not in pcs[prior_ix]);shared=np.searchsorted(ix,prior_ix);a=prior_lab[:,None]==prior_lab[None,:];b=ll[shared,None]==ll[None,shared];tr=np.triu_indices(k-1,1);s['repartition']=float(np.mean(a[tr]!=b[tr]))if len(tr[0])else 0.
   seq.append(s);prior_ix=ix;prior_lab=ll
   if record_trace:traces.append(dict(image_id=i,condition=c,cut=cut,replay=rep,arrival_index=int(order[k-1]),**s))
  # old full-pattern rule, now without final singleton share / invalid-image gate
  full_ok=[];core_ok={tol:[]for tol in(.10,.15,.20)}
  for k0 in range(2,n):
   a=seq[k0-1:];p=len({(r['total_clusters'],r['supported_clusters'])for r in a})==1 and max(r['repartition']for r in a[1:])<=.05+1e-12
   medians=[r['within_max_median']for r in a]
   full_ok.append(p and max(r['tv_all']for r in a)<=.1+1e-12 and np.isfinite(medians).all() and max(medians)-min(medians)<=.02+1e-12)
   for tol in core_ok:
    core_ok[tol].append(all(r['core_all_represented'] and r['core_min_jaccard']>=.75-1e-12 and r['tv_core']<=tol+1e-12 and np.isfinite(r['core_geometry_deviation']) and r['core_geometry_deviation']<=.02+1e-12 for r in a))
  onset=lambda vals:next((j+2 for j,v in enumerate(vals)if v),np.nan)
  tailk=max(2,n-min(3,n-2))
  row=dict(image_id=i,condition=c,cut=cut,replay=rep,n_valid=n,full_onset_no_gate=onset(full_ok),full_tail_no_gate=bool(full_ok[tailk-2]),late_half_new=np.mean([s['new_geometry']for s in seq if s['k']>n/2]),late_quarter_new=np.mean([s['new_geometry']for s in seq if s['k']>3*n/4]),late_quarter_structure=np.mean([s['new_structure']for s in seq if s['k']>3*n/4]),late_quarter_repartition=np.mean([s['repartition']for s in seq if s['k']>3*n/4]),half_tv_all=seq[max(1,n//2)-1]['tv_all'],half_tv_core=seq[max(1,n//2)-1]['tv_core'])
  for tol,oks in core_ok.items():
   tag=int(round(100*tol));row[f'core_onset_{tag}']=onset(oks);row[f'core_tail_{tag}']=bool(oks[tailk-2])
  summaries.append(row)
  for s in seq:allcurves.append(dict(image_id=i,condition=c,cut=cut,replay=rep,**s))
 curves=pd.DataFrame(allcurves).groupby(['image_id','condition','cut','k']).mean(numeric_only=True).reset_index().drop(columns='replay')
 return summaries,curves.to_dict('records'),traces

def run(orders=200):
 start=time.monotonic();groups=groups_from_raw();expert=pd.read_csv(PREV/'expert/independent_tags106.csv');expert_ids=set(expert.image_id)
 olds=pd.read_csv(PREV/'targets/primary_with_robustness.csv');old_hard=set(olds.loc[olds.grade=='difficult_candidate','image_id'])
 rows=[];cr=[];pairs=[];members=[];rares=[];replays=[];curves=[];traces=[]
 for number,((i,c),(g,v,dm,pcs)) in enumerate(groups.items()):
  focus=(i in expert_ids and len(v)>=6) or i in old_hard
  for cut in CUTS:
   st,cs,ps,labs=cluster_static(dm,pcs,cut);ident=dict(image_id=i,condition=c,building=i.split('_')[0],cut=cut,n_observed=len(g),n_excluded=len(g)-len(v),n_reviewed_retained=int(v.reviewed_repair.sum()),n_imputed_retained=int(v.imputed_point.sum()))
   rows.append(dict(ident,**st))
   for z in cs:
    medidx=z['medoid_index'];z.update(medoid_worker=v.worker_id.iloc[medidx],medoid_canonical_id=v.canonical_annotation_id.iloc[medidx]);cr.append(dict(ident,**z))
   pairs.extend([dict(ident,**z)for z in ps])
   for j,l in enumerate(labs):members.append(dict(image_id=i,condition=c,cut=cut,cluster=int(l),cluster_people=int(np.sum(labs==l)),worker_id=v.worker_id.iloc[j],canonical_annotation_id=v.canonical_annotation_id.iloc[j],point_count=int(pcs[j]),reviewed_repair=bool(v.reviewed_repair.iloc[j]),imputed_point=bool(v.imputed_point.iloc[j])))
   sizes=list(collections.Counter(labs).values())
   for m in(4,6,8,10,12,16,20):
    if m<=len(v):rares.append(dict(ident,subsample_n=m,**rarefy(sizes,m)))
   # all primary image conditions; nearby cuts only targeted prelisted human tags/old hard
   if cut==.10 or focus:
    ss,cc,tt=one_replay(dm,pcs,cut,orders if cut==.10 else max(50,orders//2),i,c,record_trace=focus and cut==.10)
    replays.extend(ss);curves.extend(cc);traces.extend(tt)
  if number%15==0:print('recompute',number+1,'of',len(groups),'seconds',round(time.monotonic()-start,1),flush=True)
 csv('structure/per_image_all_cuts.csv',rows);csv('structure/per_cluster_stability.csv',cr);csv('structure/supported_cluster_separation.csv',pairs);csv('structure/real_mode_memberships.csv.gz',members);csv('structure/fixed_partition_rarefaction.csv',rares)
 csv('process/per_order_onsets.csv.gz',replays);csv('process/mean_prefix_curves.csv.gz',curves);csv('process/focus_order_trace.csv.gz',traces)
 js('process/execution.json',dict(groups=len(groups),orders_primary=orders,orders_sensitivity=max(50,orders//2),new_geometry_inference=False,elapsed_seconds=time.monotonic()-start,primary_all_conditions=True,other_cut_growth_coverage='expert-labelled with >=6 valid people or old hard candidates',independent_new_people=0,full_partition='evaluation target only, not prefix prediction input',reclustering='every observed prefix',core_definition='all supported terminal clusters recovered at Jaccard .75 with >=2 distinct observed members, no extra supported cluster; conditional core TV<=.10/.15/.20 and cluster median distance dev<=.02 over suffix',full_definition='old G10 without a priori singleton / whole-image-invalid blocking',statuses_not_semantic_truth=True))
 print('DONE',len(rows),len(replays),round(time.monotonic()-start,1),flush=True)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--orders',type=int,default=200);a=ap.parse_args();run(a.orders)
