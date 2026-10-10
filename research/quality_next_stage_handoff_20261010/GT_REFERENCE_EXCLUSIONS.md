# GT参考排除与未决问题登记

**新质量研究须同时读取参考版本登记和正式作答gate。** 本次没有删除GT、改坐标、改loader或重写任何资格。机器登记是研究使用约束；它尚未接入正式loader，也未在新参数实验中应用。既有人员行hold已经存在，不能写成“现在才发现还未暂停”。

读取 [机器登记](reference_exclusion_registry_20261010.json) 时，按完整 `image_id`、GT对象ID、version和坐标hash绑定。多数问题GT对象自身仍是 `candidate_pending_geometry`，仅过滤GT行会漏排；必须再叠加作答清洗/质量/场景等原有门槛。新地面确认、几何可算或参考自比高分均不能解除这些约束。

## 明确问题参考和用户已要求的暂停

| 图像 | 所限参考 | 已有人员质量状态 | 依据与范围 |
|---|---|---|---|
| jtcxE69GiFV-05 | 原GT | 6 hold_reference_quality | 用户明确GT完全错，旧审核、最新上传与当前消息一致 |
| jtcxE69GiFV-17 | 原GT | 1 hold_reference_quality | GT错误把门当墙 |
| pRbA3pwrgk9-12 | 原GT | 2 hold_reference_quality | 用户明确高度错误，不仅遗漏细小凸起 |
| uNb9QFRL6hY-51 | 原GT | 4 hold_reference_quality＋2 excluded | 用户明确斜顶与GT问题；后续地面决定未认证原顶界 |
| zsNo4HB9uLZ-05 | 原GT | 4 hold_reference_quality | 用户明确GT错误 |
| x8F5xyUWy9e-01 | 原GT | 5 hold_reference_quality | 用户称不准确；不能把暂停原因改写为非正交不可标 |
| wc2JMjhGNzB-14 | 原GT、人工修订GT | 4 hold_reference_quality＋1 excluded | 两版均被指出不太对，沿用暂缓 |
| uNb9QFRL6hY-32 | 原GT | 5 hold_main_analysis | 用户明确先不进主分析，保留这项更宽暂停 |

以上8图9个具体参考版本，共34份作答：26 reference hold、5 main-analysis hold、3既有excluded。不得用于对应的新质量参数选择、主GT优劣论证和标注者不确定性校准；可保留明确标注的诊断反例。

另有用户已明确暂停但GT错误尚未定性的2图：jtcxE69GiFV-11、pRbA3pwrgk9-16，各2份 `hold_all_analysis`。继续暂停，不将“无法判断”改写成“已确认GT错误”。

## 保守研究隔离与待核查 不冒充用户裁定

q9vSo1VnCiC-16早期有明确“GT有误”评价，后续又以门外目标范围解释；未找到修正版或明确撤回。现正式gate仍8 candidate、2 excluded。机器登记将其列为 `conservative_research_quarantine_pending_review`：新规则主调参、主比较和不确定性校准先不使用，保留诊断交Pro核查；这不是新用户错误标签，也没有改正式gate。

B6ByNegPMKs-37、q9vSo1VnCiC-34等未定性范围评语仍列待核。登记 `exclude=false` 只表示未新增“确认错误参考”的排除，绝不等于可直接用于主调参。若未消解的参考问题影响新规则选择，先作诊断并核清，再决定研究用途；不得用这层谨慎约束冒称用户认定GT错误。

## 不能自动扩大为错误GT的情况

- x8F5xyUWy9e-09是真实非正交，没有用户GT错误裁定；可以做非正交专题对照，但其24份out_of_primary_scene与2份excluded不能自动恢复。
- jtcxE69GiFV-10仅疑似OOS；OOS、点数多、奇数点不等同GT错误或不可标。
- uNb-01的细微凸起遗漏、uNb-88的玻璃/走廊范围及旧环序、uNb-36的条件停止边界、uNb-47的门洞条件，须按各自问题解释；原有场景hold继续保留。
- yq-32包含原始与修订范围差异；yq-07本轮接受GT并暂不处理壁炉细节，但6份原场景hold仍保留。
- e9z-16用户明确人工修订版已没问题；不能把原始版本问题扩到修订版。

详尽原话、来源文件、JSON指针、每版GT对象ID及geometry hash见 [机器登记](reference_exclusion_registry_20261010.json)；解释见 [原审计报告](GT_REFERENCE_AUDIT_REPORT.md)。新35地面确认不证明顶界、全部原GT或派生完整参考正确。库外历史线索q9-19只保留为待查，不计入当前259图或已确认错误数。

## 实际核验和未做事项

[实际loader核验结果](verification_result.json)通过，检查22图版本绑定及6个来源文件，正式输入为3441对象、3152作答、259图、2参考专用图、1312确认环。另补做 [Git来源绑定核验](git_source_binding_validation.json)：6个输入SHA逐一匹配24360ad的Git正文或LFS内容oid。loader应用的是已提交的审核层；LFS物化在工作树显示M不代表新增坐标修改。原审计报告关于本地工作树的保守措辞不否定这一补充核验。

可在具有完整正式输入与正常研究依赖的仓库复验：

```sh
PYTHONDONTWRITEBYTECODE=1 python verify_registry.py --repo /path/to/3D_Manhattan_label
```

脚本只读，不安装依赖、不覆盖源文件。若输入hash或版本不同，须重新核验登记适用范围，不强行沿用。正式gate现状、用户已定排除、本次保守研究约束分别保存；没有运行新Q或证明这些限制已经在新算法中执行。
