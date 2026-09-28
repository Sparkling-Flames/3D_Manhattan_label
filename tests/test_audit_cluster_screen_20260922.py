import numpy as np

from tools.thesis_main.analysis.audit_cluster_screen_20260922 import relation_target, x_gap_percent


def test_uncertain_answers_and_panorama_seam():
    assert relation_target({'relation': '同一表达，可同簇', 'defer': False}) is True
    assert relation_target({'relation': '不同表达，应分开', 'defer': False}) is False
    assert relation_target({'relation': '暂不能判断', 'defer': False}) is None
    assert relation_target({'relation': '同一表达，可同簇', 'defer': True}) is None
    # 1023 and 1 are two pixels apart across the seam, not 1022.
    assert np.isclose(x_gap_percent(np.array([[1023., 80.], [1., 420.]]), np.array([[0, 1]]))[0], 2 / 1024 * 100)
