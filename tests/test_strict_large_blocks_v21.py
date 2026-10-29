import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research/workers/strict_large_blocks_v21_20261029'


def test_frozen_large_block_design():
    labels = pd.read_csv(OUT / 'FROZEN_LABELS_ALL_LOBO.csv.gz', low_memory=False)
    lookup = {(r.method, r.heldout_building, r.worker_id): r.class_id for r in labels.itertuples() if r.known}
    pools = {p['pool_id']: p for p in json.loads((OUT / 'INPUT_SNAPSHOT.json').read_text(encoding='utf-8'))['images']}
    events = pd.read_csv(OUT / 'design/EVENTS_EXACT.csv.gz')
    seen = set()
    for e in events.itertuples():
        d, x, y, z = [set(getattr(e, k).split('|')) for k in ['D', 'X', 'Y', 'Z']]
        assert len(d) == e.n-e.m > 0
        assert len(x) == len(y) == len(z) == e.m
        assert len(d | x | y | z) == e.n + 2*e.m
        assert not (d | x | y | z) & {'W019', 'W026'}
        assert all(lookup[e.method, e.building, w] == e.source_class for w in x | y)
        assert all(lookup[e.method, e.building, w] == e.target_class for w in z)
        sig = (e.pool_id, e.method, e.n, e.m, tuple(sorted(d)), tuple(sorted([tuple(sorted(x)), tuple(sorted(y))])), tuple(sorted(z)))
        assert sig not in seen
        seen.add(sig)
        for arm, block in [('A', x), ('B', y), ('C', z)]:
            assert set(getattr(e, arm+'_members').split('|')) == d | block
        assert e.reference_id == pools[e.pool_id]['meta']['reference_id']
    requests = pd.read_csv(OUT / 'design/REQUESTS.csv.gz')
    assert requests.team_key.is_unique
    assert set(requests.team_key) == set(events.A_team_key) | set(events.B_team_key) | set(events.C_team_key)
    assert len(events) == 12480 and len(requests) == 28945


def test_completed_endpoints_and_metrics():
    pools = {p['pool_id']: p for p in json.loads((OUT / 'INPUT_SNAPSHOT.json').read_text(encoding='utf-8'))['images']}
    ep = pd.read_csv(OUT / 'endpoints/ENDPOINT_SCALARS.csv.gz', low_memory=False).set_index('team_key')
    assert ep.index.is_unique and len(ep) == 28945
    for r in ep.itertuples():
        pool = pools[r.pool_id]
        own = {x['worker_id']: x['object_id'] for x in pool['records']}
        ws = r.member_workers.split('|')
        assert len(set(ws)) == r.k
        assert {own[w] for w in ws} == set(r.member_object_ids.split('|'))
        assert r.reference_id == pool['meta']['reference_id']
        assert r.reference_version == pool['meta']['reference_version']
        assert r.minimum_support == (r.k+1)//2
    events = pd.read_csv(OUT / 'results/EVENT_METRICS.csv.gz', low_memory=False)
    q = {a: events[a+'_team_key'].map(ep.B8L2) for a in 'ABC'}
    valid = q['A'].notna() & q['B'].notna() & q['C'].notna()
    ga = ((q['C']-q['A']).abs()-(q['B']-q['A']).abs()).where(valid)
    gs = (((q['C']-q['A']).abs()+(q['C']-q['B']).abs())/2-(q['B']-q['A']).abs()).where(valid)
    for actual, expected in [(events.G_A, ga), (events.G_S, gs)]:
        assert actual.isna().equals(expected.isna())
        assert (actual-expected).dropna().abs().max() < 1e-9
    assert events.ABC_scored.eq(valid).all()
    assert ep.B8L2.isna().sum() == 542
    assert ep.loc[ep.B8L2.isna(), 'score_status'].isin(['below_four', 'no_connection']).all()
