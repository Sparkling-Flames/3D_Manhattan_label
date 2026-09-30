from tools.thesis_main.analysis.receive_order_results_20260929 import merge_returns, cycle_key


def test_received_snapshot_does_not_overwrite_new_decision_and_conflicts_stop():
    old=dict(binding='same-input',status='confirmed',order=[0,1,2,3],note='',cause='',updated_at='old')
    new={**old,'order':[0,2,1,3],'updated_at':'new'}
    merged,origins,conflicts=merge_returns({'x':old},{'user':{'x':new},'yizheng':{'x':old}})
    assert merged['x']==new and origins=={'x':['user']} and not conflicts
    _,_,conflicts=merge_returns({'x':old},{'user':{'x':new},'yizheng':{'x':{**new,'order':[0,1,3,2]}}})
    assert conflicts==['x']
    assert cycle_key([0,1,2,3])==cycle_key([2,1,0,3])
    assert cycle_key([0,1,2,3])!=cycle_key([0,2,1,3])


def test_coverage_followup_and_room_snapshot_are_disjoint_and_complete():
    from tools.thesis_main.analysis.receive_order_results_20260929 import OUT, ROOT, read
    summary=read(OUT/'覆盖与续审汇总.json')
    assert summary['previous_queue_states']=={'pending':{'confirmed':1097,'pairing':1},'confirmed':{'confirmed':63}}
    assert summary['missing']==summary['previous_pending_without_current_reviewer']==[]
    package=read(OUT/'同房汇集_Matterport_当前确认快照.json')
    layouts=[o for room in package['rooms'] for image in room['images'].values() for o in image['annotations']]
    ids={o['object_id'] for o in layouts}
    assert len(ids)==len(layouts)==1160
    assert not ids.intersection(package['pairing_deferred'])
    assert len(package['pairing_deferred'])==33 and package['complete'] is False
    next_objects=read(ROOT/'analysis_results/order_followup_20260929/source_objects.json')['objects']
    assert len(next_objects)==77 and len({o['image_id'] for o in next_objects})==24
    assert not ids.intersection(o['object_id'] for o in next_objects)
    for obj in layouts:
        assert obj['links_zero_based']==[[i,i+1] for i in range(0,len(obj['points_1024x512']),2)]
        assert sorted(obj['ordered_source_point_indices'])==list(range(len(obj['points_1024x512'])))
