"""Read-only gallery adapter and explicitly ordered empirical difficulty."""
from __future__ import annotations

import collections
import csv
import hashlib
import itertools
import json
from pathlib import Path
import re

import numpy as np
from scipy.optimize import linear_sum_assignment
from shapely.geometry import Polygon

from . import simulate_annotators as base
from .difficulty_wild_sampler import VALID

VERSION = 'gallery_disagreement_20261017_v1'
BASIS = 'real_annotator_disagreement_empirical'
ROOT = base.ROOT.parent / 'output/difficulty_wild_35_20261017'
GALLERY = base.ROOT.parent / 'label_studio_gallery.html'
V6 = ROOT / 'inputs/research/difficulty/difficulty_b8l2_handoff_20261016/image_inventory.csv'
FIRST = ROOT / 'full'
BANK = base.INPUT / 'models/layouts.jsonl'
DEFAULT_OUTPUT = ROOT / 'round2_gallery_144_20261017'


def parse_gallery(path):
    text = Path(path).read_text(encoding='utf-8-sig')
    match = re.search(r'\bconst\s+DATA\s*=\s*', text)
    if match is None:
        raise ValueError('gallery_DATA_missing')
    data, _ = json.JSONDecoder().raw_decode(text[match.end():])
    tasks, seen = [], set()
    for raw in data['tasks']:
        iid = Path(raw['title']).stem
        building = iid.split('_')[0]
        if iid in seen or not iid or raw['code'].rsplit('-', 1)[0] != building:
            raise ValueError('gallery_duplicate_or_invalid_image:' + iid)
        seen.add(iid)
        if not isinstance(raw['annCount'], int) or raw['annCount'] != len(raw['workers']):
            raise ValueError('gallery_annCount_mismatch:' + iid)
        workers, identities, votes = [], set(), collections.Counter()
        for w in raw['workers']:
            worker = str(w['w'])
            if worker in identities or not worker.isdigit() or w.get('gt') is not False:
                raise ValueError('gallery_worker_or_gt_invalid:' + iid)
            identities.add(worker)
            pixels = np.asarray(w['kps'], dtype=float) * [10.24, 5.12]
            if not base.parsed(pixels):
                raise ValueError('gallery_invalid_coordinates:' + iid + ':' + worker)
            scope = {'in_scope': 'in_scope', 'out_of_scope': 'oos', 'oos': 'oos'}.get(w['scope'])
            if scope is None:
                raise ValueError('unknown_gallery_scope')
            votes['in_scope' if scope == 'in_scope' else 'out_of_scope'] += 1
            lt = w.get('lt')
            lead = float(lt) if isinstance(lt, (int, float)) and np.isfinite(lt) and lt > 0 else None
            aid = 'gallery98:' + hashlib.sha256((iid + ':' + worker).encode()).hexdigest()[:24]
            workers.append(dict(annotation_id=aid, record_id=aid, image_id=iid, building_id=building,
                worker_id=worker, worker_namespace='gallery_project98', source_condition=raw['condition'],
                points=pixels.tolist(), scope=scope, lead_time_seconds=lead, active_time_seconds=None,
                submitted_at=w.get('t'), geometry_status=base.geometry_status(pixels)))
        given = {k: int(raw['scopeVotes'].get(k, 0)) for k in ('in_scope', 'out_of_scope')}
        actual = {k: votes[k] for k in given}
        if actual != given:
            raise ValueError('gallery_scope_votes_mismatch:' + iid)
        tasks.append(dict(image_id=iid, image=raw['code'], building_id=building, image_url=raw['image'],
                          annCount=raw['annCount'], source_condition=raw['condition'], workers=workers,
                          scope_votes=actual))
    return dict(tasks=tasks, stats=data['stats'])


