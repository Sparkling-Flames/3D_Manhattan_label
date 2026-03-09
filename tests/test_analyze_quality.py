"""
analyze_quality.py 单元测试

测试覆盖范围：
- TC-U001 ~ TC-U008: 数据解析模块
- TC-G001 ~ TC-G008: 几何计算模块
- TC-L001 ~ TC-L005: 门控逻辑模块
- TC-R001 ~ TC-R006: 一致性/可靠度模块
- TC-REG001 ~ TC-REG003: 回归测试
"""

import pytest
import numpy as np
from pathlib import Path
import sys

# 导入被测模块
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
from analyze_quality import (
    parse_quality_flags_v2,
    compute_iou,
    compute_boundary_mse_rmse,
    compute_rmse,
    compute_layout_standard_metrics,
    compute_pointwise_rmse_cyclic,
    _pair_keypoints_to_layout,
    _bootstrap_ci,
    _split_choice_values,
    _scope_is_oos,
    extract_data,
)


# =============================================================================
# TC-U: 数据解析模块测试
# =============================================================================

class TestSplitChoiceValues:
    """TC-U007 ~ TC-U008: _split_choice_values 函数测试"""
    
    def test_semicolon_separated_string(self):
        """TC-U007: 分号分隔字符串"""
        result = _split_choice_values("a;b;c")
        assert result == ["a", "b", "c"]
    
    def test_list_input(self):
        """TC-U008: 列表输入"""
        result = _split_choice_values(["a", "b"])
        assert result == ["a", "b"]
    
    def test_empty_string(self):
        """空字符串返回空列表"""
        assert _split_choice_values("") == []
    
    def test_none_input(self):
        """None 输入返回空列表"""
        assert _split_choice_values(None) == []
    
    def test_whitespace_handling(self):
        """处理空格"""
        result = _split_choice_values("  a ; b ; c  ")
        assert result == ["a", "b", "c"]


class TestParseQualityFlagsV2:
    """TC-U004 ~ TC-U006: parse_quality_flags_v2 函数测试"""
    
    def test_scope_missing(self, sample_choice_map_empty):
        """TC-U004: scope 缺失时返回 tri-state None"""
        result = parse_quality_flags_v2(sample_choice_map_empty, mode='v2')
        assert result['scope_missing'] == True
        assert result['is_oos'] is None
        assert result['is_normal'] is None
    
    def test_oos_detection(self, sample_choice_map_oos):
        """TC-U005: OOS 判定"""
        result = parse_quality_flags_v2(sample_choice_map_oos, mode='v2')
        assert result['is_oos'] == True
        assert result['scope_missing'] == False
    
    def test_in_scope_detection(self, sample_choice_map_in_scope):
        """TC-U006: In-scope 判定"""
        result = parse_quality_flags_v2(sample_choice_map_in_scope, mode='v2')
        assert result['is_oos'] == False
        assert result['is_normal'] == True
        assert result['scope_missing'] == False
    
    def test_difficulty_flags(self, sample_choice_map_in_scope):
        """difficulty 字段解析"""
        result = parse_quality_flags_v2(sample_choice_map_in_scope, mode='v2')
        assert result['is_occlusion'] == True  # "遮挡" 应被识别
    
    def test_invalid_mode_raises(self):
        """无效 mode 应抛出异常"""
        with pytest.raises(ValueError):
            parse_quality_flags_v2({}, mode='legacy')


class TestScopeIsOos:
    """_scope_is_oos 辅助函数测试"""
    
    def test_oos_prefix(self):
        """OOS 前缀判定"""
        assert _scope_is_oos(['OOS：边界不可判定']) == True
        assert _scope_is_oos(['OOS：几何假设不成立']) == True
    
    def test_in_scope(self):
        """In-scope 不是 OOS"""
        assert _scope_is_oos(['In-scope：只标相机房间']) == False
    
    def test_empty_list(self):
        """空列表不是 OOS"""
        assert _scope_is_oos([]) == False


# =============================================================================
# TC-G: 几何计算模块测试
# =============================================================================

