import json
from collections import Counter
from tools.thesis_main.analysis.rebuild_v21_20261028 import OUT, Q, read


def test_inventory_retains_non_reference_exclusions_and_labels():
    old={r['object_id']:r for r in read(Q/'quality_inventory.json')}
    new=read(OUT/'quality_inventory.json')
    assert len(new)==10439 and {r['object_id'] for r in new}==old.keys()
    removable={'full_reference_unavailable','reference_not_full','score_unavailable'}
    for r in new:
        assert set(old[r['object_id']]['quality_exclusion_reasons'])-set(r['quality_exclusion_reasons'])<=removable
        assert r['quality_usable']==(r['score_status']=='complete' and not r['quality_exclusion_reasons'])
        if not r['quality_usable']:assert r['B8L2'] is None and r['D10'] is None
        if r['image_code']=='pa4otMbVnkk-11':assert r['current_class']=='中等'
        if r['image_code']=='wc2JMjhGNzB-14':assert not r['quality_usable']


def test_pool_coverage_and_no_duplicate_votes():
    pools=read(OUT/'pools/INPUT_SNAPSHOT.json')['images']
    inventory={r['object_id']:r for r in read(OUT/'quality_inventory.json')}
    counts=Counter((r['reference_id'],r['condition']) for r in inventory.values())
    all_ids=[]
    for p in pools:
        records=p['records'];assert len({r['worker_id'] for r in records})==len(records)
        assert p['meta']['pool_n']==len(records)
        assert p['meta']['source_inventory_n']==counts[p['meta']['reference_id'],p['meta']['condition']]
        for r in records:
            q=inventory[r['object_id']];assert q['quality_usable']
            assert q['reference_id']==p['reference']['target_id']
            assert r['B8L2']==q['B8L2']
            all_ids.append(r['object_id'])
    assert len(all_ids)==len(set(all_ids))==8154
