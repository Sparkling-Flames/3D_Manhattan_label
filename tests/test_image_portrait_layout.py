import numpy as np
import pytest
from tools.thesis_main.analysis.image_portrait.layout_models import guided_branches, complete_export


def test_shared_transformer_branch_order():
    enclosed = np.ones((1,256,512), dtype=np.float32)
    extended = enclosed*2
    result = guided_branches([enclosed, extended])
    assert result['fg_enclosed'].shape == (1,512,256)
    assert np.all(result['fg_enclosed'] == 1)
    assert np.all(result['fg_extended'] == 2)
    with pytest.raises(ValueError):
        guided_branches([enclosed])


def test_resume_rejects_partial_payload(tmp_path):
    import json
    path, status = tmp_path/'a.npz', tmp_path/'a.json'
    status.write_text(json.dumps(dict(image_id='a',model='bilayout',status='ok',
        phases=[dict(yaw=y,status='ok') for y in (0,90,180,270)])))
    np.savez_compressed(path, only_one_value=np.ones(1))
    assert not complete_export(path,status,'a','bilayout')
    path.write_bytes(b'PK\x03\x04truncated')
    assert not complete_export(path,status,'a','bilayout')
