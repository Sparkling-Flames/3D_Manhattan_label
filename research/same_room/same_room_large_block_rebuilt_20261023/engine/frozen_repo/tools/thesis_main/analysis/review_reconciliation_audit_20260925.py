"""只读核验原件、点号、历史修复及配对阻断；不修改裁决、坐标或环序。"""
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlparse

import numpy as np


INPUT = 'analysis_results/consensus_research_20260923/inputs/annotations.jsonl.gz'
VIEW = 'analysis_results/consensus_visual_review_20260923'
PREVIOUS = 'analysis_results/new_manual_reviewed_20260921'
HISTORY = 'analysis_results/human_review_reconciliation_20260918/用户_39图最终裁决_原始.json'
OLD_REPAIRS = 'analysis_results/confirmed_point_calculation_view_20260909_v1/reviewed/confirmed_user_decisions.json'
TOL = 1e-7


def read(path):
    with (gzip.open(path, 'rt', encoding='utf-8-sig') if path.suffix == '.gz'
          else path.open(encoding='utf-8-sig')) as stream:
        return [json.loads(line) for line in stream if line.strip()] if '.jsonl' in path.name else json.load(stream)


def same(a, b):
    if a is None or b is None:
        return a is b
    a, b = np.asarray(a, float), np.asarray(b, float)
    return a.shape == b.shape and bool(np.allclose(a, b, atol=TOL, rtol=0))


def verify_raw(source, points, task, annotation):
    """严格核对选定导出的身份、结果数组顺序及坐标；返回原始region ID。"""
    worker = annotation['completed_by']
    worker = worker['id'] if isinstance(worker, dict) else worker
    actual = dict(project=task['project'], task=task['id'], annotation=annotation['id'],
                  worker=f'W{int(worker):03d}',
                  image_id=Path(unquote(urlparse(task['data']['image']).path)).stem,
                  condition=task['data']['condition'])
    for key, value in actual.items():
        if source[key] != value:
            raise ValueError('raw_identity_mismatch:' + key)
    if task['data'].get('image_id', actual['image_id']) != actual['image_id']:
        raise ValueError('task_image_id_and_url_disagree')
    kp = [v for v in annotation['result'] if v.get('type') == 'keypointlabels']
    ids = [v['id'] for v in kp]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError('missing_or_duplicate_region_id')
    if any((v['original_width'], v['original_height'], v.get('image_rotation', 0)) != (1024, 512, 0) for v in kp):
        raise ValueError('raw_coordinate_frame_changed')
    original = [[float(v['value']['x']) * 1024 / 100, float(v['value']['y']) * 512 / 100] for v in kp]
    if not same(points, original):
        raise ValueError('raw_coordinates_mismatch')
    return ids


def point_labels(raw, effective, status, provenance, dropped=None):
    """标签对应数组位置；删除保留原p号，补点绝不伪装成原作答。"""
    labels = [f'p{i + 1}' for i in range(len(raw))]
    if same(raw, effective):
        return labels
    if status == 'researcher_coordinate_correction' and len(raw) == len(effective):
        if sum(not same(a, b) for a, b in zip(raw, effective)) != 1:
            raise ValueError('unexpected_coordinate_correction')
        return labels
    if status in {'confirmed_point_added', 'user_confirmed_add_point'}:
        if len(effective) != len(raw) + 1 or not same(raw, effective[:-1]) or not provenance:
            raise ValueError('addition_without_matching_provenance')
        if provenance.get('donor_id'):
            donor = provenance['donor_id'].rsplit('_', 1)[-1]
            label = f"补点1（供体{donor}原p{provenance['donor_raw_point_1based']}）"
        else:
            label = '补点1（研究者确认坐标，非原始作答）'
        return labels + [label]
    if status in {'confirmed_point_removed', 'researcher_confirmed_point_removed'}:
        candidates = [i for i in range(len(raw)) if same(raw[:i] + raw[i + 1:], effective)]
        if dropped is not None:
            candidates = [i for i in candidates if i == dropped]
        if len(candidates) != 1:
            raise ValueError('deleted_point_identity_unresolved')
        return [label for i, label in enumerate(labels) if i != candidates[0]]
    raise ValueError('unexplained_effective_change:' + status)


