# Manual＋Semi 联合历史分类：2026-10-22 阶段成果

本目录使用既有 **v2 真实数据**开展新的人员分类研究。`personnel_useful_taxonomy_v3_20261021` 的 v3 是上一轮研究编号，不是底层数据版本。本轮不改变资格、参考、原标注、评分或融合。

## 与旧工作的区别

上一轮 `V3_JOINT_QT` 的“联合”指结构与 Q/T 变量域联合：Manual 与 Semi 各自形成类别。本轮把**同一位人员在两种条件的历史共同用于形成标签**，之后仍须分别评价 Manual 与 Semi。更早的 `MV_TDScopeSemi_manual_new` 已用 Semi 编辑／错误机会行为辅助 Manual；这是真实的旧跨条件方案，不写成尚未实现。本轮补的是双条件几何、尺度、质量／时间以及同图条件差异。

三种有依据的候选分别选型，**三种方法不代表三类上限**：

| 方法 | 实际形成输入 | 支持要求与含义 |
|---|---|---|
| `XCOND_GEOM` | Manual 与 Semi 的转折／短边、近共线点、面积／高度；E/R/G 域等权 | 每种条件至少 12 图、4 楼；双条件表达与尺度的工作分类 |
| `XCOND_GEOM_QT` | 上述几何加两条件各自 Q 均值／低尾、同来源相对时间；五域等权 | 加原有 Q/T 机会门槛；Q/T 真正进入形成，不只是事后解释 |
| `XCOND_PAIRED` | 同人同图同参考配对的结构／尺度共同水平与 Semi−Manual 差异 | 至少 6 个配对图、3 楼；不把不同图的均值差冒充换条件效果 |

配对记录中每个条件分别按配对人员的同图中位数中心化，再取共同水平与差异；原始条件差也保留。它描述当前任务历史中的条件响应，不能解释为随机实验的条件因果效应。几乎只有新批人员有足够配对机会，旧批没有配对时保留未知。

## 发现合同与阶段保存

`DESIGN_BEFORE_TARGET_EVALUATION.json` 在标签生成前写入。每家族从 K=2 到实际人数允许的 `floor(N/3)` 全部尝试；每类至少 3 人。内层删楼用原答重建误差、成员稳定性及容量选细层，再按配对一标准误规则选择可用粗层。最小类容量须在至少 80% 内折成立，平均内折 ARI 门槛为 0.50；未过稳定性门槛但有容量的候选明确记为探索。没有读取任何目标楼团队端点选类。

外层评价同时排除目标建筑的 **Manual 与 Semi 两种记录**。全数据说明标签与楼外标签分开保存。每完成一个家族／建筑折就原子保存标签、选型、候选分母和内折结果，未等到全部完成才写入。

当前先读 `CROSS_LABELS_CHECKPOINT.csv.gz` 与 `CROSS_CLASS_CENTERS_CHECKPOINT.csv.gz`；最终冻结后使用 `CROSS_LABELS_ALL.csv`、`CROSS_LABELS_LOBO.csv.gz`、`CROSS_CLASS_CENTERS_ALL.csv`、`CROSS_CLASS_CENTERS_LOBO.csv.gz` 和 `LABEL_FREEZE.json`。同一联合标签列出 Manual／Semi 两个评价域，不能因此把两种条件的终点评分混合。

## 旧分类身份与缺失

`OLD_METHOD_REGISTRY.csv`、`OLD_METHOD_LABELS_ALL.csv`、`OLD_METHOD_LABELS_TARGET_MAPS.csv.gz`、`OLD_METHOD_MEMBERS_ALL.csv` 保存旧 M、SP、A2、v3 行为与各条件结构×QT、QTD、含 Semi 行为辅助方案、Rnew2、F01 等原身份。Rnew2／F01 的历史十楼／目标十二楼映射照原样保留，不伪造全数据标签；不同方法不是统一树。

未知不填行为 0。只有“观察机会数”为 0 时计数列可为 0，数值特征仍缺失。门洞及特殊范围库存保留但不进入普通分类拟合；历史被筛除作答与 GT 暂停记录仅按原资格提供行为证据，不恢复质量或组队资格。

用户提供的 `project_sources/01-scope-.md` 只帮助解释遮挡延伸空间与目标范围歧义。本轮不据此改动既有 OOS、GT、硬评分资格或融合合同。多画可能是可见细节、不同范围、冗余或定位错误，需要实际图证分别判断。

## 复现

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python discover_cross_condition.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python build_old_registry.py
```

阶段说明不替代后续用途判断。新分类会在冻结后对照原单条件分类及同字段连续特征，Manual／Semi 分别报告；匹配团队替换由同主题的独立实验目录接收这些冻结标签。
