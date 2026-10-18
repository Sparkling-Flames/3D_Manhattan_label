import json,gzip,csv,collections,math
from pathlib import Path
r=Path(__file__).resolve().parents[1];w=r/'extracted/work_v2_20261019';src=r/'extracted/repo_main_20261019/research/statistics/v2_evidence_audit_20261019/records.json.gz'
rows=json.load(gzip.open(src))['records'];semi=[x for x in rows if x['condition']=='semi']
def hist(xs,key):return dict(collections.Counter(str(x.get(key)) for x in xs))
def cnt(xs,k):return sum(x.get(k) is True for x in xs)
types={}
for section,fields in {'semi_evidence':['exact_initialization_bound','confirmed_error_opportunity','reported_error_opportunity','known_error_unchanged','reported_known_error_unchanged','edited','corrected_confirmed'],'scope_evidence':['judgement_opportunity','correct'],'exclusion_attribution':['specific_person_error_candidate','legacy_explicit_person_error']}.items():
 for f in fields:types[section+'.'+f]=dict(collections.Counter(type(x[section].get(f)).__name__+':'+str(x[section].get(f)) for x in rows))
byorigin={}
for origin in ['v1','new']:
 z=[x for x in semi if x['origin']==origin];s=[x['semi_evidence'] for x in z];key='confirmed_error_opportunity' if origin=='v1' else 'reported_error_opportunity';o=[v for v in s if v.get(key) is True]
 byorigin[origin]={'semi_records':len(z),'exact_bound':cnt(s,'exact_initialization_bound'),'opportunities':len(o),'opportunity_edit_states':hist(o,'edited'),'opportunity_correction_states':hist(o,'corrected_confirmed'),'known_unchanged':cnt(o,'known_error_unchanged' if origin=='v1' else 'reported_known_error_unchanged'),'all_edit_states':hist(s,'edited'),'initial_coordinates_available':sum(bool(x.get('initialization_points')) for x in s)}
scope=[x for x in rows if x['scope_evidence']['judgement_opportunity'] is True]
scope_checks={'responses':sum(x['scope_evidence']['response'] is not None for x in rows),'opportunities':len(scope),'retained_opportunities':sum(x['cleaning_disposition']=='retained' for x in scope),'gold':hist([x['scope_evidence'] for x in scope],'compatible_gold'),'correct':hist([x['scope_evidence'] for x in scope],'correct'),'unknown_correctness':sum(x['scope_evidence']['correct'] is None for x in rows)}
specific=[x for x in rows if x['exclusion_attribution']['specific_person_error_candidate'] is True];legacy=[x for x in rows if x['exclusion_attribution']['legacy_explicit_person_error'] is True]
review=list(csv.DictReader((w/'audit/exclusion_text_review_25.csv').open(encoding='utf-8-sig')));states=collections.Counter(x['independent_text_review_state'] for x in review)
labels=[]
for x in rows:
 e=x['exclusion_attribution'];s=x['semi_evidence'];sc=x['scope_evidence'];a=[k for k,v in [('legacy_person_exclusion',e['legacy_explicit_person_error'] is True),('specific_exclusion_candidate',e['specific_person_error_candidate'] is True),('old_confirmed_initial_error_unchanged',s.get('known_error_unchanged') is True),('new_reported_initial_error_unchanged',s.get('reported_known_error_unchanged') is True),('compatible_scope_incorrect',sc['correct'] is False)] if v]
 if a:labels.append((x['object_id'],a))
fold=list(csv.DictReader((w/'audit/fold_behavior_profiles.csv').open(encoding='utf-8-sig')));mismatch=[];mixed=[]
for f in fold:
 z=[x for x in rows if x['building_id']!=f['heldout_building'] and x['worker_id']==f['worker_id'] and (x['semi_evidence'].get('confirmed_error_opportunity') is True or x['semi_evidence'].get('reported_error_opportunity') is True)]
 n=len(z);b=len(set(x['building_id'] for x in z));miss=sum(x['semi_evidence'].get('known_error_unchanged') is True or x['semi_evidence'].get('reported_known_error_unchanged') is True for x in z);supported=n>=3 and b>=2
 lev='confirmed_frozen_initialization' if any(x['semi_evidence'].get('confirmed_error_opportunity') is True for x in z) else 'user_reported_flags' if n else 'unknown'
 if len(set(x['origin'] for x in z))>1:mixed.append([f['heldout_building'],f['worker_id']])
 state='repeated_retention_observed' if supported and miss>=2 else 'one_retention_observed' if supported and miss==1 else 'no_retention_reported_on_observed_opportunities_correction_unknown' if supported else 'insufficient_opportunity'
 ok=int(f['opportunities'])==n and int(f['retained_error_events'])==miss and (f['supported']=='True')==supported and f['evidence_level']==lev and f['behavior_type']==state
 ok=ok and (abs(float(f['retention_fraction'])-miss/n)<1e-12 if supported else not f['retention_fraction'])
 if not ok:mismatch.append([f['heldout_building'],f['worker_id']])
result={'semi':byorigin,'scope':scope_checks,'exclusion':{'candidate_count':len(specific),'legacy_count':len(legacy),'legacy_subset_of_candidates':set(x['object_id'] for x in legacy)<=set(x['object_id'] for x in specific),'review_ids_equal_candidates':set(x['object_id'] for x in review)==set(x['object_id'] for x in specific),'text_review_states':dict(states),'candidate_reason_codes':dict(collections.Counter(x['exclusion_attribution']['candidate_evidence']['reason_code'] for x in specific)),'severity_gold':False},'dedup':{'inventory_unique_object_ids':len(set(x['object_id'] for x in rows)),'adverse_unique_objects':len(labels),'adverse_label_occurrences':sum(len(x[1]) for x in labels)},'boolean_field_types':types,'fold_recount':{'rows':len(fold),'mismatches':mismatch,'mixed_origin_opportunity_folds':mixed},'issues_and_limits':['The 22+2+1 split is a text-category coding with one hard-coded ambiguous object and two reason-code cases; it is not independent visual severity gold.','Old exact-initialization and new self-reported opportunity levels are separate and not comparable correction-success rates.','Building-held-out behavior features use historical records excluding the target building, with >=3 opportunities and >=2 buildings; this is retrospective building transfer, not a temporal prospective validation.','Scope has no observed incorrect/OOS compatible-gold opportunities, so it cannot identify OOS false acceptance or differentiate general scope ability.','Targeted exclusion flags have no random audit denominator; cannot form general personnel penalties or rates.','No truthy string False found in these frozen JSON indicator fields; behavior selection uses explicit istrue and finite checks. Unknown remains blank/unsupported.']}
(r/'independent/source_evidence_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='boolean_field_types'},ensure_ascii=False,indent=2))
