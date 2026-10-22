# 第一轮：扩展包数值基线复现与独立核验

## 结论

报告的核心样本计数、规整收益/冲突计数、同底面不同墙顶实例、纯细分密度反例，以及 LOBO 预测失败，均可重现。未发现足以推翻这些结果的数值核错误。另发现两个需要补充的解释事实与一个 API 状态漏洞：

1. 101 份成功规整中缺少角度比较的 32 份，全部因为原 GT 环不能单值覆盖一周经度；源作答本身均可算。69 份预测子样本因此筛选了参考表示域，不只是筛选工人几何。
2. pooled LOBO AUC=0.17636 不应单独解读为“特征存在强反向效度”：不使用任何特征、只输出每折训练正例率的基线，pooled AUC 也只有 0.15273。但同建筑内部正负对 AUC 仍仅 0.13462，因此不能把失败完全归因于跨折校准。
3. 公共 API 可以在参考为空或几何不可计算时返回“参考分项可比较”。应补计算状态检查；本漏洞不改变本包已有的研究统计。

这是在现有输入上的计算复核，不是新的数据采集、人工真值认证、图像语义裁决或独立外部验证。本轮没有修改任何源代码、原坐标、资格或融合输出。

## 1. 已实际执行的工作

- 阅读完整 REPORT、METHOD、reproduce.py、全部 src 实现及所用 vendor 数值函数
- 用官方入口在新的 official/ 目录执行完整数值流程，明确使用 --no-figures
- 将重算 CSV 与随包结果逐列比较，另外比较关键 JSON
- 重新核对选中面板、候选、inventory 与扩展上游包之间的对象绑定
- 新写独立三维重建、标量有限线段距离、弧长中点采样、Manhattan 全局轴最优值及逻辑回归优化实现
- 独立构造纯细分输入并重跑原规整器；追踪 NA 到源作答和参考；执行 API 失败输入反例

官方复算日志：official.log。核验脚本：audit.py、diagnostics.py。机器可读证据与逐项结果均保留在本目录。

## 2. 输入与分母

| 项目 | 独立计数 |
|---|---:|
| 广面板图像 / 建筑 / 合格候选原答 | 37 / 21 / 359 |
| 全面板图像 / 建筑 / 输入记录 | 49 / 21 / 598 |
| 当前合格候选原答 / 排除诊断原答 | 527 / 4 |
| 实际测量原答 | 531 |
| 已有五路线状态 / 有 points 的候选 | 220 / 210 |
| 原答参考比较 / 候选参考比较 | 653 / 234 |
| 合计比较 / 范围可算 / 上下角度可算 | 887 / 886 / 575 |
| 规整尝试 / 成功 / 阻塞 | 147 / 126 / 21 |
| 广面板尝试 / 成功 / 阻塞 | 111 / 101 / 10 |
| 成功派生插值几何 | 252 |

四份排除诊断仍为 uNb-51 的 R01185、R00326、R00160、R01689，保留 inner_space_only_reference_hold / hold_reference_quality，未恢复资格。广面板 101 份成功原答全部 source_eligible=true；质量门均为 candidate_pending_geometry，并不是经过独立 Manhattan/平顶适用性认证。

49 个完整面板对象、220 个候选状态和49个 inventory 对象，与 expanded_input 相应对象完全相等。两个 vendor 文件 geometry.py、arc_consensus.py 与扩展源逐字节相等，SHA256 见 source_binding.json。这只证明本次打包/抽取绑定，没有认证上游采集或人工判断的正确性。

### NA 来源进一步拆分

全887条：575双方可算；232仅参考非单值；10仅原答非单值；66双方非单值；3原答不满足地平线上下条件；1原答配对数组无效。对于广面板101个成功规整原答，69双方可算、32仅原参考非单值。此机制性缺失不可当0，也不能默认“随机缺失”。

详见 na_provenance.csv、broad_projection_na_provenance.csv、na_provenance_summary.json。

## 3. 官方端到端复算

metrics.csv 全887行、intrinsic.csv 751行（含10个无完整候选的失败状态）、case_table、local_path、probe、roster、within_image_correlations 数值逐项相同。规整涉及优化器，其已成功输出出现极小漂移：

