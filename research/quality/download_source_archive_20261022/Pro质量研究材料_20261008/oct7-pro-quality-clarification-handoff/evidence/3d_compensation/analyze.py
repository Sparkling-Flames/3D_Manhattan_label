"""Descriptive scope-ambiguity stress test; no fitting or source mutation.
Run: python oct7-3d-compensation-study/analyze.py
Dependencies: numpy, pandas, scipy, shapely. Inputs are bundled frozen extracts.
"""
from pathlib import Path
import json, sys, hashlib
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parent
ROOT=OUT.parent
PKG=OUT
SITE=OUT/'inputs/site_sourceInfo.json'
inputs=[OUT/'inputs/manual_scored.csv',OUT/'inputs/panel.json',SITE,
        OUT/'inputs/relevant_comments.json',OUT/'inputs/record_states.json',
        OUT/'inputs/user_review.json']
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
hashes={str(p.relative_to(ROOT)):sha(p) for p in inputs}
site=json.loads(SITE.read_text()); s=site['sourceInfo']['scales']
f=pd.read_csv(inputs[0]); panel=json.loads(inputs[1].read_text())
objects={r['id']:r for r in json.loads(inputs[4].read_text())['objects']}
comments=json.loads(inputs[3].read_text())['comments']
image_codes=['B6ByNegPMKs-48','UwV83HsGsw3-09','rPc6DW4iMge-06',
             'q9vSo1VnCiC-32','yqstnuAEVhm-32','X7HyMhZNoso-19','yqstnuAEVhm-07']
selected_ids=['R00551','R00351','R00123','R00480','R00402','R01271','R01572','R01411',
              'R00164','R00224','R01557','R02190','R00020','R01518','R00500',
              'R01592','R01135','R01682','R01212','R01439','R00264','R00671',
              'R01646','R00916','R01877','R02245']
f['LC_fixed']=1-f.iou+.5*f.C
f['J_dir']=s['L']*f.direction_rms_deg/s['dir']
f['J_flat']=s['L']*f.flat_top_angular_rms_deg/s['flat']
f['J_intrinsic']=(f.J_dir+f.J_flat)/2
f['K_referenceT']=s['L']*f['T']/s['T']
f['LCG_fixed']=f.LC_fixed+.3*f.J_intrinsic
f['LCT_fixed']=f.LC_fixed+.3*f.K_referenceT
f['mixG_alpha025']=.75*f.LC_fixed+.25*f.J_intrinsic
f['mixG_alpha050']=.5*f.LC_fixed+.5*f.J_intrinsic
# Keep a separate held menu. No restoration of held eligibility through scoring.
f['menu']='unreported'
f.loc[f.primary_candidate,'menu']='primary_candidate'
f.loc[f.image=='yqstnuAEVhm-07','menu']='held_descriptive_only'
eligible=f.menu!='unreported'
for metric in ['LC_fixed','LCG_fixed','LCT_fixed','mixG_alpha025','mixG_alpha050']:
 f.loc[eligible,'rank_'+metric]=f[eligible].groupby(['image','reference_version','menu'])[metric].rank(method='average')
f.loc[eligible,'rank_denominator']=f[eligible].groupby(['image','reference_version','menu'])['id'].transform('size')
f['current_review_verdict']=f.id.map(lambda r:objects.get(r,{}).get('review',{}).get('verdict','not_in_selected_evidence_extract'))
f['order_status']=f.id.map(lambda r:objects.get(r,{}).get('order_status','not_in_selected_evidence_extract'))
cols=['image','id','worker','reference_id','reference_version','primary_candidate','menu',
      'current_review_verdict','order_status','pair_count','reference_pair_count','iou','C','T',
      'direction_rms_deg','flat_top_angular_rms_deg','J_dir','J_flat','J_intrinsic','K_referenceT',
      'LC_fixed','LCG_fixed','LCT_fixed','mixG_alpha025','mixG_alpha050','rank_denominator']
