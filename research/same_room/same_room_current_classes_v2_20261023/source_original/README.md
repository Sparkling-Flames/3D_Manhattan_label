# HOHONET 同房当前类别构成研究

主报告：`REPORT_ZH.html`（图片内嵌，独立可读）或 `REPORT_ZH.md`。
输入 main：`72a44e80c344975962e1071bd54d894dd86bb4b4`。
普通 Manual 主分析；当前结构类别 V3_BEHAVIOR，联合 V3_JOINT_QT 对照。

## 先读哪些文件

- `results/key_tables/KEY_FINDINGS.csv`：核心判断、分母口径与证据定位。
- `results/key_tables/SAME_ROOM_GROUP_OVERVIEW.csv`：17组当前构成结果与既有平均/个人结果桥接；支持分别保留。
- `results/key_tables/EXACT_REPLACEMENT_MAIN.csv`：同一实际替换的小变化、真同向、反向及失败分母。
- `results/key_tables/PRIOR_PERSON_REPEATABILITY.csv`：上一轮逐人重复性证据，身份为固定main取回。
- `NEW_OLD_RESULTS_LEDGER.csv`：取回/引用/本轮新算/定向重建/仍缺原件的区别。
- `CASE_INDEX.csv`：原图、原答、参考、团队、完整几何和局部票账。

## 功能包

所有ZIP解压到同一父目录，均保持 `HOHONET_SRCC_20261023/` 的相对结构。

|包|用途|
|---|---|
|`HOHONET_01_REPORT_CODE_DESIGN.zip`|报告源文、全部代码、固定设计、字段和输入索引、主图及关键小表|
|`HOHONET_02_CLASSIFICATION_RESULTS.zip`|类别构成/成员分解、第二批成员、楼外校准、条件结果|
|`HOHONET_03_REPLACEMENT_GEOMETRY_RESULTS.zip`|精确替换、实际背景D、定位、评分分项、时间及已有覆盖摘要|
|`HOHONET_04_BUDGET_RESULTS.zip`|精确增人、人数曲线、失败低尾、时间覆盖、奇偶门槛|
|`HOHONET_05_CASES.zip`|原图叠加、原答、局部、BEV、完整选例几何和票账|
|`HOHONET_06_PRIOR_RECOVERED.zip`|固定main取回的上一轮及Dot关键材料，保留原件身份|

`HOHONET_CODE.zip` 另提供全部脚本与运行说明，便于先审阅代码，不必先下载结果。
四份 `ENDPOINT_SCALARS_PART_01...04.csv.gz` 是可独立读取的CSV表，并非压缩分卷。
把它们放在 `results/native/parts/`，运行 `python code/assemble_native.py` 可无损拼接141,260个端点。
报告HTML另行提供，不作为唯一下载入口；原图全集、环境、缓存和数百万重复几何不打包。

复现详见 `REPRODUCE.md`，研究台接入详见 `FIELD_CONTRACT.md` 与 `INTEGRATION.json`。
旧47.1MiB ZIP没有找回；本包不冒称旧库原样恢复。所有新增团队已按冻结方法实算完成。
