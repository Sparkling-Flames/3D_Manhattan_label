"""Read-only v1 adapter, separate from historical simulator input contracts."""
from __future__ import annotations
import csv
import json
from pathlib import Path
import numpy as np

from . import simulate_annotators as base
from .difficulty_wild_sampler import load_difficulty, manual_counts
from .simulator_personality_inputs import estimate_axis, checked_points
from .simulate_annotators_opt import normalize_worker_id
from .personality_response_channels import EVIDENCE, positive

COMMIT = '1bbcf8ad6a5aa3a30be1b4f4e0249a62e02d79c8'
DEFAULT_INPUT = base.ROOT.parent / 'output/difficulty_wild_35_20261017/inputs'
DIFFICULTY = 'research/difficulty/difficulty_b8l2_handoff_20261016'
QUALITY = 'research/quality/quality_b8l2_d10_20261017'
WORKERS = 'research/workers/worker_b8l2_d10_20261017'
QUALITY_VERSION = 'WQ-B8L2-20261015'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def csv_rows(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def load_inputs(directory=DEFAULT_INPUT):
    directory = Path(directory)
    manifest = read(directory / 'frozen_manifest.json')
    if manifest['commit'] != COMMIT:
        raise ValueError('unexpected_frozen_commit')
    for name, digest in manifest['files'].items():
        if base.digest(directory / name) != digest:
            raise ValueError('frozen_input_changed:' + name)
    difficulty = load_difficulty(directory / DIFFICULTY / 'image_inventory.csv')
    shared = csv_rows(directory / QUALITY / 'shared_records.csv')
    if len(difficulty) != 259 or len(shared) != 3222 or len({r['image_id'] for r in shared}) != 261:
        raise ValueError('frozen_population_mismatch')
    data = read(directory / 'analysis_results/research_input_20261017/data.json')
    objects = {o['object_id']: o for o in data['objects']}
    qpanel = csv_rows(directory / WORKERS / 'quality_panel.csv')
    time_panel = csv_rows(directory / WORKERS / 'T_source_panel.csv')
    time_by = {r['object_id']: r for r in time_panel}
    for r in shared:
        o = objects[r['object_id']]
        if any(str(o[k]) != r[k] for k in ('image_id', 'worker_id', 'condition')):
            raise ValueError('v1_inventory_identity_mismatch:' + r['object_id'])
    records = []
    for r in qpanel:
        if r['profile_allowed'] != 'True' or r['condition'] != 'manual' or r['admission_original_holdout'] != 'False':
            raise ValueError('unapproved_quality_training_record')
        o = objects[r['object_id']]; pts = checked_points(o)
        if pts is None:
            raise ValueError('approved_training_geometry_missing:' + r['object_id'])
        t = time_by.get(r['object_id'])
        records.append(dict(annotation_id=r['object_id'], record_id=r['record_id'],
            worker_id=normalize_worker_id(r['worker_id']), image_id=r['image_id'], building_id=r['building_id'],
            points=pts, B8L2=float(r['B8L2']), D10=float(r['D10']),
            reference_id=r['reference_id'], quality_version=QUALITY_VERSION,
            active_time_seconds=float(t['source_active_time_seconds']) if t else None,
            time_context=r['image_id']))
    _, models, images, _ = base.load_inputs()
    supplements = []
    # User-authorized read-only index of existing ep300 replay outputs.
    for iid in difficulty:
        if not models.get(iid):
            paths = sorted((base.ROOT / 'analysis_results').glob('model_initialization_*_ep300_replay_20260823_v1/prediction_txt/' + iid + '.layout.txt'))
            if len(paths) != 1:
                raise ValueError('supplemental_model_not_unique:' + iid)
            p = paths[0]; pts = np.loadtxt(p).tolist()
            if not base.parsed(pts):
                raise ValueError('supplemental_model_unparseable:' + iid)
            models[iid] = {'HoHoNet': dict(name='HoHoNet', layout_id='supplemental_ep300:' + iid,
                                         points=pts, source=str(p.relative_to(base.ROOT)))}
            supplements.append(dict(image_id=iid, family='HoHoNet', source=str(p.relative_to(base.ROOT)), sha256=base.digest(p)))
        if iid not in images:
            source = next(r for r in shared if r['image_id'] == iid)
            raw_path = base.ROOT / source['source_path']
            tasks = read(raw_path)
            task = next(t for t in tasks if str(t['id']) == source['runtime_task_id'])
            images[iid] = dict(image_id=iid, building_id=source['building_id'], image_url=task['data']['image'])
    missing = [iid for iid in difficulty if iid not in images or not models.get(iid)]
    if missing:
        raise ValueError('missing_frozen_model_or_image:' + ','.join(missing))
    refs = read(directory / QUALITY / 'reference_catalog.json')
    reference_by = {r['target_id']: r for r in refs}
    v6_refs = {r['target_id']: r for r in read(directory / DIFFICULTY / 'reference_catalog_snapshot.json')}
    pending = {r['image']: r for r in read(directory / DIFFICULTY / 'pending_scope_audit.json')['records']}
    scope = csv_rows(directory / WORKERS / 'scope_response_evidence.csv')
    for row in scope:
        if row['worker_scope'] == 'out_of_scope':
            row['worker_scope'] = 'oos'
        if row['worker_scope'] not in ('in_scope', 'oos'):
            raise ValueError('unknown_scope_response')
    lead_by = {r['canonical_annotation_id']: r for r in csv_rows(EVIDENCE / 'record_evidence.csv')}
    times = []
    for r in time_panel:
        raw = lead_by.get(r['object_id'])
        if raw is None or raw['lead_time_status'] != 'available' or positive(raw['lead_time_seconds']) is None:
            continue
        if any(str(raw[k]) != str(r[k]) for k in ('image_id', 'project_id', 'runtime_task_id', 'raw_annotation_id')):
            raise ValueError('lead_time_source_identity_mismatch')
        times.append(dict(annotation_id=r['object_id'], worker_id=normalize_worker_id(r['worker_id']),
            building_id=r['building_id'], active_time_seconds=float(r['source_active_time_seconds']),
            lead_time_seconds=float(raw['lead_time_seconds']), lead_time_is_active_time=raw['time_lead_time_is_active_time'] == 'True',
            time_source=r['time_source'], time_context=r['context_key'], weight=1.))
    return dict(directory=directory, manifest=manifest, difficulty=difficulty, shared=shared,
                records=records, objects=objects, models=models, images=images,
                counts=manual_counts(shared), references=reference_by, v6_references=v6_refs,
                pending=pending, scope=scope, time_panel=time_panel, times=times, supplements=supplements)


def fit_profiles(records, building):
    training = [r for r in records if r['building_id'] != building]
    axes = {k: estimate_axis(training, k, log=k == 'active_time_seconds')
            for k in ('B8L2', 'D10', 'active_time_seconds')}
    result = {}
    for worker in sorted({r['worker_id'] for r in training}, key=int):
        q = axes['B8L2'].get(worker, {}); d = axes['D10'].get(worker, {}); t = axes['active_time_seconds'].get(worker, {})
        quality = ('higher' if q['effect'] > 0 else 'lower') if q.get('supported') and q.get('effect') else 'uncertain'
        speed = ('faster' if t['effect'] < 0 else 'slower') if t.get('supported') and t.get('effect') else 'uncertain'
        result[worker] = dict(worker_id=worker, quality=quality, speed=speed, prototype=quality + ':' + speed,
            axes=dict(quality=q, sensitivity=d, time=t), quality_version=QUALITY_VERSION,
            quality_reason=None if quality != 'uncertain' else 'insufficient_training_support',
            training_buildings=sorted({r['building_id'] for r in training if r['worker_id'] == worker}))
    return result