- after_iou 最大绝对差 1.5157×10⁻⁷
- after_bottom_mae_deg 最大绝对差 2.4565×10⁻⁶°
- LOBO 预测概率最大差 1.0873×10⁻⁸
- 所有报告中的成功/失败、胜负计数、组合选择计数与预测分类均不变

两个阻塞记录的优化器诊断文本改变，但未改变阻塞状态：R02381 从 linesearch 提示变成 iteration limit；R02309 从 invalid_footprint 变成 camera_visibility_unresolved。不能声称所有文件按字节完全一致，也不能把浮点与诊断文本差异误报为主要结论不复现。

### 广面板干预与组合

- α=.25：101份，IoU提高/降低/持平=68/28/5；69份上下可比；上界恶化>0.1°有4份，其中2份IoU提高
- α=1：101份，60/36/5；69份上下可比；上界恶化27份，其中16份IoU提高
- 强规整图像等权平均 ΔIoU≈+0.007430，平均 Δ上界MAE≈+0.086550°
- IoU、IoU+0.5C、再加0.05G、再加0.2G分别偏好规整60、60、83、96份
- 所偏好中IoU下降分别0、2、19、31份；上界恶化分别16/45、15/45、20/57、26/66

复算比较细目在 reproduction_diff.json，完整原始输出在 official/。

## 4. 独立数值核

### 三维、有限线段和轴方向

独立实现以 cot(bottom俯角)直接重建，不调用包内 rays/paired_wall_proxy。737份 geometry_status=ok 对象与包实现的坐标最大差3.55×10⁻¹⁵h。

有限线段 oracle 使用逐线段显式端点/垂足分支及叉积距离，覆盖闭合/开放路径、退化零长度边、2/3/8/20节点共3200查询；与向量化实现最大差1.78×10⁻¹⁵h。

另用分段二次目标的所有包角断点枚举求 Manhattan 轴全局最小值，不用原网格+minimize_scalar 路径；737个对象最大RMS差2.58×10⁻¹⁴°，没有发现原近似搜索漏掉更优轴。

对 uNb-18 R02846/R02843、X7-19 R01646/R00916、2t7-09 R00016，重新实现三维弧长中点与标量距离，计算上下各10项，与随包距离最大差<2×10⁻¹⁶h。例如两份同底面原答的墙顶距离仍是0.188316799和0.241600916h。

这些检验验证所声明的条件几何数学计算，不证明“最近线段”就是相同语义墙面，也没有新增实测深度。沿闭集距离1-Lipschitz的中点均值误差界 L/(4n) 与采样最大值缺口界 L/(2n)在定义下成立，P95仍无对应严格误差界。

### 独立重造密度反例

从R00016直接三维重建，在最长原边插入等距点，再用独立投影回到像素。原上下折线差约10⁻¹⁶h，平顶角RMS保持1.427494465°。

| 点对数 | 两个拟合底面的IoU | 拟合上界MAE差 | 拟合下界MAE差 |
|---|---:|---:|---:|
| 4→6 | 0.994732437 | 0.187162702° | 0.072788011° |
| 4→12 | 0.987060399 | 0.328037981° | 0.177950280° |

确证逐节点目标的密度敏感性。此处重跑了原拟合器，没有声称完成了密度不变的新拟合算法。全部可重算证据在 density_counterexample.json。

## 5. LOBO 深查

独立 scipy BFGS 最小化“二元logistic负对数似然之和 + 非截距系数L2/2”，各建筑训练折分别估计均值/标准差，固定阈值0.5，未翻转分数或调参。

结果：69份、24图、16栋；25正44负；预测正确43份，训练多数类基线正确44份；建议规整1份，该份为负；AUC=0.176363636。独立优化与sklearn概率最大差1.55×10⁻⁴，但标签、排序AUC与阈值分类完全相同。差异符合优化收敛容差，不是类别方向错误。

补充诊断：

- 只输出每折训练先验的 pooled AUC=0.152727273
- 9栋内部同时有正负例，共52个同建筑正负对，pair-weighted AUC=0.134615385
- 全部pooled AUC共有1100正负对，只有52对来自同一建筑；大多数比较横跨不同折的模型
- 每折训练AUC、测试基率、预测均值和系数见 predictor_audit.json

这说明 pooled AUC 要连同分组先验和折内表现解释；本数据同时存在真实折内失败。无法从这些小样本结果推断所有三维量无效，也不能拿同一held-out结果翻转分数后宣称成功。特征和参数未做独立预注册；代码未显示标准化泄漏，代码审查也不能证明此前未尝试别的模型。