class TestComputeIoU:
    """TC-G001 ~ TC-G003: compute_iou 函数测试"""
    
    def test_identical_polygons(self, sample_polygon_square):
        """TC-G001: 完全重合"""
        iou = compute_iou(sample_polygon_square, sample_polygon_square)
        assert iou == pytest.approx(1.0)
    
    def test_disjoint_polygons(self):
        """TC-G002: 完全不重合"""
        poly1 = [(0, 0), (1, 0), (1, 1), (0, 1)]
        poly2 = [(10, 10), (11, 10), (11, 11), (10, 11)]
        iou = compute_iou(poly1, poly2)
        assert iou == pytest.approx(0.0)
    
    def test_empty_polygon(self, sample_polygon_square):
        """TC-G003: 空多边形"""
        assert compute_iou([], sample_polygon_square) == 0.0
        assert compute_iou(sample_polygon_square, []) == 0.0
        assert compute_iou([], []) == 0.0
    
    def test_partial_overlap(self):
        """部分重叠"""
        poly1 = [(0, 0), (2, 0), (2, 2), (0, 2)]  # 面积 4
        poly2 = [(1, 0), (3, 0), (3, 2), (1, 2)]  # 面积 4，交集 2
        iou = compute_iou(poly1, poly2)
        # IoU = 2 / (4 + 4 - 2) = 2/6 ≈ 0.333
        assert iou == pytest.approx(1/3, rel=0.01)


class TestComputeRmse:
    """compute_rmse 函数测试"""
    
    def test_identical_corners(self, sample_corners_8):
        """相同角点 RMSE = 0"""
        rmse = compute_rmse(sample_corners_8, sample_corners_8)
        assert rmse == pytest.approx(0.0)
    
    def test_empty_corners(self):
        """空角点返回 None"""
        import numpy as np
        assert compute_rmse(np.array([]), np.array([[1, 2]])) is None
        assert compute_rmse(np.array([[1, 2]]), np.array([])) is None


class TestPairKeypointsToLayout:
    """TC-G007 ~ TC-G008: _pair_keypoints_to_layout 函数测试"""
    
    def test_normal_pairing(self, sample_corners_8):
        """TC-G007: 正常配对"""
        pairs, stats = _pair_keypoints_to_layout(
            sample_corners_8, width=1024, return_stats=True
        )
        assert stats['n_points'] == 8
        assert stats['n_pairs'] == 4
        assert stats['odd_points'] == False
        assert stats['coverage'] == pytest.approx(1.0)
    
    def test_odd_points_detection(self):
        """TC-G008: 奇数点检测"""
        import numpy as np
        corners_7 = np.array([
            [100, 200], [100, 400],
            [300, 180], [300, 420],
            [600, 190], [600, 410],
            [800, 210],  # 只有 7 个点
        ], dtype=np.float32)
        pairs, stats = _pair_keypoints_to_layout(corners_7, width=1024, return_stats=True)
        assert stats['odd_points'] == True
    
    def test_empty_corners(self):
        """空角点"""
        pairs, stats = _pair_keypoints_to_layout(None, width=1024, return_stats=True)
        assert stats['n_points'] == 0
        assert stats['n_pairs'] == 0


class TestComputeBoundaryMseRmse:
    """TC-G004 ~ TC-G005: compute_boundary_mse_rmse 函数测试"""
    
    def test_identical_boundaries(self, sample_corners_8):
        """TC-G004: 相同边界"""
        mse, rmse, meta = compute_boundary_mse_rmse(
            sample_corners_8, sample_corners_8, width=1024, height=512
        )
        assert rmse == pytest.approx(0.0, abs=1e-3)
    
    def test_different_point_counts(self, sample_corners_8, sample_corners_6):
        """TC-G005: 点数不一致仍能计算（鲁棒性）"""
        mse, rmse, meta = compute_boundary_mse_rmse(
            sample_corners_8, sample_corners_6, width=1024, height=512
        )
        # 应该能计算出结果（不是 None）
        assert rmse is not None or meta.get('pairing_failure_reason')


# =============================================================================
# TC-R: 一致性/可靠度模块测试
# =============================================================================

