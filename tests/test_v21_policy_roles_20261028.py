import pandas as pd
from tools.thesis_main.analysis.register_v21_policies_20261028 import definitions


def test_role_centers_are_equal_worker_means_and_exclude_unknown_workers():
    fields=['turn_history','short_history','redundancy_history','area_history','height_history','simple_turn_history','complex_turn_history','complex_short_history','q_history','q_downside','t_history']
    rows=[]
    for worker,value,known in [('a',0,True),('b',10,True),('c',900,False)]:
        rows.append(dict(worker_id=worker,method='V3_JOINT_QT',condition='manual',heldout_building='heldout',known=known,coarse_label='J1',fine_label='J1a',selected_family='CQT',**{c:value for c in fields}))
    d=definitions(pd.DataFrame(rows))
    assert len(d)==2 and d.people.eq(2).all() and d.members.eq('a|b').all()
    assert d.q_history_mean.eq(5).all() and d.t_history_mean.eq(5).all()


def test_current_policy_binary_writer_preserves_compressed_bytes(tmp_path):
    import gzip
    from tools.thesis_main.analysis.analyze_v21_current_policies_20261028 import atomic_binary
    raw=bytes(range(256))*100;payload=gzip.compress(raw);path=tmp_path/'data.gz'
    atomic_binary(path,payload)
    assert path.read_bytes()==payload and gzip.decompress(path.read_bytes())==raw
