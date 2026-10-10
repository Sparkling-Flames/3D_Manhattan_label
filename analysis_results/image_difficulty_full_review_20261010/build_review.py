"""合并两条独立审查轨道，输出只读证据和用户复核表；不写回源分类。"""
import json
from collections import Counter
from pathlib import Path

OUT = Path(__file__).parent
def read(name):
    return json.loads((OUT/name).read_text(encoding='utf-8'))

def main():
    scopes = read('all_scope_evidence.json')
    external_rows = read('external_review_20261010/source_review.json')['records']
    external = {r['image']: r for r in external_rows}
    assert len(external) == len(external_rows) == 143
    visual = {r['image']:r for r in read('agent_visual/visual_review.json')}
    decisions = read('external_review_20261010/adjudication.json')['records']
    assert len(decisions) == len({d['image'] for d in decisions}) == 25
    for d in decisions:
        v = visual[d['image']]
        assert (v['image_id'], v['gt_object_id'], v['difficulty_recommendation']) == (d['image_id'], d['gt_object_id'], d['previous_recommendation'])
        v['conflict_review'] = d
        for key in ('difficulty_recommendation', 'occlusion_level', 'visible_evidence', 'uncertainty_reason', 'gt_target_confidence', 'needs_user_review'):
            v[key] = d[key]
    old = {r['image']:r for r in read('scope_evidence.json')}
    notes = {}
    for filename in ('scope_visual_notes.json','scope_extra_notes.json'):
        for category, entries in read(filename).items():
            for code, note in entries.items():
                assert code not in notes, code
                notes[code] = (category,note)
    codes = {r['image'] for r in scopes}
    assert len(codes)==259 and codes==set(visual) and set(notes)<=codes
    assert set(external) <= codes
    contact = {c:s['sheet'] for s in read('all_scope_contact_index.json') for c in s['images']}
    records=[]
    for r in scopes:
        v=visual[r['image']]
        assert r['gt_object_id']==v['gt_object_id'] and int(v['N'])==r['N'] and int(v['H'])==r['H']
        assert v['reviewed'] and '\ufffd' not in json.dumps(v,ensure_ascii=False)
        for g in r['condition_gate_groups']:
            g['fraction_lower']=g['flagged_counts']['0.3']/g['n']
            g['fraction_upper']=(g['flagged_counts']['0.3']+g['invalid'])/g['n']
        meaningful_signal=any(g['geometry_signal'] and g['gate']!='excluded' for g in r['condition_gate_groups'])
        cat,note=notes.get(r['image'],('no_major_mismatch_seen','逐图照片与全部可画底面对照中，未见明确的大范围目标差异；不认证GT正确或所有人员目标一致。'))
        if r['image'] not in notes and meaningful_signal:
            cat,note='geometry_or_reference_uncertain','同条件资格组触发几何面积筛查，但照片/叠图未能把坐标深度误差与范围差异分开；留待人工，不认定多数选了另一空间。'
        if r['n']<3 and cat=='no_major_mismatch_seen':
            cat,note='insufficient_records','已逐图查看；作答少于3份，不判断“大量人员”或稳定人群范围差异。'
        rec={k:r[k] for k in ('image','image_id','legacy137','in_current178','n','valid_geometry','invalid_geometry','gt_object_id','original_gt_object_id','N','H','structure_class','working_class','scene','reference_flags','condition_gate_groups')}
        review = external.get(r['image'])
        if review is not None:
            assert (review['image_id'], review['gt_object_id']) == (r['image_id'], r['gt_object_id'])
        rec['external_review'] = review
        rec.update(scope_category=cat,scope_note=note,scope_reviewed=True,scope_review_depth='photo + aggregate individual footprints screening; not per-record semantic adjudication',scope_sheet=contact[r['image']],card='all_cards/'+r['image']+'.jpg',
            visual=v,changed_grade=v['difficulty_recommendation'] in ('简单','中等','困难') and r['working_class'] in ('简单','中等','困难') and v['difficulty_recommendation']!=r['working_class'],
            meaningful_geometry_signal=meaningful_signal,main_manual_panel=({k:old[r['image']][k] for k in ('n','valid_geometry','invalid_geometry','flagged_counts','majority_geometry_signal')} if r['image'] in old else None),
            records=[{k:o[k] for k in ('record_id','object_id','worker_id','condition','gate','geometry_status','selected_gt_metrics','original_gt_metrics')} for o in r['observations']],
            user_review_status='not_started',classification_applied=False)
        records.append(rec)
    assert sum(r['n'] for r in records)==3152
    summary=dict(images=len(records),records=sum(r['n'] for r in records),legacy137=sum(r['legacy137'] for r in records),current178=sum(r['in_current178'] for r in records),
        invalid_records=sum(r['invalid_geometry'] for r in records),visual_counts=dict(Counter(r['visual']['difficulty_recommendation'] for r in records)),changed_grade=sum(r['changed_grade'] for r in records),scope_counts=dict(Counter(r['scope_category'] for r in records)),
        geometry_signal_any_gate=sum(r['majority_geometry_signal'] for r in scopes),geometry_signal_nonexcluded=sum(r['meaningful_geometry_signal'] for r in records),
        sensitivity_nonexcluded={str(t):sum(any(g['gate']!='excluded' and g['n']>=3 and 2*g['flagged_counts'][str(t)]>=g['n'] for g in r['condition_gate_groups']) for r in records) for t in (.2,.3,.4)})
    (OUT/'review_data.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    html=(OUT/'review_template.html').read_text(encoding='utf-8').replace('__REVIEW_DATA__',json.dumps(records,ensure_ascii=False).replace('</','<\\/'))
    (OUT/'review.html').write_text(html,encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__': main()
