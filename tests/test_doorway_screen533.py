import json
from pathlib import Path
import pandas as pd
import pytest
from tools.thesis_main.analysis.recompute_doorway_screen533_20261031 import BASE, AUDIT, OUT, changed_pools, team_key


def test_new_screen_is_membership_only_and_before_is_frozen():
    old=json.loads((AUDIT/'CORRECTED_PRIMARY_POOLS.json').read_text(encoding='utf8'))
    ledger=json.loads((BASE/'scope_recheck40_20261031/EFFECTIVE_SCREENING_LEDGER.json').read_text(encoding='utf8'))['records']
    pools,changes=changed_pools(old,ledger)
    assert sum(p['n'] for p in pools if p['family']=='overall_after')==533
    assert sum(p['n'] for p in pools if p['family']=='overall_before')==584
    assert len(changes)==16 and len({x['image'] for x in changes})==8
    for p,q in zip(pools,old):
        assert set(p['records'])<=set(q['records'])
        assert p['n']==len(p['records'])==len(set(p['workers']))
        if p['family']=='overall_before':assert p['records']==q['records'] and p['target']=='全部'


def test_exact_cache_identity_not_image_or_team_size_only():
    assert team_key('a',['x','y'])==team_key('a',['y','x'])
    assert team_key('a',['x','y'])!=team_key('a',['x','z'])
    assert team_key('a',['x','y'])!=team_key('b',['x','y'])


def test_design_membership_and_replicates():
    pools={p['pool_id']:p for p in json.loads((OUT/'POOLS.json').read_text(encoding='utf8'))}
    frame=pd.read_csv(OUT/'CHANGED_PREFIX_DESIGN.csv.gz')
    assert frame.groupby(['pool_id','k']).size().eq(256).all()
    for r in frame.itertuples():
        ids=r.member_object_ids.split('|');assert len(ids)==len(set(ids))==r.k
        assert set(ids)<=set(pools[r.pool_id]['records'])
    assert not frame.duplicated(['pool_id','base_replicate','k']).any()


def test_completed_curves_keep_failures_and_exact_denominators():
    if not (OUT/'CHECKS.json').exists():pytest.skip('native delta still running')
    frame=pd.read_csv(OUT/'PAIRED_PATH_VALUES.csv.gz')
    assert frame.groupby(['pool_id','k']).size().eq(256).all()
    assert frame.loc[(frame.k>=3)&~frame.complete_evaluable,['B8L2','D10','IoU3D100']].isna().all().all()
    exact=pd.read_csv(OUT/'CHANGED_EXACT_VALUES.csv.gz')
    import math
    for (_,k),g in exact.groupby(['pool_id','k']):
        assert len(g)==g.member_object_ids.nunique()==math.comb(int(g.pool_n.iloc[0]),k)


def test_final439_rebuilds_scopes_and_preserves_before(monkeypatch):
    from tools.thesis_main.analysis import recompute_doorway_screen533_20261031 as module
    monkeypatch.setattr(module, 'SCREENED', 439)
    old=json.loads((AUDIT/'CORRECTED_PRIMARY_POOLS.json').read_text(encoding='utf8'))
    ledger=json.loads((BASE/'expanded_visual_review_20261031/FINAL_SCREENING_LEDGER.json').read_text(encoding='utf8'))['records']
    pools,changes=module.changed_pools(old,ledger)
    assert sum(p['n'] for p in pools if p['family']=='overall_after')==439
    assert sum(p['n'] for p in pools if p['family']=='overall_before')==584
    for p,q in zip(pools,old):
        if p['family']=='overall_before':
            assert p['records']==q['records']
        elif p['family']=='overall_after':
            assert set(p['records'])=={r['object_id'] for r in ledger if r['image']==p['image'] and r['eligibility']=='保留'}
        else:
            assert set(p['records'])=={r['object_id'] for r in ledger if r['image']==p['image'] and r['eligibility']=='保留' and r['scope']==p['target']}
    small=next(p for p in pools if p['image']=='B6ByNegPMKs-43' and p['family']=='overall_after')
    assert small['n']==14


def test_final439_completed_paths_and_capacity():
    out=BASE/'screen439_results_20261031'
    if not (out/'CHECKS.json').exists():pytest.skip('439 calculation in progress')
    pools={p['pool_id']:p for p in json.loads((out/'POOLS.json').read_text(encoding='utf8'))}
    frame=pd.read_csv(out/'PAIRED_PATH_VALUES.csv.gz')
    assert frame.groupby(['pool_id','k']).size().eq(256).all()
    assert frame.loc[(frame.k>=3)&~frame.complete_evaluable,['B8L2','D10','IoU3D100']].isna().all().all()
    for r in frame.itertuples():
        ids=r.member_object_ids.split('|')
        assert len(ids)==len(set(ids))==r.k
        assert set(ids)<=set(pools[r.pool_id]['records'])
        assert r.k<=pools[r.pool_id]['n']
    small=frame[(frame.image=='B6ByNegPMKs-43')&(frame.family=='overall_after')]
    assert small.k.max()==14 and small[small.k==14].member_object_ids.nunique()==1
    assert small[small.k==13].member_object_ids.nunique()<=14
    import math
    exact=pd.read_csv(out/'CHANGED_EXACT_VALUES.csv.gz')
    for (_,k),g in exact.groupby(['pool_id','k']):
        assert len(g)==g.member_object_ids.nunique()==math.comb(int(g.pool_n.iloc[0]),k)
    previous=pd.read_csv(OUT/'PAIRED_PATH_VALUES.csv.gz')
    cols=['pool_id','k','base_replicate','member_object_ids','B8L2','D10','IoU3D100','complete_evaluable']
    a=frame[frame.family=='overall_before'][cols].sort_values(cols[:3]).reset_index(drop=True)
    b=previous[previous.family=='overall_before'][cols].sort_values(cols[:3]).reset_index(drop=True)
    pd.testing.assert_frame_equal(a,b)


def test_curve_bands_allow_no_scorable_quality(tmp_path,monkeypatch):
    from tools.thesis_main.analysis import report_doorway_delta_20261031 as report
    monkeypatch.setattr(report,'BASE',tmp_path);monkeypatch.setattr(report,'OUT',tmp_path)
    (tmp_path/'CHANGED_POOLS.json').write_text(json.dumps([{'pool_id':'after'}]),encoding='utf8')
    orders=pd.DataFrame([dict(image='a-1',base_replicate=i,origin_stratum='base') for i in range(256)])
    rows=[dict(image='a-1',building='a',pool_id=pool,family=family,base_replicate=i,k=3,
        B8L2=float('nan'),D10=float('nan'),IoU3D100=float('nan'),complete_evaluable=False)
        for family,pool in [('overall_after','after'),('whole_compatible','whole')] for i in range(256)]
    with pytest.warns(RuntimeWarning):report.compatibility_bands(pd.DataFrame(rows),orders)
    bands=pd.read_csv(tmp_path/'CHANGED_POOL_PATH_BANDS.csv')
    quality=bands[bands.metric=='B8L2'].iloc[0]
    assert quality.status=='metric_unavailable_no_valid_output' and pd.isna(quality.pointwise_low)
    assert quality.valid_paths==0
    paired=pd.read_csv(tmp_path/'COMPATIBILITY_PAIRED_CURVE_BANDS.csv')
    assert paired[paired.k==3].capacity_images.eq(1).all()
    assert paired[paired.k>3].capacity_images.eq(0).all()
