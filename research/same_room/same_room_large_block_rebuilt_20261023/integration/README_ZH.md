# 同房大块结果的文档接续补丁

固定基础：main `e92abe8631d7f01dc192ee796b46f295ece37a6d`。本目录是可审阅的接续补丁；没有直接修改历史仓库文件，也没有用本轮新设计替换旧研究身份。

## 已完成

- `REPORT_ZH_corrected_copy.md`：旧同房主报告的完整修正版，保留原提交、实验规模与数值显示，补正源端共同支持、2.006算术劳动比、49/120与50/120零阈值差异。
- `patched_repo/research/same_room/same_room_current_classes_v2_20261023/REPORT_ZH.md`：可放回原仓库相对路径的同一修正版。
- `old_same_room_report_corrections.patch`：unified diff，只含三项口径及接续入口。新专题入口指向 `research/same_room/same_room_large_block_rebuilt_20261023/REPORT_ZH.md`。
- `HISTORICAL_REPORT_CHANGES.csv`、`HISTORICAL_PATCH_RECEIPT.json`：逐处原文、修正文、依据、固定输入blob与hash；替换段中原数字字面量全部保留。
- `PERSONNEL_REPORT_INSERTIONS_ZH.md`：可采用的人员主报告第6.2—6.3及进度段，已绑定全部正式结果。`PERSONNEL_INSERTION_VALUES.csv` 保存45项数值、正式来源和hash；`PERSONNEL_INSERTION_DECISIONS.json` 保存4项判断。原 `_TEMPLATE.md` 仅保留生成过程，不作为当前阅读稿。
- `PERSONNEL_INSERTION_VALUE_BINDINGS.csv`：数值占位符到正式输出文件/行筛选/字段的绑定。
- `REPORT_SECTIONS_ZH_TEMPLATE.md`：保留的六项问题编辑提纲；当前结论请读新专题主报告、`anchor_paths/README_ZH.md`、`direction_tables/DIRECTION_RESULTS_ZH.md`及本目录完成插入稿，不把此提纲当作最终结果。
- `REPORT_EVIDENCE_BINDINGS.csv`、`TEMPLATE_SCHEMA_CHECK.json`：19项报告证据合同和45项人员插入字段的schema核对。完成后已读取正式表表头；早期技术样例仅用于核字段，未取其效应写正式结果。
- `WORKER_IDENTIFIER_RECEIPT.json`：当前标签、冻结原答与已核画像表的人员字段来源；本轮沿用匿名号Wxxx，未得到姓名字段。方向成员并集仅是覆盖，不能当作一个实际团队。

## 应用时机与依赖

补丁应随本轮主报告和正式结果一起应用。本次终稿生成补丁时新 `REPORT_ZH.md` 和全部正式结果已经完成，回执记录完成状态；早期模板只作过程追溯。修正版中的旧图表/数据链接保留仓库相对位置，依赖main现有历史专题，不复制全套旧输入。

从仓库根目录可以先审阅diff，再使用 `git apply`，或把 `patched_repo/` 中的对应文件复制到原位置。本目录不自动执行这些写入，也不推送仓库。

若最终新专题目录名改变，重新生成：

```bash
python integration/code/build_historical_report_patch.py \
  --repo /path/to/repo \
  --out integration \
  --new-repo-dir research/same_room/same_room_large_block_rebuilt_20261023
```

人员主报告模板中的新路径应同时替换。旧研究使用的72a44e8提交保持原身份；本轮取用及重新设计基于e92abe8，两者不混写。

## 本轮完成结果的代码与来源

```bash
python integration/code/check_report_bindings.py --root .
python integration/code/finalize_personnel_insertions.py --root .
```

`finalize_personnel_insertions.py` 从本轮新ABC结果、图对/建筑汇总和成员匹配表填写人员主报告段落。真正固定A/n的规模路径、固定XYZ的背景路径由 `analysis/analyze_anchor_paths.py` 与 `analysis/report_anchor_paths.py` 生成；它们均重用已冻结端点，未新增融合。方向中文表保留原几何分量自己的六端点有效支持，并新增 `共同Q结构_` 字段供质量与结构联合解释；原字段没有被共同支持字段替换。新增小表接合回执为 `direction_tables/DIRECTION_JOINT_SUPPORT_RECEIPT.json`，基础回执与R04B中原件保持字节一致。