## 6. 已确认 API 状态缺陷

将真实R00016的一个底点设在地平线，geometry_status与reference_status均为unavailable。但提供 confirmed_same_target、reference_usable=true 后，evaluate仍返回 reference_cost_comparable_with_same_context=true 和 comparable_reference_components。合法原答传 references=[] 也返回同样可比较状态。

原因：evaluator.py的 rank_ready 只检查context和已知要求冲突，不检查是否实际存在可计算参考结果。建议改为参考级状态，至少要求存在明确参考及可用范围数值；如不同分项可用性不同，应分别暴露可比性，不能用单个宽泛布尔值代替。未对源实现作任何修改。

反例：api_guard_counterexamples.json；可执行：diagnostics.py 的 api_guard()。

## 7. 未执行与边界

- 没有重绘或审阅图像像素，本轮使用 --no-figures；视觉/语义审阅由另一工作方向完成
- 没有重新采集或裁决真值；没有把同一上游包的数据匹配称为独立数据验证
- 没有全库3152人记录重算、重跑人员分组/融合或选择新融合阈值
- 没有验证所有3D均值为精确积分；仅按所声明采样实现核验，保留其误差界
- 未独立重写整个Shapely区域运算，也未将官方程序重跑冒称全部算法独立实现
- 没有构造自动语义门、部署自动修复或修改源程序

## 8. 可移植运行

代码不依赖本次机器的绝对路径。先解压研究包和扩展输入，并在任意位置准备Python依赖；原包requirements.txt与官方输出的environment.json列出依赖。以下变量请替换为当地实际路径：

```bash
export QUALITY_AUDIT_SOURCE="/path/to/quality_deep_20261007"
export QUALITY_AUDIT_EXPANDED="/path/to/expanded_input"
export QUALITY_AUDIT_OFFICIAL_OUTPUT="/path/to/fresh_official_output"
python "$QUALITY_AUDIT_SOURCE/reproduce.py" --out "$QUALITY_AUDIT_OFFICIAL_OUTPUT" --no-figures
python audit.py --source "$QUALITY_AUDIT_SOURCE" --expanded "$QUALITY_AUDIT_EXPANDED" --official-output "$QUALITY_AUDIT_OFFICIAL_OUTPUT" > audit.log 2>&1
python diagnostics.py --source "$QUALITY_AUDIT_SOURCE" --expanded "$QUALITY_AUDIT_EXPANDED" --official-output "$QUALITY_AUDIT_OFFICIAL_OUTPUT" > diagnostics.log 2>&1
```

官方输出目录须尚未存在；核验脚本的--official-output指向已完成复算目录，只读该目录。脚本也直接读取上述同名环境变量；不传参数/变量时，使用相对本研究目录的原解包树作为默认位置。核验输出保存在脚本所在目录。

只做轻量输入绑定检查，不重新执行数值研究：

```bash
python audit.py --checks binding
python diagnostics.py --checks api
python optional_api_patch/make_patch.py --source "$QUALITY_AUDIT_SOURCE"
python optional_api_patch/test_patch.py --source "$QUALITY_AUDIT_SOURCE"
```

本次可移植整理后，已用显式--source/--expanded/--official-output执行上述轻量输入绑定、API反例及11项补丁测试；全部通过。见portability_binding_check.log、portability_api_check.log及补丁tests.log。此次只是交付清理，没有另计研究轮次，也未重跑完整实验。

## 附：可选的最小 API 诊断补丁

根据该状态反例，另提供 optional_api_patch/evaluator_optional.patch 及独立 evaluator_proposed.py。未改动返回包的src/evaluator.py。逐参考增加空间可比较标志，全局标志要求至少一个参考且所有所给参考成功计算；正常数值计算逻辑保持原样。仍保留全局context的适用边界，不把该补丁当作参考级语义裁决方案。

已实际执行11项反例/回归测试，全部通过；覆盖空参考、地平线坏几何、坏/混合参考、已接受不同目标、必要细节冲突、footprint-only以及真人案例数值不变。见 optional_api_patch/test_results.json、tests.log、README_ZH.md。此项是可选诊断修补，不改变本轮科研数值或核心结论。
