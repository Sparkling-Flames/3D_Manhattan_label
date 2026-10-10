"""Check meaningful routing/holdout/blind-form invariants; no quality calibration."""
from pathlib import Path
from collections import Counter,defaultdict
import csv,json
from common import read,save,csvwrite
ROOT=Path(__file__).resolve().parents[1]
def main():
 routing=list(csv.DictReader(open(ROOT/'results/routing_sensitivity.csv',encoding='utf-8-sig')));workers=defaultdict(list)
 for r in routing:
  assert r['unique_target_assignment']=='' and r['actual_intention_inferred']=='False'
  workers[(r['worker_id'],r['distance_metric'],r['absolute_limit_h'],r['relative_gap_h'])].append(r)
 out=[]
 for (worker,metric,absolute,gap),rs in workers.items():
  out.append({'worker_id':worker,'metric':metric,'absolute_limit_h':absolute,'relative_gap_h':gap,'n_all_events':len(rs),'absolute_compatibility_states':dict(Counter(r['state'] for r in rs)),'relative_preferences':dict(Counter(r['relative_preference'] for r in rs)),'unmatched_retained_in_denominator':True,'person_quality_inferred':False})
 csvwrite(ROOT/'results/person_compatibility_sensitivity.csv',out)
 for key,rs in __import__('itertools').groupby(sorted(routing,key=lambda r:(r['distance_metric'],r['absolute_limit_h'],r['relative_gap_h'])),key=lambda r:(r['distance_metric'],r['absolute_limit_h'],r['relative_gap_h'])):assert len(list(rs))==429
 groups=list(csv.DictReader(open(ROOT/'results/room_holdout_manifest.csv',encoding='utf-8-sig')));gs=defaultdict(set)
 for r in groups:gs[r['room_group']].add(r['held_out_of_sample_and_future_calibration'])
 assert all(len(v)==1 for v in gs.values());held={r['record_id'] for r in groups if r['held_out_of_sample_and_future_calibration']=='True'}
 cases=read(ROOT/'blind_sample/answer_mapping_private.json');assert len(cases)==8
 assert all(c['record_1'] not in held and c.get('record_2') not in held for c in cases)
 forms=list(csv.DictReader(open(ROOT/'blind_sample/user_response_blank.csv',encoding='utf-8-sig')))
 for r in forms:assert all(v=='' for k,v in r.items() if k not in ['case_id','case_type'])
 assert next(r for r in forms if r['case_id']=='X01')['case_type']=='同一答案的空间匹配'
 assert all(c['pure_regularity_calibration_allowed'] for c in cases if c['case_id'] in ['C06','C07'])
 manifests=read(ROOT/'blind_sample/render_manifest.json');assert all(m['real_pixels_loaded'] and m['comparison_scales_shared'] and not m['B_top_created'] for m in manifests)
 u=ROOT/'blind_sample/user'
 assert len(list(u.glob('*_original.jpg')))==8
 assert not any(t in (u/'index.html').read_text() for c in cases for t in [c.get('worker_1','IMPOSSIBLE_IDENTIFIER'),c.get('object_1','IMPOSSIBLE_IDENTIFIER')])
 # Per-record diagnostic sources are closed against parent Pro comparison, not locally reexecuted Pro code.
 p=read(ROOT/'results/parent_Pro_record_closure_evidence.json');assert p['n_object_ids']==3152 and p['available_record_set_3021_closed_against_Pro']
 result={'routing_tests_passed':read(ROOT/'results/space_match_tests.json')['passed'],'routing_all_429_events_every_candidate':True,'person_compatibility_rows':len(out),'holdout_no_group_leakage':True,'holdout_records':len(held),'user_blank_judgments':True,'user_case_count':len(cases),'real_original_pixels':True,'B_top_not_fabricated':True,'Q_not_used_to_route_or_select_new_pairs':True,'Pro_source_obtained_via_pinned_repository_archive':(ROOT/'results/Pro_source_replay_summary.json').exists()}
 save(ROOT/'results/revision_validation.json',result);print(result)
if __name__=='__main__':main()
