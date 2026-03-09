# 测试目录结构

此目录包含 HOHONET 标注分析工具链的测试代码。

## 目录结构

```
tests/
├── __init__.py
├── conftest.py              # pytest 配置与共享 fixtures
├── test_analyze_quality.py  # 核心分析脚本单元测试
├── fixtures/                # 当前在库的测试用数据
│   ├── sample_export_minimal.json
│   └── README.json
```

## 运行测试

```bash
# 在项目根目录执行
cd d:/Work/HOHONET

# 运行所有测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_analyze_quality.py -v

# 运行带覆盖率报告
pytest tests/ --cov=tools --cov-report=html

# 只运行回归测试
pytest tests/ -v -k "regression"
```

## 测试设计原则

1. **分层测试**: 单元测试 → 集成测试 → 端到端测试
2. **Golden Files**: 使用预期输出文件验证可复现性
3. **回归测试**: 确保历史 Bug 不复发
4. **Fixtures**: 共享测试数据，避免重复创建

## 测试覆盖度分析

### 当前状态（2026-03-07）

**当前有效测试入口**: `tests/test_analyze_quality.py`

已验证：

- `pytest tests/test_analyze_quality.py -q` 通过（32 passed）

当前判断：

- `tests/` 目录不是“没用”，它仍然能覆盖 `analyze_quality.py` 的核心单元逻辑。
- 但 README 里此前写到的 `test_integration.py`、`golden/`、`sample_export_edge_cases.json`、`sample_active_logs/` 并不在当前仓库中，属于历史计划，不是现状。
- 因此当前测试的价值主要是“核心计算与回归单测”，还不能视为完整端到端验证。

| 维度       | 覆盖度 | 说明                  |
| ---------- | ------ | --------------------- |
| 功能正确性 | 85%    | 核心计算逻辑已覆盖    |
| 边界条件   | 60%    | 缺少极端输入测试      |
| 异常处理   | 50%    | 缺少并发/恢复场景     |
| 可复现性   | 40%    | Golden Files 仍未实现 |

### 缺失的关键测试场景

#### 🔴 高优先级缺失（P0 - 需立即补充）

| 用例ID    | 测试场景                 | 风险                                           | 实施成本 |
| --------- | ------------------------ | ---------------------------------------------- | -------- |
| TC-U009   | **Unicode/特殊字符处理** | 标注者ID包含中文/emoji导致编码错误             | 低       |
| TC-G009   | **浮点精度边界**         | 极小/极大多边形（1e-10 vs 1e10）计算溢出       | 中       |
| TC-U010   | **空值三态区分**         | `scope=""` vs `scope=None` vs `scope=np.nan`   | 低       |
| TC-I007   | **重复数据检测**         | 相同 `(task_id, annotator_id)` 在JSON中出现2次 | 中       |
| TC-REG004 | **Golden Files实现**     | fixtures存在但golden缺失，无法验证可复现性     | 高       |

**示例代码**：

```python
# TC-U009: Unicode/特殊字符
def test_unicode_annotator_id():
    """标注者ID包含中文/emoji"""
    result = parse_quality_flags_v2(
        {'annotator_id': '用户A😊', 'scope': ['normal']},
        mode='v2'
    )
    assert result['is_normal'] == True

# TC-G009: 浮点精度边界
def test_iou_extreme_scale():
    """极小多边形vs极大多边形"""
    tiny = [(0, 0), (1e-10, 0), (1e-10, 1e-10), (0, 1e-10)]
    huge = [(0, 0), (1e10, 0), (1e10, 1e10), (0, 1e10)]
    # 应能正常计算，不报错或溢出
    iou_tiny = compute_iou(tiny, tiny)
    iou_huge = compute_iou(huge, huge)
    assert iou_tiny == pytest.approx(1.0)
    assert iou_huge == pytest.approx(1.0)

# TC-U010: 空值三态
def test_scope_empty_vs_none_vs_nan():
    """区分 "" / None / np.nan"""
    r1 = parse_quality_flags_v2({'scope': ""}, mode='v2')
    r2 = parse_quality_flags_v2({'scope': None}, mode='v2')
    r3 = parse_quality_flags_v2({'scope': np.nan}, mode='v2')
    # 都应标记为 scope_missing=True
    assert r1['scope_missing'] == True
    assert r2['scope_missing'] == True
    assert r3['scope_missing'] == True
```

#### 🟡 中等优先级缺失（P1 - 建议补充）

| 用例ID  | 测试场景         | 风险                                | 实施成本 |
| ------- | ---------------- | ----------------------------------- | -------- |
| TC-I006 | **时间戳跨界**   | active_logs session跨越午夜00:00    | 中       |
| TC-I008 | **大规模数据集** | 10k+ 任务的内存/性能测试            | 高       |
| TC-I009 | **异常恢复**     | CSV部分写入后中断，重新运行         | 中       |
| TC-R007 | **LOO循环依赖**  | 构造A→B→C→A的循环medoid（理论验证） | 低       |

#### 🟢 已覆盖但可增强（P2）

| 场景             | 当前测试           | 可增强点                             |
| ---------------- | ------------------ | ------------------------------------ |
| **边界RMSE**     | TC-G005            | 增加cyclic alignment跨越拼接缝的验证 |
| **Bootstrap CI** | TC-R001-R002       | 增加TC-R008: n=1000高斯分布收敛性    |
| **Medoid确定性** | 已修复（str(uid)） | 增加tie-break测试用例                |

### Fuzzy Testing 目标

**目标覆盖度**: 90%+ (当前: 70%)

**补充优先级**：

1. **P0**: TC-U009, TC-G009, TC-U010, TC-I007, TC-REG004 (5个用例) → 达到80%
2. **P1**: TC-I006, TC-I008, TC-I009 (3个用例) → 达到85%
3. **P2**: 增强已有测试 (2个用例) → 达到90%+

### 实施计划

```bash
# Phase 1: P0用例 (1周)
1. 创建 tests/test_edge_cases.py
2. 实现 TC-U009, TC-G009, TC-U010
3. 创建 tests/golden/ 目录并生成基线文件
4. 实现 TC-REG004 golden file 比对

# Phase 2: P1用例 (1周)
5. 创建 tests/test_integration_advanced.py
6. 实现 TC-I006, TC-I007, TC-I009
7. 性能基准测试 TC-I008

# Phase 3: 增强测试 (3天)
8. 增强 TC-G005 cyclic alignment
9. 增强 TC-R001-R002 Bootstrap CI
10. 全面覆盖率报告 (target: 90%+)
```

### 测试数据管理

**Fixtures 命名约定**：

```
sample_export_minimal.json          # 3任务，2标注者，基础场景
sample_export_edge_cases.json       # Unicode/空值/极端值
sample_export_unicode.json          # 专门测试编码
sample_export_large.json            # 1000+任务性能测试
```

**Golden Files 版本控制**：

- 每次 analyze_quality.py 输出格式变更时，需更新 golden files
- 使用 Git 跟踪，便于 diff 和回滚
- 在 CHANGELOG.md 中记录 golden file 版本变化

## 相关文档

- [docs/TEST_PLAN_AND_REVIEW.md](../docs/TEST_PLAN_AND_REVIEW.md): 完整测试计划与用例设计（30+用例详细说明）
- [docs/ANALYSIS_DATA_FLOW.md](../docs/ANALYSIS_DATA_FLOW.md): 数据流与门控逻辑（含已知问题追踪）
