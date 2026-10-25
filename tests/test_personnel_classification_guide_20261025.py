"""The guide preserves exact source rows, roster identities and denominator types."""
import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/workers/personnel_classification_guide_20261025'
GUIDE = json.loads((BASE / 'GUIDE.json').read_text(encoding='utf-8'))


def test_rosters_preserve_known_unknown_and_all_lobo_identity():
    labels = pd.concat([pd.read_csv(BASE / 'sources' / f) for f in [
        'NEW_METHOD_LABELS_ALL_LOBO.csv.gz', 'SCOPE_INCREMENT_LABELS_ALL_LOBO.csv.gz',
        'REVERSE_LABELS_ALL_LOBO.csv.gz']])
    expected = labels[labels.method.isin([m['id'] for m in GUIDE['methods']])]
    actual = [(r['method'], r['fold'], r['class_id'], r['known'], w)
              for r in GUIDE['rosters'] for w in r['workers']]
    target = [(r.method, r.heldout_building, r.class_id, bool(r.known), r.worker_id)
              for r in expected.itertuples()]
    assert sorted(actual) == sorted(target)
    assert len(actual) == len(set(actual)) == 9982
    all_d = [r for r in GUIDE['rosters'] if r['method'] == 'DSTRUCT_K3' and r['fold'] == 'ALL']
    assert sorted(len(r['workers']) for r in all_d) == [3, 8, 12, 39]


def test_main_conditions_keep_exact_rows_and_separate_time_failure_support():
    source = pd.read_csv(BASE / 'sources/FINAL_CONDITIONS_COMPACT.csv')
    for row in GUIDE['main_conditions']:
        match = source[(source.method == row['method']) & (source.n == row['n'])
                       & (source.m == row['m']) & (source.role == row['role'])
                       & (source.phase == row['phase'])]
        assert len(match) == 1
        for key, value in row.items():
            ref = match.iloc[0][key]
            if pd.isna(ref):
                assert value is None
            elif isinstance(value, (int, float)):
                assert value == pytest.approx(ref, abs=1e-10)
            else:
                assert value == ref
    d = GUIDE['main_conditions'][0]
    assert (d['B8L2_valid_images'], d['record_time_CB_pct_valid_images']) == (40, 30)
    assert (d['C_failed_raw_count'], d['C_failed_raw_valid_events']) == (3, 343)
    assert (d['C_loss10_CB_raw_count'], d['C_loss10_CB_raw_valid_events']) == (9, 332)
    assert len(GUIDE['all_conditions']) == 71


def test_current_frontend_payload_and_sources_are_bound():
    page = ROOT / 'research/statistics/research_explorer_v1_r2_20261017'
    index = json.loads((page / 'v2-data/index.json').read_text(encoding='utf-8'))
    document = next(d for d in index['documents'] if d['path'] == 'personnel_classification_guide')
    assert document['content'] == GUIDE
    assert 'personnel-methods.js' in (page / 'index.html').read_text(encoding='utf-8')
    for source in GUIDE['source_map']:
        path = BASE / source['file'] if source['file'].startswith('figures/') else BASE / 'sources' / source['file']
        assert path.is_file()
        assert path.stat().st_size == source['bytes']
    assert max(row['n'] for row in GUIDE['strict_paths']) == 21
    assert max(row['n'] for row in GUIDE['ac_paths']) == 28
