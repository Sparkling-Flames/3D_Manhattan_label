"""Explicit final numerical audit and complementary strata, no raw-data changes."""
import collections,json,hashlib,itertools
import numpy as np,pandas as pd
from scipy.stats import spearmanr
from tools.thesis_main.analysis.image_portrait.convergence_v2_common import *


def correct_comparisons():
 notes=[]
 p=OUT/'subgroups/equal_n_untyped_controls.csv';d=pd.read_csv(p)
 bad=d.actual_workers.str.count(';')+1!=d.n_subgroup
 if bad.any():
  csv('audit/subgroup_invalid_control_exclusions.csv',d[bad].assign(reason='subgroup_has_invalid_person_but_control_was_all_geometry_valid; not_same_denominator'))
  csv('audit/subgroup_controls_before_explicit_correction.csv',d);d=d[~bad].copy();csv('subgroups/equal_n_untyped_controls.csv',d)
  notes.append(dict(issue='invalid-person mismatch in matched controls',affected_rows=int(bad.sum()),resolution='exclude ONLY unmatched contrast; all original target groups and invalid flags retained; source corrected; pre-correction table retained'))
 z=[]
 for key,g in d.groupby(['candidate','condition']):z.append(dict(candidate=key[0],condition=key[1],**paired_interval(g,'delta')))
 csv('subgroups/equal_n_comparison_summary.csv',z)
 # means of marginally-matched contrasts must refer to exactly the same paired
 # rows, including the same permutation records before image averaging.
 # Existing image-level delta used complete permutation records; repair side
 # means if NA support differs rather than silently representing them as paired.
 p=OUT/'combinations/fixed_future_paired_image_contrasts.csv';d=pd.read_csv(p)
 mismatch=(d.mixed-d.pure_margin_matched-d.delta).abs()>1e-9
 if mismatch.any():
  csv('audit/composition_nan_side_mean_discrepancy.csv',d[mismatch]);notes.append(dict(issue='side means used different finite permutation subsets',affected_images_metrics=int(mismatch.sum()),resolution='delta remains paired; side means setNA in summary when not recoverable from exported image table; native one-side means not presented as paired'))
 out=[]
 for keys,g in d.groupby(['condition','information','metric']):
  v=g.dropna(subset=['mixed','pure_margin_matched','delta']);ok=np.allclose(v.mixed-v.pure_margin_matched,v.delta,atol=1e-9)
  out.append(dict(condition=keys[0],information=keys[1],metric=keys[2],mixed=v.mixed.mean() if ok else np.nan,pure_margin_matched=v.pure_margin_matched.mean()if ok else np.nan,side_means_same_coverage=bool(ok),**paired_interval(g,'delta')))
 csv('combinations/fixed_future_paired_summary.csv',out)
 # A disconnected graph component is NOT evidence of a different physical room.
 renamed=[]
 for p in (OUT/'transfer').glob('*.csv'):
  txt=p.read_text()
  if 'same_building_other_confirmed_room' in txt:
   p.write_text(txt.replace('same_building_other_confirmed_room','same_building_other_supported_component'));renamed.append(str(p.relative_to(OUT)))
 if renamed:notes.append(dict(issue='overstrong distinct-physical-room donor name',files=renamed,resolution='renamed to other supported component; treated as building baseline, not verified separate physical room'))
 # Single-building cluster bootstrap has no between-building information.
 changed=[]
 for p in OUT.rglob('*.csv'):
  if 'audit' in p.parts:continue
  try:d=pd.read_csv(p)
  except Exception:continue
  if {'groups','lo','hi'}<=set(d):
   one=d.groups<2
   if one.any()and(d.loc[one,['lo','hi']].notna().any().any()):
    d.loc[one,['lo','hi']]=np.nan;d.to_csv(p,index=False,float_format='%.12g');changed.append(dict(file=str(p.relative_to(OUT)),rows=int(one.sum())))
 notes.append(dict(issue='single-building CI not estimable',files=changed,resolution='retain point estimate and n; CI=NA when groups<2; common function fixed'))
 prior_path=OUT/'audit/explicit_corrections.json';previous=json.loads(prior_path.read_text())if prior_path.exists()else[]
 unique={json.dumps(r,sort_keys=True):r for r in previous+notes};js('audit/explicit_corrections.json',list(unique.values()))


