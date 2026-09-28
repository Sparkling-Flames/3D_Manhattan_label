"""应用9月21日用户终审，保留旧快照，重汇总有效点与逐人逐图数据。"""
import collections
import copy
import itertools
import json

import numpy as np
import pandas as pd

from . import analyze_new_manual_20260921 as old
from .paired_split_research.release_review import validate_review

OUT = old.ROOT / 'analysis_results/new_manual_reviewed_20260921'
REGISTRY = 'analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json'
REVIEW = OUT / 'evidence/用户审核_原始.json'
SOURCES = ['export_label/新增中文20图/project-93-at-2026-09-21-09-42-4609125d.json', *old.SOURCES[1:]]
CONFIRMATION = '用户2026-09-21明确确认本批均独立作答，相关独立性问题已关闭。'
# 原数组1-based点号。总体对应确认结合原图/坐标落实；不是跨作答映射。
PAIRS = {
    7182: [[1, 4], [2, 3], [5, 6], [7, 8], [10, 9], [11, 12]],
    6877: [[2, 1], [4, 3], [6, 5], [7, 8], [10, 9], [12, 11]],
    7433: [[i, i + 1] for i in range(1, 17, 2)],
}
REPAIRS = [(6925, 7015, 10), (7273, 6987, 8)]


def dump(name, value):
    (OUT / name).write_text(json.dumps(old.clean(value), ensure_ascii=False, indent=2,
                                     allow_nan=False) + '\n', encoding='utf8')


def prepare(history, new, registry):
    review = old.pipeline.read(REVIEW)
    manifest = old.read('analysis_results/new_manual_analysis_20260921/审核/REVIEW_MANIFEST.json')
    decisions = validate_review(review, manifest['binding'], [c['key'] for c in manifest['cases']],
                                {c['key']: c['decision_options'] for c in manifest['cases']})
    cases = {c['key'].rsplit('|', 1)[1]: decisions.get(c['key']) for c in manifest['cases']}
    assert all(cases[str(i)] and not cases[str(i)]['defer'] for i in range(8))
    assert cases['1']['relation'] == cases['2']['relation'] == '漏标需补点（见文字）'
    assert cases['3']['relation'] == '采用7272作为当前版本'
    assert all(cases[str(i)]['relation'] == '确认上下对应（见文字）' for i in [4, 5, 7])
    assert cases['6']['relation'] == '原样保留观察'
    new = copy.deepcopy(new)
    by = {r['provenance']['annotation']: r for r in new}
    reviewed_points = {r['canonical_annotation_id']: r['raw_points_1024x512']
                       for r in old.pipeline.rows_at(old.OUT / 'responses.jsonl.gz')}
    for aid in {*PAIRS, 6925, 7015, 7273, 6987, 7271, 7272, 7036}:
        r = by[aid]
        if r['raw_points_1024x512'] != reviewed_points[r['canonical_annotation_id']]:
            raise ValueError(f'审核对应点集已变化：{aid}')
    for target, donor, point in REPAIRS:
        r, source = by[target], by[donor]
        assert r['image_id'] == source['image_id'] and r['raw_point_count'] in [7, 13]
        coordinate = source['raw_points_1024x512'][point - 1].copy()
        r['effective_points_1024x512'] = copy.deepcopy(r['raw_points_1024x512']) + [coordinate]
        r['effective_point_count'] = len(r['effective_points_1024x512'])
        r['imputed_point'] = True
        r['processing_status'] = 'user_confirmed_add_point'
        r['imputation_provenance'] = dict(donor_id=source['canonical_annotation_id'],
            donor_raw_point_1based=point, added_point_1based=r['effective_point_count'],
            coordinate_1024x512=coordinate, source='evidence/用户审核_原始.json',
            selection='用户指定W033 p10' if target == 6925 else '用户允许簇1任一作答；固定取W035/6987 p8',
            borrowed_other_response=True)
    for r in new:
        p = r['provenance']; aid = p['annotation']
        p['flags_before_review'] = p['flags'].copy()
        p['flags'] = [f for f in p['flags'] if f != 'parent_annotation_independence_pending']
        p['independence_status'] = 'user_confirmed_independent'
        if aid in [7500, 7501, 7502]:
            assert p['worker'] == 'W006' and p['assignment'] == 'required'
            p['submission_context'] = '用户确认W006补交原分配任务'
            if aid == 7502:
                p['supersedes_annotation'] = 7111
        if aid in [6925, 7273]:
            p['flags'].remove('odd_unconfirmed')
        if aid in [7271, 7272]:
            p['flags'].remove('multiple_submissions_version_pending')
            p['version_decision'] = 'superseded_by_7272' if aid == 7271 else 'user_selected_current'
            if aid == 7271:
                p['flags'].append('superseded_by_7272')
        p['effective_point_count'] = r['effective_point_count']
        p['strict_include'] = p['conditional_include'] = r['calculation_included'] = not p['flags']
    rows = copy.deepcopy(history) + new
    images = {i['image_id']: i for i in registry['images']}
    audit = pd.DataFrame([dict(id=r['canonical_annotation_id'],
        code=f"{images[r['image_id']]['building']}-{images[r['image_id']]['number']:02d}")
        for r in rows]).set_index('id')
    approved = old.study.accepted_map(old.HIST, rows)
    for aid, pairs in PAIRS.items():
        r = by[aid]
        assert sorted(itertools.chain.from_iterable(pairs)) == list(range(1, r['effective_point_count'] + 1))
        assert all(r['effective_points_1024x512'][t-1][1] < r['effective_points_1024x512'][b-1][1] for t, b in pairs)
        approved[r['canonical_annotation_id']] = np.asarray(pairs) - 1
        r['pairing_review'] = dict(pairs_1based=pairs, source='evidence/用户审核_原始.json',
            interpretation='用户确认结合原图与原点号落实；不以地平线判据否定局部上下关系')
    rec, eligibility = old.study.prepare(rows, audit, approved, 'min_horizontal')
    return rows, [r['provenance'] for r in new], rec, eligibility


