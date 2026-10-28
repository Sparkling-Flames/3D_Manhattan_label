import pandas as pd
from tools.thesis_main.analysis.rescore_v21_fusion_common_20261029 import SOURCE, TARGET


def test_fixed_method_identity_and_common_domains_are_preserved():
    old=pd.read_csv(SOURCE/'METHOD_ENDPOINTS.csv');new=pd.read_csv(TARGET/'METHOD_ENDPOINTS.csv')
    keys=['team_key','method'];a=old.set_index(keys).sort_index();b=new.set_index(keys).sort_index()
    assert a.index.equals(b.index) and len(a)==414 and new.team_key.nunique()==138
    for c in ['member_workers','member_object_ids','full_output','floor_output','full_evaluable','source_record_id']:
        assert a[c].fillna('').equals(b[c].fillna(''))
    lee=new[new.method.eq('lee_mv50')]
    assert lee[['B8L2','D10','IoU3D100']].isna().all().all()
    before=pd.read_csv(SOURCE/'COMMON_TEAM_METRICS.csv');after=pd.read_csv(TARGET/'COMMON_TEAM_METRICS.csv')
    identity=['team_key','comparison','metric','support_domain']
    assert set(map(tuple,before[identity].to_numpy()))==set(map(tuple,after[identity].to_numpy()))
    assert pd.read_csv(TARGET/'THREE_METHOD_COMMON_FLOOR.csv').team_key.nunique()==131
