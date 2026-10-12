"""只重评分现有全员冻结终点；不运行融合、不推断范围资格或人数轨迹。"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

from .research_round_20260929 import reconstruct
from .quality_parallel_local_20261013 import CONFIG_SHA, sha

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/quality_parallel_local_20261012'
PACKAGE = OUT / 'source_package/quality_parameter_calibration_20261012'
CANDIDATES = ('P_tied_quad08', 'P_tied_mix08', 'B_main_relative2')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def select_reference(image_id, bindings):
    ids = bindings.get(image_id, set())
    if len(ids) == 1:
        return next(iter(ids)), 'unique_package_reference'
    return None, 'missing_reference' if not ids else 'ambiguous_reference'


def project(points):
    state = reconstruct({'points': points}, coordinate_convention='continuous')
    diagnostics = {k: state[k] for k in ('status', 'reason', 'coordinate_convention')}
    if state['status'] != 'ok':
        return None, diagnostics
    floor = state['floor']
    bottom = np.column_stack([floor[:, 0], -np.ones(len(floor)), floor[:, 1]])
    top = bottom.copy()
    top[:, 1] = state['heights'] - 1
    return dict(bottom3d=bottom.tolist(), top3d=top.tolist()), diagnostics


def projection_checks(data, loader):
    objects = {o['object_id']: o for o in loader['objects']}
    # 不同角点数各取一份，按既有记录顺序；不按质量分挑选。
    seen = set()
    checks = []
    for row in data['rows']:
        geometry = data['geometries'][row['object_id']]
        count = len(geometry['bottom3d'])
        if count in seen:
            continue
        seen.add(count)
        recovered, state = project(objects[row['object_id']]['points_1024x512'])
        assert recovered is not None, (row['id'], state)
        error = max(float(np.max(np.abs(np.array(recovered[k]) - geometry[k]))) for k in ('top3d', 'bottom3d'))
        assert error < 1e-10, (row['id'], error)
        checks.append(dict(record_id=row['id'],object_id=row['object_id'],pair_count=count,maximum_coordinate_error=error))
        if len(checks) == 6:
            break
    return checks


def run(package=PACKAGE):
    assert sha(package / 'config/frozen_selected_candidates.json') == CONFIG_SHA
    sys.path.insert(0, str(package / 'scripts'))
    from score_frozen_geometry import evaluate
    from scoring import scalar_terms
    from frozen_guard import verify_scoring_identity
    frozen = read(package / 'config/frozen_selected_candidates.json')
    verify_scoring_identity(frozen, package)
    data = read(package / 'inputs/calibration_records.json')
    loader = read(package / 'inputs/current_formal_loader_data.json')
    checks = projection_checks(data, loader)
    objects = {o['object_id']:o for o in loader['objects']}
    population = read(ROOT / 'analysis_results/direct_fusion_20261007/gap_sweep/population/inputs.json')
    members = {r['id']:r for im in population['images'] for r in im['records']}
    bindings = defaultdict(set)
    quality_records = {r['id']: r for r in data['rows']}
    reference_versions = defaultdict(set)
    room_groups = defaultdict(set)
    for row in data['rows']:
        bindings[row['image_id']].add(row['reference_object_id'])
        reference_versions[row['reference_object_id']].add(row['gate'].get('reference_version', 'not_recorded_in_calibration_gate'))
        if row.get('room_group'):
            room_groups[row['image_id']].add(row['room_group'])
    exclusions = read(ROOT/'research/quality_next_stage_handoff_20261010/reference_exclusion_registry_20261010.json')
    reference_blocks = defaultdict(list)
    for key in ('confirmed_reference_exclusions','preserved_user_analysis_holds','reference_evidence_conflicts_primary_research_quarantine'):
        for item in exclusions[key]:
            reference_blocks[item['image_id']].append(key+':'+item['classification'])
    exposure = read(ROOT/'research/quality_holdout_exposure_correction_20261011/exposure_registry.json')
    hold_groups = set(exposure['groups_touched_by_this_screen']) | set(exposure['groups_not_touched_by_this_screen'])
    folder = ROOT / 'analysis_results/consensus_delivery_20261008'
    results = []
    for current in read(folder / 'outputs.json'):
        source = folder / (current['image'] + '.json')
        item = read(source)
        reference_id, reference_status = select_reference(item['image_id'], bindings)
        for version in ('automatic', 'assisted'):
            output = item[version]
            if output is None:
                continue
            candidate = output['candidate']
            row = dict(image_id=item['image_id'], image_code=item['image'], version=version,
                source=str(source.relative_to(ROOT)).replace('\\', '/'), fusion_gap=item['gap'], n=output['n'],
                input_version='consensus_delivery_20261008:' + version,
                members=[dict(record_id=m['id'],fusion_worker_alias=m['worker'],object_id=members[m['id']]['object_id'],
                    quality_worker_id=objects[members[m['id']]['object_id']]['worker_id']) for m in output['assignments']],
                reference_id=reference_id, reference_status=reference_status,
                reference_candidates=sorted(bindings.get(item['image_id'], set())),
                reference_versions=sorted(reference_versions.get(reference_id, set())),
                feature_ids=candidate['feature_ids'], order_status=candidate.get('order_status'),
                ring_confirmed=candidate.get('ring_confirmed'), geometry_status_frozen=candidate.get('geometry_status'),
                review_status=candidate.get('review_status'), applied_reviews=item['applied_reviews'] if version=='assisted' else [],
                scope_eligibility='unknown_not_adjudicated', formal_comparison_eligible=False,
                sequence_id=None, status='unavailable', unavailable_reason=None,
                scores=None, components=None, metrics=None, projection=None)
            for member in row['members']:
                original = objects[member['object_id']]
                assert original['image_id'] == item['image_id']
                member.update(cleaning_disposition=original['cleaning_disposition'],
                    worker_quality_gate=original['worker_quality_gate'], independent_vote_eligible=original['independent_vote_eligible'])
                if member['record_id'] in quality_records:
                    assert quality_records[member['record_id']]['worker_id'] == member['quality_worker_id']
            row['contains_calibration_only_W019'] = any(m['quality_worker_id']=='W019' for m in row['members'])
            row['reference_barriers'] = reference_blocks[item['image_id']]
            row['original_holdout_groups'] = sorted(room_groups[item['image_id']] & hold_groups)
            row['member_use_barriers'] = [dict(record_id=m['record_id'],quality_worker_id=m['quality_worker_id'],
                cleaning_disposition=m['cleaning_disposition'],worker_quality_gate=m['worker_quality_gate'],
                independent_vote_eligible=m['independent_vote_eligible']) for m in row['members']
                if m['cleaning_disposition']!='retained' or m['worker_quality_gate']!='candidate_pending_geometry'
                or not m['independent_vote_eligible'] or m['quality_worker_id']=='W019']
            row['use_barriers'] = ['fusion_scope_not_adjudicated'] + row['reference_barriers']
            if row['original_holdout_groups']:
                row['use_barriers'].append('original_holdout_group_not_for_calibration')
            if row['member_use_barriers']:
                row['use_barriers'].append('member_eligibility_barriers_preserved')
            geometry = None
            if candidate['points'] is not None:
                geometry, row['projection'] = project(candidate['points'])
            if candidate['points'] is None:
                row['unavailable_reason'] = candidate.get('reason', 'missing_candidate_connection')
            elif geometry is None:
                row['unavailable_reason'] = 'projection:' + str(row['projection']['reason'])
            elif reference_id is None:
                row['unavailable_reason'] = reference_status
            else:
                evaluated = evaluate(geometry, data['geometries'][reference_id], frozen['candidates'][CANDIDATES[0]]['parameters'])
                if evaluated['status'] != 'available':
                    row['unavailable_reason'] = 'frozen_engine:' + evaluated['status']
                    row['unavailable_detail'] = evaluated
                else:
                    row.update(status='available_diagnostic_only', metrics=evaluated['metrics'])
                    row['components'] = {name:scalar_terms(evaluated['metrics'], frozen['candidates'][name]['parameters']) for name in CANDIDATES}
                    row['scores'] = {name:value['score'] for name,value in row['components'].items()}
                    row['scores'].update(Q_v11=evaluated['frozen_v11_score'], Q_official_iou3d=100*evaluated['official_corner_mean_iou3d'], Q_floor_iou=100*evaluated['metrics']['iou_2d'])
            results.append(row)
    summaries = {}
    for version in ('automatic', 'assisted'):
        rows = [r for r in results if r['version']==version]
        available = [r for r in rows if r['scores'] is not None]
        summaries[version] = dict(outputs=len(rows), scored=len(available), unavailable_reasons=dict(Counter(r['unavailable_reason'] for r in rows if r['scores'] is None)),
            candidate_minus_B_main_relative2={name:dict(min=min(r['scores'][name]-r['scores']['B_main_relative2'] for r in available),
                max=max(r['scores'][name]-r['scores']['B_main_relative2'] for r in available),
                mean=float(np.mean([r['scores'][name]-r['scores']['B_main_relative2'] for r in available]))) for name in CANDIDATES[:2]})
    return dict(schema='quality_frozen_fusion_rescore_v1', source_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        package_source_sha=data['main_sha'], candidate_configs={name:frozen['candidates'][name] for name in CANDIDATES},
        method='Fixed existing full-pool endpoint; no fusion recomputation or per-k trajectory. Automatic and assisted are distinct versions, not independent samples.',
        projection='ERP1024x512 continuous x/W,y/H via existing reconstruct; camera height one; no reorder or coordinate correction',
        qualification='All scores diagnostic. Numeric availability does not certify scope, reference validity, semantics, independence or worker eligibility.',
        reference_rule='Unique exact image_id to reference_object_id from calibration922; missing/ambiguous -> null. Never choose a higher-scoring reference.',
        sampling=dict(spherical_samples=2048,height_samples=4096), projection_checks=checks,
        summary=summaries, whole_pool_failures=read(folder/'failures.json'), rows=results)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--package',type=Path,default=PACKAGE);parser.add_argument('--out',type=Path,default=OUT/'fusion_rescore.json')
    args=parser.parse_args();result=run(args.package)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(result['summary'],ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
