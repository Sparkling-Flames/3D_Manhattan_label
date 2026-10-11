"""Conservative target-confounding filters; never modifies formal eligibility."""
from pathlib import Path
from collections import Counter
import csv
from common import read,save,csvwrite
ROOT=Path(__file__).resolve().parents[1]

def main():
    rows=read(ROOT/'results/current_components.json')
    path=ROOT/'inputs/alignment_scope_flags.json'
    if path.exists():
        flags=read(path)
    else:
        geos=read(ROOT/'inputs/current_geometry.json')['geometries'];flags={}
        for r in rows:
            s=geos[r['object_id']]['source_record'];review=s.get('final_review') or {}
            flags[r['object_id']]={'scope_difference_image':bool(review.get('scope_difference_image')),'scope_difference_annotation':bool(review.get('scope_difference_annotation')),'formal_review_source':'current loader final_review, unchanged','reference_object_id':r['reference_object_id']}
        save(path,flags)
    confirmed={r['image_id']:r for r in read(ROOT/'inputs/scope/normalized_confirmation_overlay.json')['records']}
    ab={r['image_id']:r for r in read(ROOT/'results/AB_mapping.json')}
    out=[]
    for r in rows:
        f=flags[r['object_id']];c=confirmed.get(r['image_id']);reasons=[]
        if f['scope_difference_image']:reasons.append('existing_image_scope_difference')
        if f['scope_difference_annotation']:reasons.append('existing_annotation_scope_difference')
        if c and c['decision']=='allow':reasons.append('confirmed_alternative_floor_top_pending')
        main=r['primary_included'] and r['Manhattan_applicability_group']=='ordinary_scene_supports_Manhattan'
        pending=bool(c and c['decision']=='allow')
        out.append({'record_id':r['record_id'],'object_id':r['object_id'],'image_id':r['image_id'],'image_code':r['image_code'],'worker_id':r['worker_id'],'main_Manhattan_comparison':main,'primary_without_confirmed_B_top_pending':r['primary_included'] and not pending,'Manhattan_without_confirmed_B_top_pending':main and not pending,'target_unconfounded_conservative':main and not reasons,'target_confounding_reasons':reasons,'confirmation_decision':c['decision'] if c else None,'B_top_pending':pending,'formal_scope_flags':f,'filter_changes_formal_gate':False,'historical_intention_verified':False})
    save(ROOT/'results/target_alignment_ledger.json',out);csvwrite(ROOT/'results/target_alignment_ledger.csv',out)
    chosen={r['record_id'] for r in out if r['target_unconfounded_conservative']}
    summaries=[]
    for r in csv.DictReader(open(ROOT/'results/penalty_scores_finite_grid.csv',encoding='utf-8-sig')):
        if r['record_id'] in chosen:summaries.append(r)
    csvwrite(ROOT/'results/target_aligned_penalty_scores.csv',summaries)
    lookup={r['record_id']:r for r in rows};groups={}
    for r in summaries:groups.setdefault((r['family'],r['strength']),[]).append(r)
    pairrows=list(csv.DictReader(open(ROOT/'results/same_image_pair_crossing_roots.csv',encoding='utf-8-sig')))
    pairrows=[r for r in pairrows if r['record_1'] in chosen and r['record_2'] in chosen]
    csvwrite(ROOT/'results/target_aligned_pair_crossing_roots.csv',pairrows)
    flips=list(csv.DictReader(open(ROOT/'results/real_same_image_rank_flips.csv',encoding='utf-8-sig')))
    flips=[r for r in flips if r['record_1'] in chosen and r['record_2'] in chosen]
    csvwrite(ROOT/'results/target_aligned_same_image_rank_flips.csv',flips)
    result=[]
    for (family,strength),members in groups.items():
        for severity in ['all','mild_Dle5_Fle2','severe_Dge10','intermediate_or_flatness_dominant']:
            rs=[r for r in members if severity=='all' or r['severity_group']==severity]
            changed=[r for r in rs if abs(float(r['delta_from_v11']))>1e-10]
            fs=[r for r in flips if (r['family'],r['strength'])==(family,strength)] if severity=='all' else []
            delta=[float(r['delta_from_v11']) for r in rs]
            result.append({'family':family,'strength':strength,'population':'conservative_target_unconfounded','severity_group':severity,'n_records':len(rs),'n_changed_records':len(changed),'n_changed_images':len({r['image_code'] for r in changed}),'n_changed_workers':len({lookup[r['record_id']]['worker_id'] for r in changed}),'mean_delta':sum(delta)/len(delta) if delta else None,'threshold_crossings':{str(q):sum((float(r['Q_v11'])>=q)!=(float(r['Q_candidate'])>=q) for r in rs) for q in [95,85,50,90,75,60]},'n_pair_flips':len(fs) if severity=='all' else None,'n_flip_images':len({r['image_code'] for r in fs}) if severity=='all' else None,'n_flip_workers':len({r[k] for r in fs for k in ['worker_1','worker_2']}) if severity=='all' else None})
    csvwrite(ROOT/'results/target_aligned_penalty_group_summaries.csv',result)
    summary={'all_events_retained':len(rows),'main_group_diagnostic_retained':sum(r['main_Manhattan_comparison'] for r in out),'target_unconfounded_conservative_records':len(chosen),'target_unconfounded_images':len({r['image_code'] for r in out if r['record_id'] in chosen}),'exclusion_reason_occurrences':dict(Counter(x for r in out if r['main_Manhattan_comparison'] for x in r['target_confounding_reasons'])),'same_image_pairs_in_conservative_subset':sum(r['family']=='constant_alpha' for r in pairrows),'same_image_pair_roots_all_families':len(pairrows),'rank_flip_rows_all_variants':len(flips),'Pro_1725_1724_not_locally_verified':True,'filter_is_operational_evidence_restriction_not_recovered_intention':True}
    summary['nested_primary_without_confirmed_B_top_pending']=sum(r['primary_without_confirmed_B_top_pending'] for r in out)
    summary['nested_Manhattan_without_confirmed_B_top_pending']=sum(r['Manhattan_without_confirmed_B_top_pending'] for r in out)
    summary['matching_Pro_count_alone_is_not_membership_verification']=True
    if (ROOT/'results/Pro_source_replay_summary.json').exists():
        pro=read(ROOT/'results/Pro_source_replay_summary.json')
        summary['Pro_1725_1724_not_locally_verified']=False
        summary['nested_1725_membership_verified_against_local_Pro_ids']=pro['nested_1725_membership_exactly_matches_Pro']
        summary['Pro_1724_differs_by_independent_vote_eligibility']=pro['quality_1725_minus_independent_primary_1724']
    save(ROOT/'results/target_alignment_summary.json',summary);print(summary)

if __name__=='__main__':main()
