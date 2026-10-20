"""Independent request/vector/arm and all-metric common-anchor reaggregation."""
from pathlib import Path
from collections import Counter
import gzip,json,hashlib,sys
import numpy as np,pandas as pd
B=Path('/workspace/shared/interchangeability_audit_20261020');D=B/'audit_corner/common_library';O=B/'audit_statistics/common_library';O.mkdir(exist_ok=True)
q=json.load(gzip.open(B/'audit_learning/fresh_blocks/fresh_block_requests.json.gz','rt'));anchors={a['anchor_id']:a for a in q['common_anchors']};methods=list(q['label_maps']);assert methods[0]==q['spec']['primary_method']
if len(sys.argv)>1:
 mid=sys.argv[1];D=B/'audit_corner/direct_block_assessment'/mid;O=B/'audit_statistics/direct_block_assessment'/mid;O.mkdir(parents=True,exist_ok=True);manifest=json.load(open(B/'audit_learning/block_fit/METHOD_MANIFEST.json'));mp={w:c for c,ws in manifest[mid]['classes'].items() for w in ws};q['label_maps']={mid:mp,methods[1]:q['label_maps'][methods[1]]};methods=list(q['label_maps'])
f=pd.read_csv(D/'COMMON_ENDPOINT_PAIRS.csv.gz',low_memory=False);assert f.pair_id.is_unique
expected={f"{a['anchor_id']}__{i}_{j}" for a in q['common_anchors'] for i,j in a['disjoint_block_pairs']};assert expected==set(f.pair_id)
for r in f.itertuples(index=False):
 a=anchors[r.anchor_id];left=a['blocks'][r.left_block];right=a['blocks'][r.right_block];assert r.A_team_key==left['team_key'] and r.B_team_key==right['team_key'];assert set(r.left_workers.split('|'))==set(left['workers']) and set(r.right_workers.split('|'))==set(right['workers'])
for mid,mp in q['label_maps'].items():
 arms=[];pures=[]
 for r in f[['anchor_id','left_block','right_block']].itertuples(index=False):
  a=anchors[r.anchor_id];wa=a['blocks'][r.left_block]['workers'];wb=a['blocks'][r.right_block]['workers'];ca=Counter(mp[w] for w in wa);cb=Counter(mp[w] for w in wb)
  arms.append('within' if ca==cb else 'between');pures.append(len(ca)==len(cb)==1)
 assert (f[mid+'__arm'].to_numpy()==arms).all();assert (f[mid+'__pure'].to_numpy()==pures).all()
assert (f.valid_distance==(f.status=='unique_cyclic_candidate').astype(float)).all();assert (f.different_count==(f.status=='different_corner_count').astype(float)).all();assert (f.missing_geometry==(f.status=='missing_connected_geometry').astype(float)).all();assert (f.noncomplete==(~f.complete).astype(float)).all()
for m in ['bev_mean_h','bev_max_h','top_mean_h','top_max_h']:assert f.loc[f.status!='unique_cyclic_candidate',m].isna().all()
report=pd.read_csv(D/'COMMON_LIBRARY_BUILDINGS.csv');summary=pd.read_csv(D/'COMMON_LIBRARY_SUMMARY.csv');metrics=summary.metric.unique().tolist();errs=[];counts=[];out=[];rng=np.random.default_rng(20261020)
keys=['anchor_id','pool_id','image_id','building','n','m']
for subset in ['all_count_vectors','pure_class_only']:
 arms=[]
 for mi,mid in enumerate(methods):
  z=f.copy()
  if subset=='pure_class_only':z=z[z[mid+'__pure']]
  z['arm']=z[mid+'__arm'];z=z[z.arm!='unknown'];a=z.groupby(keys+['arm'])[metrics].mean();a['method']=mi;arms.append(a.reset_index())
 a=pd.concat(arms)
 for (n,m),z in a.groupby(['n','m']):
  for metric in metrics:
   x=z.pivot(index=keys,columns=['method','arm'],values=metric).reindex(columns=pd.MultiIndex.from_product([[0,1],['within','between']])).dropna()
   b=x.groupby(['building','image_id']).mean().groupby('building').mean();calc=pd.DataFrame(index=b.index)
   for mi,name in [(0,'candidate'),(1,'baseline')]:
    calc[name+'_within']=b[(mi,'within')];calc[name+'_between']=b[(mi,'between')];calc[name+'_gap']=calc[name+'_between']-calc[name+'_within']
   calc['delta_within']=calc.candidate_within-calc.baseline_within;calc['delta_gap']=calc.candidate_gap-calc.baseline_gap
   rr=report[(report.subset==subset)&(report.n==n)&(report.m==m)&(report.metric==metric)].set_index('building');assert set(rr.index)==set(calc.index)
   sr=summary[(summary.subset==subset)&(summary.n==n)&(summary.m==m)&(summary.metric==metric)].iloc[0];assert sr.common_anchors==len(x) and sr.images==x.index.get_level_values('image_id').nunique() and sr.buildings==len(b)
   for c in calc:
    err=abs(calc[c]-rr[c]).max();err2=abs(calc[c].mean()-sr[c]);assert pd.isna(err) or err<1e-10;assert pd.isna(err2) or err2<1e-10
    if pd.notna(err):errs.extend([err,err2])
    vals=calc[c].dropna().to_numpy();dist=vals[rng.integers(0,len(vals),(50000,len(vals)))].mean(axis=1) if len(vals)>=3 else np.array([np.nan])
    out.append(dict(subset=subset,n=n,m=m,metric=metric,contrast=c,common_anchors=len(x),images=x.index.get_level_values('image_id').nunique(),buildings=len(vals),estimate=vals.mean() if len(vals) else np.nan,ci025=np.quantile(dist,.025),ci975=np.quantile(dist,.975),positive_buildings=int((vals>1e-9).sum()),negative_buildings=int((vals< -1e-9).sum())))
pd.DataFrame(out).to_csv(O/'COMMON_LIBRARY_INDEPENDENT_BOOTSTRAP.csv',index=False)
r=dict(inputs_sha256={x:hashlib.sha256((D/x).read_bytes()).hexdigest() for x in ['COMMON_ENDPOINT_PAIRS.csv.gz','COMMON_LIBRARY_BUILDINGS.csv','COMMON_LIBRARY_SUMMARY.csv','COMMON_LIBRARY_RECEIPT.json']},pair_rows=len(f),exact_request_pair_set_verified=True,exact_endpoint_membership_identifiers_verified=True,all_count_vector_arms_and_pure_flags_independently_verified=True,exclusive_status_risks_verified=True,all_unavailable_distances_null=True,summary_cells=len(summary),compared_numeric_values=len(errs),max_aggregate_error=max(errs),observed_images=f.image_id.nunique(),observed_buildings=f.building.nunique(),frozen_anchors=len(anchors),statuses=f.status.value_counts().to_dict(),interpretation='Same raw endpoint library and four-cell common anchor per metric, NOT identical within-pair populations across methods. Conditional distances and all-observed risk supports reported separately. Existing assessment reuse, selected12image design; only11images have library support.')
(O/'COMMON_LIBRARY_STATS_RECEIPT.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
