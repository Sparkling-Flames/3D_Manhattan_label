import gzip
import json
from tools.thesis_main.analysis.fuse_v21_new_pools_20261028 import design, TARGET
from tools.thesis_main.analysis.rebuild_v21_20261028 import OUT, read


def test_orders_are_256_complete_permutations_and_teams_are_exact_prefixes():
    pool=dict(pool_id='test',records=[dict(worker_id='W'+str(i)) for i in range(6)])
    d=design(pool,20261028)
    assert d==design(pool,20261028) and len(d['paths'])==256
    expected=set()
    for path in d['paths']:
        assert sorted(path['workers'])==['W'+str(i) for i in range(6)]
        for k in range(1,7):expected.add(tuple(sorted(path['workers'][:k])))
    assert {tuple(t) for t in d['teams']}==expected


def test_frozen_engine_parity_and_completed_new_pool_statuses():
    assert read(TARGET/'ENGINE_PARITY.json')['geometry_and_scores_match']
    assert read(OUT/'population256_rescore/ENGINE_PARITY.json')['max_abs_error']<1e-8
    directory=TARGET/'b8cTxDM8gDG-18__manual__v21_1'
    plan=read(directory/'DESIGN.json');rows=[]
    for p in sorted(directory.glob('part_*.jsonl.gz')):
        with gzip.open(p,'rt',encoding='utf-8') as f:rows.extend(json.loads(x) for x in f)
    assert len(rows)==len(plan['teams'])
    assert {tuple(r['member_workers']) for r in rows}=={tuple(t) for t in plan['teams']}
    deferred=[r for r in rows if r['k']==2]
    assert deferred and all(r['B8L2'] is None and r['score_status']=='two_person_deferred' for r in deferred)
    assert all(r['data_release']=='v2.1' for r in rows)
