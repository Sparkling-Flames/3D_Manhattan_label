"""Current-input adapter and building-held-out descriptive personnel effects."""
from __future__ import annotations

import collections
import copy
import csv
import json
import math

import numpy as np
import pandas as pd

from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
from tools.thesis_main.analysis import simulate_annotators as base
from tools.thesis_main.analysis.simulate_annotators_opt import normalize_worker_id
from tools.thesis_main.analysis.fit_worker_evidence_strata_20260908 import informative, sufficient, solve

QUALITY_VERSION = 'WQ-LS08-20261014'
JOINT = base.ROOT / 'research/quality_joint_closeout_review_20261015/JOINT_COMPARISON_1145.csv'
INVENTORY = base.ROOT / 'research/worker_classification_progress_20261014/source_inventory.csv'
ADMISSION = base.ROOT / 'research/quality_data_admission_audit_20261013/FULL_ADMISSION.json'


def read_csv(path):
    with open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def truth(value):
    return value is True or str(value).lower() == 'true'


def checked_points(obj):
    """Consume the loader's authorized paired representation; never infer links."""
    if not obj.get('links_zero_based'):
        return None
    points = obj.get('points_1024x512')
    if points is not None and len(obj['links_zero_based']) * 2 != len(points):
        raise ValueError('paired_link_count_mismatch:' + obj['object_id'])
    indices = obj.get('ordered_source_point_indices')
    if indices is not None and (len(indices) != len(points or []) or len(set(indices)) != len(indices)):
        raise ValueError('source_point_identity_mismatch:' + obj['object_id'])
    return copy.deepcopy(points) if points is not None and base.parsed(points) else None


def bind_rows(objects, gates, inventory, joint):
    by_id = {o['object_id']: o for o in objects}
    sources = {r['record_id']: r for r in inventory}
    scores = {r['record_id']: r for r in joint}
    if len(sources) != len(inventory) or len(scores) != len(joint):
        raise ValueError('duplicate_inventory_or_score_identity')
    records, ledger = [], []
    for gate in gates:
        obj = by_id[gate['object_id']]
        inv = sources.get(gate['record_id'])
        score = scores.get(gate['record_id'])
        identity = ('object_id', 'image_id', 'worker_id', 'condition')
        if any(obj[k] != gate[k] for k in identity):
            raise ValueError('current_object_identity_mismatch:' + gate['record_id'])
        for row in (inv, score):
            if row is not None and any(row[k] != gate[k] for k in identity):
                raise ValueError('sidecar_identity_mismatch:' + gate['record_id'])
            if row is not None and row['building_id'] != obj['building_id']:
                raise ValueError('building_identity_mismatch:' + gate['record_id'])
        if inv is not None and inv.get('current_role', gate['role']) != gate['role']:
            raise ValueError('inventory_role_mismatch:' + gate['record_id'])
        if score is not None and score['role'] != gate['role']:
            raise ValueError('score_role_mismatch:' + gate['record_id'])
        if inv is not None:
            for key, source_key in [('project_id', 'project'), ('runtime_task_id', 'task'), ('raw_annotation_id', 'annotation')]:
                if str(inv[key]) != str(obj['source'][source_key]):
                    raise ValueError('source_identity_mismatch:' + gate['record_id'])
        score_ok = (score is not None and score['score_status'] == 'full'
                    and not any(truth(score[k]) for k in
                                ('original_holdout', 'same_target_quality_hold', 'latest_step_reference_pending', 'same_target_unconfirmed')))
        if score is not None and score['reference_id'] not in by_id:
            raise ValueError('reference_object_missing:' + gate['record_id'])
        if score is not None and by_id[score['reference_id']]['image_id'] != obj['image_id']:
            raise ValueError('reference_image_mismatch:' + gate['record_id'])
        eligible = (gate['condition'] == 'manual' and gate['role'] == 'manual_development_candidate'
                    and not gate['original_holdout'] and not gate['personnel_barriers'] and not gate['context_barriers']
                    and obj.get('independent_vote_eligible') is True)
        pts = checked_points(obj)
        seconds = None
        if inv is not None and eligible and truth(inv['time_training_eligible']) and truth(inv['time_usable']):
            seconds = float(inv['time_seconds'])
            if not math.isfinite(seconds) or seconds <= 0:
                raise ValueError('invalid_frozen_time:' + gate['record_id'])
        ledger.append(dict(record_id=gate['record_id'], object_id=obj['object_id'], image_id=obj['image_id'],
            worker_id=obj['worker_id'], condition=obj['condition'], role=gate['role'],
            original_holdout=gate['original_holdout'], eligible_manual=eligible,
            paired_points_available=pts is not None, full_quality_available=score_ok,
            ring_confirmed=obj.get('ring_confirmed', False), order_status=obj.get('order_status'),
            semi_source=inv.get('semi_initialization_evidence') if inv else None,
            source_cohort=gate.get('source_cohort'), model_edit_status=gate.get('model_edit_status'),
            trap_status=gate.get('trap_status')))
        if not eligible or pts is None:
            continue
        q = float(score['WQ']) if score_ok else None
        iou = float(score['IoU3D100']) if score_ok else None
        if q is not None and not all(math.isfinite(v) for v in (q, iou)):
            raise ValueError('nonfinite_quality')
        records.append(dict(annotation_id=obj['object_id'], record_id=gate['record_id'],
            image_id=obj['image_id'], building_id=obj['building_id'], worker_id=normalize_worker_id(obj['worker_id']),
            points=pts, WQ=q, IoU3D100=iou, active_time_seconds=seconds,
            time_context=inv.get('time_context') if seconds is not None else None,
            reference_id=score['reference_id'] if score_ok else None,
            reference_version=by_id[score['reference_id']].get('object_kind') if score_ok else None,
            quality_version=QUALITY_VERSION if score_ok else None,
            metrics={k: float(score[k]) for k in ('iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter')} if score_ok else None,
            ring_confirmed=obj.get('ring_confirmed', False), order_status=obj.get('order_status'),
            source_point_indices=obj.get('ordered_source_point_indices'),
            source_pair_indices=obj.get('ordered_source_pair_indices'), source=copy.deepcopy(obj['source'])))
    return records, ledger