cols += [c for c in f.columns if c.startswith('rank_') and c!='rank_denominator']
f[f.id.isin(selected_ids)][cols].to_csv(OUT/'selected_records.csv',index=False)
f[f.image.isin(image_codes)][cols].to_csv(OUT/'case_menus.csv',index=False)
lookup=f[f.reference_version=='original'].set_index('id')
pair_specs=[
 ('rpc_accepted_outer_vs_detail_errors','R01557','R02190','plausible_relative_rescue'),
 ('rpc_accepted_outer_vs_gtlike','R01557','R00020','two_acceptable_scope_options_not_strict_preference'),
 ('rpc_accepted_outer_vs_near_reference','R01557','R01518','no_nonnegative_intrinsic_rescue'),
 ('uw_medium_vs_gtlike_geometric_error','R00480','R01572','plausible_relative_rescue_not_certified_pair'),
 ('uw_unreviewed_small_vs_gtlike','R01271','R01572','not_individually_reviewed_no_semantic_certification'),
 ('uw_medium_vs_clean_gtlike','R00480','R01411','no_nonnegative_intrinsic_rescue'),
 ('corridor_far_stop_vs_less_far','R00551','R00351','scope_context_only_no_pair_preference'),
 ('corridor_far_stop_vs_near_reference','R00551','R00123','almost_equal_intrinsic_cannot_offset_large_LC_gap'),
 ('q9_missed_corners_vs_alternative_scope','R01592','R01682','regular_omission_risk_not_current_invalid_label'),
 ('yq_simple_four_pairs_vs_detail_rich','R01439','R00264','simplification_warning_no_new_semantic_adjudication'),
 ('x7_partition_vs_omission','R01646','R00916','human_scene_faithfulness_preference_not_represented'),
 ('yq07_fireplace_vs_omission','R01877','R02245','held_detail_preference_no_eligibility_change'),
]
def pair_row(spec,lam=.5,eta=.5,nu=0,version='original'):
 name,aid,bid,kind=spec
 sub=f[f.reference_version==version].set_index('id')
 if aid not in sub.index or bid not in sub.index:return None
 a,b=sub.loc[aid],sub.loc[bid]
 dl=(1-a.iou+lam*a.C)-(1-b.iou+lam*b.C)
 dj=eta*(a.J_dir-b.J_dir)+(1-eta)*(a.J_flat-b.J_flat)
 dk=a.K_referenceT-b.K_referenceT
 intercept=dl+nu*dk
 threshold=-intercept/dj if dj else np.nan
 if dj<0:
  condition=f'mu > {threshold:.12g}' if threshold>=0 else 'A preferred for every mu >= 0'
 elif dj>0:
  condition=f'0 <= mu < {threshold:.12g}' if threshold>0 else 'A never preferred for mu >= 0'
 else:condition='A preferred for every mu >= 0' if intercept<0 else 'A never strictly preferred for mu >= 0'
 return dict(case=name,A=aid,B=bid,interpretation=kind,reference_version=version,
             lambda_C=lam,eta_direction=eta,nu_referenceT=nu,delta_LC=dl,delta_J=dj,delta_K=dk,
             tie_mu=threshold,nonnegative_tie=bool(threshold>=0),
             equivalent_convex_alpha=threshold/(1+threshold) if threshold>=0 else np.nan,
             A_preferred_condition=condition,delta_at_mu03=intercept+.3*dj)
pairrows=[pair_row(x) for x in pair_specs]
pairrows += [r for x in pair_specs if (r:=pair_row(x,version='manual_revision')) is not None]
pd.DataFrame(pairrows).to_csv(OUT/'pair_thresholds.csv',index=False)
trade=[]
for lam,eta,nu in [(0,.5,0),(.25,.5,0),(.5,.5,0),(1,.5,0),(.5,0,0),(.5,.25,0),(.5,.75,0),(.5,1,0),(.5,.5,.3)]:
 rr={x[0]:pair_row(x,lam,eta,nu) for x in pair_specs}
 rpc=rr['rpc_accepted_outer_vs_detail_errors']['tie_mu']; uw=rr['uw_medium_vs_gtlike_geometric_error']['tie_mu']; q9=rr['q9_missed_corners_vs_alternative_scope']['tie_mu']
 trade.append(dict(lambda_C=lam,eta_direction=eta,nu_referenceT=nu,rpc_rescue_lower=rpc,
                   uw_rescue_lower=uw,q9_omission_protection_upper=q9,
                   rpc_plus_q9_interval_nonempty=rpc<q9,
                   rpc_uw_plus_q9_interval_nonempty=max(rpc,uw)<q9,
                   caution='Diagnostic constraints, not validated strict human pair labels'))
pd.DataFrame(trade).to_csv(OUT/'weight_tradeoffs.csv',index=False)

# Recompute the focal raw geometry and selected original/manual-reference comparisons.
# Calls only read source points; no sorting, repairs, fitting-to-reference, or mutation.
sys.path.insert(0,str(PKG/'vendor'))
from components_reused import intrinsic,compare
geochecks=[]; snapshots=[]
for im in panel['images']:
 for a in im['annotations']:
  if a['id'] not in selected_ids:continue
  intr=intrinsic(a)
  snapshots.append({'image':im['code'],'record':a,'references':im['references']})
  for ref in im['references']:
   rows=f[(f.id==a['id'])&(f.reference_id==ref['id'])]
   if len(rows)!=1:continue
   old=rows.iloc[0]; new=compare(a,ref)
   for key,val in [('direction_rms_deg',intr['direction_rms_deg']),('flat_top_angular_rms_deg',intr['flat_top_angular_rms_deg']),
                   ('iou',new['iou']),('C',new['centroid_distance_h']/np.sqrt(new['reference_area_h2'])),('T',new['top3d_symmetric_mean_h'])]:
    err=abs(old[key]-val)
    geochecks.append(dict(image=im['code'],id=a['id'],reference_id=ref['id'],reference_version=ref['version'],metric=key,stored=old[key],recomputed=val,absolute_error=err))
