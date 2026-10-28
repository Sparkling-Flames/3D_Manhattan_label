import gzip
import json
import pytest
from tools.thesis_main.analysis.enrich_v21_population_scores_20261028 import enrich
from tools.thesis_main.analysis.rescore_v21_population_20261028 import SOURCE, TARGET
from tools.thesis_main.analysis.rebuild_v21_20261028 import OUT, read
from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine
from tools.thesis_main.analysis.wall_consensus_quality_20261015 import measured


def test_saved_complete_metrics_and_deferred_state():
    refs = {r['target_id']: r for r in read(OUT / 'reference_catalog.json')}
    path = next(TARGET.rglob('*.jsonl.gz'))
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        row = json.loads(next(f))
    with gzip.open(SOURCE / row['geometry_source'], 'rt', encoding='utf-8') as f:
        original = json.loads(next(f))
    geometry = original['geometry']; ref = refs[row['reference_id']]
    q = row['result']['B8L2']
    with scoring_engine() as (engine, _):
        enriched = enrich(dict(row['result']), geometry, row['k'], ref, engine)
        expected = measured(engine, dict(n=row['k'], candidate=geometry,
            node_consensus=dict(nodes=[None]*len(geometry['footprint']))),
            dict(floor=ref['floor_xz_h'], points=ref['points_1024x512']))
        for key in ['omission', 'extension', 'WQ', 'boundary_loss', 'direction_loss', 'height_loss']:
            assert enriched[key] == pytest.approx(expected[key], abs=1e-10)
        assert enriched['B8L2'] == q
        deferred = enrich(None, geometry, 2, ref, engine)
        assert deferred['score_status'] == 'two_person_deferred'
        assert deferred['WQ'] is None
