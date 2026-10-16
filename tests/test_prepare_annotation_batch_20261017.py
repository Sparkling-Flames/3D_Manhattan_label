import numpy as np
import pytest

from tools.thesis_main.data_prep.prepare_annotation_batch_20261017 import numbered_pairs


def test_numbered_pairs_keep_source_indices_before_applying_manual_order():
    raw=[[75,30],[75,70],[10,25],[10,75],[40,30],[40,70]]
    pairs=numbered_pairs(raw)
    assert pairs==[[0,1],[2,3],[4,5]]
    assert np.asarray(raw).tolist()==raw


def test_ambiguous_pairing_is_not_chosen_using_gt_or_quality():
    with pytest.raises(ValueError,match='ambiguous_horizontal_assignment'):
        numbered_pairs([[20,30],[20,35],[20,70],[20,75]])
