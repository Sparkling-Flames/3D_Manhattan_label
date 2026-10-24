# 质量独立验证准备字段合同

CSV为UTF-8；gzip候选表不改变行内容。`review_id`为本审查集键，`object_id/reference_id/image/building/condition`保留原来源身份。`canonical_side=a/b`只表示登记时的原ID顺序；真正左右以私有映射为准，不能凭分差猜左右。

|文件|行单位|口径|
|---|---|---|
|`DESIGN.json`|设计与覆盖|固定类别、候选数、排除原因、选样/曝光及相机坐标政策；人工状态待定。|
|`PAIR_CANDIDATE_LEDGER.csv.gz`|同图同参考原答对×满足的类别|一对可满足多个类别，行数不能当独立样本量。指标关系仅用于平衡选样。|
|`REVIEW_PAIR_REGISTRATION.csv`|25对|`left_is_a`为固定随机左右映射；20新候选不认证全历史未曝光，5旧例明确机制复核。|
|`REVIEW_MAPPING_PRIVATE.json`|25对|左右原对象、图/楼、参考、原图路径与曝光身份；不加载进评阅页。|
|`REVIEW_METRICS_PRIVATE.csv`|25对×两原答，50行|冻结五分项/总分与新增同几何legacy指标；人判前不显示。|
|`HEIGHT_CONTROL_METRICS.csv`|110份既有控制|62份有3D几何补深度，48份原几何未归档仅保存原分项与冻结评分，深度列空；不是110次独立真实图片。|
|`EXPOSED_STRUCTURE_AND_NEAR_SCORE_METRICS.csv`|S1/S2/S3/S09各3个已存团队|共12端点，旧曝光与同时改变多项几何的机制身份，不冒充纯结构单因素或新独立验证。|
|`BOTTOM_POINT_CONTROL_METRICS.csv`|2原答×dy=-2/0/+2|6行，固定其它点与参考的单底点敏感性；同图重复控制不作独立样本。|
|`index.html`|25题自包含页面|内嵌原图、完整点对/逐边、参考和显示几何；不含算法名、分数、选样类别或推荐答案。|
|`BROWSER_QA.json`|临时浏览器功能核验|file协议、图片、交互、自动保存/重载和导出；不等同科学效度或人工完成。|

`B8L2/D10/IoU3D100`为0—100；`iou_2d/legacy_iou2d/legacy_iou3d_mean_height/δ1`为0—1。`S_bottom_deg/dir/corner_bottom_assignment_mean_deg`为度；Hmean/Hcenter为相对高度量；`layout_depth_rmse_m`基于两侧共同假定相机高1.6米的布局渲染，除以1.6为相机高度单位。逐列顶部未均值化；均高仅用于legacy棱柱IoU。`legacy_status!=ok`时适用指标留空，绝不填失败0。

底角9°用原声明角点的球面最小总成本一一分配，precision/recall分母分别是候选/参考角点数；这是几何位置诊断，不能认证隐藏墙角的语义必要性。所有评价的目标/参考、半球、相机拍摄点位与尺度必须一致；GT暂停、OOS、scope冲突不能因数值可算而恢复正式质量资格。

导出答案schema为 `quality_independent_human_answers_20261024_v1`，含`review_set`、时间、题数、`answers`。每个题键下`choice`只能为`left/right/close/uncertain`或尚未选择的null，`reason`为原文字。未选择题保留缺失。`updated_at`是浏览器记录时间，不是活动耗时。页面默认无答案；本地存储只属于当前浏览器，导出后才成为可回连的研究材料。

## 2026-10-24人工返回与视觉辅助

- `REVIEW_MAPPING_PRIVATE.json`、`REVIEW_METRICS_PRIVATE.csv`、`REVIEW_PAIR_REGISTRATION.csv`、`PAIR_CANDIDATE_LEDGER.csv.gz`、`human_review/ANSWER_METRIC_COMPARISON.csv` 含原对象/参考/来源映射及逐对象指标，仅本机保留，由仓库根 `.gitignore` 排除。
- `human_review/ANSWERS_ORIGINAL.json`：用户返回的原始导出，按字节复制；选择、comment和浏览器时间均不改写。`answers_received_at_delivery=0`保留初次交付历史，`REVIEW_STATUS.json.current_answers_received=25`表示当前状态。
- `human_review/ANSWER_METRIC_COMPARISON.csv`：25题，按固定私有映射回连原左右对象，不用canonical a/b猜左右。`human_choice/human_comment/human_updated_at`为原答；`directional_human_answer`仅left/right为true。每个指标保留`left_*`、`right_*`、`delta_right_minus_left_*`、`preferred_*`和`agrees_human_*`。IoU/总分/δ1越高越好，误差/偏差越低越好；只有原数值差严格等于0才为equal。这个数值平不是人评接近阈值。
- `agrees_human_*`仅原left/right题可为true/false；close、uncertain和未答均留空。comment中的“可能偏左”不自动升级，uncertain不等于低质量，close也不等于高质量。原人判与指标反向的题保留分母。
- `human_review/METRIC_DIRECTION_SUMMARY.csv`：按曝光身份×Manual/Semi×指标；原答数、二元方向数、方向题图片/建筑数、同向、反向、数值平、close和uncertain分别保存。每个单元的同向+反向+数值平=二元方向数；不同指标行是重复测量，不能相加当样本。没有事后接近阈值、总体胜率或推断检验。
- `human_review/ASSISTANT_VISUAL_NOTES.json`：25题独立于原答的辅助证据层；`assistant_choice/assistant_lean/strength/comment_assessment/visual_evidence/interpretation`是Codex看过用户意见和指标后的解释，不是第二名独立盲评者、不增加人评n，也不覆盖任何原选择或正式资格。保留11张已检查的关键对照图/三维图；其它题通过原工作台复看。
- `human_review/REPORT_ZH.md`：完整原comment及逐题视觉说明；原图边界覆盖、主体范围、点位及高度还原、目标表达分别解释。QV018接续既有壁炉裁决，当前参考/难度/评分/eligibility不变。
- `REVIEW_STATUS.json.validation_passed=false/global_validity_certified=false`表示没有全局效度认证，不能解释为全部题验证失败；当前状态为已收到答案并完成有边界视觉复核。
