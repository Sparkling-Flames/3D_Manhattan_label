#!/usr/bin/env python3
"""This round's read-only source index; no model, fusion, or effect calculation."""
from pathlib import Path
import csv, gzip, hashlib, json

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
COMMIT = 'e92abe8631d7f01dc192ee796b46f295ece37a6d'
CONTEXT = BASE / 'source_context'
POP = 'research/workers/personnel_population_curves_v2_20261023/'
MIX = 'research/workers/personnel_mixture_comparison_20261022/'
QT = 'research/workers/personnel_exchange_adoption_followup_20261022/manual_qt_followup/'
STOP = 'research/same_room/same_room_profile_return_review_20261021/pro/prior_integration/'

specs = [
 ('S01','research/workers/personnel_exchange_closure_20261022/classification/FIELD_GUIDE_ZH.md',None,'method=V3_BEHAVIOR vs V3_JOINT_QT; selected_family; coarse/fine contract'),
 ('S02',MIX+'integration/METHOD_SELECTION_AND_COVERAGE.csv',None,'method=V3_BEHAVIOR/V3_JOINT_QT; evaluation_condition=manual; ALL vs LOBO'),
 ('S03',MIX+'configurations/FINE_INCREMENT_COVERAGE.csv',None,'condition=manual; method=V3_BEHAVIOR/V3_JOINT_QT'),
 ('S04','research/same_room/same_room_current_classes_v2_20261023/source_index/CURRENT_MANUAL_LABELS_LOBO.csv',BASE/'design/inputs/CURRENT_MANUAL_LABELS_LOBO.csv','method=V3_BEHAVIOR; building=B6,pRb,wc2,jh4; coarse and fine labels'),
 ('S05',QT+'CLASS_QT10_IDENTITY_SUMMARY.csv',None,'n=20; m=3,4,5,6; anchors=identical_teams'),
 ('S06',QT+'MANUAL_QT_ADOPTION_REPORT_ZH.md',None,'sections 3 and 4; identical teams and same-candidate QT comparison'),
 ('S07',QT+'GLOBAL_POLICIES_COMMON_SUMMARY.csv',None,'n=20,m=4; policy=class_QT_10,continuous_QT_10,continuous_QT_20,continuous_Q_0; P-A; quality_common_anchors=1890'),
 ('S08',QT+'FINITE_SELECTION_INCREMENT_SUMMARY.csv',None,'n=20,m=4; policy=finite_QT10; versus same-anchor finite uniform Z'),
 ('S09',POP+'code/analyze_natural_curves.py',ROOT/'work/original_recovery_20261023/recompute/population_existing_originals/code/analyze_natural_curves.py','attainments: threshold 80/90; first_hit_k,first_hit_k_ge3,sustained_from_k'),
 ('S10',POP+'code/analyze_policy_curves.py',ROOT/'work/original_recovery_20261023/recompute/population_existing_originals/code/analyze_policy_curves.py','policy_attainments: first_hit_all_k,first_hit_k_ge3,sustained_to_full_pool; posterior not stop rule'),
 ('S11',POP+'events/POLICY_PAIRED_PREFIX_EVENTS_LINKED.csv.gz',BASE/'population_stability/input_cache/events/POLICY_PAIRED_PREFIX_EVENTS_LINKED.csv.gz','formal 04C, not source_original; pool_id/base_path_id/path_id/policy/k; achieved_Q80/90 natural/priority/delta'),
 ('S12',POP+'README.md',None,'actual received packages and absent natural/policies derived-table packages'),
 ('S13','research/same_room/same_room_large_block_rebuild_20261023/population_stability/README_ZH.md',BASE/'population_stability/README_ZH.md','new R03 analysis boundary, existing exact paths; not original recovered bootstrap'),
 ('S14','research/same_room/same_room_acceptance_20261022/USES_CLOSEOUT.md',None,'section 4: accepted same-room stopping, geometry top-up and acquisition cost'),
 ('S15',STOP+'stopping_support.csv',None,'panel=whole_group; group_id,building,common_workers,paths,activity_all_new_complete'),
 ('S16',STOP+'stopping_summary.csv',None,'history_budget=single_source/minimum_majority/maximum_history; panel=whole_group; support=all_attempts; policy=source_within2_min3_geometry/fixed_7_geometry/full_common_pool; time_support separate'),
 ('S17',STOP+'source_acquisition_summary.csv',None,'history_budget,panel,policy; historical source acquisition and remaining targets separate'),
 ('S18','research/statistics/pro_return_review_20261023/population/NATURAL_RECOMPUTED.csv',None,'condition/layer/difficulty/k; image and scalar curve summary; existing not new bootstrap'),
 ('S19','research/statistics/pro_return_review_20261023/population/POLICY_RECOMPUTED.csv',None,'existing policy point summaries; do not replace R03 same-semantic time support with these old time fields'),
]

rows=[]
for sid,repo,local,keys in specs:
    p=local if local is not None else CONTEXT/repo
    if not p.exists() or p.stat().st_size==0:
        raise RuntimeError(f'Missing actual nonempty source: {p}')
    sha=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''): sha.update(block)
    nrows=None; fields=[]
    if p.name.endswith(('.csv','.csv.gz')):
        opener=gzip.open if p.name.endswith('.gz') else open
        with opener(p,'rt',encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f);fields=reader.fieldnames;nrows=sum(1 for _ in reader)
    else:
        p.read_text(encoding='utf-8-sig')
    rows.append(dict(source_id=sid,version=COMMIT if sid!='S13' else 'current_rebuild_20261023',repository_path=repo,
        repository_path_status='fixed_main' if sid!='S13' else 'proposed_new_package_path',
        actual_local_path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha.hexdigest(),rows=nrows,
        key_or_section=keys,read_status='actual_nonempty_file_read_to_EOF',
        field_count=len(fields),fields='|'.join(fields),
        reuse='main_dependency_do_not_duplicate' if sid!='S13' else 'new_analysis_already_saved_in_R03'))
out=BASE/'integration/EXISTING_METHOD_ADOPTION_SOURCES.csv'
with out.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
receipt=dict(work='This round read-only source index; not new fitting or fusion',sources=len(rows),fixed_commit=COMMIT,
    index=str(out.relative_to(ROOT)),all_actual_nonempty=True,all_read_to_EOF=True,
    formal_04C_rows=next(x['rows'] for x in rows if x['source_id']=='S11'),
    note='Expected but absent threshold/attainment derived originals are not listed as available files.')
(BASE/'integration/EXISTING_METHOD_READ_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':
    pass
