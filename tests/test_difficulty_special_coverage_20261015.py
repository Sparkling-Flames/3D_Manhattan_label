from tools.thesis_main.analysis.difficulty_special_coverage_20261015 import markability


def test_difficult_doorway_does_not_imply_unannotatable():
    assert markability({'oos_subtype': 'subtype_not_resolved', 'doorway_status': 'difficult'}) == 'unknown_not_inferred_from_difficulty'


def test_nonorthogonal_can_be_annotatable():
    assert markability({'oos_subtype': 'nonorthogonal_annotatable', 'doorway_status': 'not_recorded'}) == 'conditional_nonorthogonal_annotatable'


def test_explicit_doorway_annotation_is_preserved():
    assert markability({'oos_subtype': 'not_recorded', 'doorway_status': 'annotatable'}) == 'recorded_doorway_annotatable'
