import numpy as np
import pandas as pd
import pytest

from tools.thesis_main.analysis.audit_doorway_delivery_20261031 import paired_metric


def test_user_confirmed_rings_no_longer_request_confirmation():
    import json
    from tools.thesis_main.analysis.prepare_doorway_correction_20261031 import OUT
    receipt=json.loads((OUT/'USER_RING_CONFIRMATION.json').read_text(encoding='utf8'))
    rows={r['object_id']:r for r in json.loads((OUT/'CORRECTION_OVERLAY.json').read_text(encoding='utf8'))}
    assert {r['object_id'] for r in receipt['records']}=={'v2:new:100168','v2:new:100176','v2:new:100741'}
    for r in receipt['records']:
        assert r['ring_confirmed'] and r['points'] and not r['quality_adopted']
        assert rows[r['object_id']]['ring_confirmed_by_user']
        assert 'input_ring_confirmation_required' not in rows[r['object_id']]['correction_reasons']


def test_pairing_keeps_missing_and_repeated_path_weights():
    result=paired_metric(pd.Series([0.,0.,0.,0.,np.nan]),pd.Series([1.,1.,4.,10.,30.]),
                         pd.Series(['a','a','a','b','b']),{'b'})
    assert result['mean']==6.0  # Image means 2 and 10; paths are not pooled across images.
    assert result['per_image']=={'a':2.0,'b':10.0}
    assert result['paired_finite']==4 and result['attempts']==5
    assert result['clean_image_subset_mean']==2.0


def test_formation_uses_every_attempt_including_false():
    result=paired_metric(pd.Series([True,False,True,False]),pd.Series([True,True,False,False]),
                         pd.Series(['a','a','b','b']),set())
    assert result['paired_finite']==result['attempts']==4
    assert result['mean']==pytest.approx(0)
    assert result['positive']==result['negative']==1


def test_corrected_scope_pool_boundaries():
    import json
    from tools.thesis_main.analysis.prepare_doorway_correction_20261031 import OUT
    pools=json.loads((OUT/'CORRECTED_PRIMARY_POOLS.json').read_text(encoding='utf8'))
    ledger=json.loads((OUT/'CORRECTED_RECORD_LEDGER.json').read_text(encoding='utf8'))
    byid={r['object_id']:r for r in ledger}
    for p in pools:
        assert len(p['records'])==p['n']==len(set(p['workers']))
        if p['family'] in ['space1','space2','whole_compatible']:
            assert all(byid[x]['final_scope_code']==p['family'] for x in p['records'])
    jtc=next(p for p in pools if p['image']=='jtcxE69GiFV-12' and p['family']=='space2')
    assert jtc['n']==0 and not jtc['records']
    assert sum(r['base_candidate'] for r in ledger)==584
    assert sum(r['base_candidate'] and r['final_scope']=='都不符合（看不懂）' for r in ledger)==31


def test_computed_delta_retains_failure_and_real_path_frequencies():
    from tools.thesis_main.analysis.prepare_doorway_correction_20261031 import OUT
    scores=pd.read_csv(OUT/'computed_delta/NEW_TARGET_SCORES.csv.gz')
    assert len(scores)==16219 and not scores.score_key.duplicated().any()
    assert scores.loc[~scores.complete_evaluable,'B8L2'].isna().all()
    paths=pd.read_csv(OUT/'computed_delta/CORRECTED_PREFIX_LINKS.csv.gz')
    assert paths.groupby(['pool_id','k']).size().eq(256).all()
    assert not ((paths.image=='jtcxE69GiFV-12')&(paths.family=='space2')).any()


def test_exclusion_sensitivity_removes_exact_thirteen_members():
    import json
    from tools.thesis_main.analysis.prepare_doorway_correction_20261031 import OUT
    holds={r['object_id'] for r in json.loads((OUT/'INDEPENDENT_HOLDS_13.json').read_text(encoding='utf8'))}
    requests=json.loads((OUT/'EXCLUDE13_SELECTED_REQUESTS.json').read_text(encoding='utf8'))
    assert len(holds)==13
    assert all(not holds.intersection(r['members']) and len(r['members'])==r['k'] for r in requests)
    assert {r['k'] for r in requests}=={6,10}
