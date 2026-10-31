"""Checks for the follow-up audit; no new labels or fusion endpoints."""
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.diagnose_v21_structure_q_20261031 import OUT,STUDY,ROOT,UP


def test_different_selection_support_and_identity():
    d=pd.read_csv(OUT/'DIFFERENT_SELECTION_EVENTS.csv');d=d[d.comparator.eq('Q_RAW')]
    assert d.groupby('n').size().to_dict()=={14:28,20:7}
    assert d.changed_people.eq(1).all()
    assert d.groupby('n').class_composition_same.sum().to_dict()=={14:15,20:6}
    assert d.groupby('n').B8L2_delta.count().to_dict()=={14:24,20:6}
    assert d.groupby('n').apply(lambda g:g.fusion_turn_n_delta.eq(0).sum(),include_groups=False).to_dict()=={14:22,20:5}
    raw=pd.read_csv(UP/'classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz',low_memory=False).set_index(['pool_id','worker_id'])
    for r in d.itertuples():
        assert r.removed_raw_B8L2==raw.loc[(r.pool_id,r.removed),'B8L2']
        assert abs(r.added_raw_B8L2-raw.loc[(r.pool_id,r.added),'B8L2'])<1e-10


def test_class_means_and_association_are_descriptive():
    h=pd.read_csv(STUDY/'HISTORY_LOBO.csv');h=h[h.known.eq(True)]
    c=pd.read_csv(OUT/'CLASS_BY_FOLD.csv')
    for r in c.itertuples():
        g=h[h.heldout_building.eq(r.heldout_building)&h.class_id.eq(r.class_id)]
        assert len(g)==r.workers and abs(g.raw_q.mean()-r.raw_q)<1e-10
    assert h.heldout_building.nunique()==20
    wide=c.pivot(index='heldout_building',columns='class_id',values='raw_q')
    assert (wide.C3>wide.C2).all()
    # Fold rows repeat people, not independent participants.
    assert h.worker_id.nunique()<len(h)/10


def test_existing_primary_scores_and_preferences_preserved():
    bridge=pd.read_csv(OUT/'PRIMARY_DIFFICULTY_PARITY.csv')
    assert len(bridge)==178 and np.allclose(bridge.B8L2_mean,bridge.Q_record_mean)
    new=pd.read_csv(OUT/'DIFFICULTY_PREFERENCES_CURRENT.csv');new=new[new.scope.eq('primary')]
    old=pd.read_csv(ROOT/'research/data/releases/v2.1/personnel_descriptive/difficulty_preferences.csv')
    d=new.merge(old,on='worker_id',suffixes=('_new','_old'),validate='one_to_one')
    assert len(d)==60
    for field in ['B8L2_hard_mean','B8L2_nonhard_mean','B8L2_advantage','B8L2_leave_building_min','B8L2_leave_building_max']:
        assert np.allclose(d[field+'_new'],d[field+'_old'],atol=1e-10,equal_nan=True)


def test_added_targets_not_counted_as_extra_images():
    c=pd.read_csv(OUT/'WORKER_DIFFICULTY_CURRENT.csv');d=c[c.condition.eq('manual')]
    assert d.groupby('scope').records.sum().to_dict()=={'all_admitted':6739,'primary':6512}
    assert (d.records>=d.images).all()
    raw=pd.read_csv(UP/'classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz',low_memory=False)
    raw=raw[raw.history_eligible]
    assert raw.groupby('image_id').official_difficulty.nunique().eq(1).all()
    for r in d[d.scope.eq('all_admitted')].itertuples():
        g=raw[raw.condition.eq('manual')&raw.worker_id.eq(r.worker_id)&raw.official_difficulty.eq(r.difficulty)]
        assert r.images==g.image_id.nunique()
