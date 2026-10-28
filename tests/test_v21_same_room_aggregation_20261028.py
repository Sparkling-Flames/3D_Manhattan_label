import json
import numpy as np
import pandas as pd
import pytest
from tools.thesis_main.analysis.rebuild_v21_20261028 import OUT


@pytest.mark.parametrize('relative,expected',[('same_room_current_labels_results',1954),('same_room_current_results/finite',2659)])
def test_same_room_response_variance_identity_and_support(relative,expected):
    folder=OUT/relative/'response'
    receipt=json.loads((folder/'ANALYSIS_RECEIPT.json').read_text(encoding='utf8'))
    assert receipt['complete_panels']==receipt['design_panels']==expected
    d=pd.read_csv(folder/'PANEL_DECOMPOSITION.csv.gz')
    assert len(d)==receipt['decomposition_rows']
    for side in ['a','b']:
        cols=[c+'_'+side for c in ['total_var','between_var','within_var']]
        z=d[cols].dropna()
        assert len(z)>0
        np.testing.assert_allclose(z.iloc[:,0],z.iloc[:,1]+z.iloc[:,2],rtol=1e-10,atol=1e-10)
    assert d.n_joint_finite.le(d.n_requested).all()


def test_same_room_coverage_preserves_frozen_members_and_scope():
    root=OUT/'same_room_current_capacity'
    check=json.loads((root/'CHECKS.json').read_text(encoding='utf8'))
    assert check['old_structure_members_verified_unchanged']
    d=pd.read_csv(root/'DIRECT_PAIR_CURRENT_CLASS_CAPACITY.csv')
    assert not d.duplicated(['pair_key','method']).any()
    assert d.common_n.eq(d.known_common_n+d.unknown_common_n).all()
    assert d.common_n.eq(d.common_members.fillna('').map(lambda x:len(x.split('|')) if x else 0)).all()
    added=pd.read_csv(root/'ADDED_DIRECT_PAIRS.csv')
    assert len(added)==check['added_pairs'] and added.scope_comparable.sum()==check['added_scope_comparable']
    assert not added.oos_pending.any() and not added.substantive_conflict.any()
    assert added.physical_adopted.all()
    assert added.loc[~added.scope_comparable,'ordinary_comparable'].eq(False).all()