def diagnose_pairing(row, old, labels):
    """复用旧配对判据；候选只解释歧义，不写入links，不推断墙体环序。"""
    from scipy.optimize import linear_sum_assignment
    from .paired_split_research.study import infer_links
    p = np.asarray(row['effective_points_1024x512'], float)
    result = dict(status=row['pairing_status'], reason=old.get('pairing_source') or old.get('role_status'),
                  description='', candidates=[], evidence_source=PREVIOUS + '/eligibility.json',
                  semantics='候选中的每项仅表示一对上下点；列表排列不是墙体连接顺序，未自动采用。')
    if row['links_zero_based'] is not None:
        result['description'] = '已有可用配对；是否经人工确认以pairing_source和原始审核记录为准。'
        return result
    up, dn = np.flatnonzero(p[:, 1] < 255.5), np.flatnonzero(p[:, 1] > 255.5)
    result.update(n_top=len(up), n_bottom=len(dn), on_horizon=int(np.sum(p[:, 1] == 255.5)))
    if not len(up) or not len(dn) or len(up) + len(dn) != len(p):
        reason, meta = 'empty_role_or_point_on_horizon', {}
    else:
        links, reason, meta = infer_links(p, up, dn)
        if links is not None:
            raise ValueError('unavailable_pairing_diagnostic_changed')
    if reason != result['reason']:
        raise ValueError('pairing_reason_drift:' + str(result['reason']) + ':' + reason)
    result.update({k: float(v) if np.isfinite(v) else None for k, v in meta.items()})
    descriptions = {
        'unbalanced_top_bottom': f'按现有地平线规则识别到{len(up)}个top、{len(dn)}个bottom，无法完整一一配对；不能据此判定漏点或无效。',
        'empty_role_or_point_on_horizon': '现有地平线角色规则未获得完整上下两组；这是表示规则的限制，不能自动归为人员错误。',
        'ambiguous_horizontal_assignment': '水平距离总和存在等价最优配对，算法保留歧义并未存入links；候选需要人工确认。',
        'no_pairing_within_inherited_x_bound': '无法在继承的51.2px水平距离界限内完成配对。',
    }
    result['description'] = descriptions[reason]
    near = []
    for i in range(len(p)):
        for j in range(i + 1, len(p)):
            distance = float(np.linalg.norm(p[i] - p[j]))
            if distance < 1:
                near.append(dict(labels=[labels[i], labels[j]], distance_px=distance))
    result['near_overlapping_points'] = near
    if near:
        result['description'] += '存在相距不足1px的点，视觉上可能重叠；未自动删点。'
    if reason == 'ambiguous_horizontal_assignment':
        cost = abs((p[up, None, 0] - p[dn, 0][None, :] + 512) % 1024 - 512)
        cost = np.where(cost < 51.2, cost, 1e9)
        i, j = linear_sum_assignment(cost)
        candidate_indices = [(i, j)]
        # ponytail: 两个等价方案足以解释拒绝原因；这不是所有可能配对的枚举器。
        for u, v in zip(i, j):
            alternative = cost.copy()
            alternative[u, v] = 1e9
            ii, jj = linear_sum_assignment(alternative)
            if np.max(alternative[ii, jj]) < 1e9 and abs(float(alternative[ii, jj].sum()) - meta['pair_cost_px']) < 1e-8:
                candidate_indices.append((ii, jj))
                break
        for ii, jj in candidate_indices:
            result['candidates'].append(dict(diagnostic_only=True,
                pairs=[[labels[int(up[u])], labels[int(dn[v])]] for u, v in zip(ii, jj)],
                total_horizontal_cost_px=float(cost[ii, jj].sum())))
    return result


