import copy
import json
from pathlib import Path

import pytest

from tools.thesis_main.data_prep.prepare_confirmed_point_calculation_view_20260909 import (
    RULES, apply_view, apply_review, build,
)

ROOT = Path(__file__).resolve().parents[1]


def test_reviewed_decisions_preserve_sources_and_imputation(tmp_path):
    decisions = ROOT / 'analysis_results/multibuilding_threshold_stability_20260909_v1/geometry_audit/USER_DECISIONS.json'
    rows, audit = build(ROOT, tmp_path, decisions)
    by_id = {r['canonical_annotation_id']: r for r in rows}
    assert len(rows) == 2501 and len(audit) == 16
    assert sum(r['processing_status'] == 'confirmed_point_removed' for r in rows) == 8
    assert sum(r['processing_status'] == 'confirmed_response_excluded' for r in rows) == 4
    assert sum(r['imputed_point'] for r in rows) == 2
    for cid in ('3a772c253f77d4b7', '40ac299ba105fdef'):
        row = by_id[cid]
        assert row['effective_points_1024x512'][:-1] == row['raw_points_1024x512']
        assert row['distance_recompute_required'] and row['calculation_included']
        assert row['imputation_provenance']['reference_evidence'] == 'ADD_POINT_PROPOSALS.json'
    excluded = by_id['e6701d3b7c423a86']
    assert excluded['effective_points_1024x512'] is None
    assert not excluded['unassisted_manual_included']
    kept = by_id['ee2e59495db1c2bf']
    assert kept['effective_points_1024x512'] == kept['raw_points_1024x512']
    manifest = json.loads(decisions.read_text(encoding='utf-8'))
    decision = copy.deepcopy(manifest['point_decisions'][7])
    decision['candidate_point'][0] += 1
    with pytest.raises(ValueError, match='coordinate'):
        apply_review(by_id[decision['canonical_annotation_id']], decision)


def test_confirmed_view_and_source_preservation(tmp_path):
    rows, audit = build(ROOT, tmp_path)
    assert len(rows) == 2501 and len(audit) == 4
    assert sum(r['processing_status'] == 'confirmed_point_removed' for r in rows) == 3
    assert sum(r['processing_status'] == 'confirmed_ambiguous_excluded' for r in rows) == 1
    for r in rows:
        rule = RULES.get(r['canonical_annotation_id'])
        raw = r['raw_points_1024x512']
        if rule and rule['drop'] is not None:
            i = rule['drop']
            assert r['effective_points_1024x512'] == raw[:i] + raw[i + 1:]
            assert r['effective_point_count'] == len(raw) - 1
            assert r['distance_recompute_required']
            r['effective_points_1024x512'][0][0] += 1
            assert r['effective_points_1024x512'][0][0] != raw[0][0]
        elif rule:
            assert r['effective_points_1024x512'] is None
            assert not r['calculation_included']
        else:
            assert r['effective_points_1024x512'] == raw
        if r['raw_condition'] == 'semi':
            assert not r['unassisted_manual_included']
    assert json.loads((tmp_path / 'verification.json').read_text())['source_exports_checked'] == 18


def test_exact_identity_and_unconfirmed_odd():
    cid, rule = next(iter(RULES.items()))
    meta = dict(canonical_annotation_id=cid, annotation_identity='wrong',
                image_id=rule['image'], raw_condition='manual', assistance_exposure='none')
    with pytest.raises(ValueError, match='identity'):
        apply_view(meta, [[1, 2]] * rule['count'])
    meta['canonical_annotation_id'] = 'unconfirmed'
    raw = [[i, 200] for i in range(9)]
    before = copy.deepcopy(raw)
    result = apply_view(meta, raw)
    assert raw == before == result['effective_points_1024x512']
    assert result['processing_status'] == 'unconfirmed_odd_unchanged'
    meta['raw_condition'] = 'oos'
    result = apply_view(meta, raw)
    assert result['unassisted_manual_included']
