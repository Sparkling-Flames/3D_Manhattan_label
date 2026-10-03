"""Read-only independent validation of a frozen return bundle; writes audit outputs only."""
from pathlib import Path
from itertools import combinations
from math import comb
import hashlib,json,sys,subprocess,tempfile
import numpy as np
import pandas as pd
from scipy.stats import spearmanr,hypergeom
from shapely import contains_xy
from shapely.geometry import Polygon
from shapely.ops import unary_union,polygonize
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'worker-audit-inputs/extracted/worker_consensus_independent_20261003'
RUN=ROOT/'worker-audit-repro'
OUT=Path(__file__).resolve().parent
summary={}
manifest=json.loads((SRC/'MANIFEST.json').read_text())
summary['manifest']={'files':len(manifest['files']),'failures':[x['path'] for x in manifest['files'] if len((SRC/x['path']).read_bytes())!=x['bytes'] or hashlib.sha256((SRC/x['path']).read_bytes()).hexdigest()!=x['sha256']]}
mat={}
rows=[]
for x in json.loads((SRC/'inputs/transfer_checks.json').read_text()):
 p=SRC/'inputs'/x['file'];b=p.read_bytes();d=pd.read_csv(p,float_precision='round_trip');mat[x['file']]=d
 y=d.iloc[:,2:].to_numpy(float)
 rows.append({'file':x['file'],'bom':b[:3]==b'\xef\xbb\xbf','image_rows':len(d),'worker_columns':y.shape[1],'cells':y.size,'missing':int(np.isnan(y).sum()),'finite':bool(np.isfinite(y).all()),'git_blob_sha':hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest(),'expected_git_blob_sha':x['expected_git_blob_sha']})
 assert rows[-1]['git_blob_sha']==x['expected_git_blob_sha']
f=mat['matrix_original_iou.csv'];workers=list(f.columns[2:]);buildings=f.building.to_numpy();B=sorted(set(buildings))
for d in mat.values():assert d.iloc[:,:2].equals(f.iloc[:,:2]) and list(d.columns)==list(f.columns)
summary['matrices']={'checks':rows,'building_image_counts':f.groupby('building').size().to_dict(),'all_rows_columns_aligned':True}
head=json.loads((RUN/'results/profile_analysis_summary.json').read_text())
skills=[]
for policy in ('original','revised_where_available'):
 Y=mat[f'matrix_{policy}_iou.csv'].iloc[:,2:].to_numpy(float)
 for omitted in [[],['P017'],['P017','P002']]:
  ids=[j for j,w in enumerate(workers) if w not in omitted];Z=Y[:,ids]
  r=Z-Z.mean(1)[:,None]
  pred=np.vstack([r[buildings!=b].mean(0) for b in buildings])
  numerator=float(np.sum((r-pred)**2));denominator=float(np.sum(r**2));s=1-numerator/denominator
  key='influence_'+('-'.join(omitted) or 'none')
  assert abs(s-head[policy][key]['skill'])<1e-14
  skills.append(dict(policy=policy,omitted='|'.join(omitted),workers=len(ids),evaluated_cells=Z.size,sse=numerator,zero_sse=denominator,S=s))
 splits=pd.read_csv(RUN/'results/disjoint_building_splits.csv');splits=splits[splits.policy==policy]
 assert len(splits)==comb(8,4)//2
 assert splits.same_half_fraction.median()==14/24
 for row in splits.itertuples():
  a=set(row.buildings_a.split('|'));b=set(row.buildings_b.split('|'));assert len(a)==len(b)==4 and not a&b and a|b==set(B)
  r=spearmanr(Y[np.isin(buildings,list(a))].mean(0),Y[np.isin(buildings,list(b))].mean(0)).statistic
  assert abs(r-row.spearman)<1e-14
summary['independent_S']=skills
summary['disjoint']={'policies':2,'unordered_splits_per_policy':35,'distinct_calibration_building_sets_per_policy':70,'median_same_half_workers':14,'worker_denominator':24,'independent_validation_experiments':False}
npz=[]
for p in sorted((SRC/'results').glob('*.npz')):
 with np.load(p,allow_pickle=False) as a,np.load(RUN/'results'/p.name,allow_pickle=False) as b:
  assert set(a.files)==set(b.files)
  for k in a.files:
   npz.append({'file':p.name,'array':k,'shape':list(a[k].shape),'array_equal':bool(np.array_equal(a[k],b[k])),'max_abs_diff':float(np.max(abs(a[k]-b[k])))})