def counts(rows):
    return dict(responses=len(rows), images=len({r['image_id'] for r in rows}),
        workers=len({r['worker_id'] for r in rows}), buildings=len({r['building_id'] for r in rows}))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    history = old.pipeline.rows_at(old.HIST / 'responses.jsonl.gz')
    registry = old.read(REGISTRY)
    new, _ = old.intake(history, registry, SOURCES)
    rows, receipts, rec, eligibility = prepare(history, new, registry)
    old.pipeline.write_rows(OUT / 'responses.jsonl.gz', rows)
    dump('intake.json', receipts)
    dump('eligibility.json', eligibility.to_dict('records'))
    dump('review_applied.json', dict(independence_confirmation=CONFIRMATION,
        repairs=[r for r in rows if r.get('processing_status') == 'user_confirmed_add_point'],
        pairing_overrides=[dict(annotation=a, pairs_1based=p) for a, p in PAIRS.items()],
        selected_version=7272, preserved_unpaired=7036,
        uNb40='按用户意见保留W002与其他作答的差异，不应用循环换起点合簇'))
    accepted = [r for r in rows if r['calculation_included'] and r['worker_id'] not in {'W019', 'W026'}]
    bound = [r['row'] for r in rec.values() if r['links'] is not None]
    manual = [r for r in accepted if r['raw_condition'] in ['manual', 'oos']]
    bound_manual = [r for r in bound if r['raw_condition'] in ['manual', 'oos']]
    predictive = [r for r in bound_manual if not r['imputed_point']]
    views = dict(all_accepted=accepted, manual_descriptive=manual, bound_all=bound,
                 bound_manual=bound_manual, unaided_prediction=predictive)
    required = {(r['image_id'], f"W{r['worker_id']:03d}") for r in old.read(
        'import_json/scene_stability_stage1_20260913_v2/required_assignments.json')}
    submitted = {(r['image_id'], r['worker']) for r in receipts if r['point_count']}
    included = {(r['image_id'], r['worker']) for r in receipts if r['strict_include']}
    summary = dict(schema='reviewed_manual_summary_v1', independence_status=CONFIRMATION,
        raw_history=len(history), raw_new=len(new),
        accepted_new=sum(r['strict_include'] for r in receipts),
        bound_new=sum(r['canonical_annotation_id'].startswith('new_') for r in bound),
        repaired_responses=2, added_points=2, parent_records_confirmed=sum(bool(r['parent_annotation']) for r in receipts),
        sources=SOURCES,
        required_assignment_coverage=dict(planned=len(required), nonempty_submitted=len(required & submitted),
            included=len(required & included), missing=sorted(required - submitted)),
        w006_makeup_annotations=[7500, 7501, 7502],
        flags=collections.Counter(f for r in receipts for f in r['flags']),
        views={name: counts(v) for name, v in views.items()},
        time_status='新增active_time未冻结，原冻结时间不变',
        downstream_status='本次更新数据汇总与25.6px候选分簇；旧收敛、人员组合、预测报告仍属旧快照')
    dump('SUMMARY.json', summary)
    for key, filename in [('image_id', 'per_image.json'), ('worker_id', 'per_worker.json')]:
        table = []
        for identity in sorted({r[key] for r in rows}):
            table.append(dict(identity=identity, **{name: counts([r for r in v if r[key] == identity]) for name, v in views.items()}))
        dump(filename, table)
    grouped = collections.defaultdict(list)
    for cid, r in rec.items():
        if r['links'] is not None:
            grouped[r['row']['image_id'], r['row']['raw_condition']].append(cid)
    distances, partitions, memberships = [], [], []
    for (iid, condition), ids in sorted(grouped.items()):
        ids.sort(); d = np.full((len(ids), len(ids)), 1e6); np.fill_diagonal(d, 0)
        for i, j in itertools.combinations(range(len(ids)), 2):
            a, b = rec[ids[i]], rec[ids[j]]
            if len(a['p']) == len(b['p']):
                d[i, j] = d[j, i] = max(e['image_px'] for e in old.local_points.endpoint_rows(a, b))
        base = dict(image_id=iid, condition=condition, code=rec[ids[0]]['audit']['code'])
        distances.append(dict(**base, ids=ids, image=d))
        for method in ['complete', 'representative']:
            stats, labels, reps = old.statistics(d, ids, 25.6, method)
            partitions.append(dict(**base, method=method, pixel_probe=25.6, **stats))
            memberships.extend(dict(**base, method=method, id=cid, group=int(label), representative=cid in reps) for cid, label in zip(ids, labels))
    dump('distances.json', distances); dump('partitions.json', partitions); dump('memberships.json', memberships)
    lines = ['# 新增数据审核后汇总（2026-09-21）', '', CONFIRMATION,
        '本版替代旧版的待定独立性与点位／版本状态；旧数值报告保留历史身份。', '',
        '## 已落实', '',
        f"- {summary['parent_records_confirmed']}份父关联记录全部纳入主汇总，相关独立性问题关闭。",
        '- 用户确认W006补交原分配任务：uNb-66/7500、uNb-67/7501、uNb-87/7502；7502替代同人同图7111，只计一票。采用Project93/09:42导出，本批实收由649变为651条。',
        '- uNb-59 W031/6925：13→14点，新增p14取W033/7015原p10，与原p13成对。',
        '- e9-26 W034/7273：7→8点，新增p8取簇1 W035/6987原p8（bottom）。',
        '- wc-29 W034采用7272；7271留存来源，不多计一人。',
        '- W010/7182、W033/6877、W028/7433按审核落实上下对应，坐标不改。',
        '- uNb-59 W037/7036孤立p3/p4原样保留，进入描述数据；不强行提供完整绑定或3D。',
        '- uNb-40 W013/7285及uNb-59 W006/7086恢复主分析；原先未显示分簇源于父关联筛选。', '',
        '## 数量', '', '| 口径 | 作答份数 | 图片 | 人员 | 建筑 |', '|---|---:|---:|---:|---:|']
    names = dict(all_accepted='全部纳入（含Semi）', manual_descriptive='Manual/OOS描述数据',
        bound_all='上下绑定可计算（含Semi）', bound_manual='Manual/OOS上下绑定', unaided_prediction='不借用补点的预测视图')
    for name, z in summary['views'].items():
        lines.append(f"| {names[name]} | {z['responses']} | {z['images']} | {z['workers']} | {z['buildings']} |")
    lines += ['', f"历史原始{len(history)}份，本批实收{len(new)}条（含空记录）；新增纳入{summary['accepted_new']}份，其中上下绑定可计算{summary['bound_new']}份。",
        f"原480份必做任务：按人员×图片核对，非空提交{len(required & submitted)}/480，纳入{len(required & included)}/480；非空提交不等于全数通过上下绑定。",
        '两份补点有明确来源且保留描述价值；借用其他作答的几何点另标，避免用补入信息评价独立预测。', '',
        '## 文件及验证边界', '',
        '`responses.jsonl.gz`同时保留raw/effective点；`intake.json`保留原处置与当前决定；`review_applied.json`登记补点来源及完整对应。',
        '`per_image.json`、`per_worker.json`给出各口径覆盖；`distances.json`、`partitions.json`、`memberships.json`重算二维25.6px候选。',
        '没有重跑收敛、人员分类或同房预测；既有相关报告不是本次新汇总的结果。没有改变分簇探针、原始导出、正式合同、采集或冻结时间。',
        'uNb-21跨作答人工映射仍保留旧敏感性版本，本次未扩展算法范围。',
        '复算：`D:/anaconda/python.exe -X utf8 -B -m tools.thesis_main.analysis.reviewed_manual_20260921`。',
        '验证：`D:/anaconda/python.exe -X utf8 -B -m pytest tests/test_reviewed_manual_20260921.py tests/test_new_manual_20260921.py -q`。']
    (OUT / '汇总说明.md').write_text('\n'.join(lines) + '\n', encoding='utf8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
