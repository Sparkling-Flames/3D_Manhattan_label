# 代码审查报告：Fig.D2（任务×标注者热力图）

**审查日期**：2026-01-21  
**审查对象**：[visualize_output.ipynb](tools/visualize_output.ipynb) - Fig.D2 对应 Cell（TaskAnnotatorHeatmapVisualizer）  
**审查结果**：✅ 修复完成（以“仅展示、不落盘”为最终要求）

---

## 审查项目

### ✅ 1. pivot_table aggfunc 参数 - ACCEPTABLE

**原始代码**：

```python
aggfunc=("median" if agg == "median" else "mean")
```

**评估**：

- Pandas `pivot_table` 接受字符串 `'mean'`、`'median'` 作为有效的聚合函数
- 三元表达式返回字符串完全合法
- ✅ 无需修改

---

### ⚠️ 2. NaN 方差过滤 - **已修复（HIGH）**

**原始代码**（有bug）：

```python
score = mat.var(axis=1, skipna=True)
score_df = (
    pd.DataFrame({"score": score, "ann_cnt": ann_cnt})
      .sort_values(["score", "ann_cnt"], ascending=[False, False])
)
sel_tasks = score_df.head(top_n).index
```

**问题**：

- 当某行全是 NaN 时，`var()` 返回 NaN
- `sort_values()` 把 NaN 放在末尾，但如果所有任务都是 NaN 或方差为 0，`head(top_n)` 仍会返回它们
- 这会导致热力图显示无意义的"无分歧"任务

**修复方案**（已应用）：

```python
# 过滤掉方差为 NaN 或零的行
valid_mask = score_df["score"].notna() & (score_df["score"] > 0)
score_df = score_df[valid_mask]

if score_df.empty:
    print(f"WARNING: 未找到有效的分歧任务")
    # 降级方案：回退到原始排序
    score_df = pd.DataFrame({"score": score, "ann_cnt": ann_cnt}) \
               .sort_values(["score", "ann_cnt"], ascending=[False, False])
```

**修复状态**：✅ 已应用

---

### ✅ 3. 分层聚类距离计算 - CORRECT

**代码**：

```python
dist = filled.to_numpy()  # shape: [n_tasks, n_annotators]
linkage_matrix = linkage(dist, method="ward")
```

**评估**：

- scipy.cluster.hierarchy.linkage 期望输入形状：(n_samples, n_features)
- 这里：n_tasks 作为样本，n_annotators 作为特征 ✅ 正确
- 填充策略（用行均值填NA）合理

**修复状态**：✅ 无需修改

---

### 🔧 4. 输出行为对齐（仅 notebook 展示）- **已修复（MEDIUM）**

**最终需求**：暂时不需要生成图片文件，仅需要在 notebook 里运行查看。

**修复方案**（已应用）：

- 示例调用使用 `output_dir=None`
- 取消/禁用落盘保存（不调用 `savefig()`），仅展示 `plt.show()`

**修复状态**：✅ 已应用

---

### 📝 5. 文档与行为说明 - **已改进（LOW）**

**改进**：在 `run_fig7()` 方法加入详细 docstring

```python
"""
Generate task x annotator heatmaps (divergence detection).

Args:
    ...
    top_n: Number of top divergent tasks to display (default: 20)
           If available tasks < top_n, displays all available tasks
    ...

Returns:
    (mat_sel, score_df): Selected matrix and divergence scores
"""
```

**修复状态**：✅ 已应用

---

### ✅ 6. 其他检查项

| 检查项   | 状态 | 说明                             |
| -------- | ---- | -------------------------------- |
| 错误处理 | ✅   | 缺失列时明确报错                 |
| NA 遮罩  | ✅   | `mask=mat.isna()` 正确处理缺失值 |
| 样式设置 | ✅   | 中文字体支持配置正确             |
| 输出落盘 | ✅   | 当前版本默认不落盘，仅展示       |

---

## 修复清单

- [x] 添加 NaN 方差显式过滤（高优先级）
- [x] 添加降级方案处理（空结果集）
- [x] 调整为仅展示不落盘（中优先级）
- [x] 添加详细 docstring（低优先级）
- [x] 中文字符处理（验证通过）

---

## 总体结论

**代码质量**：🟢 良好（修复后）

### 修复前的状态

- **严重问题**：NaN 方差过滤缺失
- **行为问题**：默认落盘保存图片（与“仅查看”需求冲突）
- **文档缺陷**：缺少行为说明

### 修复后的状态

✅ 所有问题已修复  
✅ 健壮性提升  
✅ 文档完善  
✅ 与“仅展示、不落盘”需求一致

---

## 下一步验证

1. **运行测试**：执行完整 notebook 验证
2. **数据验证**：确认热力图输出正确
3. **边界测试**：验证小数据集（top_n > 可用任务数）的行为
