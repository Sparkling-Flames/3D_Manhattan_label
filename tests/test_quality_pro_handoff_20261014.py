from zipfile import ZipFile

import pytest

from tools.thesis_main.analysis import quality_pro_handoff_20261014 as q


@pytest.fixture
def delivered_package(tmp_path, monkeypatch):
    with ZipFile(q.OUT/'quality_pro_handoff_20261014_READY.zip') as archive:
        archive.extractall(tmp_path)
    monkeypatch.setattr(q, 'PACK', tmp_path)


def test_denominator_diagnostic_does_not_confuse_largest_with_large():
    row=dict(boundary_loss=.001,direction_loss=.002,global_height_loss=.0001,local_height_loss=.0002,height_score_drop=.03)
    result=q.penalty_diagnostic(row)
    assert result['largest_denominator_term']=='direction_loss'
    assert 'score' not in result and '分子IoU' in result['interpretation']


def test_delivered_review_is_bound_blinded_and_unanswered(delivered_package):
    manifest=q.read(q.PACK/'data/human_review_manifest.json')
    selected=[r for r in manifest['cards'] if r['questions']]
    assert len(selected)==3 and manifest['status']=='awaiting_receipt'
    for card in selected:
        assert card['bindings']['A']['image_id']==card['bindings']['B']['image_id']==card['image_id']
        assert card['bindings']['A']['reference_object_id']==card['bindings']['B']['reference_object_id']
        assert all(any(o[0]=='uncertain' for o in question['options']) for question in card['questions'])
        assert not {'answer','score','candidate_components','algorithm'} & card.keys()
        assert (q.PACK/card['photo']).exists()
    text=(q.PACK/'review_data.js').read_text(encoding='utf-8')
    assert 'hill_global08' not in text and 'candidate_components' not in text and '"score"' not in text


def test_held_and_preprocessing_data_are_preserved_in_bundle(delivered_package):
    data=q.read(q.PACK/'data/cohorts.json');objects=q.read(q.PACK/'data/objects.json')
    assert len(data['ordinary'])==574 and len(data['severe'])==9
    held=[r for r in data['doorway'] if r['status']=='held']
    assert len(held)==92 and all(r['metrics'] is None and r['reason_codes'] for r in held)
    assert sum(r['original_holdout'] for r in data['doorway'])==8
    assert len(objects['geometry_unavailable'])==5
    assert all(r['original_holdout'] is False for r in data['ordinary'])
