from tools.thesis_main.analysis.b8l2_room_descriptions_20261016 import build_room_descriptions
from tests.test_b8l2_room_descriptions_20261016 import fixture


def adoption(bundle):
    registry=bundle['data']['room_registry']
    candidates=[]
    groups=[]
    pairs=[]
    for c in registry['candidates']:
        c['review_state']='viewed_per_user_statement'
        groups.append(dict(review_code=c['candidate_id'],group_id=c['candidate_id'],image_ids=c['image_ids'],
            viewed=True,review_state=c['review_state'],raw_current=dict(physical_same='支持',note='人工已分组'),
            interpretation={},source_pair_ids=[]))
        candidates.append(dict(candidate_id=c['candidate_id'],image_ids=c['image_ids'],
            source_group_codes=c['source_group_codes'],physical_supported=True,adopted_comparable=True,
            scope_comparable=True,subset_scope='whole_group',notes=['人工已分组']))
        a,b=sorted(c['image_ids'])
        pairs.append(dict(image_a=a,image_b=b,tier='user_classified_comparable',
            candidates=[c['candidate_id']],evidence=[],user_group_ids=[c['candidate_id']],
            physical_adopted=True,scope_comparable=True,substantive_conflict=False))
    registry['groups']=groups
    return dict(version='working_groups_v1',candidates=candidates,groups=groups,relations=pairs)


def test_existing_viewed_groups_use_official_adoption_without_status_or_unique_id_gate():
    records,bundle=fixture()
    adopted=adoption(bundle)
    result=build_room_descriptions(records,bundle,adoption=adopted)
    assert {r['relation_tier'] for r in result['room_group_registry']}=={'user_classified_comparable'}
    assert all(r['user_classification_adopted'] for r in result['room_group_registry'])
    assert all('physical_room_identity_certified' not in r for r in result['room_group_registry'])
    assert {tuple(r['image_ids']) for r in result['room_direct_pair_registry']}=={('a','b'),('b','c')}
    assert len(result['user_original_group_summary'])==2
    group=next(r for r in result['room_group_summary'] if r['group_id']=='candidate:G1')
    assert group['B8L2_n']==3 and group['relation_adoption_version']=='working_groups_v1'


def test_negative_and_other_scope_classifications_stay_visible_and_separate():
    records,bundle=fixture(); adopted=adoption(bundle)
    adopted['candidates'][0].update(physical_supported=False,adopted_comparable=False)
    adopted['groups'][0]['raw_current']['physical_same']='不支持'
    adopted['candidates'][1].update(adopted_comparable=False,scope_comparable=False)
    result=build_room_descriptions(records,bundle,adoption=adopted)
    tiers={r['candidate_id']:r['relation_tier'] for r in result['room_group_registry']}
    assert tiers=={'G1':'not_supported','G2':'user_classified_other_scope'}
    assert len(result['user_original_group_summary'])==2
    assert result['room_raw_group_evidence'][0]['user_physical_classification']=='不支持'


def test_outside_retained_subgroup_is_not_misreported_as_missing_original_classification():
    records,bundle=fixture(); adopted=adoption(bundle)
    bundle['data']['room_registry']['candidates'][1]['image_ids']=['b']
    adopted['candidates'][1]['image_ids']=['b']
    result=build_room_descriptions(records,bundle,adoption=adopted)
    row=next(r for r in result['room_unlinked_images'] if r['image_id']=='c')
    assert row['original_user_group_ids']==['G2']
    assert row['room_evidence_status']=='outside_retained_working_subgroups; original_group_available'


def test_relation_freeze_refresh_changes_labels_only_and_rejects_changed_members():
    from copy import deepcopy
    import pytest
    from tools.thesis_main.analysis.b8l2_room_descriptions_20261016 import refresh_adoption_labels
    records,bundle=fixture(); current=adoption(bundle)
    tables=build_room_descriptions(records,bundle,adoption=current)
    before=deepcopy(tables['room_group_summary'])
    current['version']='working_groups_v2'
    current['candidates'][0]['adopted_comparable']=False
    current['relations'][0]['tier']='user_classified_other_scope'
    refresh_adoption_labels(tables,current)
    assert tables['room_group_summary'][0]['relation_adoption_version']=='working_groups_v2'
    assert tables['room_group_summary'][0]['relation_tier']=='user_classified_other_scope'
    for old,new in zip(before,tables['room_group_summary']):
        assert {k:v for k,v in old.items() if k not in ('relation_tier','relation_adoption_version')}=={
            k:v for k,v in new.items() if k not in ('relation_tier','relation_adoption_version')}
    current['candidates'][0]['image_ids']=['changed']
    with pytest.raises(AssertionError,match='membership changed'):
        refresh_adoption_labels(tables,current)