def ordered_distance(a, b):
    """Preserve source indices, including their dependence on ring start."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    n = min(len(a), len(b))
    if n < 2 or n % 2:
        raise ValueError('insufficient_paired_coordinates')
    delta = a[:n] - b[:n]
    delta[:, 0] = (delta[:, 0] + 512) % 1024 - 512
    return float(np.linalg.norm(delta, axis=1).mean())


def disagreement(answers):
    if len(answers) < 2:
        raise ValueError('disagreement_requires_two_answers')
    return float(np.mean([ordered_distance(a, b) for a, b in itertools.combinations(answers, 2)]))


def classify(values):
    values = np.asarray(values, float)
    if not len(values) or not np.isfinite(values).all():
        raise ValueError('nonfinite_disagreement')
    thresholds = np.quantile(values, [1/3, 2/3], method='linear').tolist()
    labels = ['简单' if v <= thresholds[0] else '中等' if v <= thresholds[1] else '困难' for v in values]
    return labels, thresholds


def select_targets(tasks, excluded, expected=True):
    selected = sorted([t for t in tasks if t['image_id'] not in excluded], key=lambda t: t['image_id'])
    if expected:
        counts = collections.Counter(t['annCount'] for t in selected)
        if len(selected) != 144 or counts != {16: 140, 15: 4}:
            raise ValueError('gallery_target_population_mismatch:' + str(counts))
        if sum(35 - t['annCount'] for t in selected) != 2740:
            raise ValueError('gallery_total_need_mismatch')
    values = [disagreement([r['points'] for r in t['workers']]) for t in selected]
    labels, thresholds = classify(values)
    return [dict(t, real_manual_n=t['annCount'], need=35-t['annCount'], difficulty=label,
                 difficulty_basis=BASIS, difficulty_version=VERSION, disagreement_px=v,
                 difficulty_thresholds=thresholds) for t, label, v in zip(selected, labels, values)]


def paired_delta(model, answer):
    """Reuse the existing whole-pair spherical assignment for residual transfer."""
    a = np.asarray(model, float).reshape(-1, 2, 2)
    b = np.asarray(answer, float).reshape(-1, 2, 2)
    ar = base.rays(a.reshape(-1, 2)).reshape(-1, 2, 3)
    br = base.rays(b.reshape(-1, 2)).reshape(-1, 2, 3)
    costs = np.arccos(np.clip(np.einsum('ikd,jkd->ijk', ar, br), -1, 1)).mean(axis=-1)
    ii, jj = linear_sum_assignment(costs)
    delta = b[jj] - a[ii]
    delta[:, :, 0] = (delta[:, :, 0] + 512) % 1024 - 512
    return delta


def image_calibration(target, bank):
    valid = [r for r in target['workers'] if r['geometry_status'] == VALID]
    if not valid:
        raise ValueError('no_usable_target_calibration:' + target['image_id'])
    by_family = {}
    for family in base.FAMILIES:
        model = bank[family]['points']
        delta = [paired_delta(model, r['points']) for r in valid]
        amplitudes = [float(np.sqrt(np.mean(d**2))) for d in delta]
        if max(amplitudes) <= 0:
            raise ValueError('target_calibration_zero_residual')
        component = np.concatenate(delta, axis=0)
        deletes = [min(2, len(model)//2-len(r['points'])//2) for r in target['workers']
                   if len(r['points']) < len(model)]
        by_family[family] = dict(normal_amplitude=np.quantile(amplitudes, [.25, .50]).tolist(),
            wild_amplitude=np.quantile(amplitudes, [.75, .95]).tolist(),
            cap=np.quantile(np.abs(component), .95, axis=0).tolist(),
            missing_frequency=len(deletes)/len(target['workers']), deletion_counts=deletes,
            model_pairs=len(model)//2, calibration_annotation_ids=sorted(r['annotation_id'] for r in valid),
            calibration_building_id=target['building_id'],
            usage='target_image_scalar_statistics_only_no_target_residual_vectors')
    areas = []
    for r in valid:
        rays = base.rays(np.asarray(r['points'])[1::2])
        areas.append(float(Polygon(-rays[:, (0, 2)]/rays[:, 1, None]).area))
    counts = collections.Counter(len(r['points'])//2 for r in target['workers'])
    votes = target['scope_votes']
    return dict(image_id=target['image_id'], families=by_family,
        point_count_distribution={str(k): v for k, v in sorted(counts.items())},
        modal_pair_count=min(counts, key=lambda k: (-counts[k], k)),
        floor_area_quantiles=np.quantile(areas, [.25, .5, .75]).tolist(),
        scope_votes=votes, scope_oos_majority=votes['out_of_scope'] > votes['in_scope'],
        scope_majority='tie' if votes['out_of_scope'] == votes['in_scope'] else
            'oos' if votes['out_of_scope'] > votes['in_scope'] else 'in_scope',
        scope_interpretation='response_votes_and_observed_range_statistics_no_gt_adjudication')


def load_gallery(gallery=GALLERY):
    parsed = parse_gallery(gallery)
    if len(parsed['tasks']) != 378 or sum(t['annCount'] for t in parsed['tasks']) != 5496:
        raise ValueError('gallery_inventory_changed')
    with V6.open(encoding='utf-8-sig') as f:
        excluded = {r['image_id'] for r in csv.DictReader(f)}
    if len(excluded) != 259:
        raise ValueError('v6_inventory_changed')
    targets = select_targets(parsed['tasks'], excluded)
    models = collections.defaultdict(dict)
    for r in base.read_jsonl(BANK):
        if r['source_role'] not in {'offline_ep300_replay', 'offline_dual_prediction'}:
            continue
        family = 'HoHoNet' if r['model_family'] == 'HoHoNet' else 'Bi-' + r['head']
        if family in models[r['image_id']]:
            raise ValueError('duplicate_frozen_model')
        if base.parsed(r['points_1024x512']):
            models[r['image_id']][family] = dict(points=r['points_1024x512'], layout_id=r['layout_id'])
    records = [r for t in parsed['tasks'] for r in t['workers']]
    usable = [r for r in records if r['geometry_status'] == VALID
              and all(f in models.get(r['image_id'], {}) for f in base.FAMILIES)]
    photos = {}
    for t in targets:
        iid = t['image_id']
        paths = sorted((base.ROOT/'data/mp3d_layout').glob('*/img/'+iid+'.png'))
        if len(paths) != 1 or not all(f in models.get(iid, {}) for f in base.FAMILIES):
            raise ValueError('target_model_or_panorama_missing:' + iid)
        photos[iid] = paths[0]
    old_ids = [r['export_worker_id'] for r in base.read_jsonl(FIRST/'simulations.jsonl')]
    if len(old_ids) != 6678 or len(set(old_ids)) != 6678:
        raise ValueError('round1_identity_inventory_changed')
    return dict(gallery=Path(gallery), tasks=parsed['tasks'], targets=targets, records=records,
                usable=usable, models=dict(models), photos=photos, first_ids=set(old_ids))


def source_hashes(sources):
    files = [sources['gallery'], V6, BANK, *sources['photos'].values()]
    files.extend(p for p in FIRST.rglob('*') if p.is_file())
    return {str(p.resolve()): base.digest(p) for p in sorted(set(files))}
