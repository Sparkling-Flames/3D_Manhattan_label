from collections import Counter

from tools.thesis_main.analysis.plan_cn_first10_20260922 import prepare, allocate


def test_first10_latest_counts_exposure_and_independent_floor():
    candidates, seen, profiles, sources = prepare()
    rows = allocate(candidates, seen, profiles)
    assert any('09-42-4609125d' in p for p in sources)
    assert Counter(r['worker'] for r in rows) == {w:10 for w in profiles}
    assert len({(r['worker'],r['image_id']) for r in rows}) == 90
    assert all(r['worker'] not in seen[r['image_id']] for r in rows)
    counts = Counter(r['image_id'] for r in rows)
    assert sum(r['kind']=='旧图补足' for r in rows) == 74
    assert all(counts[r['image_id']] <= r['capacity'] for r in candidates)
    assert all(any(r['worker']==w and r['kind']=='已采用新图' for r in rows) for w in profiles)
    e9 = next(r for r in candidates if r['code']=='e9zR4mvMWw7-26')
    assert (e9['current_n'], e9['predictive_n'],counts[e9['image_id']]) == (8,7,5)
    for code in ['Z6MFQCViBuw-02','wc2JMjhGNzB-54']:
        r=next(r for r in candidates if r['code']==code)
        assert len([w for w in profiles if w not in seen[r['image_id']]]) == 6
        assert counts[r['image_id']] == 6
    assert all(not r['boundary'] for r in rows if r['kind']=='已采用新图')
