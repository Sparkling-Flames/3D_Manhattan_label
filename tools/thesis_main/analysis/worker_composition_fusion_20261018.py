"""真实v1修订输入的有界成员组合重放；历史输出只读，评分与资格不变。"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import itertools
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
from shapely.ops import unary_union

from . import wall_consensus_v1_process_20261017 as base
from .wall_consensus_population_20261014 import compare_outputs, footprint, summarize_state, transition
from .wall_consensus_quality_20261015 import measured, save
from .quality_b8l2_d10_20261017 import dual_scores, read
from .wall_consensus_b8l2_20261016 import COMPONENTS, finite
from .research_round_20260929 import prepare_record, reconstruct
from .scope_quality_scoring_20261016 import scoring_engine
from ..data_prep.consolidate_research_input import load_current_bundle
from ..data_prep.project_public_research_20260929 import project_bundle

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'research/fusion/worker_composition_fusion_20261018'
PRIOR_COMPOSITION = OUT
OLD = ROOT/'research/fusion/wall_consensus_v1_process_20261017'
INPUT = ROOT/'research/data/processed_input_review_20261018/manifest.json'
RECOVERY_IMAGE = 'rPc6DW4iMge-22'
GEOMETRY_FIELDS = ('id', 'worker', 'points', 'source_pair_indices', 'ring_confirmed', 'order_used')


def changed_records(old, current):
    before = {r['id']: r for r in old['records']}
    return {r['id'] for r in current['records']
            if r['id'] not in before or any(r.get(k) != before[r['id']].get(k) for k in GEOMETRY_FIELDS)}


def compatible_states(states, changed):
    return {key: value for key, value in states.items() if not changed.intersection(key.split('|'))}


def same_measurement_reference(old, current):
    return old['reference'] == current['reference']


def resolve_members(request, records):
    workers = request['worker_ids']
    if len(set(workers)) != len(workers):
        raise ValueError('duplicate_requested_worker')
    lookup = {r['worker_id']: r for r in records}
    if not workers or not set(workers) <= set(lookup):
        raise ValueError('missing_requested_worker')
    if len(workers) != int(request['k']):
        raise ValueError('request_k_differs_from_member_count')
    selected = [lookup[w] for w in sorted(workers)]
    return selected, '|'.join(sorted(r['id'] for r in selected))


def quality_flags(im, selected):
    same_target = all(r['chosen_target_id'] == im['reference']['target_id'] for r in selected)
    allowed = im['layer'] != 'oos_diagnostic' and same_target and all(r['quality_usable'] for r in selected)
    main = allowed and not any(r['original_holdout'] for r in selected) and im['layer'] in ('ordinary', 'doorway_conditional')
    return same_target, allowed, main


def single_exchange_meta(a, b):
    if (a['image_code'], a.get('condition', 'manual'), a['k']) != (b['image_code'], b.get('condition', 'manual'), b['k']):
        raise ValueError('exchange_requires_same_pool_and_k')
    wa, wb = set(a['worker_ids']), set(b['worker_ids'])
    if len(wa) != a['k'] or len(wb) != b['k'] or len(wa & wb) != a['k']-1:
        raise ValueError('exchange_requires_exactly_single_person_replacement')
    for request in (a, b):
        if 'background_worker_ids' in request:
            background = request['background_worker_ids']
            if (len(background) != a['k']-1 or set(background) != wa & wb or request['entrant_worker_id'] in background
                    or set(request['worker_ids']) != set(background) | {request['entrant_worker_id']}):
                raise ValueError('exchange_background_metadata_mismatch')
    return dict(shared_workers=len(wa & wb), outgoing_worker=next(iter(wa-wb)), incoming_worker=next(iter(wb-wa)))


def canonical_ring(points):
    rows = tuple(tuple(row) for row in points)
    variants = [rows[i:]+rows[:i] for i in range(len(rows))]
    reverse = tuple(reversed(rows))
    variants += [reverse[i:]+reverse[:i] for i in range(len(reverse))]
    return min(variants)


def geometry_content_comparison(a, b):
    """严格坐标相等，无数值容差；节点内容和最终连接分别判断。"""
    def signatures(state):
        candidate = state['candidate']
        floor = candidate['footprint']
        floor_key = canonical_ring(floor) if footprint(floor) is not None else None
        points = candidate['points']
        full_key = None
        if floor_key is not None and len(floor) >= 4 and points is not None and candidate['geometry_status'] == 'ok':
            rows = [list(xz)+[points[2*i][0] % 1024, points[2*i][1], points[2*i+1][0] % 1024, points[2*i+1][1]]
                    for i, xz in enumerate(floor)]
            full_key = canonical_ring(rows)
        nodes = state['node_consensus']['nodes']
        node_key = tuple(sorted((n['points'][0][0] % 1024, n['points'][0][1],
                                 n['points'][1][0] % 1024, n['points'][1][1]) for n in nodes)) if nodes else None
        return floor_key, full_key, node_key
    first, second = signatures(a), signatures(b)
    return {name: x == y if x is not None and y is not None else None
            for name, x, y in zip(('floor_geometry_equal', 'full_geometry_equal', 'node_content_equal'), first, second)}


def prepare(request_path=None, include_recovery=True, request_family='fine_composition'):
    prior = read(OLD/'input_snapshot.json')
    bundle = load_current_bundle(INPUT)
    projected, aliases = project_bundle(bundle)
    objects = {o['object_id']: o for o in bundle['data']['objects']}
    sources = {r['id']: r for im in projected['images'] for r in im['annotations']}
    reassessments = {r['object_id']: r for r in read(INPUT.parent/'quality_reassessment.json')}
    requests, paths, comparisons = [], [], []
    if request_path:
        payload = read(request_path)
        requests = [dict(r, request_family=request_family) for r in payload['requests']]
        comparisons = payload.get('comparisons', [])
        save(OUT/'request_inputs/source_requests.json', payload)
    if include_recovery:
        old_requests = read(ROOT/'research/workers/worker_v1_composition_20261017/TEAM_REQUESTS.json')
        recovery = [dict(r, request_family='recovery', scheme='prior_worker_policies', composition='',
                         draw_id='', order_id='', step_k=r['k'])
                    for r in old_requests['teams'] if r['image_code'] == RECOVERY_IMAGE]
        assert len(recovery) == 242
        requests += recovery
        requests.append(dict(request_id='RECOVERY_R01424_SINGLE', request_family='repaired_individual',
                             image_code=RECOVERY_IMAGE, condition='manual', worker_ids=['W002'], k=1))
        paths = [r for r in old_requests['paths'] if r['image_code'] == RECOVERY_IMAGE]
        recovery_pool = next(im for im in prior['images'] if im['image'] == RECOVERY_IMAGE and im['condition'] == 'manual')
        random = np.random.default_rng(base.SEED)
        for repeat in range(4):
            workers = random.permutation(sorted(r['worker_id'] for r in recovery_pool['records'])).tolist()
            ids = []
            for k in range(1, len(workers)+1):
                rid = f'RECOVERY_RANDOM_{repeat}_{k:02d}'
                ids.append(rid)
                requests.append(dict(request_id=rid, request_family='recovery_random_baseline', image_code=RECOVERY_IMAGE,
                     condition='manual', worker_ids=workers[:k], k=k, scheme='prior_random_baseline', composition='',
                     draw_id=repeat, order_id='', step_k=k))
            paths.append(dict(path_id=f'random_{repeat}', prefix_request_ids=ids, family='recovery_random_baseline'))
    wanted = {(r['image_code'], r.get('condition', 'manual')) for r in requests}
    images, changes = [], []
    for im in prior['images']:
        if (im['image'], im['condition']) not in wanted:
            continue
        old = json.loads(json.dumps(im))
        for r in im['records']:
            obj = objects[r['object_id']]
            source = sources[aliases['records'][r['object_id']]]
            fresh = prepare_record(dict(source, source_pair_indices=obj['ordered_source_pair_indices']))
            # 几何修订不自行恢复参考绑定、质量资格或历史留出。
            for key in fresh:
                r[key] = fresh[key]
            if r['object_id'] in reassessments:
                reviewed = reassessments[r['object_id']]
                r['chosen_target_id'] = reviewed['binding']['chosen_target_id']
                r['quality_usable'] = reviewed['policy']['quality_usable']
                r['binding_status'] = reviewed['binding']['binding_status']
                r['quality_exclusion_reasons'] = reviewed['policy']['quality_exclusion_reasons']
        changed = changed_records(old, im)
        if changed:
            changes.append(dict(pool_id=im['pool_id'], changed_record_ids=sorted(changed)))
        images.append(im)
    assert len(images) == len(wanted), 'requested_pool_not_in_existing_admitted_inventory'
    assert len({r['request_id'] for r in requests}) == len(requests), 'duplicate_request_id'
    for r in requests:
        r.setdefault('condition', 'manual')
        r['pool_id'] = r['image_code']+'__'+r['condition']
        im = next(im for im in images if im['pool_id'] == r['pool_id'])
        resolve_members(r, im['records'])
    request_lookup = {r['request_id']: r for r in requests}
    for pair in comparisons:
        single_exchange_meta(request_lookup[pair['request_a']], request_lookup[pair['request_b']])
    save(OUT/'input_snapshot.json', dict(data_release='v1', analysis_revision=OUT.name,
         input_manifest=str(INPUT.relative_to(ROOT)), old_snapshot=str((OLD/'input_snapshot.json').relative_to(ROOT)),
         images=images, coordinate_changes=changes, fusion_gap=base.WORKING_GAP,
         score_policy='unchanged B8L2/D10; N1 not applied; reference and quality gates preserved'))
    save(OUT/'requests.json', dict(requests=requests, recovery_paths=paths, comparisons=comparisons))
    if include_recovery:
        save(OUT/'repaired_individual_score.json', dict(source=str((INPUT.parent/'quality_reassessment.json').relative_to(ROOT)),
             records=list(reassessments.values()), usage='direct individual score against pre-score bound target; diagnostic only'))
    print({'prepared_pools': len(images), 'requests': len(requests), 'changes': changes}, flush=True)


def load_cache(im):
    old = next(x for x in read(OLD/'input_snapshot.json')['images'] if x['pool_id'] == im['pool_id'])
    changed = changed_records(old, im)
    states, scores, origins = {}, {}, {}
    sources = [(OLD, old)]
    if PRIOR_COMPOSITION != OUT:
        prior = next((x for x in read(PRIOR_COMPOSITION/'input_snapshot.json')['images'] if x['pool_id'] == im['pool_id']), None)
        if prior is not None:
            sources.append((PRIOR_COMPOSITION, prior))
    sources.append((OUT, im))
    for root, source_im in sources:
        directory = root/'pools'/im['pool_id']
        path = directory/'states.json.gz'
        if not path.exists():
            continue
        payload = json.load(gzip.open(path, 'rt', encoding='utf-8'))
        invalid = changed_records(source_im, im)
        accepted = compatible_states({r['subset']: r['automatic'] for r in payload['states']}, invalid)
        states.update(accepted)
        if root != OUT:
            origins.update({key: str(path.relative_to(ROOT)) for key in accepted})
        else:
            for row in payload['states']:
                key = row['subset']
                if key in accepted and key not in origins:
                    origin = row.get('origin', 'new_actual_subset_replay')
                    origins[key] = 'new_actual_subset_replay' if origin.startswith(str(OUT.relative_to(ROOT))) else origin
        score_path = directory/'score_cache.json'
        if score_path.exists() and same_measurement_reference(source_im, im):
            cached = read(score_path)
            if directory.is_relative_to(OUT) and cached['context'] != base.measurement_context(im):
                raise ValueError('current_cache_input_context_changed')
            scores.update({key: value for key, value in cached['measurements'].items() if key in accepted})
    return states, scores, origins, changed


def run_pool(im, requests, output_root=None):
    global OUT
    if output_root is not None:
        OUT = Path(output_root)
    started = time.monotonic()
    target = OUT/'pools'/im['pool_id']
    target.mkdir(parents=True, exist_ok=True)
    cache, scores, origins, changed = load_cache(im)
    initial = set(cache)
    records = im['records']
    polygons = [footprint(reconstruct(r, coordinate_convention='continuous')['floor']) for r in records]
    valid = [p for p in polygons if p is not None]
    union = unary_union(valid).area if valid else None
    distances = np.full((len(records), len(records)), np.nan)
    for i, j in itertools.combinations(range(len(records)), 2):
        if polygons[i] is not None and polygons[j] is not None:
            distances[i, j] = distances[j, i] = polygons[i].symmetric_difference(polygons[j]).area
    indices = {r['id']: i for i, r in enumerate(records)}
    ref = im['reference']
    reference = dict(floor=ref['floor_xz_h'], points=ref['points_1024x512'] if ref['full_reference_available'] else None)
    results, used = [], set()
    with base.cached_matching(), scoring_engine(base.ENGINE/'measurement_engine.zip', base.ENGINE/'working_models.py') as (engine, models):
        for request in requests:
            selected, key = resolve_members(request, records)
            state = base.selected_state(selected, cache)
            used.add(key)
            if key not in scores:
                raw = measured(engine, state, reference)
                dual = dual_scores(raw, models) if finite(raw, COMPONENTS) else {'B8L2': None, 'D10': None}
                scores[key] = dict(raw, diagnostic_B8L2=dual['B8L2'], diagnostic_D10=dual['D10'])
            score = scores[key]
            same_target, quality, main = quality_flags(im, selected)
            times = [r['source_time_seconds'] for r in selected]
            known_time = all(t is not None and t != '' and np.isfinite(float(t)) for t in times)
            known_source = [float(t) for t in times if t is not None and t != '' and np.isfinite(float(t))]
            target_times = [r.get('target_time_seconds') for r in selected]
            known_target = [float(t) for t in target_times if t is not None and t != '' and np.isfinite(float(t))]
            meta = {k: v for k, v in request.items() if not isinstance(v, (list, dict))}
            results.append(dict(meta, data_release='v1', execution_status='returned', image=im['image'], image_id=im['image_id'], building=im['building'],
                layer=im['layer'], difficulty=im['difficulty'], scene=im['scene'],
                member_workers='|'.join(sorted(request['worker_ids'])), ordered_workers='|'.join(request['worker_ids']),
                member_records=key, member_object_ids='|'.join(sorted(r['object_id'] for r in selected)), subset=key,
                subset_origin=origins.get(key, 'new_actual_subset_replay'),
                geometry_source=str((target/'states.json.gz').relative_to(ROOT)), geometry_state_pointer=key,
                reference_id=ref['target_id'], reference_version=ref['reference_version'],
                full_reference_available=ref['full_reference_available'], same_target=same_target,
                quality_allowed=quality, main_comparison_allowed=main,
                quality_missing_member_n=sum(not r['quality_usable'] for r in selected),
                original_holdout_member_n=sum(r['original_holdout'] for r in selected),
                source_time_available=known_time, source_active_seconds=sum(float(t) for t in times) if known_time else None,
                source_time_known_sum=sum(known_source) if known_source else None,
                source_time_missing_n=len(selected)-len(known_source),
                target_time_known_sum=sum(known_target) if known_target else None,
                target_time_missing_n=len(selected)-len(known_target),
                **summarize_state(state), **base.original_disagreement([indices[r['id']] for r in selected], distances, union),
                **score, B8L2=score['diagnostic_B8L2'] if quality else None, D10=score['diagnostic_D10'] if quality else None))
            if len(results) % 50 == 0:
                print(im['pool_id'], len(results), '/', len(requests), 'elapsed', round(time.monotonic()-started, 1), flush=True)
    pd.DataFrame(results).to_csv(target/'team_results.csv', index=False, encoding='utf-8-sig')
    with gzip.open(target/'states.json.gz', 'wt', encoding='utf-8') as f:
        json.dump(dict(pool_id=im['pool_id'], states=[dict(subset=key, automatic=cache[key],
             origin=origins.get(key, 'new_actual_subset_replay')) for key in sorted(used)]), f, ensure_ascii=False, allow_nan=False)
    save(target/'score_cache.json', dict(context=base.measurement_context(im), measurements={key: scores[key] for key in sorted(used)}))
    save(target/'original_pair_disagreement.json', dict(record_ids=[r['id'] for r in records], union_h2=union,
         valid_polygons=len(valid), pair_symdiff_h2=distances))
    status = dict(pool_id=im['pool_id'], requests=len(results), unique_subsets=len(used),
                  reused_subsets=len(used & initial), new_subsets=len(used-initial),
                  historical_v1_geometry_reused=sum(origins.get(key, '').startswith(str(OLD.relative_to(ROOT))) for key in used),
                  previous_composition_geometry_reused=sum(origins.get(key, '').startswith(str(PRIOR_COMPOSITION.relative_to(ROOT))) for key in used),
                  current_revision_actual_subsets=sum(origins.get(key, 'new_actual_subset_replay') == 'new_actual_subset_replay' for key in used),
                  changed_record_ids=sorted(changed), elapsed_seconds=time.monotonic()-started)
    save(target/'DONE.json', status)
    return status


def aggregate():
    payload = read(OUT/'requests.json')
    frames, states, completion = [], {}, []
    for im in read(OUT/'input_snapshot.json')['images']:
        directory = OUT/'pools'/im['pool_id']
        if not (directory/'DONE.json').exists():
            continue
        frames.append(pd.read_csv(directory/'team_results.csv', keep_default_na=False))
        completion.append(read(directory/'DONE.json'))
        states[im['pool_id']] = {r['subset']: r['automatic'] for r in json.load(gzip.open(directory/'states.json.gz', 'rt', encoding='utf-8'))['states']}
    if not frames:
        return
    frame = pd.concat(frames, ignore_index=True)
    frame.to_csv(OUT/'team_results.csv', index=False, encoding='utf-8-sig')
    frame.drop_duplicates(['pool_id', 'subset']).to_csv(OUT/'unique_teams.csv', index=False, encoding='utf-8-sig')
    comparisons, between, transitions = [], [], []
    fine = frame[frame.request_family.eq('fine_composition')]
    if len(fine):
        for group, rows in fine.groupby(['pool_id', 'scheme', 'composition', 'k'], dropna=False):
            rows = rows.drop_duplicates('subset')
            for a, b in itertools.combinations(rows.to_dict('records'), 2):
                if int(a['k']) != 4:
                    continue
                pa, pb = states[group[0]][a['subset']], states[group[0]][b['subset']]
                comparisons.append(dict(pool_id=group[0], scheme=group[1], composition=group[2], k=group[3],
                    request_a=a['request_id'], request_b=b['request_id'], subset_a=a['subset'], subset_b=b['subset'],
                    shared_workers=len(set(a['member_workers'].split('|')) & set(b['member_workers'].split('|'))),
                    both_quality=a['B8L2'] != '' and b['B8L2'] != '',
                    both_main=bool(a['main_comparison_allowed'] and b['main_comparison_allowed']),
                    **compare_outputs(pa, pb)))
        fixed = fine[fine.experiment.eq('fixed_k_composition_and_members')]
        for group, rows in fixed.groupby(['pool_id', 'scheme', 'k']):
            rows = rows.drop_duplicates('subset')
            for a, b in itertools.combinations(rows.to_dict('records'), 2):
                if a['composition'] == b['composition']:
                    continue
                pa, pb = states[group[0]][a['subset']], states[group[0]][b['subset']]
                between.append(dict(pool_id=group[0], scheme=group[1], k=group[2],
                    composition_a=a['composition'], composition_b=b['composition'],
                    request_a=a['request_id'], request_b=b['request_id'], subset_a=a['subset'], subset_b=b['subset'],
                    shared_workers=len(set(a['member_workers'].split('|')) & set(b['member_workers'].split('|'))),
                    both_quality=a['B8L2'] != '' and b['B8L2'] != '',
                    both_main=bool(a['main_comparison_allowed'] and b['main_comparison_allowed']),
                    **compare_outputs(pa, pb)))
    lookup = frame.set_index('request_id').to_dict('index')
    request_lookup = {r['request_id']: r for r in payload['requests']}
    exchanges = []
    for pair in payload.get('comparisons', []):
        ra, rb = pair['request_a'], pair['request_b']
        if ra not in lookup or rb not in lookup:
            continue
        a, b = lookup[ra], lookup[rb]
        exchange = single_exchange_meta(request_lookup[ra], request_lookup[rb])
        pa, pb = states[a['pool_id']][a['subset']], states[b['pool_id']][b['subset']]
        differences = {key+'_difference': float(b[key])-float(a[key]) if a[key] != '' and b[key] != '' else None
                       for key in ('B8L2', 'D10', 'diagnostic_B8L2', 'diagnostic_D10', 'R_union_normalized',
                                   'omission', 'extension', 'source_active_seconds')}
        exchanges.append(dict(pair, pool_id=a['pool_id'], image=a['image'], building=a['building'],
            layer=a['layer'], scheme=a['scheme'], k=a['k'], subset_a=a['subset'], subset_b=b['subset'],
            both_quality=a['B8L2'] != '' and b['B8L2'] != '',
            both_main=bool(a['main_comparison_allowed'] and b['main_comparison_allowed']),
            both_complete=bool(a['complete_evaluable'] and b['complete_evaluable']),
            nodes_a=a['nodes'], nodes_b=b['nodes'], nodes_signed_difference=b['nodes']-a['nodes'],
            **exchange, **differences, **compare_outputs(pa, pb), **geometry_content_comparison(pa, pb)))
    paths = [{'path_id': p['path_id'], 'request_ids': p['prefix_request_ids'], 'family': p.get('family', 'recovery')} for p in payload['recovery_paths']]
    if len(fine) and 'order_id' in fine:
        for order, rows in fine[fine.order_id.ne('')].groupby('order_id'):
            paths.append(dict(path_id=order, request_ids=rows.sort_values('step_k').request_id.tolist(), family='fine_composition'))
    for path in paths:
        for ra, rb in zip(path['request_ids'], path['request_ids'][1:]):
            if ra not in lookup or rb not in lookup:
                continue
            a, b = lookup[ra], lookup[rb]
            pa, pb = states[a['pool_id']][a['subset']], states[b['pool_id']][b['subset']]
            transitions.append(dict(path_id=path['path_id'], family=path['family'], pool_id=a['pool_id'],
                 request_a=ra, request_b=rb, k_from=a['k'], k_to=b['k'],
                 **transition(pa, pb), **{k: v for k, v in compare_outputs(pa, pb).items() if k.startswith('floor_')}))
    if len(fine):
        pd.DataFrame(comparisons).to_csv(OUT/'same_composition_pairs.csv', index=False, encoding='utf-8-sig')
        pd.DataFrame(between).to_csv(OUT/'between_composition_pairs.csv', index=False, encoding='utf-8-sig')
    if len(fine) or payload['recovery_paths']:
        pd.DataFrame(transitions).to_csv(OUT/'transitions.csv', index=False, encoding='utf-8-sig')
    if payload.get('comparisons'):
        pd.DataFrame(exchanges).to_csv(OUT/'exchange_pairs.csv', index=False, encoding='utf-8-sig')
    summaries = []
    for family, rows in frame.groupby('request_family'):
        summaries.append(dict(family=family, requests=len(rows), images=rows.image.nunique(), buildings=rows.building.nunique(),
            unique_teams=len(rows.drop_duplicates(['pool_id', 'subset'])), complete_geometry=int(rows.complete_evaluable.sum()),
            numeric_scores=int(rows.diagnostic_B8L2.ne('').sum()), quality_scores=int(rows.B8L2.ne('').sum()),
            main_quality_scores=int((rows.B8L2.ne('') & rows.main_comparison_allowed).sum()),
            two_person_deferred=int(rows.score_status.eq('two_person_deferred').sum())))
    status = dict(data_release='v1', requested=len(payload['requests']), returned=len(frame),
        missing_request_ids=sorted({r['request_id'] for r in payload['requests']}-set(frame.request_id)),
        families=summaries, completed_pools=completion, same_composition_pairs=len(comparisons),
        between_composition_pairs=len(between), transitions=len(transitions),
        requested_exchange_pairs=len(payload.get('comparisons', [])), returned_exchange_pairs=len(exchanges),
        source_manifest=str(INPUT.relative_to(ROOT)), old_results_overwritten=False, N1_applied=False)
    save(OUT/'STATUS.json', status)
    print(status, flush=True)


def verify():
    """核验真实请求覆盖、几何绑定、用途和两个现场重算；不把NaN当通过。"""
    payload = read(OUT/'requests.json')
    requests = {r['request_id']: r for r in payload['requests']}
    images = {im['pool_id']: im for im in read(OUT/'input_snapshot.json')['images']}
    frame = pd.read_csv(OUT/'team_results.csv', keep_default_na=False)
    assert frame.request_id.is_unique and set(frame.request_id) == set(requests)
    states = {pool: {r['subset']: r['automatic'] for r in json.load(gzip.open(OUT/'pools'/pool/'states.json.gz', 'rt', encoding='utf-8'))['states']}
              for pool in images}
    for row in frame.to_dict('records'):
        request = requests[row['request_id']]
        im = images[row['pool_id']]
        selected, key = resolve_members(request, im['records'])
        assert row['subset'] == key and row['geometry_state_pointer'] == key
        assert row['member_workers'] == '|'.join(sorted(request['worker_ids']))
        assert row['reference_id'] == im['reference']['target_id']
        assert int(row['k']) == states[row['pool_id']][key]['n']
        assert tuple(row[k] for k in ('same_target', 'quality_allowed', 'main_comparison_allowed')) == quality_flags(im, selected)
        assert (row['B8L2'] != '') == (row['D10'] != '')
        if not row['quality_allowed']:
            assert row['B8L2'] == '' and row['D10'] == ''
        assert row['data_release'] == 'v1'
        assert row['source_time_available'] == (row['source_time_missing_n'] == 0)
        assert 0 <= row['source_time_missing_n'] <= row['k']
        assert 0 <= row['target_time_missing_n'] <= row['k']
        for name in ('B8L2', 'D10', 'diagnostic_B8L2', 'diagnostic_D10'):
            if row[name] != '':
                assert np.isfinite(float(row[name])) and 0 <= float(row[name]) <= 100
    fresh_checks = []
    for layer in ('ordinary', 'doorway_conditional'):
        candidates = frame[(frame.request_family.isin(['fine_composition', 'exchangeability'])) & (frame.layer == layer)]
        if candidates.empty:
            continue
        row = candidates.sort_values('k', ascending=False).iloc[0]
        selected, key = resolve_members(requests[row.request_id], images[row.pool_id]['records'])
        with base.cached_matching():
            fresh = base.selected_state(list(reversed(selected)), {})
        stored = states[row.pool_id][key]
        assert fresh == stored
        fresh_checks.append(dict(pool_id=row.pool_id, request_id=row.request_id, reversed_fresh_full_state_equal=True))
    exchange_checks = []
    if payload.get('comparisons'):
        pairs = pd.read_csv(OUT/'exchange_pairs.csv', keep_default_na=False).set_index('comparison_id')
        assert pairs.index.is_unique and set(pairs.index) == {p['comparison_id'] for p in payload['comparisons']}
        for pair in payload['comparisons']:
            expected = single_exchange_meta(requests[pair['request_a']], requests[pair['request_b']])
            actual = pairs.loc[pair['comparison_id']]
            assert all(actual[key] == value for key, value in expected.items())
        exchange_checks = dict(pairs=len(pairs), all_same_k_pool_and_exactly_one_replacement=True)
    result = dict(status='passed', request_ids_checked=len(frame), unique_geometries=sum(len(s) for s in states.values()),
        request_geometry_reference_time_and_usage_bindings_checked=True, fresh_reversed_checks=fresh_checks,
        exchange_checks=exchange_checks,
        numerical_model='unchanged B8L2/D10; no N1', limits='finite selected pools; not human certification of wall identity')
    save(OUT/'CHECKS.json', result)
    print(result, flush=True)


def main():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['prepare', 'run', 'aggregate', 'verify'])
    parser.add_argument('--requests', type=Path)
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--pool')
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--request-family', choices=['fine_composition', 'exchangeability'], default='fine_composition')
    parser.add_argument('--skip-recovery', action='store_true')
    args = parser.parse_args()
    OUT = args.out.resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.stage == 'prepare':
        prepare(args.requests, include_recovery=not args.skip_recovery, request_family=args.request_family)
        return
    if args.stage == 'verify':
        verify()
        return
    if args.stage == 'run':
        requests = read(OUT/'requests.json')['requests']
        images = read(OUT/'input_snapshot.json')['images']
        images = [im for im in images if not args.pool or im['pool_id'] == args.pool]
        with ProcessPoolExecutor(max_workers=args.jobs) as executor:
            futures = {executor.submit(run_pool, im, [r for r in requests if r['pool_id'] == im['pool_id']], OUT): im['pool_id'] for im in images}
            for future in as_completed(futures):
                print(future.result(), flush=True)
    aggregate()


if __name__ == '__main__':
    main()
