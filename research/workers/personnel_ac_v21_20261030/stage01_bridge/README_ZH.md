# 严格 ABC 与直接 AC 的共同人数桥接

本补充只登记直接 AC，不新建或重跑任何 ABC。它解决一个已发现的比较缺口：
最新严格 m9 的 n 为 11 及各池 N−18；严格 m10 的 TARGET 条件为 n12/14，RAW3 为 n12/15。
主直接 AC 的默认人数网格并不覆盖这些共同条件。因此，不能只凭同图或同 m 把两种研究当作相同条件。

## 冻结设计

来源提交为 `ec0973ad46fcfa64d3cdbedfeeef1fee180c4cff`。唯一的严格 ABC 输入是已登记的
66 个 pool/方法/类别方向/n/m 设计单元 `STRICT_SOURCE_CELLS.csv`，没有读取其分数、几何或劳动结果来选设计。
直接 AC 的源样本来自 `stage01_design_review/registered_v2` 的身份表。

- 覆盖全部 66 个既有严格条件、24 个真实图片目标池。
- 每个类别块条件复用主直接 AC 已有的 X/Z 块，最多 8 个；两个严格 n 水平使用同一组块。
- 当前各格均有 8 个块，合计 528 方法事件、496 个不同物理端点对、986 支不同团队。
- D 从主直接 AC 同一 `neutral_members_0` 成员路径取长度 n−m 的前缀；不改类别、池、目标或参考。
- 其中 49 支团队、32 个方法事件已在 v2 登记；其余 937 支团队、496 个方法事件为 v2 身份表之外的请求。
  这里的“之外”不排除它们还能在更早的历史端点缓存中复用。

抽样种子沿用 `202610291901`。若源 X/Z 块多于 8，使用明确的
`strict_common_n_bridge_subsample` 随机令牌抽 8 个，避免把完整枚举表中的前几个字典序组合当作代表。
`BLOCK_SELECTION_AND_BRIDGE_REASONS.csv.gz` 保存源事件、原样本序号、批次、精确 X/Z/D、可选块数和保留块数。
原登记模块已冻结为 `code/source_registration_module_frozen.py`，SHA 写入回执。

## 方向与解释

事件表保留主直接 AC 的历史角色排序方向。严格 ABC 的原来源/目标及与当前方向的正负转换
保存在 `bridge_strict_source_class`、`bridge_strict_target_class`、`bridge_strict_to_canonical_sign`。
例如严格 TARGET 的历史转折秩 2→1 方向，需要把当前 canonical 的有符号差取反后再比较；
绝对变化不因方向翻转而改变。类别编号本身不代表全局语义，需连接相应楼外折的角色表。

共同 pool、目标、n、m 和角色方向允许比较两种设计的结果分布。但严格 ABC 另要求一个真实且互斥的同类 Y，
其可选成员与背景空间因此受额外约束。桥接没有 B，不能单独支持“跨类变化大于同类变化”的判断。
该判断仍只来自原严格 ABC 的三队结果；桥接用于说明在较宽的直接 AC 成员/背景空间下，同条件变化是否持续、减弱或反向。
完全相同的 AC 端点对需按物理身份合并，不能当作独立重复证据。

## 文件与验证

正式目录为 `registered_bridge_v1/`，提供与主登记一致的
`AC_EVENTS.csv.gz`、`DESIGN_LINKS.csv.gz`、`TEAM_REQUESTS.csv.gz`、
`REGISTERED_AC_CELLS.csv.gz` 和 `PHYSICAL_PAIR_METHOD_OVERLAP.csv.gz`。
另有每块来源/理由、设计回执、完整 gzip 读取回执及冻结 SHA 清单。
`stage01_capacity/BRIDGE_DESIGN_CAPACITY_REVIEW.json` 已独立核对所有身份、LOBO 类别、目标参考、
互斥 D/X/Z、精确块/背景、n/m、父类、无向物理对和链接计数，结果通过。

复现命令为：

```bash
python HOHONET_v21_AC_population_20261029/stage01_bridge/code/register_strict_common_n.py --source-registration registered_v2 --name registered_bridge_v1
```

程序拒绝覆盖已有登记目录；复现时需用新的 `--name`。计算端点和评价状态由总任务后续统一执行与报告。