def strata():
 s=pd.read_csv(OUT/'process/image_uncertainty_structure.csv');s=s[s.cut==.1]
 s['kind']=np.select([s.n_supported_modes<2,s.same_topology_multimodality&(s.supported_topologies==1),s.same_topology_multimodality],['not_supported_multimodal','same_point_only_multimodal','mixed_point_and_geometry_multimodal'],default='different_point_only_multimodal')
 csv('structure/mode_structure_kinds.csv',s)
 curves=pd.read_csv(OUT/'process/image_growth_curves.csv.gz');c=curves[curves.cut==.1].merge(s[['image_id','condition','kind']],on=['image_id','condition'])
 rows=[]
 for (im,arm),g in c.groupby(['image_id','condition']):
  n=int(g.n_valid_full.iloc[0]);h=max(2,int(np.ceil(n/2)));r=g[g.k==h]
  if r.empty:continue
  row=r.iloc[0];later=g[g.k>h]
  rows.append(dict(image_id=im,building=im.split('_')[0],condition=arm,kind=row.kind,n=n,k=h,half_TV=row.TV_full_observed,half_within_geometry=row.within_mode_max_median_d,half_future_coverage=row.future_coverage,late_new_geometry=later.new_incompatible_mode.mean(),late_support_promotions=later.support_promotions.mean(),full_within_geometry=g.iloc[-1].within_mode_max_median_d))
 a=csv('structure/growth_by_mode_kind_images.csv',rows);rr=[]
 for keys,g in a.groupby(['condition','kind']):
  for band,lo,hi in [('all',0,100),('4to9',4,9),('10plus',10,100),('20plus',20,100)]:
   z=g[g.n.between(lo,hi)]
   if len(z):rr.append(dict(condition=keys[0],kind=keys[1],n_band=band,images=len(z),buildings=z.building.nunique(),median_n=z.n.median(),half_TV=z.half_TV.mean(),late_new_geometry=z.late_new_geometry.mean(),late_support_promotions=z.late_support_promotions.mean(),half_future_coverage=z.half_future_coverage.mean(),full_within_geometry=z.full_within_geometry.mean()))
 csv('structure/growth_by_mode_kind_summary.csv',rr)
 # Same final scalar/vector neighborhood does not imply the same process.
 d=pd.read_csv(OUT/'structure/same_final_structure_different_growth.csv');z=d[(d.n_a>=10)&(d.n_b>=10)&((d.geometry_a-d.geometry_b).abs()<=.02)]
 csv('structure/comparable_final_geometry_different_growth.csv',z)
 # Source-split and native-n sensitivities retain original predictions, never
 # refit on outer outcomes or change the held-out folds.
 p=pd.read_csv(OUT/'prediction/cold_all_predictions.csv.gz');meta=images()[['image_id','source_split']];p=p.merge(meta,on='image_id',how='left');tg=pd.read_csv(OUT/'prediction/process_targets.csv');tg=tg[tg.cut==.1][['image_id','condition','n_valid']];p=p.merge(tg,on=['image_id','condition'],how='left',validate='many_to_one')
 err='absolute_error';rr=[]
 for strata_col in ['source_split','n_band']:
  if strata_col=='n_band':p['n_band']=pd.cut(p.n_valid,[0,3,9,100],labels=['1to3','4to9','10plus']).astype(str)
  for keys,g in p.groupby(['condition','feature','algorithm','target',strata_col],observed=True):
   if err not in g:break
   z=g.dropna(subset=[err]);rr.append(dict(condition=keys[0],feature=keys[1],algorithm=keys[2],target=keys[3],stratum_field=strata_col,stratum=keys[4],n=len(z),buildings=z.building.nunique(),MAE=z[err].mean()))
 csv('prediction/source_split_and_n_sensitivity.csv',rr)
 # Human reviewed categories are distinct from AI trait fields.
 st=pd.read_csv(OUT/'process/image_state_probabilities.csv');st=st[(st.cut==.1)&(st.rule=='G10_geometry')];csv('images/human_scene_state_summary.csv',st.groupby(['condition','scene','state']).agg(images_with_state=('image_id','nunique'),expected_images=('fraction','sum')).reset_index())
 ct=pd.read_csv(OUT/'combinations/fixed_future_paired_image_contrasts.csv').merge(s[['image_id','condition','scene']],on=['image_id','condition']);r=[]
 for keys,g in ct.groupby(['condition','information','metric','scene']):r.append(dict(condition=keys[0],information=keys[1],metric=keys[2],human_scene=keys[3],**paired_interval(g,'delta')))
 csv('combinations/human_scene_fixed_future_contrasts.csv',r)
 # Actual measurement separates rule correctness, scope choice, and geometry.
 rm=read_responses();rm=rm[rm.main_worker_included];rows=[]
 for (im,arm),g in rm.groupby(['image_id','raw_condition']):
  cnt=collections.Counter(g.scope.fillna('unknown'));rows.append(dict(image_id=im,condition=arm,n=len(g),scope_counts=json.dumps(cnt),scope_known=sum(v for k,v in cnt.items()if k!='unknown'),scope_categories_supported=sum(v>=2 for k,v in cnt.items()if k!='unknown'),scope_entropy_known=entropy([x for x in g.scope if pd.notna(x)and x!='unknown']),not_geometry_policy_truth=True))
 csv('structure/scope_choice_distribution.csv',rows)


def preservation():
 a=json.loads((OUT/'audit/preceding_results_preservation.json').read_text());bad=[]
 for f in a['files']:
  p=ROOT/f['path']
  if not p.exists()or hashlib.sha256(p.read_bytes()).hexdigest()!=f['sha256']:bad.append(f['path'])
 js('audit/final_preservation_check.json',dict(original_files_checked=len(a['files']),modified_or_missing=bad,passed=not bad))
 if bad:raise AssertionError(bad)

if __name__=='__main__':
 correct_comparisons();strata();preservation();print('FINAL AUDIT OK',flush=True)
