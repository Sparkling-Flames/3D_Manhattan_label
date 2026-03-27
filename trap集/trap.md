# trap集当前说明

这份文件只记录当前仍然有效的使用边界，不再保留已经过时的讨论口径。

## 一、当前最该相信什么

当前 `trap` 相关判断请按下面顺序理解：

1. 最新 verified `project-20` export
2. 当前 `trap集/` 目录结构
3. task / family 下的 `特别注意.md / 特别说明.md`
4. `analysis_results/truth_layer_extraction_20260324/`
5. 更旧的汇总表与复核表

因此：
- 旧讨论文件不能覆盖当前目录与最新 export
- 目录 bucket 也不能单独覆盖当前 `scope`

## 二、当前 `trap集` 目录不是 final gold 或导入清单

当前已经完成的是：
- `trap ∩ latest export = 61`
- `manual=30 / semi=21 / OOS=10`
- latest export / final-gold truth layer 已可稳定抽取
- `kp` 已明确为当前 geometry 主抽取源
- 项目级 `final_gold_records_v1.jsonl`、Stage 1 freeze 与 import 文件已经在 `analysis_results/` 与 `import_json/` 中物化

当前目录层仍然只是：

> **working candidate pool**

## 三、当前 geometry / metadata 边界

- `kp`：当前主 geometry source
- `poly`：只保留为 raw residue
- `.txt`：只保留为 `legacy_mp3d_reference`
- `scope`：决定样本是否进入主几何指标或 OOS gate
- `OOS` 的目录 family 与 final scope subtype 需要分开理解：
  - 目录 family 用于 candidate bookkeeping
  - final scope subtype 以 latest verified export / final gold 为准
  - `task560` 当前就是显式例子：目录在 `边界不可判定`，但 final scope 是 `oos_geometry`

## 四、manual 当前规则

### 1. 人工锚点的硬排除条件

- 只有明确带 `低优先` 的 task，默认不进入人工锚点集
- 这条规则只约束 `expert-anchor`，不代表该 task 不能标注，也不代表它必须从 manual pool 删除

### 2. 其他括号说明的语义

下面这些默认只作 `review annotation`，不自动降级：
- `高难度`
- `较为困难`
- `略微有点遮挡`
- `可能有歧义`
- `同时是一角多点`
- `同时是角点错位`

也就是说：
- 它们可以继续留在 candidate pool
- 其中一部分仍可进入 `expert-anchor`
- 最终是否进入 anchor，以 final freeze 的 keep/drop 为准，而不是以括号本身为准

### 3. 遮罩 family 的例外

- `task696(低优先,不确定,难标注)`：继续按低优先处理
- `task711(中低优先,难标注)`：当前作为保留例外，不按普通 `低优先` 自动排除
- 但 `711` 目前仍不应直接作为默认 `expert-anchor`

## 五、semi 与 OOS 的当前理解

### semi

- `模型标注质量好` 主要对应 `control`
- 当前默认主 12 张 trap 仍围绕：
  - `跨门扩张`
  - `过度解析`
  - `角点错位`
  - `角点重复`
- `漏标` 仍是正式 `extension family`
- `模型预标注失败` 仍是 `low-priority / optional / holdout`
- 当前正式 `semi` freeze 以 [prescreen_semi_final_selection_v10.json](d:/Work/HOHONET/analysis_results/phase1_progress_20260324/prescreen_semi_final_selection_v10.json) 为准：
  - `625` 替换 `474`
  - `overextend_adjacent` 已改为 natural-only
  - `668` 替换 `580` 成为更干净的第三条 natural overextend
  - `580` 保留为 `special_review reserve`
  - `665` 作为新增 `underextend` extension-family candidate
  - `475` 当前只保留在 `fail holdout`

### OOS

- 当前 `OOS` 目录保存的是 OOS gate candidate pool
- low-priority OOS 的含义是“是否真算 OOS 仍较不确定”，不是“无法标注”
- 当前 latest export 与目录 `scope_binary(in_scope/oos)` 已无活动 mismatch
- 但仍存在个别 `family_dir != final_scope_alias` 的子类型重协调样本，当前显式例子是 `task560`
- 项目级 OOS final quota 已在：
  - [oos_final_quota_binding_v2.json](d:/Work/HOHONET/analysis_results/phase1_progress_20260324/oos_final_quota_binding_v2.json)

## 六、当前不应再说的话

不要再把当前 `trap集` 写成：

- `final gold`
- `manual / semi / OOS 目录即导入文件`
- `目录本身就等于 Stage 1 executable pool`

当前最准确的表述是：

> `trap集` 目录本身已经整理成可审计的 candidate pool；项目级 final gold、Stage 1 freeze 与 LS import 已在其他结果文件中物化，但二者不应直接混写。
