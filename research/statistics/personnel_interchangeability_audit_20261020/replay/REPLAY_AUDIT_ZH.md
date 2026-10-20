# 新成果包的独立原生重放审计

审计对象：`personnel_interchangeability_20261020.zip`。本次新建环境恢复冻结输入，实际重算，不把包内自报回执当作独立验证结果。

## 已通过

- 包内清单的643个文件逐件SHA256及大小核查通过。
- 10个关键冻结输入、融合源文件及测量程序均与声明SHA256一致，实际内容不是Git LFS指针。对三个归档/任务提交e572eb73、445686f8及本次读取main ea7d77bb的Git树逐件核对，10项实际blob均相同。
- 输入快照SHA256为83179b9842d06916b105d80ff181918c223e4fee2073f425f9825db124ec11d7，含229个池。冻结科学提交82c6164b，融合gap=7.5，N1=false。
- 10个案例的嵌入成员记录、参考和元数据与完整快照逐项相同；实际重放39支不同团队，9张图、5栋楼，数值最大差0，最终几何完全一致。
- 实际重算17,726个池×团队，46张图、7栋楼、59人；每队32个最终字段及最终几何SHA全部相同，数值最大差0。原生融合耗时225.71秒，3个进程；此耗时不包括恢复环境、案例或后续统计。
- 评分状态逐队复现：complete_conditional 17,514，no_connection 167，below_four 32，invalid_floor 13。没有将失败补零或改成成功。
- 1,819个ABC配对事件重新计算，原脚本的分层汇总通过。另独立比较全部1,819行×30列，数值最大差0、缺失位置和非数值字段相同，避免仅凭汇总相同判断逐事件相同。
- 18个设计流全部核查通过：16个依冻结规则、种子和容量重建，2个小请求精确保留核对。完整请求、多重集、成员、共同背景、类别人数、换人规模、事件和台账指纹均相同。

## 解释边界

这验证的是数值重现与输入/程序一致性，不证明探索性人员分类已具有外部效度。17,726个核心任务仅是全研究569,529个去重池×团队的一部分；并未在本审计中重算全部17批宽搜或全部反向候选。案例、重复团队、交付重放不增加独立图像/人员支持。complete_conditional沿用冻结参考和环序资格，不能改称新增人工确认。

B8L2仍使用冻结模型版本WQ-B8L2-20261015、方向尺度8度、二阶汇总；D10只将方向尺度替换为10度。新角点距离诊断由单独补充研究处理，不改变这些质量分数或融合算法。

## 回执位置

- FROZEN_INPUTS_INDEPENDENT.json
- GIT_SOURCE_PARITY_INDEPENDENT.json
- cases/REPLAY_RECEIPT.json
- core/CORE_REPLAY_RECEIPT.json
- core/REPLAYED_PAIRED_EVENTS.csv.gz
- core/REPLAYED_CORE_AGGREGATES.csv
- PAIRED_ROWS_INDEPENDENT.json
- design_retry/designs/DESIGN_REBUILD_RECEIPT.json

早期环境恢复曾因并行Git临时包占满磁盘而中断；只清理本次中断临时文件，随后改为固定提交原始文件下载并逐件核SHA。第一次设计运行仅完成forward_wide，其余因环境ENOSPC失败；上面采用的是磁盘恢复后全新目录重跑的最终通过回执，没有把环境失败冒充结果不一致或隐藏未重跑项。

## 为角点距离分类补充恢复的历史原生结果

另外实际重建H20冻结历史请求31,539支不同团队，81张图、10栋历史楼、60人；3进程耗时483.26秒。全部请求的精确成员与输出逐一一致。状态为complete_conditional 30,744、no_connection 585、below_four 206、invalid_floor 4。这里保留所有不可评分状态，不补零。完整几何已交给仅使用历史数据的新增角点距离分类流程；不读取目标楼评估结果，不构成新增独立验证样本。

回执：`HISTORY_NATIVE_INDEPENDENT.json`、`history_native/RUN_history_requests.json`；原生几何：`history_native/pools/`。完整外部A归档也已核对3,844个文件、1,552,498,895字节全部SHA一致，见`RESTORATION_INDEPENDENT.json`。科学依赖版本与运行环境见`REPLAY_ENVIRONMENT.json`。

## 冻结后执行的新增块替换探针

请求SHA256为2324bf001fbc0b5387632758b817645fe5cd6965e391850a6ccc4e0c89167600。独立核对12,229支团队、2,552个类专属ABC事件、200个嵌套背景组、152个类别无关共同背景及63,476个不相交块对，精确成员、类别人数、共同背景、换人规模m、同源新人员替换、嵌套前缀均通过。

原生执行覆盖全部12,229支团队，12张内部重复使用的评估图、6栋楼、59人，耗时159.01秒。每队精确成员对象ID、快照上下文、参考ID/版本和图楼元数据均再次核对。状态为complete_conditional 11,977、below_four 184、no_connection 68。最终几何完整保留在`fresh_corner_blocks/pools/`，供角点距离评估与跨方法共同支持比较。

回执：`FRESH_DESIGN_INDEPENDENT.json`、`FRESH_NATIVE_INDEPENDENT.json`、`fresh_corner_blocks/RUN_fresh_block_requests.json`。上述“通过”指冻结设计与实际执行/覆盖的一致性，不是分类效果通过；效果、覆盖权衡和负面结果由后续统计报告解释。该探针不是独立外部盲测，不得用结果重新调类、调阈值或替换不利成员。

## 直接m2块学习的独立历史原生面板

后续另行冻结的历史m2请求SHA256为9fa849e711bbe71d2b052096aeadb9722cb2b1f22f08b90a7940a61e900e9e00。其7,670支团队、160个共同背景、144,140个不相交块比较及40条嵌套路径经独立设计检查通过。所有参与图片的楼集合恰为原划分的10栋历史楼，与发现/评估楼不相交；换入换出块均为真实新源人员，背景可以含旧源人员。没有在本原生执行步骤中拟合类别或改变参考。

实际完成全部7,670支团队，20张历史图、10栋楼、全团队共55名人员，3进程109.64秒；状态complete_conditional 7,502、below_four 77、no_connection 91。精确成员对象ID、快照上下文、参考和元数据逐队核查通过。完整几何交由单独历史块学习流程处理。

回执：`HISTORY_BLOCK_DESIGN_INDEPENDENT.json`、`HISTORY_BLOCK_NATIVE_INDEPENDENT.json`、`history_corner_blocks/RUN_history_block_requests.json`。原生输出：`history_corner_blocks/pools/`。人员支持资格、训练目标、折内拟合及最终有效性由后续学习/统计审计单独判定。
