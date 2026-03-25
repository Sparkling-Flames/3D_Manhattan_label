# trap集当前说明

这份文件只记录当前仍然有效的使用边界，不再保留已经过期的讨论口径。

## 一、当前最该相信什么

当前 trap 相关判断请按下面顺序理解：

1. latest `project-20` export
2. 当前 `trap集` 目录结构
3. task / family 下的 `特别注意.md`、`特别说明.md`
4. `analysis_results/truth_layer_extraction_20260324/`
5. 更旧的汇总稿与复核稿

因此：

- 旧讨论稿不能覆盖当前目录与 latest export
- 目录 bucket 也不能单独覆盖当前 `scope`

## 二、当前 trap集不是 final gold

当前已经完成的是：

- `trap ∩ latest export = 58`
- `manual=30 / semi=18 / OOS=10`
- working-consensus truth layer 已可抽取
- `kp` 已明确为当前 geometry 主抽取源

当前仍未完成的是：

- final adjudicated gold
- manual final anchor / non-anchor binding 的最终 gold 级确认
- semi final executable keep/drop
- OOS final quota / binding

所以当前 trap集最准确的定位仍然是：

> **working-consensus candidate pool**

## 三、当前 geometry / metadata 边界

- `kp`：当前主 geometry source
- `poly`：只保留为 raw residue
- `.txt`：只保留为 `legacy_mp3d_reference`
- `scope`：决定样本是否进入主几何指标

## 四、manual 侧当前规则

### 1. 人工锚点的硬排除条件

- 只有明确带 `低优先` 的 task，默认不进入人工锚点集
- 这条规则只约束 expert-anchor，不代表该 task 无法标注，也不代表它必须从 manual pool 删除

### 2. 其他括号说明的语义

下面这些默认只作为 review annotation，不自动降级：

- `高难度`
- `较为困难`
- `略微有点遮挡`
- `可能有歧义`
- `同时是一角多点`
- `同时是角点错位`

也就是说：

- 它们可以继续留在 candidate pool
- 其中一部分仍可进入 expert-anchor
- 最终是否进入 anchor，要看当前 freeze 的 keep/drop，而不是看括号本身

### 3. 遮罩 family 的例外

- `task696(低优先,不确定,难标注)`：继续按低优先处理
- `task711(中低优先,难标注)`：当前保留为例外，不按普通 `低优先` 自动排除
- 但 `711` 目前仍不应直接作为默认 expert-anchor；它更多是遮罩 family 里保留的较优代表，且 `711 > 696`

## 五、semi 与 OOS 的当前理解

### semi

- `模型标注质量好` 主要对应 control 候选
- 当前 default core natural trap family 仍是：
  - `跨门扩张`
  - `过度解析`
  - `角点错位`
  - `角点重复`
- `漏标` 仍是 extension family
- `模型预标注失败` 仍是 low-priority / optional / audit case

### OOS

- 当前 `OOS` 目录保存的是 OOS gate candidate pool
- low-priority 的 OOS 样本含义是“是否算 OOS 仍较不确定”，不是“无法标注”
- 当前 latest export 与目录 `scope` 已无 active mismatch
- 但这仍不等于 OOS final quota 已冻结

## 六、当前不应再说的话

不要再把当前 trap集写成：

- `final gold`
- `manual / semi / OOS 已 executable`
- `Stage 1 ready`

当前最强表述只能是：

> **trap集 已整理成 working-consensus candidate pool，truth-layer extraction 已可审计；但 final gold 与 Stage 1 executable freeze 仍未完成。**
