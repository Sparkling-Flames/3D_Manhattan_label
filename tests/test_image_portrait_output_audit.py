import numpy as np
import pytest
from tools.thesis_main.analysis.image_portrait.audit_outputs import check_npz
from tools.thesis_main.analysis.image_portrait import audit_outputs


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


def test_partial_modern_payload_is_not_complete(tmp_path, monkeypatch):
    monkeypatch.setattr(audit_outputs, 'read_images', lambda: [{'image_id': 'image'}])
    directory = tmp_path/'models/da3'
    directory.mkdir(parents=True)
    np.savez_compressed(directory/'image.features.npz', image_ids=np.asarray(['image']))
    report = audit_outputs.audit(tmp_path)['models']['da3']
    assert report['numerical_image_count'] == 1
    assert report['complete_payload_image_count'] == 0
    assert report['incomplete_payload_image_ids'] == ['image']