class TestBootstrapCI:
    """TC-R001 ~ TC-R002: _bootstrap_ci 函数测试"""
    
    def test_empty_array(self):
        """TC-R001: 空数组"""
        stat, lo, hi = _bootstrap_ci([], np.median)
        assert stat is None
        assert lo is None
        assert hi is None
    
    def test_single_value(self):
        """TC-R002: 单值"""
        stat, lo, hi = _bootstrap_ci([0.5], np.median)
        assert stat == pytest.approx(0.5)
        assert lo == pytest.approx(0.5)
        assert hi == pytest.approx(0.5)
    
    def test_multiple_values(self):
        """多值时 CI 应该包含 median"""
        values = [0.3, 0.5, 0.7, 0.8, 0.9]
        stat, lo, hi = _bootstrap_ci(values, np.median, n_iters=500, ci=0.95, seed=42)
        assert stat == pytest.approx(0.7)  # median
        assert lo <= stat <= hi
    
    def test_reproducibility(self):
        """相同 seed 应产生相同结果"""
        values = [0.1, 0.2, 0.3, 0.4, 0.5]
        r1 = _bootstrap_ci(values, np.median, seed=123)
        r2 = _bootstrap_ci(values, np.median, seed=123)
        assert r1 == r2


# =============================================================================
# TC-REG: 回归测试
# =============================================================================

class TestRegressionBugs:
    """TC-REG001 ~ TC-REG003: 回归测试"""
    
    def test_scope_missing_no_is_normal(self):
        """TC-REG002: scope 缺失时 is_normal 必须为 None，不能为 True"""
        result = parse_quality_flags_v2({}, mode='v2')
        # 关键断言：不能是 True
        assert result['is_normal'] is None
        assert result['is_oos'] is None
        assert result['scope_missing'] == True
    
    def test_v2_mode_no_legacy_fallback(self):
        """TC-REG002 补充: v2 模式不应回退到 legacy 推断"""
        # 模拟有 quality 文本但无 scope 字段的情况
        choice_map = {}
        quality_all = "Normal"  # 旧版可能从这里推断
        result = parse_quality_flags_v2(choice_map, quality_all=quality_all, mode='v2')
        # 即使 quality_all 包含 "Normal"，也不应推断 is_normal=True
        assert result['is_normal'] is None
        assert result['scope_missing'] == True


class TestLayoutStandardMetricsP01:
    """TC-REG003: P0-1 回归测试 - layout 指标不应因 n_pairs_mismatch 失败"""
    
    def test_layout_metrics_no_mismatch_gate(self, sample_corners_8, sample_corners_6):
        """TC-REG003: layout 指标应能计算不同点数的输入（P0-1 核心验证）"""
        from analyze_quality import compute_layout_standard_metrics
        
        # 8点 vs 6点：点数不同，但 layout 2D/3D IoU 应该能计算
        iou2d, iou3d, depth_rmse, delta1, used, meta = compute_layout_standard_metrics(
            sample_corners_8, sample_corners_6, width=1024, height=512
        )
        
        # P0-1 核心断言：gate_reason 不应是 n_pairs_mismatch
        assert meta.get("gate_reason") != "n_pairs_mismatch", \
            f"P0-1 REGRESSION: layout 指标仍因 n_pairs_mismatch 失败! gate_reason={meta.get('gate_reason')}"
        
        # 如果 used=True，应该有 2D/3D IoU
        if used:
            assert iou2d is not None and 0.0 <= iou2d <= 1.0
            assert iou3d is not None and 0.0 <= iou3d <= 1.0
    
    def test_pointwise_still_requires_match(self, sample_corners_8, sample_corners_6):
        """TC-REG003 补充: pointwise RMSE 仍应因点数不同而拒绝计算"""
        from analyze_quality import compute_pointwise_rmse_cyclic
        
        # pointwise RMSE 需要点级对应，应当失败
        rmse, used, meta = compute_pointwise_rmse_cyclic(
            sample_corners_8, sample_corners_6, width=1024
        )
        
        # pointwise 指标应该因 n_pairs_mismatch 失败（这是设计意图）
        assert used == False
        assert meta.get("gate_reason") == "n_pairs_mismatch", \
            f"Expected n_pairs_mismatch for pointwise, got: {meta.get('gate_reason')}"


# =============================================================================
# 运行入口
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
