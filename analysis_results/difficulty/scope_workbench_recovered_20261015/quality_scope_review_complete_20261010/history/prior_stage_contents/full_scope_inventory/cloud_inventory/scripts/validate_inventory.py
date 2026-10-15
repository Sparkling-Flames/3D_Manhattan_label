from pathlib import Path
import json,csv,collections,hashlib,math
P=Path(__file__).parent;D=json.load(open(P/'inventory.json'));C=D['comments'];O=D['occurrences'];G=D['geometry_records'];I=D['images'];src=P/'sources';checks=[]
def chk(name,ok,detail=None):
 assert ok,(name,detail);checks.append(dict(check=name,passed=True,detail=detail))
chk('all_259_unique_image_ids',len(I)==len({r['image_id'] for r in I})==259)
chk('all_3152_unique_record_ids',len(G)==len({r['record_id'] for r in G})==3152)
chk('all_3152_unique_object_ids',len({r['object_id'] for r in G})==3152)
chk('image_denominators_sum_3152',sum(r['total_records'] for r in I)==3152)
chk('condition_gate_denominators_sum_3152',sum(r['n_records'] for r in D['condition_gate_groups'])==3152)
chk('current_manual_pool_1866',sum(r['in_current_manual_pool'] for r in G)==1866)
chk('excluded_records_218_preserved',sum(r['gate']=='excluded' for r in G)==218)
chk('five_floor_confirmations_separate',sum(r['user_confirmed_floor_region'] for r in I)==5)
chk('one_memory_identity_confirmation_separate',sum(r['memory_identity_confirmed'] for r in I)==1 and next(r for r in I if r['memory_identity_confirmed'])['image_code']=='uNb9QFRL6hY-88')
chk('203_broad_and_56_unhit_partition',sum(r['broad_review_queue'] for r in I)==203 and sum(not r['broad_review_queue'] for r in I)==56)
chk('28_current_vs_original_reference_differences',sum(r['historical_reference_version_pending'] for r in I)==28)
chk('four_historical_snapshot_holds_preserved',sum(r['historical_snapshot_hold'] for r in I)==4)
chk('two_current_user_quality_holds_preserved',{r['image_code'] for r in I if r['current_user_quality_reference_hold']}=={'x8F5xyUWy9e-01','wc2JMjhGNzB-14'})
chk('three_observed_formal_quality_holds_preserved',{r['image_code'] for r in I if r['formal_quality_hold_observed']}=={'jtcxE69GiFV-18','q9vSo1VnCiC-29','zsNo4HB9uLZ-13'})
chk('nine_known_hold_contexts_not_full_policy',sum(r['reference_paused'] for r in I)==9)
chk('q9_floor_confirmation_does_not_release_quality_hold',next(r for r in I if r['image_code']=='q9vSo1VnCiC-29')['user_confirmed_floor_region'] and next(r for r in I if r['image_code']=='q9vSo1VnCiC-29')['formal_quality_hold_observed'])
lookup={c['comment_id']:c for c in C}
chk('unique_comment_ids',len(C)==len(lookup))
for r in I:
 for c in filter(None,r['keyword_comment_ids'].split(';')):chk('comment_image_match_'+c,lookup[c]['image_id']==r['image_id'])
# Verify exact source pointers for every extracted occurrence.
cache={};bad=[]
for r in O:
 p=src/r['source_path'];ptr=r['source_pointer']
 if p.suffix=='.csv':
  if str(p) not in cache:cache[str(p)]=list(csv.DictReader(open(p,encoding='utf-8-sig')))
  value=cache[str(p)][int(ptr.split('/')[-1])]['comment']
 else:
  if str(p) not in cache:cache[str(p)]=json.load(open(p))
  value=cache[str(p)]
  for bit in ptr.split('/')[1:]:
   bit=bit.replace('~1','/').replace('~0','~');value=value[int(bit)] if isinstance(value,list) else value[bit]
 if value!=r['comment']:bad.append((r['source_path'],ptr))
chk('all_6340_source_pointers_match_exact_text',not bad,{'occurrences':len(O),'bad':bad})
indexed=[c for c in C if 'historical_deduplicated_index' in c['source_roles']]
chk('all_1157_historical_index_comments_preserved',len(indexed)==1157)
indexonly=[c for c in indexed if c['source_roles']==['historical_deduplicated_index']]
chk('1153_index_comments_also_have_json_provenance',len(indexed)-len(indexonly)==1153,{'index_only':len(indexonly),'index_only_ids':[c['comment_id'] for c in indexonly]})
chk('all_annotation_comments_exact_record_mapped',all(c['record_id'] for c in C if c['object_kind']=='annotation'))
chk('no_unresolved_identities',all(c['identity_status']!='unresolved' for c in C))
# Metrics copied, not recalculated; validate internal identity and no invalid geometry fabricated.
for g in G:
 a=g['selected_gt_metrics_symmetric_difference'];b=g['selected_gt_metrics_missing'];c=g['selected_gt_metrics_excess']
 if a!='':chk('metric_sum_'+g['record_id'],abs(a-b-c)<1e-8)
 else:chk('missing_metric_not_zero_'+g['record_id'],b==c=='')
report={'status':'passed','source_commit':D['source_commit'],'checks_count':len(checks),'high_level_checks':[x for x in checks if not x['check'].startswith(('comment_image_match_','metric_sum_','missing_metric_not_zero_'))],'all_pointer_checks':len(O),'all_metric_checks':len(G),'limitations':['108396834-byte LFS comments.json payload not available; complete 1157-row historical index and 35 parsed JSON sources were read instead.','Keyword/semantic triage and existing area differences are retrieval evidence, not new human scope truth.','21 historical source images are outside the current259-image annotated corpus and retained separately.','Comments may refer to earlier reference versions; 28 current/original differences explicitly flagged.']}
(P/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
