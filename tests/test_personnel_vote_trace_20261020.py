from tools.thesis_main.analysis.personnel_vote_trace_20261020 import trace_groups


def group(name, members, selected):
    return dict(feature_id=name, members=[dict(worker=w, source_pair_index=i) for w,i in members], support=len(members), selected=selected)


def test_feature_id_is_not_identity_and_votes_balance():
    a=[group("node_1",[("keep",0),("old",1)],True)]
    b=[group("node_9",[("keep",0),("new",2),("new2",1)],True)]
    r=trace_groups(a,b,{"keep"})[0]
    assert r["kind"]=="one_to_one" and r["support_delta"]==1
    assert r["outgoing_votes"]==1 and r["incoming_votes"]==2 and r["retained_delta"]==0


def test_split_not_forced_into_one_to_one():
    a=[group("x",[("keep",0),("keep2",1)],True)]
    b=[group("y",[("keep",0)],False),group("z",[("keep2",1)],False)]
    r=trace_groups(a,b,{"keep","keep2"})[0]
    assert r["kind"]=="split" and r["support_delta"]==0
    assert r["selected_before"]==1 and r["selected_after"]==0