def load_current():
    bundle = load_current_bundle()
    gates = json.loads(ADMISSION.read_text(encoding='utf-8-sig'))['records']
    records, ledger = bind_rows(bundle['data']['objects'], gates, read_csv(INVENTORY), read_csv(JOINT))
    _, models, images, _ = base.load_inputs()
    return dict(records=records, ledger=ledger, objects={o['object_id']: o for o in bundle['data']['objects']},
                gates=gates, models=models, images=images, validation=bundle['validation'], manifest=bundle['manifest'],
                quality_version=QUALITY_VERSION)


def estimate_axis(training, field, log=False):
    cells = []
    for row in training:
        value = row.get(field)
        if value is None:
            continue
        context = (row['image_id'], row['reference_id']) if not log else ('frozen_time_task', row['time_context'])
        cells.append(dict(worker_id=row['worker_id'], building_id=row['building_id'],
                          context_key=json.dumps(context), value=math.log1p(value) if log else value))
    if not cells:
        return {}
    frame = informative(pd.DataFrame(cells))
    if frame.empty:
        return {}
    stat = sufficient(frame)
    estimate, status, _ = solve(stat, np.ones(len(stat['buildings'])))
    draws = []
    if estimate is not None:
        for i in range(len(stat['buildings'])):
            weights = np.ones(len(stat['buildings'])); weights[i] = 0
            beta, _, _ = solve(stat, weights)
            if beta is not None:
                draws.append(beta)
    out = {}
    for j, worker in enumerate(stat['workers']):
        part = frame[frame.worker_id == worker]
        supported = status == 'usable' and part.context_key.nunique() >= 6 and part.building_id.nunique() >= 3
        values = [d[j] for d in draws]
        effect = float(estimate[j]) if estimate is not None else None
        lo, hi = (float(min(values)), float(max(values))) if values else (None, None)
        stable = supported and len(draws) >= .8 * len(stat['buildings']) and (lo > 0 or hi < 0)
        out[worker] = dict(effect=effect, supported=bool(supported), stable=bool(stable),
            lower_delete_building=lo, upper_delete_building=hi, valid_deletions=len(draws),
            contexts=int(part.context_key.nunique()), buildings=int(part.building_id.nunique()), status=status)
    return out


def fit_profiles(records, heldout):
    training = [r for r in records if r['building_id'] != heldout]
    axes = dict(quality=estimate_axis(training, 'WQ'), iou=estimate_axis(training, 'IoU3D100'),
                time=estimate_axis(training, 'active_time_seconds', log=True))
    profiles = {}
    for worker in sorted({r['worker_id'] for r in training}, key=int):
        q, i, t = [axes[k].get(worker, {}) for k in ('quality', 'iou', 'time')]
        quality, reason = 'uncertain', 'insufficient_or_boundary_support'
        if q.get('supported') and i.get('supported'):
            if q['effect'] * i['effect'] < 0:
                reason = 'WQ_IoU_sign_conflict'
            elif q.get('stable') and i.get('stable'):
                quality, reason = ('higher' if q['effect'] > 0 else 'lower'), None
        speed = ('faster' if t['effect'] < 0 else 'slower') if t.get('stable') else 'uncertain'
        profiles[worker] = dict(worker_id=worker, quality=quality, speed=speed, quality_reason=reason,
            axes=dict(quality=q, iou=i, time=t), prototype=quality + ':' + speed,
            training_buildings=sorted({r['building_id'] for r in training if r['worker_id'] == worker}),
            quality_version=QUALITY_VERSION)
    return profiles
