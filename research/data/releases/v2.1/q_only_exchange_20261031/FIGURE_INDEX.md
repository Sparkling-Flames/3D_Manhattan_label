# 英文论文图表索引

两图均由`tools/thesis_main/analysis/q_only_exchange_v21_20261031.py`生成，保留PDF/SVG和300 dpi PNG。Q为B8L2。TARGET K3为20261030图片难度统一后的楼外工作标签，不代表最终分类。

## 1. Quality differences between structural and Q-only replacement policies with fixed backgrounds and equal replacement sizes

文件：`figures/quality_policy_comparison.{pdf,svg,png}`。源表：`SUMMARY.csv`，metric=B8L2、comparator=Q_RAW/Q_PEER。横轴为结构−Q-only的质量差（Q points），纵轴为Q选人规则；两面板使用相同横轴范围。

**Caption.** Mean differences in consensus quality between the frozen structural replacement block and historical-Q-selected blocks under TARGET working labels. The background, initial team, candidate pool, reference, team size, and seven-person replacement size are fixed within each event. Raw historical Q is the primary comparator; image/target-centered Q is a prespecified sensitivity analysis. Historical information excludes the target building. Points are image-equal means after averaging within backgrounds, blocks, and pools. Bars show percentile 95% intervals from 2,000 building-cluster bootstrap samples. The 14/7 comparison includes 140 jointly scored events, 68 images, and 20 buildings; the 20/7 comparison includes 59 events, 53 images, and 18 buildings. Positive values favor the structural policy. Unscoreable outputs are reported separately and are not assigned zero quality. Only 14/7 replaces half the team.

## 2. Image-level consensus quality under structural and raw-Q replacement using TARGET working labels and fixed candidate support

文件：`figures/paired_image_quality.{pdf,svg,png}`。源表：`IMAGE_EFFECTS.csv`，metric=B8L2、comparator=Q_RAW。横轴Q-only、纵轴结构，两轴Q points，固定0—100。每点为同一图片的配对输出均值。

**Caption.** Paired image-level quality under structural and raw historical-Q replacement with fixed backgrounds. Each point represents one image, averaged over the same jointly scored events within each background, block, and pool. The dashed line indicates equal quality. The panels include 68 images at n=14, m=7 and 53 images at n=20, m=7. Coincident points may overlap. Identical seven-person replacement blocks occur in 119 of 147 registered 14/7 events and 54 of 61 registered 20/7 events. The comparison concerns these frozen replacement policies and does not estimate a class effect at equal historical quality.

## 输出字段合同

- `PAIRED_EVENTS.csv`：每个事件×比较政策一行；`*_delta=*_structure−*_comparator`仅在该分项双方均可得时写值。劳动比为结构/Q-only（比较A/B时对应结构/A或B）。
- `IMAGE_EFFECTS.csv`：每条件×比较政策×分项×图一行；`effect`为分项差，劳动行为比值。
- `SUMMARY.csv`：events/images/buildings为该分项实际配对分母；mean是图等权均值；ci按建筑整群重采样。`positive_images`对劳动使用比值>1，其他使用差值>1e-9；`negative_images`同理。质量P10是图级输出分布的分位数。
- `OUTPUT_STATUS.csv`：每事件×五政策保留状态，不因缺Q丢行；`STATUS_SUMMARY.csv`为原始事件计数，不作为独立抽样量。
- `ENDPOINTS.jsonl.gz`：670个唯一团队；624项为具备精确身份的存档评分，`geometry_copied=false`；46项为新融合完整端点。`member_workers`、`member_object_ids`统一为列表。原始评分字段和空值保留。
- `SELECTION_OVERLAP.csv`：同队与共享换入人数是事件描述，不赋予独立样本含义。两类历史重叠表是固定caliper容量诊断，不是新匹配实验。
