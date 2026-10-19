#!/usr/bin/env python3
"""Independent consumption checks. Does not claim collection/score regeneration."""
from pathlib import Path
from collections import Counter
import hashlib, gzip, json
import pandas as pd

ROOT=Path(__file__).resolve().parent
MAIN=ROOT.parent/'main_personnel_A_20261019'
OUT=ROOT/'input'; OUT.mkdir(exist_ok=True)
EP=MAIN/'research/statistics/v2_evidence_audit_20261019/records.json.gz'
TP=MAIN/'research/statistics/v2_integrated_analysis_20261019/tables.json.gz'
records=json.load(gzip.open(EP,'rt'))['records']
tables=json.load(gzip.open(TP,'rt'))['tables']
def sizes(rows):
    return dict(records=len(rows), images=len({r['image_id'] for r in rows}), workers=len({r['worker_id'] for r in rows}), buildings=len({r['building_id'] for r in rows}))
q=[r for r in records if r['quality_usable']]
ordinary=[r for r in q if r['condition']=='manual' and r['quality_use']=='ordinary_primary']
assert len(records)==len({r['object_id'] for r in records})==10439
assert len(q)==7302 and len(ordinary)==5719
rows=[]
for r in records:
    s=r['semi_evidence'];c=r['scope_evidence'];e=r['exclusion_attribution']
    rows.append({k:r.get(k) for k in ['object_id','worker_id','image_id','image_code','building_id','condition','origin','current_class','quality_usable','quality_use','cleaning_disposition','calculation_class','source_active_time_seconds','target_matched_time_seconds']} | {
      'scope_recorded':c.get('response_recorded'), 'scope_response':c.get('response'), 'scope_gold_opportunity':c.get('judgement_opportunity'), 'scope_correct':c.get('correct'),
      'semi_exact_initialization':s.get('exact_initialization_bound'), 'semi_confirmed_error_opportunity':s.get('confirmed_error_opportunity'), 'semi_reported_error_opportunity':s.get('reported_error_opportunity'),
      'semi_confirmed_unchanged':s.get('known_error_unchanged'), 'semi_reported_unchanged':s.get('reported_known_error_unchanged'), 'semi_edited':s.get('edited'), 'semi_corrected_confirmed':s.get('corrected_confirmed'), 'semi_attributable_gain_available':s.get('worker_attributable_gain_available'),
      'specific_person_error_candidate':e.get('specific_person_error_candidate'), 'legacy_explicit_person_error':e.get('legacy_explicit_person_error'), 'individually_reviewed':r.get('coordinate_evidence',{}).get('final_review',{}).get('individually_reviewed')})
df=pd.DataFrame(rows);df.to_csv(OUT/'RECORD_EVIDENCE_LEDGER.csv.gz',index=False)
per=[]
for w,g in df.groupby('worker_id'):
    z={'worker_id':w,'inventory':len(g),'quality':int(g.quality_usable.sum()),'inventory_images':g.image_id.nunique(),'inventory_buildings':g.building_id.nunique()}
    for col in ['source_active_time_seconds','target_matched_time_seconds','scope_response','semi_edited']:
        z[col+'_known']=int(g[col].notna().sum())
    for col in ['scope_gold_opportunity','scope_correct','semi_exact_initialization','semi_confirmed_error_opportunity','semi_reported_error_opportunity','semi_confirmed_unchanged','semi_reported_unchanged','semi_corrected_confirmed','semi_attributable_gain_available','specific_person_error_candidate','legacy_explicit_person_error','individually_reviewed']:
        z[col+'_true']=int(g[col].eq(True).sum());z[col+'_known']=int(g[col].notna().sum())
    per.append(z)
pd.DataFrame(per).to_csv(OUT/'WORKER_EVIDENCE_COVERAGE_62.csv',index=False)
v1=tables['statistics__v1_v2_common_membership']
v1=[r for r in v1 if r['quality_usable_v1']]
assert len(v1)==1911
v1_max={k:max(abs(r[k]) for r in v1) for k in ['B8L2_v2_minus_v1','D10_v2_minus_v1']}
assert all(v<=1e-12 for v in v1_max.values())
counts={
 'main_commit':'dafa73ac7d8ada9a7f5c0e483d695adcbd916550', 'input_data_release':'v2',
 'input_sha256':hashlib.sha256(EP.read_bytes()).hexdigest(),
 'inventory':sizes(records),'quality':sizes(q),'ordinary_manual':sizes(ordinary),
 'origins':dict(Counter(r['origin'] for r in records)),
 'geometry':dict(Counter(r['calculation_class'] for r in records)),
 'ordinary_difficulty':{d:sizes([r for r in ordinary if r['current_class']==d]) for d in sorted({r['current_class'] for r in ordinary})},
 'source_time_n':int(df.source_active_time_seconds.notna().sum()),'target_time_n':int(df.target_matched_time_seconds.notna().sum()),
 'source_time_by_origin':df[df.source_active_time_seconds.notna()].origin.value_counts().to_dict(),
 'scope_responses':int(df.scope_response.notna().sum()),'scope_gold':int(df.scope_gold_opportunity.eq(True).sum()),'scope_correct':int(df.scope_correct.eq(True).sum()),
 'scope_gold_retained':int((df.scope_gold_opportunity.eq(True)&df.cleaning_disposition.eq('retained')).sum()),
 'semi_by_origin':{},'specific_person_error_candidates':int(df.specific_person_error_candidate.eq(True).sum()),'legacy_explicit_person_errors':int(df.legacy_explicit_person_error.eq(True).sum()),
 'v1_fixed_1911_in_published_comparison_max_difference':v1_max,
 'v1_fixed_1911_in_published_comparison_unchanged_within_1e_minus_12':True,
 'new_score_engine_replay_performed_in_this_input_check':False,'full_collection_reproduced':False,'Dot_complete_payload_reproduced':False,
 'current_scientific_input_matches_archive':True,'n1_applied':False,
 'inherited_coordinate_and_reference_contract':'already processed points, mean-x, repairs, deletions and declared rings; no raw-export replacement',
}
for o,g in df[df.condition.eq('semi')].groupby('origin'):
 counts['semi_by_origin'][o]={'n':len(g),**{col:int(g[col].eq(True).sum()) for col in ['semi_exact_initialization','semi_confirmed_error_opportunity','semi_reported_error_opportunity','semi_confirmed_unchanged','semi_reported_unchanged','semi_edited','semi_corrected_confirmed','semi_attributable_gain_available']}}
assert counts['source_time_n']==9236 and counts['target_time_n']==440
assert counts['scope_responses']==9845 and counts['scope_gold']==93
(OUT/'CURRENT_INPUT_AUDIT.json').write_text(json.dumps(counts,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(counts,ensure_ascii=False,indent=2))
