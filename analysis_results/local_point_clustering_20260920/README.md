# 局部点位分簇：新Pro对话资料与本地比较

本轮依据用户批准的计划执行，新增要求为：**工作方法确认后，视觉核验覆盖全部214张历史图片、239个图片×条件单元**。先处理争议，不把当前数值检查或旧局部审图称为全量验收。

## 阅读顺序

1. `PRO_TASK.md`：可直接用于新Pro对话的完整任务。
2. `evidence/latest_decisions.json`：最新用户原话、完整对应及后续澄清。
3. `evidence/user_review_16.json`：原审核文件，文字和暂缓状态原样保留；`review_manifest_16.json`绑定当时点集和问题。
4. `rc2_received/REPORT_ZH.md`及其`code/`、`results/`：收到的RC2数值研究，不当作视觉真值。
5. `results/CHECKS.json`、`partition_summary.csv`、`groups.json`：本地四组最小对照；`full_history_visual_coverage.csv`是后续全量验收清单，空白不等于通过。

仓库中大体积数值输入/输出集中在`pro_local_points_20260920.zip`，解压后与上述相对目录一致。没有原始active logs、凭据或新上传的原图；RC2的数值/文本文件保留，图片、控制台日志、pid与HTML展示副本未收入。原RC2 MANIFEST用于来源对照，不能据此声称被省略展示文件也在包内；本包完整性以DELIVERY_MANIFEST.json为准。

## 云端复算

在解压根目录，使用已有依赖numpy/pandas/scipy：

```sh
python -X utf8 -B -m tools.thesis_main.analysis.clustering_release.local_points --root rc2_received/sources/current/study --evidence evidence --out verification
```

该命令只写verification，不改源study。数值入口完整校验原清单内的非展示输入与结果；仅不要求历史visual_checked/history_visual_review下11张展示JPG，本地视觉生成入口仍要求它们齐全。该范围明确记录在CHECKS.json，不以缺少图片放宽任何JSON/点集/时间校验。源study的18份导出来源对账、冻结时间及两项有效点修复沿用已绑定快照；本轮不伪称重新审计原日志。

同一比较固定上下绑定与跨人对应，分别改变距离或整簇规则。图上距离保留每个原端点；球面沿用旧半像素中心约定。两种成簇规则均以canonical身份稳定并列选择。代表半径只保证接近代表，不保证簇内两两接近；完整链接则可能拆开一些近对。无唯一自动绑定的记录保留在eligibility和历史角色分开结果中，不悄悄丢弃。

`automatic`为自动固定点对顺序；`human_correspondence`仅对最新完整确认的作答对替换对应，其余沿用自动距离，属于后见解释视图。两者均保留相同人群。不移动点位，不将相近意见变成零距离或强制合簇。

当前exact_curves为固定全池分区的后见统计及成对未覆盖，不冒充前k人独立预测。前缀重新分簇、人员历史方案回接和最终工作方法建议由新Pro继续完成，再由本地复算与人工核验。

## 审核与发布边界

首批继续处理16图中的暂缓及已有误拆/混簇问题。独立审核页复用Studio foundation，保留原16图作为只读证据；新裁决留空。后续全量核验逐项记录原图、指定作答、整簇、方法版本和确认人，缺任何范围就不称完整验收。

当前没有最终分簇方法、容差或停止人数冻结；未完成新数据验收。正式Paper A合同、原始导出、时间真源、既有人群排除和采集计划不变。
