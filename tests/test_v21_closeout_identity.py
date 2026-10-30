import pandas as pd
from tools.thesis_main.analysis.audit_v21_closeout_identity_20261030 import complete_class, OUT

def test_whole_class_requires_exact_members_not_count():
    roster={'a':'C1','b':'C1','c':'C2'};pool=set(roster)
    assert complete_class({'a','b'},pool,roster,'C1')
    assert not complete_class({'a','c'},pool,roster,'C1')
    assert not complete_class(set(),pool,roster,'C3')

def test_saved_identity_checks_do_not_conflate_declared_and_valid():
    a=pd.read_csv(OUT/'ALLIANCE_IDENTITY.csv.gz')
    e=pd.read_csv(OUT/'AC_IDENTITY.csv.gz')
    assert len(a)==2942 and len(e)==80740
    assert a.pool_roster_complete.all() and e.pool_roster_complete.all()
    assert not (e.still_declared_direction & ~e.still_cross_class).any()
    changed=a[~a.still_declared_alliance]
    assert len(changed)>0
    assert (changed.added_members.notna() | changed.removed_members.notna()).all()

def test_alliance_trace_partitions_changed_teams():
    d=pd.read_csv(OUT/'ALLIANCE_414_TRACE.csv')
    assert len(d)==414
    assert not d.only_label_permutation.any()
    assert not d.old_team_is_other_new_alliance.any()
    assert d.action.value_counts().to_dict()=={'not_in_AC_endpoint_archive':279,'reuse_saved_endpoint':123,'capacity_only_n_lt3':11,'historical_endpoint_contract_check':1}
    assert d.loc[d.action.eq('capacity_only_n_lt3'),'new_n'].lt(3).all()
    assert d.loc[d.action.eq('reuse_saved_endpoint'),'endpoint_found'].all()
    assert not d.duplicated(['pool_id','new_members']).any()
