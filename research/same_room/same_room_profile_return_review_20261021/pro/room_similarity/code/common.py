"""Frozen HOHONET inputs; no quality, reference, eligibility, or room edits."""
import sys as _delivery_sys
from pathlib import Path as _DeliveryPath
_delivery_root = next((p for p in _DeliveryPath(__file__).resolve().parents if (p / 'direct_io.py').is_file()))
_delivery_sys.path.insert(0, str(_delivery_root))
from direct_io import read_csv as _read_csv, open_data as _open_data, write_csv as _write_csv, write_bytes as _write_bytes, data_exists as _data_exists
from pathlib import Path
import gzip
import json
import numpy as np
import pandas as pd
COMMIT = '561584c8f64d5349d497ec1c6e91f1aeb4bbd7c9'
RELATION_VERSION = 'same_room_user_working_classification_20261016_v2'
METRICS = ['B8L2', 'D10']

def read(path):
    with _open_data(path, 'rt', encoding='utf8') if str(path).endswith('.gz') else open(path, encoding='utf-8-sig') as f:
        return json.load(f)

def save_csv(frame, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(frame, path, index=False, encoding='utf-8-sig', compression='infer')

def load(repo):
    repo = Path(repo)
    raw = read(repo / 'research/statistics/v2_evidence_audit_20261019/records.json.gz')['records']
    allowed = {r['object_id'] for r in read(repo / 'research/workers/worker_b8l2_d10_20261017/admission_snapshot.json') if not r['original_holdout'] and r['role'] == 'manual_development_candidate' and (not r['personnel_barriers']) and (not r['context_barriers'])}
    rows = []
    fields = ['object_id', 'image_id', 'image_code', 'worker_id', 'building_id', 'condition', 'origin', 'current_class', 'quality_usable', 'quality_use', 'pool_analysis_eligible', 'independent_vote_eligible', 'is_oos', 'is_doorway', 'B8L2', 'D10', 'reference_id', 'reference_version', 'cleaning_disposition', 'source_active_time_seconds', 'target_matched_time_seconds', 'declared_pair_count']
    for r in raw:
        x = {k: r.get(k) for k in fields}
        be = r.get('binding_evidence', {}) or {}
        ie = r.get('image_evidence', {}) or {}
        diff = ie.get('difficulty_record', {}) or {}
        x.update(chosen_target_id=be.get('chosen_target_id'), current_target_id=be.get('current_target_id'), target_aligned=be.get('chosen_target_id') == be.get('current_target_id'), training_allowed=r.get('origin') == 'new' or r['object_id'] in allowed, layer='excluded_oos' if r.get('is_oos') else 'doorway' if r.get('is_doorway') else 'ordinary', N_floor=diff.get('N_floor'), N_turn=diff.get('N_turn'), H=diff.get('H'), conditional_difficulty=diff.get('conditional_difficulty'), main_visual_space=ie.get('main_visual_space'), expected_annotation_extent=ie.get('expected_annotation_extent'), scope_response=(r.get('scope_evidence', {}) or {}).get('response'), image_comments=json.dumps(r.get('image_comments'), ensure_ascii=False))
        rows.append(x)
    d = pd.DataFrame(rows)
    gate = d.pool_analysis_eligible & d.quality_usable & ~d.is_oos & d.target_aligned & d.quality_use.isin(['ordinary_primary', 'doorway_quality'])
    d['formal_quality'] = gate
    q = d[gate].copy()
    assert q.object_id.is_unique
    assert not q.duplicated(['image_id', 'condition', 'worker_id']).any()
    assert q.groupby(['image_id', 'condition']).reference_id.nunique().max() == 1
    rel = read(repo / 'research/same_room/relation_adoption_20261016/relations.json')
    groups = read(repo / 'research/same_room/relation_adoption_20261016/original_groups.json')
    candidates = read(repo / 'research/same_room/relation_adoption_20261016/candidate_adoption.json')
    return (d, q, rel, groups, candidates)

def agg_building(frame, values, key='building_id'):
    return frame.groupby(key)[values].mean().mean().to_dict()

def cluster_interval(values, seed=20261021):
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    m = np.mean(rng.choice(x, (5000, len(x)), replace=True), axis=1)
    return tuple(np.quantile(m, [0.025, 0.975]))
