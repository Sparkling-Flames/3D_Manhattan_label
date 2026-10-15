# 当前交接状态（2026-10-14，审核修订后）

本文件优先于包内历史“待回执”表述。当前已有三例回执及一次用户修订，请依次读取 human_review/quality_pro_review_20261014_v1.json、human_review/quality_pro_review_20261014_amendment_01.json、human_review/REVIEW_FINDINGS.md。补充修订优先，原件不覆盖。

## 当前不需要新增人工审核

Q01：大范围与小房间均合理，现有大范围顶部参考可用；小房间精确边界/顶界参考未在本次回执中定义。现有大范围下分数仅为条件诊断，不将其当成小房间总体质量真值，也不拿该份作答自身作参考。需要量化小范围质量时，先查既有空间候选与来源，再准备最小边界确认材料；缺参考不阻塞其余普通样本研究。

Q02：原A略好未看高度，补看后明确B更规整；完整质量排序未确定，不当成总分反向约束。

Q03：原B略好未看高度，保留中间拐角B略好的局部观察；高度两者都不太平，用户肉眼无法准确比较。不得将“不确定”变为相等、强制排序或失败标签。

后续只有当候选方法在有依据的整体排序上发生实质取舍，或需要确认小房间的具体目标边界时，再集中少量审核。暂不要求用户再看Q02/Q03强排先后；局部分项归因、资料整理与参考核对由分析方先做。

## Pro研究目标

以PRO_TASK.md的研究目标与证据边界为准，具体方法由Pro独立判断。两条原overall选项不再是完整质量约束。保持普通粗调→冻结→门洞细调→普通回归的顺序；OOS不调参，9严重例外单列。不得为了符合弱排序而改点、改参考或改融合。

## 展示约定

用户确认以后采用10月11日静态三维图：坐标轴、刻度、网格、共同尺度；BEV标相机位置。此次明确先不改，包内网页和图像保留原样。未让用户评价真实米制高度，h仍是相机高度单位。

## 评分版本与有效审核状态

三例回执已收到，Q02/Q03有后续修订；完整质量排序未建立不等于尚未审核，不要求重复审核。`human_review/effective_status.json`是当前审核状态，原manifest的`awaiting_receipt`仅为历史状态。启动输出`review_status=received_with_amendments`，`historical_review_status=awaiting_receipt`；`read_report`指向CURRENT_STATUS.md，`review_findings`指向修订解释。

`data/cohorts.json`普通/严重行的`components`来自旧带方向尾项基线，门洞行的`candidate_components.center`才是新工作版。不要混用这些保存分数。普通/严重统一当前结果读`stage/COARSE.json.records[*].hill_global08`；各层统一复算使用`stage/WORKING_FINAL.json`的config与冻结score引擎。保留历史分数，不覆盖。

现在足以启动Pro普通粗调，不需等待92份门洞held解锁。Q01既有小房间候选核查留作门洞阶段局部待办；未定参考时仅作范围条件诊断，不逼迫调参。Q02/Q03原overall选项不是完整排序约束，分项数据已齐，可由Pro归因。普通粗调→冻结→门洞细调→普通回归；OOS不调参。

## 本次包验证与局限

唯一推荐交付`quality_pro_handoff_20261014_READY.zip`。原PENDING_REVIEW、WITH_REVIEW包保留为历史快照。此次仅修订入口、有效审核状态及启动返回；冻结评分引擎、几何、分数、原manifest和原始回执均未改。

此前实际解包启动的数值验证见BASE_EXTRACTED_STARTUP.json；当前startup_result.json仅更新审核状态并明确该数值验证来源。新代码的状态函数、入口与包内容一致性另作定向验证；该次清理没有重复全量复算。原始启动报告另存history/startup_result_before_status_cleanup.json。

本包作为本次授权上传main的正式交接材料；尚未自动创建或发送Pro任务，未改算法或宣布校准完成。发布准备仅改入口与任务表述，新增目标导向任务书；具体方法不受旧操作步骤限制。

## 发布前最终检查

最终READY包已在独立临时目录实际启动，结果另存READY_STARTUP.json：583份存储metrics重评分一致，R03274、2个底点控制和7个菱形重建成功，当前审核状态正确。7项相关测试及JS语法检查通过。这没有重新计算全部样本几何，也不代表校准已经完成。临时解包目录已清理。
