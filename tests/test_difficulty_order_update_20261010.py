import copy
import pytest
from tools.thesis_main.data_prep.apply_difficulty_orders_20261010 import apply_data, apply_bundle, read, ROOT, REVIEW
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle, validate_bundle


def test_only_three_orders_change_and_replay_is_idempotent():
    before = load_current_bundle()
    after = apply_bundle(copy.deepcopy(before))
    old = {o['object_id']: o for o in before['data']['objects']}
    ids = set(read(REVIEW/'confirmed_orders.json')['records'])
    for o in after['data']['objects']:
        prev = old[o['object_id']]
        if o['object_id'] not in ids:
            assert o == prev
        else:
            for k in ('original_export_points','preprocessed_points','before_preprocessing_points','links_zero_based','point_labels','main_quality_gate','main_consensus_gate','independent_vote_eligible'):
                assert o[k] == prev[k]
            assert o['ordered_source_pair_indices'] == [0,1,3,2,5,4,6,7]
            assert o['ring_confirmed'] and o['order_status']=='human_confirmed'
    assert apply_bundle(copy.deepcopy(after)) == after
    assert validate_bundle(after['data'],after['research'],after['comments'],after['final_summary'])['confirmed_orders']==1312


@pytest.mark.parametrize('kind',['coordinates','binding','permutation','status','missing'])
def test_bad_receipt_rejected_without_mutation(kind):
    data=read(ROOT/'analysis_results/research_input_20260929/preprocessed_source.json')
    receipt=read(REVIEW/'confirmed_orders.json'); oid=next(iter(receipt['records'])); r=receipt['records'][oid]
    if kind=='coordinates':next(o for o in data['objects'] if o['object_id']==oid)['preprocessed_points'][0][0]+=1
    elif kind=='binding':r['binding']=r['binding'].replace('E1"','bad"',1)
    elif kind=='permutation':r['order'][0]=r['order'][1]
    elif kind=='status':r['status']='draft'
    else:receipt['records'].pop(oid)
    unchanged=copy.deepcopy(data)
    with pytest.raises(ValueError):apply_data(data,receipt)
    assert data==unchanged


def test_rebuild_retains_confirmed_orders(tmp_path, monkeypatch):
    from tools.thesis_main.data_prep import materialize_current_research_input as builder
    monkeypatch.setattr(builder, 'OUT', tmp_path)
    rebuilt = builder.build()
    current = read(ROOT/'analysis_results/research_input_20260929/preprocessed_source.json')
    ids = set(read(REVIEW/'confirmed_orders.json')['records'])
    assert {o['object_id']:o for o in rebuilt['objects'] if o['object_id'] in ids} == {o['object_id']:o for o in current['objects'] if o['object_id'] in ids}
    assert rebuilt['summary']['confirmed_orders']==1298
