正向 Q、T、难度人员画像：v2 独立复算
==================================

主要入口
1. FORWARD_REPORT_ZH.html：可离线阅读，内嵌逐人选择与完整60人表，不需要联网。
2. 人员画像与候选细类60人.csv：中文全字段，含覆盖、边界、缺失与独立行为证据。
3. FOLD_SCHEMA.json：团队与反向路线应读取的训练外字段、支持门与未知规则。
4. paired_model_comparison.csv：所有模型在相同人员/同伴上重建的正式配对比较。
5. fine_information_controls.csv：细类对Q3×T3及保留连续Q幅度的诊断，防止重复信息算作增益。

输入固定
Sparkling-Flames/3D_Manhattan_label GitHub main:
82c6164b0d4630de5316199c92aa405930973168
继承已处理点位、删除修订、平均x、参考绑定和声明环序；未回到原始导出覆盖数据。
本模块从已审计证据开始复现统计，不声称重新复现整个采集清洗流程。

依赖与一键重放
本次实际环境 Python 3.12.14, NumPy 2.3.5, pandas 2.2.3, SciPy 1.17.0。
实际模型只使用 NumPy/pandas；pandas 的 Spearman 诊断需要 SciPy。

python reproduce_forward_profiles.py --repo /path/to/frozen/repo \
  --out /path/to/new/results \
  --evidence /path/to/audit/person_evidence_62.csv

--evidence 是根审计独立输出，只用于最后把 Semi/scope/排除证据连接到Q/T画像。
同目录如存在 exclusion_text_review_25.csv，中文表会同时附加逐条文本归因待定；
不存在时显式标为未提供，不补0。它不参与Q、T或分类训练。
建议 --out 使用新目录；默认完整重放包含v1历史对照和嵌套双排除，不能把历史留出称新盲测。
--verify-inputs-only 仅核对三个核心源SHA和独立证据文件；不将其当成完整统计重放。

可复核运行证据
REGISTRATION.json / REGISTRATION_DTYPE_EXTENSION.json：预定支持门和规则，未按融合胜負调整。
VALIDATION_REVISIONS.json：比较模型时先匹配相同人员再重构同伴相对目标的实现纠正；
主FE/部分汇聚结果不受该修正影响。bootstrap按固定比较键取随机种子，避免增加诊断改变原区间。
AUDIT_CHECKS.json：22折重新拟合、目标Q污染检验、双排除5组独立检查、既有v1方法精确重放。
fold_training_membership_audit.csv：每折训练建筑/作答成员hash，无目标建筑泄漏。
各种 *_RECEIPT.json 和 *.log：真实运行记录。新的完整重放会写 REPRODUCE_FORWARD_RECEIPT.json。
CURRENT_CODE_MANIFEST.json：交付时当前代码摘要；早期单脚本receipt可能早于后来正确性修补。

数据层与验证目标
普通Manual主层5719份/177图/22栋；Q支持6任务3栋，59/60人达门。
主验证5717份：同任务相对Q预测，不是使用测试图均值的事前绝对Q预测。
prediction_absolute 独立使用训练任务均衡难度截距；没有用目标图Q选择人员。
单模型逐图汇总的可评人员可能不同，不能直接互减表中均值；优劣应引用配对比较表。
建筑为主要推断单位，不把团队变体、重复路径和双排除人员行当独立真人样本。
原直接房间组仅original且physical_same支持；不把楼或关系传递当房间，未关联图不造singleton。

采用结论
保留绝对Q、任务调整连续Q、部分汇聚连续难度与T的分轴画像；Q3/QT用于沟通，稀疏细类探索保留。
λ20在v2相对Q预测总体改善约1.26%，简单无改善，困难方向较弱，D10困难区间跨0。
fine_dtype对Q2×T2改善约7.52%，但对Q3×T3基本持平；不能把Q幅度恢复称全部难度新信息。
当前单人验证不能证明细类内可互换，也不能否定它对团队组成有用；需结合独立团队/簇替换结果。
hard_relative_lift_only 的中文为“难图相对上升、同伴优势不足（θ难<3，未必绝对低）”，
它描述两种历史自身效应对照，不等于实际位次上升或绝对质量低。支持门一直是6唯一任务、3栋，
同时单列图片数；任务键为image/condition/reference/version。类型扩展登记中的6 images单位文字不准确，
实际代码与主登记均按任务计数，详见WORDING_CLARIFICATIONS.json；未改变任何阈值或类别。
来源时间旧/新与人员cohort混杂；无跨来源人员可校准。440同目标时间和source逐份相等、非独立样本。
Semi、scope、个人排除不并入几何Q，不制造总分、总体错误率或新的统一严重gold。
