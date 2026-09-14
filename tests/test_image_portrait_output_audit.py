import numpy as np
import pytest
from tools.thesis_main.analysis.image_portrait.audit_outputs import check_npz


def test_no_pickle_and_no_nonfinite(tmp_path):
    path = tmp_path/'sample.npz'
    np.savez_compressed(path, image_ids=np.array(['a']), prediction=np.array([1.25],dtype=np.float32))
    assert check_npz(path) == 2
    np.savez_compressed(path, prediction=np.array([np.nan]))
    with pytest.raises(ValueError, match='nonfinite'):
        check_npz(path)
    np.savez_compressed(path, prediction=np.array([{}],dtype=object))
    with pytest.raises(ValueError):
        check_npz(path)