assert all(x['array_equal'] for x in npz)
summary['npz_replay']=npz
obj=json.loads((SRC/'inputs/one_image_geometry.json').read_text());polys=[Polygon(r['footprint']) for r in obj['records']];G=Polygon(obj['reference']['footprint'])
assert len(polys)==24 and all(p.is_valid and p.area>0 for p in polys)
assert [r['worker'] for r in obj['records']]==workers
union=unary_union(polys);tiles=list(polygonize(unary_union([p.boundary for p in polys])))
pts=np.array([(t.representative_point().x,t.representative_point().y) for t in tiles]);votes=np.array([contains_xy(p,pts[:,0],pts[:,1]) for p in polys]);sel=votes.any(0);votes=votes[:,sel];tiles=[t for t,s in zip(tiles,sel) if s];areas=np.array([t.area for t in tiles]);inter=np.array([t.intersection(G).area for t in tiles]);ga=G.area
single_iou=np.array([p.intersection(G).area/p.union(G).area for p in polys]);single_c=np.array([p.centroid.distance(G.centroid)/np.sqrt(ga) for p in polys]);ix=list(f.image).index(obj['image'])
summary['geometry']={'image':obj['image'],'candidates':24,'distinct_coordinate_lists':len(set(json.dumps(r['footprint']) for r in obj['records'])),'tiles':len(tiles),'gt_area_h2':ga,'all_candidate_union_area_h2':union.area,'single_iou_max_abs_difference':float(np.max(abs(single_iou-f.iloc[ix,2:].to_numpy(float)))),'single_centroid_max_abs_difference':float(np.max(abs(single_c-mat['matrix_original_centroid_normalized.csv'].iloc[ix,2:].to_numpy(float))))}
assert summary['geometry']['single_iou_max_abs_difference']<1e-14 and summary['geometry']['single_centroid_max_abs_difference']<1e-14
Y=f.iloc[:,2:].to_numpy(float);means=Y[buildings!=obj['building']].mean(0);hi=means>np.median(means);assert hi.sum()==12
mh=votes[hi].sum(0);ml=votes[~hi].sum(0)
grid=pd.read_csv(RUN/'results/one_image_all_composition_area_expectations.csv');assert len(grid)==336
maxerr=0;rbverr=0
for row in grid.itertuples():
 h,l=int(row.higher_n),int(row.lower_n);threshold=(h+l+1)//2 if row.method=='mv50' else (h+l)//2+1
 q=sum(hypergeom.pmf(a,12,mh,h)*hypergeom.sf(threshold-a-1,12,ml,l) for a in range(h+1))
 under=ga-float(inter@q);over=float((areas-inter)@q);bias=ga+float(areas@(q*q))-2*float(inter@q);v=float(areas@(q*(1-q)));risk=under+over
 assert row.composition_count==comb(12,h)*comb(12,l)
 checks=[abs(row.expected_under_h2-under),abs(row.expected_over_h2-over),abs(row.consensus_field_bias_h2-bias),abs(row.consensus_field_variance_h2-v),abs(row.member_symdiff_h2-2*v)]
 maxerr=max(maxerr,*checks);rbverr=max(rbverr,abs(risk-bias-v))
