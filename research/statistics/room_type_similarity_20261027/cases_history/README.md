# 同用途研究：历史连接与完整原答案例

本子目录接入 2026-10-27 用途相似性研究。主读 `CASE_FINDINGS_ZH.md`；精确旧结果联系在 `HISTORY_CONNECTIONS_ZH.csv`。案例输入最初固定为 `b9bcec809fbaec8ab055931a1abb7baa5db44dac`，数据真人 v2；接续采用最新 main `b2b0898b90bd631df37f1f2e75e8380800a43cf8` 时五个核心输入 blob 保持相同，且256自然顺序成果已归档，见主包 `source/MAIN_UPDATE_SOURCE_CHECK.json`。三个案例属于三个不同建筑；本子目录不判断更多物理房间关系。

## 已实际完成

1. 读取旧用途描述统计、旧构成用途分层、难度条件和同物理房间预测文档及表。提取既有 H1 历史 Q 高类 C03 对低类 C01、纯类各 9 人的原验证用途分层，保留 contrast_id 与全部支持字段。它是引用旧端点，不是新融合。
2. 从冻结 v2 证据中提取 b8-07、S9-05、jtc-13 的 104 份正式 Manual 答案，保留对象、人员、参考、坐标、资格、Q/D10、时间来源、结构和定位诊断；计算两个图对的共同人员描述。
3. 从指定 Release 按 HTTP Range 取三张原始 2048×1024 图，验证 CRC 与尺寸，保存提取 SHA；实际查看原图及生成的完整全景／局部／BEV 图。原图随案例包提供，未包含原图全集。
4. 原 b8/jtc 两图机制为历史复用；S9/jtc 同用途跨楼条件对照、小表和重新绘图为本轮新增描述。新融合=0，新评分=0，新分类=0。

## 文件与键

|文件|内容与关联|
|---|---|
|`case_records.json.gz`|104份冻结证据的原样子集；`object_id`主键，含质量资格、来源、有效点、接收点、完整reference_evidence；保留raw_original_available=false|
|`case_frozen_features.csv`|104份既有难度/表达特征子集；`object_id`连接，不重新改变H、短边或有效转折定义|
|`CASE_GEOMETRY.jsonl.gz`|104份完整绘图几何；`object_id`、`image_code`、`reference_id`；处理后顶底点、接收坐标、摄像机高度归一三维点与完整参考|
|`CASE_ALL_FORMAL_ANSWERS.csv`|104份标量；同图排除本人后的相对Q仅作描述，不是楼外一般能力校正|
|`CASE_FEATURED_ANSWERS.csv`|W107/W112×三图共6份；不是重新选人或重新分类|
|`CASE_COMMON_PERSON_COMPARISONS.csv`|b8/jtc33人、S9/jtc31人，共64比较行；两比较人员可重复，不能当64独立房间|
|`CASE_PAIR_SUMMARY.csv`|两图对的共同人员Q、排序和转折差；探索机制例，未赋予总体用途效应含义|
|`CASE_IMAGE_SUMMARY.csv`|三图全部正式人员的均值、SD、结构支持；与共同人员分母分开|
|`CASE_VISUAL_LOCATIONS.json`|三张原图相对路径、完整ERP坐标窗口、最短参考边索引|
|`HISTORICAL_Q9_ROOM_STRATA.csv`|7条原验证用途分层；非本轮训练或融合结果|
|`HISTORY_CONNECTIONS_ZH.csv`|五条历史专题的身份、实际复用和不混用事项|
|`CASE_SOURCE_MANIFEST.csv`|固定提交下的准确源路径、Git blob和本地字节SHA|
|`CASE_PACKAGE_CONTENTS.json`|独立案例包所需文件、字节、SHA、CSV行数及EOF核验结果|

## 复算与复画

依赖：Python 3.12、numpy、pandas、matplotlib、Pillow、scipy（pandas秩相关使用）。此案例没有 CJK 字体依赖；图内英文、说明中文。

```bash
MPLCONFIGDIR=/tmp/room_type_case_mpl python build_case_evidence.py --cases /绝对路径/cases_history
python assemble_history_links.py --out /绝对路径/cases_history
```

第一条仅需本包 `case_records.json.gz`、`case_frozen_features.csv` 与三张原图；已用不存在的 `--source-root` 实跑，确认不会隐式依赖整仓库。第二条复用包内冻结 `room_type_frozen_rule_strata.csv.gz`，不请求新融合。运行会更新本目录表和图。

全景曲线按冻结配对有效点投影到三维线段再投回ERP，保留环序与跨缝拆线。BEV距离单位是摄像机高度，不是实测米。空间Q沿用原参考身份，普通图资格不随图中可见门口改变。短边张角是几何代理，不是全库照片遮挡裁定。

## 与主报告的分工

主报告的跨建筑、同支持分析回答用途平均增量与个人一般能力扣除。这个案例子目录负责解释为何用途、难度、转折数相同时仍可能有结构和定位差异。不要以两个选定图对的相关系数替代全库估计，也不要以总体用途预测较弱否定已观察到的局部结构差异。

完整案例原件及结果已经保存在这里；未安排后续实验或新增人工裁定。
