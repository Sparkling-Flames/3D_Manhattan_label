"""Small local-evidence table; geometric family evidence is separate from intent."""
import json,csv,math
from collections import Counter
import numpy as np
from shapely.geometry import Polygon,Point,LineString,box
from shapely.ops import transform
from recompute_floor import ROOT,project,strict_poly,dump
def main():
 seed=json.loads((ROOT/'inputs/previous/editor_seed_data.json').read_text());c=seed['images'][0];A=project(c['reference_points_1024x512']);ledger=json.loads((ROOT/'results/reference_ledger.json').read_text());T={r['space_label']:strict_poly(r['polygon_xz_h']) for r in ledger['spaces']};globalrows={r['record_id']:r for r in json.loads((ROOT/'results/floor_recompute_20.json').read_text())['rows']}
 entrance=(A[4]+A[7])/2;far=(A[5]+A[6])/2;e=(far-entrance);L=float(np.linalg.norm(e));e/=L;n=np.array([e[1],-e[0]])
 local=lambda p:np.column_stack(((np.asarray(p)-entrance)@n,(np.asarray(p)-entrance)@e))
 quad=strict_poly(A[[4,5,6,7]]);difference=T['A'].difference(T['C']);back=T['B'].difference(T['A']);assert difference.area>0 and back.area>0
 localquad=strict_poly(local(A[[4,5,6,7]]));farhalf=localquad.intersection(box(-100,L/2,100,100));farwall=LineString([A[5],A[6]])
 # No final matching thresholds. Bands only expose distance from two observed
 # endpoint clusters and reserve the intermediate cases for user review.
 evidence=[]
 for a in c['annotations']:
  g=globalrows[a['record_id']]
  if g['geometry_status']!='valid':evidence.append(dict(record_id=a['record_id'],geometry_status='invalid',family='unresolved_invalid'));continue
  q=project(a['points']);p=strict_poly(q);lp=strict_poly(local(q));cov=p.intersection(difference).area/difference.area;quad_cov=p.intersection(quad).area/quad.area;deep=lp.intersection(farhalf).area/farhalf.area;backcov=p.intersection(back).area/back.area
  row=dict(record_id=a['record_id'],worker_id=a['worker_id'],geometry_status='valid',in_manual_pool=g['automatic_summary_denominator_eligible'],quality_primary_included=g['frozen_primary_included'],cached_footprint_status=g['cached_footprint_status'],front_difference_area_h2=difference.area,front_difference_coverage=cov,GT5_6_7_8_quad_coverage=quad_cov,far_half_coverage=deep,far_wall_boundary_distance_h=p.boundary.distance(farwall),back_B_minus_A_difference_coverage=backcov,global_best_floor_IoU=g['automatic_best_floor_IoU'],global_best_IoU=g['new_ABCD_best_IoU'],global_gap=g['best_second_gap'])
  for label,ix in [('GT5',4),('GT8',7)]:
   ds=np.linalg.norm(q-A[ix],axis=1);near=int(ds.argmin());prev=(near-1)%len(q);nxt=(near+1)%len(q);gains=[float((q[j]-q[near])@e) for j in (prev,nxt)]
   row.update({label+'_nearest_annotation_vertex_1based':near+1,label+'_nearest_corner_distance_h':float(ds[near]),label+'_adjacent_depth_gains_h':gains,label+'_max_adjacent_extension_over_L':max(gains)/L})
  # The actual data form two separated structural groups: far-half coverage 0
  # versus almost 1. Keep a broad middle as unresolved; never use nearest corners alone.
  if deep<=1e-10 and cov<=.05:family='CD_family_extension_not_expressed';strength='strong_local_stop_evidence'
  elif deep>=.90 and cov>=.90:family='AB_family_extension_expressed';strength='strong_local_extension_evidence'
  else:family='ambiguous_local_extension';strength='partial_or_distorted_local_structure'
  if a['record_id']=='R01412':family='AB_family_partial_extension_missing_entry_turn';strength='partial_or_ambiguous_entry_structure_parent_pixel_audit'
  subtype=None;route='local_structure_first';confidence='structural_family_only_not_intent'
  if family.startswith('CD'):
   if backcov<=.05:subtype='C';route='two_local_difference_regions';confidence='structural_candidate_not_true_intent'
   elif backcov>=.90:subtype='D';route='two_local_difference_regions';confidence='structural_candidate_not_true_intent'
  elif family.startswith('AB'):
   if backcov<=.05:subtype='A';route='two_local_difference_regions';confidence='structural_candidate_not_true_intent'
   elif backcov>=.90:subtype='B';route='two_local_difference_regions';confidence='structural_candidate_not_true_intent'
  if subtype is None:
   allowed='CD' if family.startswith('CD') else 'AB' if family.startswith('AB') else 'ABCD';subtype=max(allowed,key=lambda k:g[k+'_iou']);route='local_family_then_floor_IoU_fallback' if len(allowed)==2 else 'floor_IoU_fallback_local_ambiguous';confidence='low_geometric_fallback_not_intent'
  row.update(local_family=family,local_evidence_strength=strength,geometric_candidate_space=subtype,geometric_candidate_route=route,candidate_confidence=confidence,manual_target='D' if a['record_id']=='R02962' else None,effective_target='D' if a['record_id']=='R02962' else None,effective_target_source='user_specified' if a['record_id']=='R02962' else 'not_manually_assigned',true_intent_established=False)
  evidence.append(row)
 spec=dict(paired_GT_numbering_1based={str(i+1):dict(top_ERP_1024x512=c['reference_points_1024x512'][2*i],bottom_ERP_1024x512=c['reference_points_1024x512'][2*i+1],floor_xz_h=A[i].tolist()) for i in [4,5,6,7]},entrance_pair_numbers=[5,8],far_end_pair_numbers=[6,7],quad_area_h2=quad.area,A_minus_C_extension_area_h2=difference.area,extension_depth_h=L,second_difference_B_minus_A_area_h2=back.area,criteria='Corner proximity alone is not positive evidence. Use adjacent depth extension and covered far-half of protruding region. All raw quantities remain visible.',descriptive_evidence_bands={'near_zero_max_coverage':.05,'near_full_min_coverage':.90,'zero_far_half_tolerance':1e-10},bands_are_not_final_thresholds=True,half_depth_is_a_geometric_partition_not_quality_cutoff=True,pixel_screenshot_library_id='libfile_31d539c46e7c81919f8ff808adef8f6c',screenshot_independently_materialized=False,numbering_pixel_crosscheck='parent viewed actual pixels; this executor verifies GT coordinates and generates own local figure',priority_order=['explicit_user_target','local_differentiating_structure','floor_IoU_fallback_only_for_partial_distorted_ambiguous_structure'],rows=evidence)
 dump(ROOT/'results/local_structure_20.json',spec)
 fields=list(dict.fromkeys(k for r in evidence for k in r));
 with (ROOT/'results/local_structure_20.csv').open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n");w.writeheader();w.writerows(evidence)
 rows=[r for r in evidence if r.get('in_manual_pool')];summary=dict(manual_pool_denominator=len(rows),family_counts=dict(Counter(r['local_family'] for r in rows)),local_candidate_counts=dict(Counter(r['geometric_candidate_space'] for r in rows)),low_confidence_fallback_records=[r['record_id'] for r in rows if r['candidate_confidence'].startswith('low')],AB_structural_exceptions=[r for r in rows if r['local_family'].startswith('AB')],excluded_diagnostic_records=[r for r in evidence if not r.get('in_manual_pool')],all_20_object_statuses_preserved=True,T30_explicit_D_preserved=True)
 dump(ROOT/'results/local_summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
