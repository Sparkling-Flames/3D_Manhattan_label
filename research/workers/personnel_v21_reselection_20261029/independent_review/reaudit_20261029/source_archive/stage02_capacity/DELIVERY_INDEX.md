# 容量、补算验收与独立采用意见：展开交付目录

## 建议阅读顺序

1. `FINAL_CAPACITY_AND_ADOPTION_REVIEW_ZH.md`：最终独立推荐、补算后的完整覆盖、两种幅度与两种汇总权重。
2. `completed_supplement/FINAL_COMPETITIVE_N_M_FUNNEL.csv`：五法四主格及小块桥接的完整数量链。
3. `completed_supplement/FINAL_REPLACEMENT_BAND_COVERAGE.csv`：固定七/八人任意合法 n、半队、过半、较大队 ABC/AC 分开统计；普通主池206、其他准入30与合并236三种入口。
4. `completed_supplement/PRIMARY_ROLE_DIRECTION_RESULTS.csv`：主角色轴、同 A 与对称幅度并列；这里按事件先池内等权。
5. `completed_supplement/PRIMARY_HARD_ROLE_COMMON_POOL_COMPARISON.csv`：TARGET 与 RAW3 的共同图支持。
6. `CAPACITY_AUDIT_ZH.md`：补算前快照，说明哪些缺口促成此次计算；不覆盖旧阶段解释。

## 目录职责

| 目录 | 保存内容 |
|---|---|
| `results/` | 45 配置全部 Manual 容量、旧 89,660 事件链、n/m 与直接 AC 漏斗、未覆盖方向、补算候选池与成员 |
| `extended_capacity/` | 45 旧配置与 18 个复现/敏感性配置的真实楼外容量，合计 63 配置 |
| `new_registration_audit/` | 新 6,548 事件独立身份检查、2,068 对实际同 XYZ 嵌套 D、全部违规表（空） |
| `completed_supplement/` | 新端点接分数、最终漏斗、两种幅度、主角色轴与敏感性、共同图片、重放端点和逐事件主程序一致性 |

## 必须保留的逐事件与逐池文件

- `results/ALL_EXECUTED_EVENTS_Q_AND_IDENTITIES.csv.gz`：旧事件、D/X/Y/Z、全部端点键与来源阶段。
- `results/ALL_MANUAL_POOL_METHOD_CAPACITY.csv.gz`、`ALL_MANUAL_DIRECTED_CAPACITY.csv.gz`：旧45法全池容量。
- `extended_capacity/ALL_MANUAL_POOL_METHOD_CAPACITY.csv.gz`、`ALL_MANUAL_DIRECTED_CAPACITY.csv.gz`：含新候选的全池容量。
- `new_registration_audit/INDEPENDENT_FIXED_XYZ_NESTED_N_PAIRS.csv.gz`：真实配对身份。
- `completed_supplement/NEW_EVENTS_INDEPENDENT_Q_AND_STATUS.csv.gz`：新事件独立分数和失败/票数状态。
- `completed_supplement/COMPETITIVE_OLD_AND_NEW_EVENTS_Q.csv.gz`：五法合并事件链，保留旧/新身份。
- `completed_supplement/FINAL_COMPETITIVE_POOL_LEVEL_FUNNEL.csv.gz`：每张图每格的具体退出与可评原因。
- `completed_supplement/FINAL_REPLACEMENT_BAND_POOL_FUNNEL.csv.gz`：9,440 行逐池 band 漏斗，保存所有容量/已登记 n/m、未执行容量格和退出原因。
- `completed_supplement/FINAL_REPLACEMENT_BAND_DEFINITIONS.csv`：n/m 上下界、全部合法格和互斥/支持条件。
- `completed_supplement/EVENTS_BOTH_CROSS_DEFINITIONS.csv.gz`：两种幅度的全部逐事件值。
- `completed_supplement/PRIMARY_ROLE_EVENTS_BOTH_CROSS_DEFINITIONS.csv.gz`：hard/challenge/Q 主角色轴与旧角色敏感性逐事件关联。
- `completed_supplement/HARD_VS_CHALLENGE_CHANGED_EVENTS.csv.gz`、`HARD_VS_CHALLENGE_CHANGED_POOL_N_M.csv`：全部受角色轴影响的实例。
- `completed_supplement/INDEPENDENT_NESTED_N_Q_EFFECTS.csv.gz`：四端点共同可评的 ΔC、ΔB、Δ(C−B)。

原生新团队完整几何与票账位于主交付 `HOHONET_v21_reaudit_20261029/stage03_new_abc/endpoints/`；本目录保留其精确键和独立核验，不复制一份相同几何制造新的证据身份。

## 复算代码

| 脚本 | 作用 |
|---|---|
| `audit_large_blocks.py` | 从快照/楼外标签重算容量，从全部旧精确事件与端点重建证据链 |
| `finalize_capacity_audit.py` | 旧容量源一致性、替换比例分组、直接 AC 与关键条件 |
| `build_supplement_candidates.py` | 输入驱动的七八人缺口、具体方向与候选成员、共同图片容量 |
| `audit_new_registration.py` | 新登记逐事件身份、标签、背景与嵌套路径独立审计 |
| `integrate_completed_supplement.py` | 新完成标量、旧/新分离汇总、最终漏斗、逐事件主程序核对 |
| `compare_common_structure_pools.py` | 保留旧 challenge 轴的共同支持敏感性比较 |
| `compare_cross_definitions.py` | 同 A 与旧对称幅度逐事件并列 |
| `build_primary_role_results.py` | 主角色轴明确对齐、差异折/池/事件与主表 |
| `build_final_replacement_bands.py` | 补算完成后的八种替换问题，按三个范围入口派生最终容量与执行并集，保留未设计 n/m 格 |
| `verify_audit_outputs.py` | CSV、gzip CRC 与 JSON 的完整读取验证 |

脚本使用同一工作区的 `repo/`、`audit_classification/`、`audit_comparison/` 与 `HOHONET_v21_reaudit_20261029/`。这些依赖保存于主交付的对应目录；移动工作区时保留该相对布局或调整脚本顶部路径，不更改数据和成员。

## 验收回执

`results/INDEPENDENT_CAPACITY_CHECKS.json`、`new_registration_audit/REGISTRATION_AUDIT.json`、`completed_supplement/COMPLETED_SUPPLEMENT_AUDIT.json`、`completed_supplement/EXHAUSTIVE_DIRECTION_COVERAGE_CHECK.json`、`completed_supplement/INDEPENDENT_METRIC_PARITY.json`、`completed_supplement/FINAL_REPLACEMENT_BAND_RECEIPT.json`、`FINAL_READABILITY_CHECK.json`。

源报告与中间结果的定义不被追改。最终正文采用主比较代理的 XYZ 先平均层级，本目录采用事件先池内平均的文件均在报告中明示；没有把两种权重的微差宣称为计算错误。