assert maxerr<1e-12 and rbverr<1e-12
summary['composition_grid']={'total_states':len(grid),'per_rule':len(grid)//2,'count_formula':'2*((12+1)*(12+1)-1)','independent_scipy_hypergeometric_area_max_abs_error':maxerr,'R_B_plus_V_max_abs_error_h2':rbverr,'not_mean_iou':'ratio_of_expected_intersection_union','states_with_nonzero_variance':int((grid.consensus_field_variance_h2>1e-12).sum())}
# Pair contrasts independently constructed with background triples as outer loop.
members=np.array(list(combinations(range(24),4)),dtype=int);assert len(members)==10626
triple_contexts=list(combinations(range(24),3));look={tuple(m):i for i,m in enumerate(members)}
pairs=list(combinations(range(24),2));pair_ix={p:i for i,p in enumerate(pairs)}
paired=[];direct=[]
rng=np.random.default_rng(5102);check_ids=sorted(set([0,len(members)-1,*map(int,rng.choice(len(members),20,replace=False))]))
for method in ('mv50','mv_strict'):
 with np.load(RUN/f'results/one_image_k4_{method}.npz',allow_pickle=False) as ar:
  assert np.array_equal(ar['members'],members)
  s=ar['iou'];assert len(s)==10626
  D=[[] for _ in pairs]
  for T in triple_contexts:
   available=[j for j in range(24) if j not in T]
   vals={a:s[look[tuple(sorted((*T,a)))]] for a in available}
   for a,b in combinations(available,2):D[pair_ix[(a,b)]].append(vals[a]-vals[b])
  published=pd.read_csv(RUN/f'results/paired_replacements/{method}.csv').set_index(['worker_a','worker_b'])
  err=0;sd_error=0
  for (a,b),d in zip(pairs,D):
   row=published.loc[(workers[a],workers[b])];assert len(d)==row.common_context_n==1540
   err=max(err,abs(np.mean(d)-row.mean_a_minus_b));sd_error=max(sd_error,abs(np.std(d)-row.sd_a_minus_b))
  paired.append({'method':method,'pairs':len(pairs),'contexts_per_pair':1540,'total_comparisons':sum(map(len,D)),'mean_max_abs_error':err,'sd_max_abs_error':sd_error})
  assert err<1e-14 and sd_error<1e-14
  for j in check_ids:
   pp=[polys[i] for i in members[j]];local=list(polygonize(unary_union([p.boundary for p in pp])));threshold=2 if method=='mv50' else 3
   kept=[t for t in local if sum(p.contains(t.representative_point()) for p in pp)>=threshold]
   shape=unary_union(kept);globalshape=unary_union([t for t,inc in zip(tiles,votes[members[j]].sum(0)>=threshold) if inc]);shape_diff=shape.symmetric_difference(globalshape).area
   iou=shape.intersection(G).area/shape.union(G).area
   direct.append(dict(method=method,subset_index=j,workers='|'.join(workers[i] for i in members[j]),iou_error=abs(iou-s[j]),shape_symdiff_h2=shape_diff))
assert max(x['iou_error'] for x in direct)<1e-12 and max(x['shape_symdiff_h2'] for x in direct)<1e-12
pd.DataFrame(direct).to_csv(OUT/'independent_direct_geometry.csv',index=False)
summary['paired_replacement']=paired
summary['independent_current_subset_geometry']={'distinct_member_sets':len(check_ids),'rule_evaluations':len(direct),'max_iou_error':max(x['iou_error'] for x in direct),'max_region_symdiff_h2':max(x['shape_symdiff_h2'] for x in direct)}
existing=pd.read_csv(RUN/'results/current_subset_direct_checks.csv');summary['published_direct_checks']={'rows':len(existing),'distinct_member_sets':existing.members.nunique(),'rules':2}
# Adversarial API checks. Deliberately malformed copied inputs only; source remains untouched.
sys.path.insert(0,str(RUN/'src'));from paired_replacement import paired_effects
small=np.array(list(combinations(range(5),3)));base=np.arange(len(small),dtype=float)
fractional_accepted=False
try:paired_effects(small.astype(float)+.1,base,list('abcde'));fractional_accepted=True
except ValueError:pass
empty=OUT/'malformed_source_fixture';empty.mkdir(exist_ok=True);(empty/'rosters.json').write_text(json.dumps({'workers':list('abcde'),'groups':[{'key':'missing_image','image':'missing_image'}]}));np.savez(empty/'subsets.npz',members=small)
p=subprocess.run([sys.executable,str(RUN/'src/paired_replacement.py'),'--source-dir',str(empty),'--out',str(OUT/'malformed_source_output')],capture_output=True,text=True)
summary['robustness_findings']={'fractional_member_indices_silently_truncated':fractional_accepted,'all_missing_reference_score_keys_exit_code':p.returncode,'all_missing_reference_score_keys_csv_outputs':len(list((OUT/'malformed_source_output').glob('*.csv'))),'all_missing_reference_score_keys_stdout':p.stdout,'all_missing_reference_score_keys_stderr':p.stderr,'scope':'Malformed future input handling only; frozen valid demonstration unaffected'}
# Numerical stages emitted no warnings; figures can emit writable-cache diagnostics.
logs={p.name:p.read_text() for p in (RUN/'results').glob('replay_step_*.log')}
summary['logs']={'tests':logs['replay_step_4.log'].strip(),'figure_fontconfig_warning_count':logs['replay_step_5.log'].count('Fontconfig error'),'numerical_stages_warning_counts':{k:v.lower().count('warning:') for k,v in logs.items() if k in ['replay_step_1.log','replay_step_2.log','replay_step_3.log']}}
(OUT/'independent_checks.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
