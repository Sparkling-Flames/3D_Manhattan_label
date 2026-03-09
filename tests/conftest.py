"""
pytest 配置与共享 fixtures

用于 HOHONET 标注分析工具链的测试。
"""

import pytest
import sys
from pathlib import Path

# 确保 tools 目录在 Python 路径中
PROJECT_ROOT = Path(__file__).parent.parent
TOOLS_DIR = PROJECT_ROOT / "tools"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


@pytest.fixture
def project_root():
    """返回项目根目录路径"""
    return PROJECT_ROOT


@pytest.fixture
def tools_dir():
    """返回 tools 目录路径"""
    return TOOLS_DIR


@pytest.fixture
def fixtures_dir():
    """返回测试 fixtures 目录路径"""
    return Path(__file__).parent / "fixtures"

@pytest.fixture
def sample_corners_8():
    """8 个角点的样例数据（4 对 ceiling/floor）"""
    import numpy as np
    return np.array([
        [100, 200],  # ceil 0
        [100, 400],  # floor 0
        [300, 180],  # ceil 1
        [300, 420],  # floor 1
        [600, 190],  # ceil 2
        [600, 410],  # floor 2
        [800, 210],  # ceil 3
        [800, 390],  # floor 3
    ], dtype=np.float32)


@pytest.fixture
def sample_corners_6():
    """6 个角点的样例数据（3 对 ceiling/floor）"""
    import numpy as np
    return np.array([
        [100, 200],
        [100, 400],
        [400, 190],
        [400, 410],
        [700, 200],
        [700, 400],
    ], dtype=np.float32)


@pytest.fixture
def sample_polygon_square():
    """正方形多边形样例"""
    return [(0, 0), (100, 0), (100, 100), (0, 100)]


@pytest.fixture
def sample_choice_map_in_scope():
    """In-scope 的 choice_map 样例"""
    return {
        'scope': ['In-scope：只标相机房间'],
        'difficulty': ['遮挡', '低纹理'],
        'model_issue': [],
    }


@pytest.fixture
def sample_choice_map_oos():
    """OOS 的 choice_map 样例"""
    return {
        'scope': ['OOS：边界不可判定'],
        'difficulty': [],
        'model_issue': [],
    }


@pytest.fixture
def sample_choice_map_empty():
    """空的 choice_map 样例（scope 缺失）"""
    return {}
