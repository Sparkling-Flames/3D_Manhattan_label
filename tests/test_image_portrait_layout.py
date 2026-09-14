import numpy as np
import pytest
from tools.thesis_main.analysis.image_portrait.layout_models import guided_branches


def test_shared_transformer_branch_order():
    enclosed = np.ones((1,256,512), dtype=np.float32)
    extended = enclosed*2
    result = guided_branches([enclosed, extended])
    assert result['fg_enclosed'].shape == (1,512,256)
    assert np.all(result['fg_enclosed'] == 1)
    assert np.all(result['fg_extended'] == 2)
    with pytest.raises(ValueError):
        guided_branches([enclosed])
