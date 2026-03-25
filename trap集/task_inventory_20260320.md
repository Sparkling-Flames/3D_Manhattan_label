# Trap 任务清单

文件名保留 `20260320`，但内容已经按当前 latest export 与目录结构刷新。

当前刷新依据：

- latest export：`export_label/人工精标/project-20-at-2026-03-25-01-17-926f4b7f.json`
- 当前 `trap集` 实际目录
- `analysis_results/truth_layer_extraction_20260324/truth_layer_extraction_summary_v1.json`

## 当前状态

- `manual`：30 个任务
- `semi`：18 个任务
- `OOS`：10 个任务
- 总计：58 个任务
- 当前 `58/58` 都已在 latest export 中 join 到
- 当前 `58/58` 都具备 `kp + scope + difficulty + model_issue`

注意：

- 这份清单是当前 candidate inventory，不是 final selection
- 只有明确带 `低优先` 的任务，才默认不进入人工锚点集
- 其他括号说明默认只视为 review annotation，不自动降级
- `task711(中低优先,难标注)` 是当前遮罩 family 的保留例外，`711 > 696`

## 汇总

| 类别 | 任务数 |
| --- | ---: |
| `manual` | 30 |
| `semi` | 18 |
| `OOS` | 10 |

## manual

| 子类 | 数量 | 任务 |
| --- | ---: | --- |
| `玻璃` | 6 | `task470, task509(可能有歧义), task555, task567(低优先), task697, task714(高难度)` |
| `非常简单` | 4 | `task550, task554, task556, task630` |
| `拼接缝及拉伸` | 5 | `task462, task510, task570(同时是角点错位), task670, task687` |
| `纹理弱 纯色墙` | 3 | `task559, task569(同时是一角多点,纹理弱), task614` |
| `遮挡明显` | 10 | `task497, task533(低优先,有歧义), task562, task564(较为困难), task578, task635(低优先,有歧义,尽量不考虑), task676(低优先,太难标注了,暂时不考虑), task677(略微有点遮挡), task707, task717` |
| `遮罩` | 2 | `task696(低优先,不确定,难标注), task711(中低优先,难标注)` |

## semi

| 子类 | 数量 | 任务 |
| --- | ---: | --- |
| `模型标注质量好` | 6 | `task492, task501, task568, task572, task573, task576` |
| `模型预标注失败` | 1 | `task475(低优先)` |
| `漏标` | 2 | `task579, task712(墙角太难了,低优先)` |
| `角点错位` | 2 | `task474, task625` |
| `角点重复` | 1 | `task477` |
| `跨门扩张` | 3 | `task493, task499, task577` |
| `过度解析` | 3 | `task505, task574, task683` |

## OOS

| 子类 | 数量 | 任务 |
| --- | ---: | --- |
| `边界不可判定` | 2 | `task459, task609` |
| `错层,天花板下凸` | 5 | `task476, task495(不确定算不算错层), task496, task575, task661` |
| `几何假设不成立(弧形墙)` | 2 | `task526, task560(低优先,感觉可以标注)` |
| `证据不足` | 1 | `task529` |

## 当前 inventory 的使用提醒

1. 当前目录与 latest export 的 `scope` 已对齐，没有活动中的 directory-scope mismatch。
2. 当前 `manual=30 / semi=18 / OOS=10` 只说明候选池已经整理好，不代表 Stage 1 executable freeze 已完成。
3. 当前 final geometry 参考应以 latest export 的 `kp` 为准，而不是目录里的 legacy `.txt`。
4. 当前 `poly` 仅作 residue 标记，不纳入 thesis-facing 主 geometry contract。
