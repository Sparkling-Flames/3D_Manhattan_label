"""重建固定候选范围下的259图粗分类；视觉编码为显式审查输入，不是自动识别。"""
import csv
import json
from collections import Counter
from pathlib import Path

from tools.thesis_main.analysis.scope_difficulty_review_20261011 import ROOT, PRIOR, floor_features, read, write

OUT = ROOT / 'analysis_results/difficulty_scope_preferred_20261011'
VERSION = 'scope_preferred_difficulty_20261011_v2'


def choose_target(candidates):
    assert len(candidates) in (1, 2)
    assert candidates[0]['role'] == 'selected_gt'
    if len(candidates) == 1:
        return candidates[0]
    old, new = candidates
    assert new['role'] == 'confirmed_scope'
    if new['features']['H'] == 0:
        return new
    if old['features']['H'] == 0:
        return old
    return new


def classify(n, burden, special):
    assert burden in ('low', 'moderate', 'high', 'undetermined')
    if special:
        return '单列'
    if burden == 'undetermined':
        return '待复核'
    if burden == 'high':
        return '困难'
    if burden == 'low' and n <= 6:
        return '简单'
    return '中等'


def build():
    audit = read(OUT / 'geometry_audit.json')['records']
    notes = read(OUT / 'visual_decisions.json')['records']
    assert len(audit) == len(notes) == 259
    notes = {r['image']: r for r in notes}
    assert len(notes) == 259 and set(notes) == {r['image'] for r in audit}
    base = {r['image']: r for r in read(PRIOR / 'review_data.json')}
    previous = {r['image']: r for r in read(ROOT / 'analysis_results/scope_difficulty_audit_20261011/current_259.json')['records']}
    user = {r['image']: r for r in read(PRIOR / 'user_review_20261010/source_review.json')['records']}
    result = []
    for r in audit:
        d, old = notes[r['image']], base[r['image']]
        assert d['image_id'] == r['image_id'] == old['image_id']
        for c in r['candidates']:
            assert floor_features(c['floor']) == c['features'], r['image']
        selected = choose_target(r['candidates'])
        assert selected == r['selected'], 'visual evidence must bind the selected target'
        assert d['target_version'] == selected['target_id']
        f = selected['features']
        special = r['old_class'] == '单列'
        grade = classify(f['N_turn'], d['inference_burden'], special)
        conditional = classify(f['N_turn'], d['inference_burden'], False)
        assert d['reviewed'] and d['evidence']
        assert (conditional == '待复核') == bool(d['question'])
        result.append(dict(image=r['image'], image_id=r['image_id'], current_class=grade,
            conditional_difficulty=conditional, target_version=selected['target_id'],
            selected=selected, candidates=r['candidates'], N_floor=f['N_floor'], N_turn=f['N_turn'], H=f['H'],
            scene=r['scene'], oos_subtype=old['visual']['oos_subtype'],
            doorway_status=old['visual']['doorway_status'],
            previous_visual_class=r['old_class'], previous_scope_class=previous[r['image']]['current_class'],
            external_review=old['external_review'], previous_user_review=user.get(r['image']),
            old_visual_evidence=old['visual']['visible_evidence'],
            old_visual_question=old['visual']['uncertainty_reason'],
            previous_reference_issue=old['visual']['reference_issue'],
            previous_scope_note=old.get('scope_note'), reference_flags=old.get('reference_flags'),
            selection_reason=r['selection_reason'], photo=r['photo'],
            card='cards/'+r['image']+'.jpg', old_card='../image_difficulty_full_review_20261010/'+old['card'],
            scope_comparison=('../scope_difficulty_audit_20261011/cards/'+r['image']+'.jpg') if len(r['candidates'])==2 else None,
            top_boundary_pending=True if selected['role']=='confirmed_scope' else None,
            classification_basis='geometry_and_codex_photo_review_not_blind', **{k:v for k,v in d.items() if k not in ('image','image_id','target_version')}))
    assert len({r['image_id'] for r in result}) == 259
    return result


def main():
    rows = build()
    counts = dict(Counter(r['current_class'] for r in rows))
    summary = dict(version=VERSION, reviewed=259, counts=counts,
        accepted_alternatives=sum(len(r['candidates'])==2 for r in rows),
        changed_from_previous_scope=sum(r['current_class']!=r['previous_scope_class'] for r in rows),
        changed_from_visual_v2=sum(r['current_class']!=r['previous_visual_class'] for r in rows),
        oos=sum('oos' in r['scene'] for r in rows), doorway=sum('doorway' in r['scene'] for r in rows))
    write(OUT / 'current_259.json', dict(version=VERSION, summary=summary, records=rows))
    write(OUT / 'pending_review.json', dict(version=VERSION, records=[r for r in rows if r['current_class']=='待复核']))
    fields=['image','image_id','current_class','conditional_difficulty','target_version','N_floor','N_turn','H',
            'inference_burden','H_interpretation','scene','oos_subtype','doorway_status','applicability_note',
            'previous_visual_class','previous_scope_class','top_boundary_pending','evidence','question','classification_basis']
    with (OUT / 'current_259.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    payload=json.dumps(dict(version=VERSION,summary=summary,records=rows),ensure_ascii=False).replace('</','<\\/')
    (OUT/'review.html').write_bytes((OUT/'review_template.html').read_text(encoding='utf-8').replace('__DATA__',payload).encode('utf-8'))
    write(PRIOR/'CURRENT.json',dict(version=VERSION,table='../difficulty_scope_preferred_20261011/current_259.csv',
        details='../difficulty_scope_preferred_20261011/current_259.json',review='../difficulty_scope_preferred_20261011/review.html',
        status='exploratory_target_conditioned; photo coding is not automatic; GT and eligibility unchanged'))
    print(json.dumps(summary,ensure_ascii=False))


if __name__ == '__main__':
    main()
