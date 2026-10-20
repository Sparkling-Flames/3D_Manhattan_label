#!/usr/bin/env python3
"""Join existing, frozen usage records by object_id; no geometry or eligibility edits.

The two CSVs count actual records, people, images and teams in each analysis
domain. The broader non-OOS behavior inventory is the denominator. A and B
training domains, candidate voting eligibility and realized fusion usage stay
separate. Counts for extension experiments are independently named.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
OUT = HERE / 'evidence'
CLUSTERS = ROOT / 'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/clusters'
INPUTS = {
    'audit_records': ROOT / 'research/statistics/v2_evidence_audit_20261019/records.json.gz',
    'behavior_expression': ROOT / 'research/workers/personnel_marking_patterns_20261020/record_expression.csv',
    'A_formal_records': CLUSTERS / 'records_geometry.csv.gz',
    'A_labels': HERE / 'route_a/worker_labels.csv',
    'B_labels': HERE / 'route_b/final_labels.csv',
    'B_main_selected_pools': HERE / 'fusion/SELECTED_POOLS.csv',
    'B_main_teams': HERE / 'fusion/TEAMS.json.gz',
    'B_main_requests': HERE / 'fusion/REQUESTS.json.gz',
    'B_nested_teams': HERE / 'fusion/NESTED_TEAMS.json.gz',
    'A2_specific_teams': HERE / 'fusion/a2_specific/TEAMS.json.gz',
    'semi_position_teams': HERE / 'fusion/semi_position/TEAMS.json.gz',
}


def read_json(path):
    with gzip.open(path, 'rt', encoding='utf8') if str(path).endswith('.gz') else open(path, encoding='utf8') as f:
        return json.load(f)


def read_csv(path):
    with gzip.open(path, 'rt', encoding='utf8') if str(path).endswith('.gz') else open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def truth(x):
    return x is True or str(x).lower() in {'true', '1', '1.0'}


def size_support(rows):
    return dict(n_records=len(rows), n_workers=len({r['worker_id'] for r in rows}),
                n_images=len({r['image_id'] for r in rows}), n_buildings=len({r['building_id'] for r in rows}))


def team_inventory(path):
    teams = read_json(path)
    clean = {}
    for key, t in teams.items():
        clean[key] = {k: t[k] for k in ['pool_id', 'image_id', 'condition', 'building', 'layer', 'member_workers', 'member_object_ids', 'k']}
        assert len(t['member_workers']) == len(t['member_object_ids']) == t['k'], key
        assert len(set(t['member_workers'])) == t['k'], key
    del teams
    return clean


def write_csv(path, rows):
    with open(path, 'w', encoding='utf8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    OUT.mkdir(exist_ok=True)
    expression = {r['object_id']: r for r in read_csv(INPUTS['behavior_expression'])}
    formal = {r['object_id']: r for r in read_csv(INPUTS['A_formal_records'])}
    b_labels = read_csv(INPUTS['B_labels'])
    b_assigned = {(r['condition'], r['worker_id']) for r in b_labels if r['label_status'] == 'assigned'}
    a_labels = read_csv(INPUTS['A_labels'])
    a_assigned = {(r['condition'], r['worker_id']) for r in a_labels
                  if r['stage'] == 'all_data_descriptive' and r['method'] == 'A2_samecount_source_residual'
                  and r['class_id'] not in {'', 'unassigned', 'unknown'}}
    full = read_json(INPUTS['audit_records'])['records']
    assert len({r['object_id'] for r in full}) == len(full)
    n_full, n_oos = len(full), sum(truth(r['is_oos']) for r in full)
    records = []
    for r in full:
        if truth(r['is_oos']):
            continue
        oid = r['object_id']
        e = expression[oid]
        for key in ['worker_id', 'image_id', 'image_code', 'building_id', 'condition']:
            assert r[key] == e[key], (oid, key)
        reasons = set(r.get('quality_exclusion_reasons') or [])
        pc = truth(e['personal_comparison'])
        bc = pc and float(e.get('peer_n') or 0) >= 3 and e['layer'] == 'ordinary'
        ac = oid in formal and formal[oid]['layer'].startswith('ordinary_')
        qual = truth(r['quality_usable'])
        vote = truth(r['independent_vote_eligible'])
        attr = r.get('exclusion_attribution') or {}
        row = {key: r[key] for key in ['object_id', 'worker_id', 'image_id', 'image_code', 'building_id', 'condition', 'origin']}
        row.update(layer=e['layer'], quality_use=r['quality_use'],
                   formal_pool_id=formal[oid]['pool_id'] if oid in formal else '',
                   formal_layer=formal[oid]['layer'] if oid in formal else '',
                   n_non_oos_behavior=1,
                   n_personal_comparison=int(pc),
                   n_B_candidate_observations=int(bc),
                   n_B_fit_observations=int(bc and (r['condition'], r['worker_id']) in b_assigned),
                   n_A_formal_original_answers=int(oid in formal),
                   n_A_ordinary_candidate_observations=int(ac),
                   n_A_fit_observations=int(ac and (r['condition'], r['worker_id']) in a_assigned),
                   n_quality_usable=int(qual),
                   n_independent_vote_eligible=int(vote),
                   n_pool_analysis_eligible=int(truth(r['pool_analysis_eligible'])),
                   n_quality_and_vote_eligible=int(qual and vote),
                   n_doorway=int(truth(r['is_doorway'])),
                   n_gt_error_quality_blocked=int(not qual and bool(reasons & {'existing_gt_error', 'historical_gt_substantive_error', 'current_gt_error'})),
                   n_reference_quality_hold=int(any('hold_reference_quality' in x for x in reasons)),
                   n_reference_not_full=int(not truth(r['reference_full_available'])),
                   n_cleaning_historical_not_accepted=int(r['cleaning_disposition'] == 'historical_not_accepted'),
                   n_cleaning_excluded_by_review=int(r['cleaning_disposition'] == 'excluded_by_review'),
                   n_cleaning_retained_pending=int(r['cleaning_disposition'] == 'retained_pending'),
                   n_historical_worker_exclusion=int(truth(attr.get('historical_worker_exclusion', False))))
        records.append(row)
    del full
    assert {r['object_id'] for r in records} == set(expression), 'Non-OOS behavior inventory mismatch'
    assert set(formal) <= set(expression)
    quality_ids = {r['object_id'] for r in records if r['n_quality_usable']}
    assert set(formal) == quality_ids, 'Current quality/formal match is a receipt check, not a rule redefining qualification'
    by_id = {r['object_id']: r for r in records}
    selected = read_csv(INPUTS['B_main_selected_pools'])
    selected_pools = {r['pool_id'] for r in selected}
    assert len(selected) == len(selected_pools)
    experiments = {}
    for prefix in ['B_main', 'B_nested', 'A2_specific', 'semi_position']:
        path = INPUTS[prefix + '_teams']
        if not path.exists():
            continue
        teams = team_inventory(path)
        obj_teams, obj_pools = defaultdict(set), defaultdict(set)
        for key, t in teams.items():
            for worker, oid in zip(t['member_workers'], t['member_object_ids']):
                r = by_id[oid]
                assert r['worker_id'] == worker and r['formal_pool_id'] == t['pool_id'], (prefix, key, oid)
                assert r['n_quality_usable'] and r['n_independent_vote_eligible'], (prefix, key, oid)
                obj_teams[oid].add(key)
                obj_pools[oid].add(t['pool_id'])
        experiments[prefix] = dict(teams=teams, obj_teams=obj_teams, obj_pools=obj_pools,
                                   pools={t['pool_id'] for t in teams.values()})
    main_ex = experiments['B_main']
    assert main_ex['pools'] <= selected_pools
    events = read_json(INPUTS['B_main_requests'])['events']
    object_events = defaultdict(set)
    pool_worker_object = {(r['formal_pool_id'], r['worker_id']): r['object_id'] for r in records if r['formal_pool_id']}
    for event in events:
        for w in set(event['A_workers']) | set(event['B_workers']) | set(event['C_workers']):
            oid = pool_worker_object[(event['pool_id'], w)]
            object_events[oid].add(event['event_id'])
    count_keys = [k for k in records[0] if k.startswith('n_')]

    def summarize(rows):
        d = {k: sum(r[k] for r in rows) for k in count_keys}
        objects = {r['object_id'] for r in rows}
        d.update(origin_keys='|'.join(sorted({r['origin'] for r in rows})),
                 quality_use_keys='|'.join(sorted({r['quality_use'] for r in rows})),
                 A_formal_layer_keys='|'.join(sorted({r['formal_layer'] for r in rows if r['formal_layer']})),
                 n_B_main_selected_pools=len({r['formal_pool_id'] for r in rows if r['formal_pool_id'] in selected_pools}),
                 n_B_main_selected_pool_available_records=sum(r['formal_pool_id'] in selected_pools for r in rows),
                 n_B_main_actual_pool_available_records=sum(r['formal_pool_id'] in main_ex['pools'] for r in rows),
                 n_B_main_swap_events=len(set().union(*(object_events[o] for o in objects))))
        for prefix, ex in experiments.items():
            d['n_' + prefix + '_actual_pools'] = len(set().union(*(ex['obj_pools'][o] for o in objects)))
            d['n_' + prefix + '_actual_used_records'] = sum(bool(ex['obj_teams'][o]) for o in objects)
            d['n_' + prefix + '_actual_teams'] = len(set().union(*(ex['obj_teams'][o] for o in objects)))
        return d

    image_groups, worker_groups = defaultdict(list), defaultdict(list)
    for r in records:
        image_groups[tuple(r[k] for k in ['image_id', 'image_code', 'building_id', 'condition', 'layer'])].append(r)
        worker_groups[tuple(r[k] for k in ['worker_id', 'condition', 'layer'])].append(r)
    image_rows, worker_rows = [], []
    for keys, rows in sorted(image_groups.items()):
        d = dict(zip(['image_id', 'image_code', 'building_id', 'condition', 'layer'], keys))
        d.update(n_workers=len({r['worker_id'] for r in rows}), **summarize(rows))
        image_rows.append(d)
    for keys, rows in sorted(worker_groups.items()):
        d = dict(zip(['worker_id', 'condition', 'layer'], keys))
        d.update(n_images=len({r['image_id'] for r in rows}), n_buildings=len({r['building_id'] for r in rows}), **summarize(rows))
        worker_rows.append(d)
    write_csv(OUT / 'inventory_usage_by_image.csv', image_rows)
    write_csv(OUT / 'inventory_usage_by_worker.csv', worker_rows)

    all_totals = summarize(records)
    assert sum(r['n_non_oos_behavior'] for r in image_rows) == sum(r['n_non_oos_behavior'] for r in worker_rows) == len(records)
    assert sum(r['n_B_main_actual_teams'] for r in image_rows) == len(main_ex['teams'])
    layers = []
    for condition, layer in sorted({(r['condition'], r['layer']) for r in records}):
        rows = [r for r in records if (r['condition'], r['layer']) == (condition, layer)]
        layers.append(dict(condition=condition, layer=layer, **size_support(rows), **summarize(rows)))
    formal_layers = []
    for layer in sorted({r['layer'] for r in formal.values()}):
        rows = [by_id[o] for o, r in formal.items() if r['layer'] == layer]
        formal_layers.append(dict(formal_layer=layer, **size_support(rows), n_pools=len({r['formal_pool_id'] for r in rows})))
    training = []
    for condition in ['manual', 'semi']:
        for flag in ['n_B_candidate_observations', 'n_B_fit_observations', 'n_A_ordinary_candidate_observations', 'n_A_fit_observations']:
            training.append(dict(condition=condition, domain=flag, **size_support([r for r in records if r['condition'] == condition and r[flag]])))
    fusion_receipts = {}
    for prefix, ex in experiments.items():
        ts = list(ex['teams'].values())
        layers_f = []
        for layer in sorted({t['layer'] for t in ts}):
            subset = [t for t in ts if t['layer'] == layer]
            layers_f.append(dict(layer=layer, n_teams=len(subset), n_pools=len({t['pool_id'] for t in subset}), n_images=len({t['image_id'] for t in subset}), n_buildings=len({t['building'] for t in subset}), n_workers=len({w for t in subset for w in t['member_workers']})))
        fusion_receipts[prefix] = dict(n_teams=len(ts), n_actual_pools=len(ex['pools']),
                                      n_images=len({t['image_id'] for t in ts}), n_buildings=len({t['building'] for t in ts}),
                                      n_workers=len({w for t in ts for w in t['member_workers']}),
                                      n_unique_used_records=len({o for t in ts for o in t['member_object_ids']}),
                                      team_size_counts=dict(sorted(Counter(t['k'] for t in ts).items())),
                                      by_formal_layer=layers_f)
    fusion_receipts['B_main'].update(n_selected_pools=len(selected_pools), n_swap_events=len(events),
                                     n_selected_but_no_realized_team_pools=len(selected_pools - main_ex['pools']))
    definitions = {
        'row_keys': {'by_image': 'image_id × condition × behavioral layer; image_code/building_id are identifiers', 'by_worker': 'worker_id × condition × behavioral layer'},
        'layer': 'record_expression behavioral inventory layer ordinary/doorway. Existing fusion special_* pools belong to ordinary behavior and remain identifiable in A_formal_layer_keys and by_formal_layer receipt.',
        'n_non_oos_behavior': 'All audited records with is_oos=false, exactly joined to record_expression by object_id; no new eligibility filtering.',
        'n_personal_comparison': 'Existing record_expression.personal_comparison=true; includes ordinary and doorway behavior.',
        'n_B_candidate_observations': 'personal_comparison & peer_n>=3 & layer=ordinary, separately by condition; candidate worker features before support threshold.',
        'n_B_fit_observations': 'B candidate observations whose condition-specific person has an assigned final descriptive label (>=12 images and >=4 buildings). These are all-data fit counts; each LOBO training count varies after excluding the target building.',
        'n_A_formal_original_answers': 'Object IDs actually present in frozen records_geometry/CLUSTER_API, all formal layers. This is not the full behavior inventory.',
        'n_A_ordinary_candidate_observations': 'Frozen original answers in ordinary_manual/ordinary_semi, before person support threshold.',
        'n_A_fit_observations': 'A ordinary observations of persons with assigned all-data A2 labels (>=6 images and >=3 buildings); LOBO training excludes the target building.',
        'n_quality_usable': 'Audited quality_usable flag, including explicit doorway and special-conditional qualification; never restored by behavior analysis.',
        'n_independent_vote_eligible': 'Audited independent_vote_eligible flag alone; it is not sufficient for formal quality/fusion admission.',
        'n_pool_analysis_eligible': 'Audited pool_analysis_eligible flag alone; existing additional reference/quality conditions remain applicable.',
        'n_quality_and_vote_eligible': 'Both audited quality_usable and independent_vote_eligible.',
        'n_doorway': 'Audited is_doorway=true, kept separate from ordinary behavior.',
        'n_gt_error_quality_blocked': 'quality_usable=false with an explicit existing_gt_error, historical_gt_substantive_error or current_gt_error exclusion reason; genuine detail omission alone does not trigger this count.',
        'n_reference_quality_hold': 'Any existing quality_exclusion_reason contains hold_reference_quality; potentially overlaps GT-error counts and is not a synonym for explicit GT error.',
        'n_reference_not_full': 'Audited reference_full_available=false.',
        'n_cleaning_historical_not_accepted': 'cleaning_disposition=historical_not_accepted; record-level inherited nonacceptance, not automatically person-level exclusion.',
        'n_cleaning_excluded_by_review': 'cleaning_disposition=excluded_by_review.',
        'n_cleaning_retained_pending': 'cleaning_disposition=retained_pending.',
        'n_historical_worker_exclusion': 'Existing exclusion_attribution.historical_worker_exclusion=true, never a newly inferred worker status.',
        'n_B_main_selected_pools': 'Distinct selected formal pool IDs represented among the row group\'s formally available records; by-worker count is opportunity availability, before realized team membership.',
        'n_B_main_selected_pool_available_records': 'Original formal records in the 105 selected pools, whether or not the person is used in a feasible team.',
        'n_B_main_actual_pool_available_records': 'Original formal records in the 94 realized main pools, including available persons not selected into any team.',
        'n_B_main_swap_events': 'Distinct realized ABC event IDs containing at least one original record in this row group; by-worker count is event participation.',
        'n_*_actual_pools': 'Distinct pools in which at least one record in the row group actually appears in that named experiment\'s saved teams.',
        'n_*_actual_used_records': 'Unique object IDs from this row group actually appearing in that named experiment\'s saved teams.',
        'n_*_actual_teams': 'Distinct saved team IDs containing at least one record in this row group. Image rows sum to experiment total; worker rows sum to memberships, not teams.',
        'extension_prefixes': 'B_main=3828-team main experiment; B_nested, A2_specific, semi_position are independent completed files, never added to the B_main totals.',
    }
    receipt = dict(schema='personnel_taxonomy_inventory_usage_v1',
                   input_files={name: {'path': str(p.relative_to(ROOT)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for name, p in INPUTS.items() if p.exists()},
                   all_audited_records=n_full, excluded_oos_records=n_oos,
                   non_oos_inventory=size_support(records), by_image_rows=len(image_rows), by_worker_rows=len(worker_rows),
                   totals=all_totals, by_condition_behavior_layer=layers, A_formal_original_layers=formal_layers,
                   all_data_training_inventory=training, fusion_experiments_separate=fusion_receipts,
                   field_definitions=definitions,
                   coverage_notes_zh=[
                       '全部非OOS行为库存与质量可用原答库存分开，未把7302份冻结分簇当作9217份行为全库存。',
                       'B候选观察与实际拟合观察并列：Manual的W022有2条可比观察但不满足人员支持门槛；W019/W026无可比历史。',
                       'GT暂停、未获正式评分资格及历史筛除记录可以保留行为观察，但不会因此恢复正式组队资格。',
                       'ordinary行为层包含既有special_conditional_only评分层；门洞行为单列，A/B普通类别拟合均不使用门洞。',
                       '正式投票资格、池分析资格与质量资格是独立原字段。只持有独立投票标志不等于已经可以进入正式融合池。',
                       'GT错误暂停、reference quality hold与筛除计数可以重叠，不可相加当作互斥缺失原因。',
                       'selected池成员是正式可用机会库存，actual_used_records是实际使用；二者不混计。',
                       'B主交换及三项扩展各按当前保存的精确团队分别计数，不以总和掩盖实验复用或成员重叠。',
                   ],
                   reproduction='python research/workers/personnel_taxonomy_20261021/code/build_inventory_usage.py',
                   geometry_scores_eligibility_modified=False)
    (OUT / 'INVENTORY_RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'non_oos': receipt['non_oos_inventory'], 'row_counts': {'image': len(image_rows), 'worker': len(worker_rows)}, 'training': training, 'fusion': {k: {f: v[f] for f in ['n_teams', 'n_actual_pools', 'n_unique_used_records']} for k, v in fusion_receipts.items()}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
