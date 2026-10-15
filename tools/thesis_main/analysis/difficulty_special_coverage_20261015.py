"""投影已有特殊场景证据与覆盖；不新增难度、可标性或人员能力裁决。"""
import csv
import io
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from ..data_prep.consolidate_research_input import load_current_bundle

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/difficulty/difficulty_special_coverage_20261015'


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8-sig'))


def rows(path):
    with (ROOT / path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def save(name, data):
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def markability(d):
    if d['oos_subtype'] == 'nonorthogonal_annotatable':
        return 'conditional_nonorthogonal_annotatable'
    if d['doorway_status'] == 'annotatable':
        return 'recorded_doorway_annotatable'
    return 'unknown_not_inferred_from_difficulty'


def main():
    bundle = load_current_bundle()
    difficulty = read('analysis_results/difficulty_scope_preferred_20261011/current_259.json')
    live = {r['image_id']: r for r in bundle['research']['images']}
    joint = rows('research/difficulty/difficulty_target_integration_20261015/quality_bindings_1145.csv')
    history = rows('analysis_results/worker_four_block_exploration_20260910_v1/scope_responses.csv')
    bound = rows('research/workers/worker_classification_progress_20261014/source_inventory.csv')
    fusion = read('research/fusion/wall_consensus_population_20261014/input_snapshot.json')
    fusion_ids = {r['image_id'] for r in fusion['images']}
    with zipfile.ZipFile(ROOT / 'research/quality/quality_joint_closeout_review_20261015/pro_closeout_delta.zip') as z:
        assert bundle['data'] == json.loads(z.read('source/historical_current_formal_loader_data.json')), '质量快照已改变，须重新核验后绑定'
        ledger = list(csv.DictReader(io.StringIO(z.read('results/ALL_3152_LEDGER.csv').decode('utf-8-sig'))))
    grouped = []
    for source in (joint, history, ledger, bound):
        group = defaultdict(list)
        for r in source:
            group[r['image_id']].append(r)
        grouped.append(group)
    q, h, l, bindings = grouped
    assert len(difficulty['records']) == len(live) == 259
    assert len(ledger) == len({r['object_id'] for r in ledger}) == 3152
    assert len(joint) == 1145
    output, evidence, targets = [], [], []
    for d in difficulty['records']:
        iid = d['image_id']; current = live[iid]
        oos = d['scene'] in ('oos', 'oos_and_doorway')
        doorway = d['doorway_status'] in ('difficult', 'annotatable')
        layer = 'overlap' if oos and doorway else 'oos' if oos else 'doorway' if doorway else 'oos_pending' if d['scene'] == 'oos_pending' else 'other'
        evidence.append({'image_id': iid, 'image_code': d['image'],
            'difficulty_evidence': {k: d[k] for k in ('scene', 'oos_subtype', 'doorway_status', 'evidence', 'question', 'applicability_note', 'previous_user_review', 'reference_flags')},
            'live_evidence': {k: current[k] for k in ('oos_status', 'doorway_status', 'stable_nonorthogonal', 'room_spatial_classification', 'room_classification_sources', 'main_visual_space', 'expected_annotation_extent', 'image_comment', 'gt_evidence', 'quality_gate_counts', 'consensus_gate_counts')},
            'historical_final_aliases': sorted({r['final_scope_alias'] for r in h[iid]}),
            'historical_later_holds': sorted({r['later_hold'] for r in h[iid] if r['later_hold']})})
        output.append({'image_id': iid, 'image_code': d['image'], 'difficulty_version': difficulty.get('version', d['target_version']),
            'difficulty_class': d['current_class'], 'conditional_difficulty': d['conditional_difficulty'],
            'target_id': d['selected']['target_id'], 'top_boundary_pending': d['top_boundary_pending'],
            'special_layer': layer, 'difficulty_scene': d['scene'], 'difficulty_oos_subtype': d['oos_subtype'],
            'live_oos_status': current['oos_status'], 'doorway_status': current['doorway_status'],
            'oos_status_discrepancy': oos != (current['oos_status'] == 'confirmed'),
            'markability_from_explicit_label': markability(d),
            'reference_ids_available_not_certified': encoded(current['references']),
            'all_answer_count': len(l[iid]), 'ledger_score_status_counts': encoded(Counter(r['score_status'] for r in l[iid])),
            'joint_quality_count': len(q[iid]), 'joint_use_counts': encoded(Counter(r['use_panel'] for r in q[iid])),
            'joint_scope_or_reference_hold_count': sum(r['use_panel'] == 'hold_scope_or_reference' for r in q[iid]),
            'historical_S_count': len(h[iid]),
            'historical_S_bound_count': sum(r['scope_historical_bound'] == 'True' for r in bindings[iid]),
            'historical_S_final_aliases': encoded(sorted({r['final_scope_alias'] for r in h[iid]})),
            'fusion_12_panel_covered': iid in fusion_ids,
            'formal_eligibility_granted_by_this_audit': False})
        for c in d['candidates']:
            targets.append({'image_id': iid, 'image_code': d['image'], 'target_id': c['target_id'],
                'role': c['role'], 'selected': c['target_id'] == d['selected']['target_id'],
                'reference_completeness': 'floor_only_top_pending' if c['role'] == 'confirmed_scope' else 'gt_geometry_available_not_semantically_certified',
                'reference_flags': encoded(d['reference_flags']), 'special_layer': layer})
    special = [r for r in output if r['special_layer'] != 'other']
    summary = {'image_count': len(output), 'special_layers': dict(Counter(r['special_layer'] for r in special)),
        'special_joint_records': sum(r['joint_quality_count'] for r in special),
        'special_fusion_12_images': sum(r['fusion_12_panel_covered'] for r in special),
        'oos_status_discrepancies': [r['image_code'] for r in output if r['oos_status_discrepancy']],
        'historical_S_records': sum(r['historical_S_count'] for r in output),
        'historical_S_bound_records': sum(r['historical_S_bound_count'] for r in output),
        'formal_eligibility_granted': False, 'existing_difficulty_modified': False}
    assert summary['historical_S_records'] == summary['historical_S_bound_records'] == 1013
    assert summary['special_layers'] == {'doorway': 17, 'oos': 23, 'overlap': 2, 'oos_pending': 1}
    OUT.mkdir(exist_ok=True)
    save('image_coverage_259.csv', output)
    save('special_coverage_43.csv', special)
    save('reference_targets.csv', targets)
    # 原历史答题与当前对象绑定表已存在，复用路径，不重新构造人员身份或评分。
    for name, value in [('evidence.json', evidence), ('CHECKS.json', summary)]:
        (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(encoded(summary))


if __name__ == '__main__':
    main()
