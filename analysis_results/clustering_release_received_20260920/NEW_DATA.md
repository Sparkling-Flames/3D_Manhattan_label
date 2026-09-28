# 新增真人接入（RC1-20260920）

## 入口与输出

解压后进入包根目录。Python 3.11及以上，安装`requirements.txt`中的依赖。输入目录不可作为输出目录。首次仅重算已有历史：

```bash
python -B code/run_all.py --root . --config config.json --out results/my_history_rerun
```

新增文件是UTF-8 JSONL或`.jsonl.gz`，每行一位真人在一张图一个原始条件下的独立初始canonical响应。它在冻结历史之后追加，不是整份历史的替换副本。

```bash
python -B code/run_all.py --root . --config config.json --new-responses new_data/responses.jsonl --out results/arrival_01
python -B code/make_figures.py --data results/arrival_01 --figdir results/arrival_01/figures
```

制图脚本保留历史示范图和模型对照的布局；不得将历史固定文案中的样本数自动当作新一轮结论。CSV中的实际N是依据。主结果报告不自动重写；新增报告应根据新结果审阅。`--skip-models`只跳过辅助模型预测，主成员及人数曲线仍生成；`--permutations`控制真实人员排列的计算次数，不改变真实样本量。

## 输入合同

必须与历史相同的含义：

- `canonical_annotation_id`：全局唯一稳定字符串；与旧ID冲突时拒绝覆盖。
- `worker_id`：如`W038`，统一人员注册，不因重来一遍就分配新ID。
- `image_id`、`building_id`、可选`image_code`：稳定图像和建筑身份，不以文本相似猜同房。
- `raw_condition`：`manual` / `semi` / `oos`。保留原采集条件；任务OOS裁决不是自动改条件的指令。
- `record_type`：必须明确为`independent_initial`。任何revision/parent关系不当新增独立票。
- `stage`、`block_index`、`assistance_exposure`：实际历史/新批次、block及信息条件，不能伪装成旧P1/C1。
- `coordinate_width=1024`、`coordinate_height=512`：本计算视图坐标。百分比/2048原图等换算必须在上游审计并保留原导出，入口不猜单位。
- `raw_points_1024x512`、`effective_points_1024x512`：二维数值列表。raw与effective分别保存；effective缺失写null，不能回填raw。数组顺序保留。
- `raw_point_count`、`effective_point_count`：必须与实际payload一致；effective=null则count=null。
- `calculation_included`：显式布尔值；`processing_status`、`imputed_point`：上游确认后的状态。确认后删补须带`confirmation_source`/`imputation_provenance`等来源，不能把算法建议当人工接受。
- 可选`point_roles`：按原有效点顺序给出完整`top`/`bottom`。当前入口只支持已经通过一般点集和初步角色资格的记录覆盖角色；角色资格完全不成立的特殊图先作为不可计算/待角色复核保存，不声称可自动恢复。
- 建议带`raw_annotation_version_id`、`raw_export_path`、原导出SHA、实际完成时间、共享初始化版本和初次接触/先前同房暴露。当前随机回放不依赖完整时序，但真正前k人预测和熟悉效应分析必须依赖它们。

原始2,501条输入不改。相同人×图×条件重复出现时，入口拒绝直接运行；需上游明确首个独立作答与修订版的关系。排除W019/W026是当前合同，仍保存其输入审计行。W011历史保留。

同一图有不同阶段的人参与，历史主摘要按原始条件合并，必须在解释中保留阶段/暴露差异。新验证宜预先冻结目标队列及信息条件；不能依据结果选择看起来稳定的一批人。

## 输出与新增资料缺口

`eligibility.csv`单列不可计算；`memberships.csv`包含各视图和阈值，不依赖整数簇号跨版本同义。`cluster_version_hash`反映成员集合，不是永久语义ID。`endpoint_correspondences.csv.gz`保留每个原点号及误差。`cache.json`保存对应矩阵。

`historical_exact_curves.csv`是固定池边际覆盖；`prefix_reclustering_*`是真实人员排列后每个前缀重分簇；`retrospective_*`明确使用完整池类别回看。不把三者混成一个“收敛人数”。

新图片没有模型/同房标签时，主分析照常运行；模型和同房附加结果只研究已有可靠关联。`model_image_features.csv`与同房注册表是冻结历史输入，增加新特征必须作为新版本另保存、核对来源，不能修改旧记录证明预测。

`evidence_diagnostics.csv`只评价冻结历史审核，不复制为新图标签。新数据重跑会输出`NEW_DATA_EVIDENCE_BOUNDARY.json`，历史用户审核不自动扩展。新增人工审核须单列版本。软件接入测试只用拿出的10份历史记录重新追加，并没有生成新真人数据。

## 人工对应侧表

复制`results/final_run/human_correspondence_template.csv`。填写：图片/条件、A/B canonical ID、`role`、`point_a_1based`、`point_b_1based`、status、reviewer、evidence_source与两个点集SHA。SHA按 `review_correspondence.pointsha` 对有效点数组生成，不允许凭显示三位小数生成。

```bash
python -B code/review_correspondence.py --root . --review new_data/reviewed_correspondence.csv --out results/review_v1
```

`confirmed`以外条目仍可保存，但不参与残差确认。只有完整双侧一一映射才输出`full_correspondence_distance`；部分锚点只输出已确认部分的距离。程序验证身份/角色/版本/一一对应以及跨多人冲突，**不会自动改簇**。当前侧表程序默认核验冻结历史；新增作答的角色与对应审核应先绑定对应新增响应版本，不将新ID套到旧源。

若计划把完整人工映射用于下一版距离，需明确新的测量版本与影响表，并重新分簇；“人工确认对应”不是“人工要求同组”。只有uNb-21的3→4被确认时，禁止把4→3及全体其它位置当作已确认。

## 版本变化

`config.json`精确匹配RC1；自定义新阈值/新门/新角色算法须另命名版本并报告敏感性，不能覆盖旧输出。主输入不含新收集的完整日志；active time资格仍需沿用上游SOP，lead_time不替代active time。