assert max(x['absolute_error'] for x in geochecks)<1e-9
pd.DataFrame(geochecks).to_csv(OUT/'reproduction_checks.csv',index=False)
(OUT/'selected_geometry.json').write_text(json.dumps(snapshots,ensure_ascii=False,indent=2)+'\n')

evidence=[]
for c in comments:
 if c['record_id'] in selected_ids or (c['record_id'] is None and c['image_code'] in image_codes):
  evidence.append({k:c[k] for k in ['comment_id','text','record_id','image_code','evidence_level','occurrences']})
reviews={rid:{'current_verdict':objects[rid]['review']['verdict'],'current_quality_gate':objects[rid]['worker_quality_gate'],
              'order_status':objects[rid]['order_status'],'source_point_indices':objects[rid]['ordered_source_point_indices']} for rid in selected_ids}
(OUT/'evidence.json').write_text(json.dumps({'source':str(inputs[3].relative_to(ROOT)),
 'comments':evidence,'current_record_states':reviews,
 'later_context':{'X7HyMhZNoso-19':'Parent-supplied current instruction and previous_REPORT_ZH.md supersede historical strict correctness language: same big space, both acceptable; partition preferred',
                 'yqstnuAEVhm-07':'Parent-supplied current instruction and previous_REPORT_ZH.md: fireplace preferred, omission acceptable; held status retained'},
 'limits':['Historical comments are record-bound context, not new pairwise labels. Historical verdicts do not override current usability.',
           'R01271 not individually reviewed. Image-level scope ambiguity does not certify each annotation.',
           'No raw user export or new semantic adjudication was performed.']},ensure_ascii=False,indent=2)+'\n')

primary=f[(f.reference_version=='original')&f.primary_candidate]
common=primary.dropna(subset=['LC_fixed','LCG_fixed','LCT_fixed']).copy()
for metric in ['LC_fixed','LCG_fixed','LCT_fixed']:
 common['common_rank_'+metric]=common.groupby('image')[metric].rank(method='average')
primary[primary[['LC_fixed','LCG_fixed','LCT_fixed']].isna().any(axis=1)][cols].to_csv(OUT/'unavailable_primary_rows.csv',index=False)
global_stats={'primary_original_rows':len(primary),'primary_original_images':primary.image.nunique(),
 'common_finite_rows':len(common),'common_finite_images':common.image.nunique(),
 'finite_current_LCG_rank_changes':int((common.common_rank_LCG_fixed!=common.common_rank_LC_fixed).sum()),
 'finite_current_LCT_rank_changes':int((common.common_rank_LCT_fixed!=common.common_rank_LC_fixed).sum()),
 'case_menu_original_rows':int(((f.reference_version=='original')&f.image.isin(image_codes)).sum()),
 'interpretation':'Rank movement is descriptive, not a count of quality improvements; no weights were fitted.'}
checks={'max_recomputed_metric_error':max(x['absolute_error'] for x in geochecks),
        'geometry_records_checked':len(snapshots),'reference_record_comparisons_checked':len(geochecks)//5,
        'source_hashes_unchanged':all(sha(ROOT/p)==v for p,v in hashes.items())}
assert checks['source_hashes_unchanged']
summary={'scales':s,'lambda':.5,'mu':.3,'direction_fraction':.5,
         'fixed_scale_source':str(SITE.relative_to(ROOT))+'/sourceInfo/scales',
         'rank_method':'average within image, reference version, and unchanged eligibility menu',
         'global_descriptive_coverage':global_stats,'checks':checks,'source_sha256':hashes,
         'formulas':{'LC':'1-IoU + lambda*C','G_additive':'LC + mu*J',
                     'J':'sL*(eta*dir/sDir+(1-eta)*flat/sFlat)',
                     'T_additive':'LC + nu*K; K=sL*T/sT',
                     'convex':'(1-alpha)*LC + alpha*J; same rankings as mu=alpha/(1-alpha)',
                     'mixed':'LC+mu*J+nu*K'},
         'qualifications':['Fixed development scales; not calibration from these cases.',
           'Coordinates: original ordered 1024x512 paired points; camera origin; floor y=-1; x,z ground; h not metres.',
           'T is reference-relative conditional top-polyline distance. Intrinsic direction/flatness measures own-model consistency, not truth.',
           'No training, test-set validation, future-worker prediction, candidate eligibility edits, GT edits, or site edits.']}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'global':global_stats,'checks':checks},indent=2))
print(pd.DataFrame(trade).to_string(index=False))
