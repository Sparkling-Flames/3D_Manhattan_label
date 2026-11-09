参与者困难反馈与几何表达：正式结果（2026-11-09）

正文最值得保留的两句话
在72张可比较的Manual图片上，报告遮挡的人比未报告者少遗漏4.81个百分点的参考底面面积，简化比例低3.75个百分点；同人比较也显示较少遗漏（4.18个百分点）。Semi没有重复出一致的关联方向，报告困难并不直接意味着标注更差。

英文正文建议（可压为两句）
On 72 comparable Manual images, respondents reporting occlusion omitted 4.81 percentage points less reference footprint and simplified 3.75 percentage points less often than those not reporting it; the image-centered within-person comparison also showed less omission (4.18 percentage points). Semi did not reproduce a consistent association across the two comparisons.

采用与位置
研究结论可放RQ1的个人标法/图片条件之后。建议图表为论文材料，FIGURE_CAPTION.tex及 figures/participant_feedback.pdf/svg/png留在本机，不纳入公开研究归档；研究结果表、分析数据及脚本可复现核心数字。频数输入表、全部100项关联、16项焦点及区间留补充。

正式支持
Manual 1016份、118图、24人、22楼；Semi 456份、34图、24人、11楼。每项几何指标均有值。这是问卷反馈子集，不替换全研究人数和作答分母。主比较支持为同时有人选择/未选择该因素的图或人，具体见FOCAL_RESULTS.csv。

关键同步值（旧文所有出现处一起改）
Manual遮挡，同图72图：简化差−3.7531个百分点，95%区间[−6.4061,−0.9985]；遗漏比例差−0.048093，区间[−0.074714,−0.012368]。
Manual遮挡，同人24人：简化差−2.0848个百分点，区间[−6.9339,+2.7830]；遗漏比例差−0.041769，区间[−0.062412,−0.020795]。
其余精确值以results/FOCAL_RESULTS.csv为准；同图和同人估计不是互相独立的两批实验。

方法与文件
ANALYSIS_CONTRACT.json：字段、支持、权重、4000次重抽及来源。
inputs/formal_feedback_records.csv：1472份最小复算输入（匿名人员、对象、目标、因素和五指标）。
results/difficulty_association_summary.csv：两条件×五因素×五指标×两种比较，共100行。
results/difficulty_same_image_target_contrasts.csv：逐图目标组差。
results/difficulty_same_person_building_contrasts.csv和difficulty_same_person_summary.csv：逐人逐楼及逐人结果。
results/metric_support.csv：逐指标支持；results/FOCAL_RESULTS.csv：16项焦点。
inputs/previous_association_summary.csv和results/aggregation_change_check.csv仅是接续核对，不进入论文。
论文图及图注文件（PDF/SVG/PNG/TEX）留在本机；不随公开研究归档上传。

复算命令（仓库根运行）
python tools/thesis_main/analysis/reaggregate_participant_feedback_20261109.py
python tools/thesis_main/analysis/verify_participant_feedback_20261109.py
python tools/thesis_main/analysis/draw_participant_feedback_20261109.py

验证
正式对象和参考一对一核对；既有1464份记录五指标一致，Manual/Semi各恢复4份。独立聚合实现复算16项焦点均值及4000次区间，通过1e-11容差；138份Semi状态及图中矩阵核对通过。图像已目视检查，修复轴标签与脚注重叠。
未改正式论文，未改参考、评分、分类、融合与其他分析；未编译整篇PDF。写作线程负责正文与补充统一接入。
