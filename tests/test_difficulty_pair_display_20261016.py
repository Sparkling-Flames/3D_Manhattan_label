from copy import deepcopy
import numpy as np
import pytest
from tools.thesis_main.analysis.difficulty_pair_display_20261016 import display_pairs, apply_correction, normalize_source_evidence
from tools.thesis_main.analysis.difficulty_coarse_closeout_20261014 import floor


def test_preview_preserves_floor_and_is_not_a_complete_reference():
    polygon=[[-1,-1],[1,-1],[1,1],[-1,1]]
    ref=dict(full_reference_available=False,evidence=dict(constructions=[dict(source_plane=dict(plane=[0,0,0.8]))]))
    before=deepcopy(ref)
    points,status=display_pairs(polygon,ref)
    assert status=='source_ceiling_extrapolation_preview'
    assert np.allclose(floor(points),polygon)
    assert np.allclose(np.array(points)[::2,0],np.array(points)[1::2,0])
    assert ref==before


def test_existing_full_pairs_are_reused_and_invalid_ceiling_rejected():
    p=[[1,100],[1,400]]
    assert display_pairs([],dict(full_reference_available=True,points_1024x512=p))==(p,'existing_full_reference')
    with pytest.raises(ValueError):
        display_pairs([[1,1]],dict(full_reference_available=False,evidence=dict(constructions=[dict(source_plane=dict(plane=[0,0,-1]))])))


def test_preview_evidence_uses_repo_relative_archive_without_mutating_source():
    source=dict(constructions=[dict(source_plane=dict(archive=r'C:\Users\ASUS\Downloads\label_data.zip'))])
    result=normalize_source_evidence(source,'data/external/label_data.zip')
    assert result['constructions'][0]['source_plane']['archive']=='data/external/label_data.zip'
    assert source['constructions'][0]['source_plane']['archive'].startswith('C:')


def test_user_pending_and_gt_error_take_priority():
    a=dict(image='uNb9QFRL6hY-36',current_class='简单',difficulty_analysis_eligible=True)
    apply_correction(a)
    assert a['current_class']=='待复核' and not a['difficulty_analysis_eligible']
    b=dict(image='zsNo4HB9uLZ-05',current_class='简单',difficulty_analysis_eligible=True)
    apply_correction(b)
    assert b['gt_error_excluded'] and not b['difficulty_analysis_eligible']
