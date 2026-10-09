"""稳定原点身份、版本区分和输入不变性的关键边界。"""
import copy,csv,json
import pytest
from tools.thesis_main.analysis.build_point_edit_review_20261009 import OUT,RECEIVED,RESCREEN,QUEUE_RESOLUTION,normalize
def fixture():
 objects=json.loads((RECEIVED/'source_extracts/current_109_records.json').read_text(encoding='utf-8'))['objects']
 o=next(o for o in objects if o['id']=='R00541')
 r=next(r for r in json.loads((RECEIVED/'review_109_identity_and_actionability.json').read_text(encoding='utf-8')) if r['record_id']=='R00541')
 h=next(h for h in json.loads((RECEIVED/'history/historical_four_deletions_preview.json').read_text(encoding='utf-8'))['cases'] if h['record_id']=='R00541')
 return o,r,h
def test_historical_deletion_preserves_original_labels_and_missing_current():
 o,r,h=fixture();before=copy.deepcopy(o);c=normalize(o,r,h,{'sha256':'photo'})
 assert [p['label'] for p in c['versions']['raw']['points']]==[f'p{i}' for i in range(1,10)]
 assert [p['label'] for p in c['versions']['historical']['points']]==['p1','p2','p3','p4','p6','p7','p8','p9']
 assert c['versions']['historical']['pairs']==[] and not c['versions']['current']['available']
 assert not o['independent_vote_eligible'] and o==before
def test_same_short_name_never_authorizes_other_canonical_or_annotation():
 o,r,h=fixture();bad=copy.deepcopy(h);bad['canonical_object_id']='different-answer'
 with pytest.raises(AssertionError):normalize(o,r,bad,{})
 bad=copy.deepcopy(h);bad['source']['annotation']+=1
 with pytest.raises(AssertionError):normalize(o,r,bad,{})
def test_current_missing_point_identity_is_not_raw_fallback():
 o,r,h=fixture();o=copy.deepcopy(o);o['preprocessed_points']=[[1,2],[3,4]];o['original_export_indices']=[]
 c=normalize(o,r,None,{})
 assert not c['versions']['current']['available'] and len(c['versions']['raw']['points'])==9
 assert any('身份' in s for s in c['warnings'])
def test_real_queue_109_and_proposals_remain_pending():
 js=(OUT/'data.js').read_text(encoding='utf-8')
 d=json.loads(js.removeprefix('window.POINT_REVIEW_DATA=').split(';\nwindow.STUDIO_IMAGES=',1)[0])
 assert len(d['cases'])==109 and len({c['record_id'] for c in d['cases']})==109
 assert len({c['canonical_object_id'] for c in d['cases']})==109 and len({c['image_id'] for c in d['cases']})==71
 assert sum(len(c['proposed_deletions']) for c in d['cases'])==33
 assert all(c['reviewer']['user_confirmation_of_reviewer_patch']=='not established' for c in d['cases'])
 assert d['categories']['需补点']==39 and d['categories']['需删点']==37
 assert all(c['local_coordinate_parity'] for c in d['cases'])
 assert all(any('冻结研究输入' in w for w in c['warnings']) for c in d['cases'] if not c['versions']['current']['available'])
 with RESCREEN.open(encoding='utf-8-sig',newline='') as f:screen=list(csv.DictReader(f))
 selected=[r for r in screen if r['保留在本次待核验清单'].startswith('是')]
 assert len(screen)==109 and len(selected)==25
 resolved=json.loads(QUEUE_RESOLUTION.read_text(encoding='utf-8'))['records']
 assert resolved==d['review_queue']['resolved_items'] and len(resolved)==11
 assert {k for k,v in resolved.items() if v['outcome']=='existing_invalid'}=={'R01210','R02183','R03177','R01812','R02016'}
 assert {k for k,v in resolved.items() if v['outcome']=='retained_oos_uncalculable'}=={'R00089','R01732','R02219','R02393','R00773'}
 assert {k for k,v in resolved.items() if v['outcome']=='oos_no_effective_points'}=={'R01283'}
 assert [r['record_id'] for r in selected if r['record_id'] not in resolved]==[r['record_id'] for r in d['review_queue']['items']]
 assert d['review_queue']['selected_records']==14 and d['review_queue']['selected_images']==8 and d['review_queue']['excluded_records']==84
 local={r['object_id']:r['worker_id'] for r in json.loads((OUT.parent/'research_input_20260929/preprocessed_source.json').read_text(encoding='utf-8'))['objects'] if 'worker_id' in r}
 from collections import Counter
 assert Counter((r['worker'],local[r['canonical_object_id']]) for r in screen if r['保留在本次待核验清单']=='否')=={('P013','W019'):57,('P016','W026'):27}
 assert not any(r['图片OOS判定']=='是' for r in screen if r['record_id'] in {x['record_id'] for x in d['review_queue']['items']})

def test_received_return_audit_keeps_archive_edits_separate():
 audit=json.loads((OUT/'received_return_audit_20261010.json').read_text(encoding='utf-8'))
 rows=audit['records'];summary=audit['summary']
 assert len(rows)==18 and summary['current_queue_records']==14 and summary['archive_only_records']==4
 assert summary['current_queue_full_pair_coverage']==14 and summary['current_queue_changed_adjacency']==3
 assert summary['prior_exact_object_order_found']==0 and summary['current_queue_prior_same_image_worker']==11
 assert {r['record_id'] for r in rows if r['review_scope']=='archive_only'}=={'R00003','R00013','R00089','R01210'}
 assert all(r['ring_confirmed'] is False and r['apply_to_formal'] is False for r in rows)

def test_109_scope_csv_distinguishes_records_from_images():
 with (OUT/'109份审核范围与返回核对_20261010.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
 assert len(rows)==len({r['record_id'] for r in rows})==109
 assert {s:sum(r['final_scope']==s for r in rows) for s in {'excluded_worker','resolved_outside_queue','current_review_14'}}=={'excluded_worker':84,'resolved_outside_queue':11,'current_review_14':14}
 selected=[r for r in rows if r['final_scope']=='current_review_14']
 assert len({r['image_id'] for r in selected})==8 and all(r['return_status']=='completed' for r in selected)
 assert sum(r['image_oos_confirmed']=='true' and int(r['original_point_count'])<8 and r['final_scope']=='excluded_worker' for r in rows)==11