def audit(root: Path) -> dict:
    """返回当前3019份作答的只读溯源审计；任何核验失败显式进入failures。"""
    root = Path(root)
    rows = [r for r in read(root / INPUT) if r['accepted_before_new_review']]
    if len({r['canonical_annotation_id'] for r in rows}) != len(rows):
        raise ValueError('duplicate_canonical_id')
    upstream = {r['canonical_annotation_id']: r for r in read(root / PREVIOUS / 'responses.jsonl.gz')}
    eligibility = {r['id']: r for r in read(root / PREVIOUS / 'eligibility.json')}
    previous = read(root / HISTORY)
    point_history = {r['canonical_annotation_id']: r for r in previous['point_decisions']}
    by_id = {r['canonical_annotation_id']: r for r in rows}
    source_files, cases, annotations, failures = {}, {}, {}, []
    mirrors = defaultdict(list)
    for path in (root / 'export_label').rglob('project-*.json'):
        mirrors[path.name].append(path.relative_to(root).as_posix())

    def load_source(path):
        if path not in source_files:
            tasks = read(root / path)
            if len({t['id'] for t in tasks}) != len(tasks):
                raise ValueError('duplicate_task_in_snapshot')
            source_files[path] = {t['id']: t for t in tasks}
        return source_files[path]

    for row in rows:
        cid = row['canonical_annotation_id']
        pv = row.get('provenance') or {}
        selected_path = row.get('raw_export_path') or pv['source']
        source = dict(path=selected_path, selected_snapshot_path=selected_path,
            project=int(re.search(r'project-(\d+)-', Path(selected_path).name).group(1)),
            task=int(row.get('runtime_task_id') or pv['task']),
            annotation=int(row.get('raw_annotation_id') or pv['annotation']),
            worker=row['worker_id'], image_id=row['image_id'], condition=row['raw_condition'])
        item = dict(source=source, raw_verified=False, raw_region_ids=[], raw_point_labels=[],
                    effective_point_labels=[], shared_x_point_labels=[], repairs=[], history=[],
                    pairing={}, processing_status=row['processing_status'])
        annotations[cid] = item
        try:
            tasks = load_source(selected_path)
            if not selected_path.startswith('export_label/'):
                matched = mirrors[Path(selected_path).name]
                if len(matched) != 1 or load_source(matched[0]) != tasks:
                    raise ValueError('raw_export_mirror_mismatch')
                source.update(path=matched[0], mirror_path=matched[0], mirror_verified=True)
            task = tasks[source['task']]
            matches = [a for a in task['annotations'] if a['id'] == source['annotation']]
            if len(matches) != 1:
                raise ValueError('raw_annotation_not_unique')
            raw, effective = row['raw_points_1024x512'], row['effective_points_1024x512']
            item['raw_region_ids'] = verify_raw(source, raw, task, matches[0])
            item['raw_verified'] = True
            prior = upstream[cid]
            if not same(prior['raw_points_1024x512'], raw) or not same(prior['effective_points_1024x512'], effective):
                raise ValueError('upstream_point_version_mismatch')
            item['raw_point_labels'] = [f'p{i + 1}' for i in range(len(raw))]
            labels = point_labels(raw, effective, row['processing_status'], row.get('imputation_provenance') or {},
                                  prior.get('dropped_point_index_zero_based'))
            item['effective_point_labels'] = labels
            if not same(raw, effective):
                evidence = (PREVIOUS + '/review_applied.json' if row['processing_status'] == 'user_confirmed_add_point'
                            else prior.get('legacy_repair_audit_source') or OLD_REPAIRS)
                if row['processing_status'].startswith('researcher_'):
                    evidence = 'analysis_results/clustering_numeric_received_20260920/results/effective_version_changes.csv'
                repair = dict(status='applied', description=f"原始{len(raw)}点→有效{len(effective)}点；{row['processing_status']}。原始点保留。",
                              evidence_source=evidence, confirmation_source=prior.get('confirmation_source'),
                              raw_count=len(raw), effective_count=len(effective))
                provenance = row.get('imputation_provenance')
                if provenance:
                    repair['provenance'] = provenance
                    if provenance.get('donor_id'):
                        donor = by_id[provenance['donor_id']]
                        donor_point = donor['raw_points_1024x512'][provenance['donor_raw_point_1based'] - 1]
                        if donor['image_id'] != row['image_id'] or not same(donor_point, effective[-1]):
                            raise ValueError('donor_point_mismatch')
                        repair.update(donor_id=provenance['donor_id'], donor_raw_point_1based=provenance['donor_raw_point_1based'])
                if len(raw) == len(effective):
                    repair['changed_points'] = [dict(label=labels[i], before=a, after=b)
                                               for i, (a, b) in enumerate(zip(raw, effective)) if not same(a, b)]
                elif len(raw) > len(effective):
                    repair['removed_labels'] = [label for label in item['raw_point_labels'] if label not in labels]
                item['repairs'].append(repair)
            links = row['links_zero_based']
            if links is not None:
                flat = [i for pair in links for i in pair]
                if sorted(flat) != list(range(len(effective))):
                    raise ValueError('pairing_does_not_cover_effective_points')
                item['shared_x_point_labels'] = [labels[i] for i in flat]
                expected = []
                for top, bottom in links:
                    a, b = effective[top], effective[bottom]
                    x = (a[0] + b[0]) / 2
                    expected.append([[x, a[1]], [x, b[1]]])
                if not same(expected, row['pairs_shared_x']):
                    raise ValueError('shared_x_coordinates_mismatch')
            item['pairing'] = diagnose_pairing(row, eligibility[cid], labels)
            iid = row['image_id']
            if iid not in cases:
                text = (root / VIEW / 'cases' / (iid + '.js')).read_text(encoding='utf8')
                case = json.loads(text.split('=', 1)[1].strip().removesuffix(';'))
                if case['image_id'] != iid or Path(case['image_src']).stem != iid:
                    raise ValueError('case_image_identity_mismatch')
                cases[iid] = {a['canonical_annotation_id']: a for a in case['annotations']}
            case_row = cases[iid][cid]
            for key in ('raw_points_1024x512', 'effective_points_1024x512', 'pairs_shared_x', 'links_zero_based'):
                if not same(case_row[key], row[key]):
                    raise ValueError('case_point_version_mismatch:' + key)
            if case_row['worker_id'] != row['worker_id'] or case_row['raw_condition'] != row['raw_condition']:
                raise ValueError('case_worker_or_condition_mismatch')
            item['case_verified'] = True
            if cid in point_history:
                h = point_history[cid]
                quote = h.get('reason') or '历史逐点复核：confirmed=false，pending_not_applied；具体操作未确认。'
                item['history'].append(dict(source=HISTORY, quote=quote,
                    interpretation='该条是历史状态；当前是否已执行以有效点和后续修复记录为准。'))
                if not item['repairs'] and not h['confirmed']:
                    item['repairs'].append(dict(status='proposed_not_applied', description=quote,
                                                evidence_source=HISTORY))
            if cid == '032cd152706166629e82':
                h = next(d for d in previous['decisions'] if d['image_id'] == iid and '补点' in d['answer'])
                quote = h['answer'] + '；' + h['note']
                item['repairs'].append(dict(status='proposed_not_applied', description=quote,
                    evidence_source=HISTORY, limitation='旧簇1尚未绑定具体供体、点号和坐标；不能自动补点。'))
                item['history'].append(dict(source=HISTORY, quote=quote, interpretation='曾提出补点，但当前仍是6点。'))
        except (KeyError, ValueError, IndexError, TypeError, OSError) as exc:
            failures.append(dict(canonical_annotation_id=cid, reason=str(exc)))
    unpaired = [a for a in annotations.values() if a['pairing'].get('status') == 'unavailable']
    summary = dict(annotations=len(rows), raw_verified=sum(a['raw_verified'] for a in annotations.values()),
        cases_verified=sum(a.get('case_verified', False) for a in annotations.values()),
        raw_points=sum(len(a['raw_region_ids']) for a in annotations.values()),
        selected_snapshots=len({a['source']['selected_snapshot_path'] for a in annotations.values()}),
        mirrored_snapshots=len({a['source']['mirror_path'] for a in annotations.values() if a['source'].get('mirror_verified')}),
        applied_repairs=sum(r['status'] == 'applied' for a in annotations.values() for r in a['repairs']),
        proposed_not_applied=sum(r['status'] == 'proposed_not_applied' for a in annotations.values() for r in a['repairs']),
        pairing_unavailable=len(unpaired), pairing_failure_reasons=dict(Counter(a['pairing']['reason'] for a in unpaired)),
        failures=len(failures))
    return dict(schema='review_reconciliation_audit_v1', summary=summary, annotations=annotations,
                failures=failures, guard='只核验与解释既有数据；不应用本轮裁决，不增删点，不调整配对或环序，不重估active_time。')


if __name__ == '__main__':
    result = audit(Path(__file__).resolve().parents[3])
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))
    raise SystemExit(bool(result['failures']))
