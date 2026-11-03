# 当前连接诊断与人工案例入口

**人工回收已完成：** 57组全部confirmed，坐标/排列/团队绑定验证通过。见[回收索引与9模块依赖](user_order_return/README.md)和[Pro接续提示词](user_order_return/PRO_PROMPT_ZH.md)。无需重复排序；辅助重建和结论影响尚待接续。

当前结论以[完整核查报告](CURRENT_REAUDIT.md)及[最终回执](FINAL_AUDIT_CHECKS.json)为准。[打开57个几何组的工作台](index.html)。

旧81,072项跨历史库存清单已经撤回，不再作为人工任务。旧页、人工导出和浏览器保存键保留。81,072条 `prepared/` 中间缓存打成 ZIP 分片并附 SHA-256 清单；原始散文件不纳入 Git。恢复完整复核前先运行 `python -X utf8 tools/thesis_main/analysis/restore_missing_ring_prepared_20261104.py --restore-to research/fusion/missing_ring_review_20261104/prepared`。当前队列严格读取VALIDATED_REVIEW_IDS.json，缺少该文件时拒绝生成，不会退回全部库存。

## 索引

- [当前引用入口与分母](CURRENT_REFERENCE_SOURCES.csv)：558个源表入口；包含不同方法、阶段与目标，不能合并成独立样本。
- [各模块的连接问题范围](CURRENT_MODULE_IMPACT.csv)、[主半队及同房事件影响](CURRENT_MAIN_EVENT_IMPACT.csv)。
- [原答已确认顺序与实际输入](CURRENT_RAW_ORDER_CHECK.csv)：1,076次引用、911份原答，全部匹配。
- [当前保存诊断](CURRENT_LINKED_DIAGNOSTIC_CHECKS.csv)、[门洞原生记录核查](CURRENT_NATIVE_FAILURES.csv)。
- [此前延期但实际已执行的72个两人结果](ACTUAL_K2_PREVIOUSLY_DEFERRED_CHECK.csv)、[位置未定及单列项](CURRENT_UNPREPARED.csv)。
- [57个精确几何组](TARGETED_MANUAL_CASES.csv)、[各组的全部实验引用](TARGETED_MANUAL_ALL_REFERENCES.csv.gz)。
- [页面覆盖](PAGE_INDEX.json)、[当前静态交付检查](CURRENT_DELIVERY_QA.json)：57组、22页、654个只读原答视图，本地资源无缺失。PREPARE.json、SCAN.json及旧DELIVERY_QA.json仅描述历史库存恢复，不是当前任务验收。

## 判断与导出

保持入选节点、坐标及票数不变，判断能否形成合理完整连接。可以填写排列或拖动点对，选择“采用这个顺序”；节点或位置需要修改时选择“节点或位置有问题”，并填写编号和原因。完整原答只读，不能作为融合判断提交。

默认不显示闭合布局。节点编号不等于环序；三维连线须主动开启，仅为排列预览。不得把GT顺序或横坐标排序直接当成人工答案。

在完成排序的同一浏览器中，返回首页点击“一键导出全部图片的排序记录”，可合并当前队列各页保存在本地的记录；页面显示已采用、节点问题、待判断和草稿的数量。未保存的案例不会出现在记录中，导出不会清除或修改本地记录。汇总文件用于集中备份和后续分析，不能直接导入单个案例页；如需逐页恢复，仍需逐页导出备份。不同浏览器或不同来源地址的记录不会自动合并。

导出含固定点对绑定、完整排列、状态、团队身份及geometry_group_id；通过组映射连接所有实验用途。confirmed表示采用顺序，pairing表示发现节点/位置问题，pending和draft不表示采用。导出不会改写正式自动结果；回收后如计算辅助几何/质量，必须单列方法及对应支持。

这些案例用于补充机制解释，不是维持现有自动研究结论必须完成的修复。当前节点不足、未定位、OOS和容量记录均不安排排序。

## 复现

```powershell
python -X utf8 tools/thesis_main/analysis/audit_current_ring_references_20261104.py
python -X utf8 -m tools.thesis_main.analysis.close_current_ring_audit_20261104
python -X utf8 -m tools.thesis_main.analysis.build_missing_ring_review_20261104 --phase pages
python -X utf8 -m pytest tests/test_missing_ring_review_20261104.py -q
```

需要重新核查完整81,072条记录时，先用上面的恢复命令解包缓存；当前57个案例的人工工作台只使用`VALIDATED_REVIEW_IDS.json`指向的22页。历史生成页不随版本库提交，但保留在本机以避免丢失旧页面路径及其浏览器本地状态。

源表和正式研究输出均保持原样。已完成数据及静态检查；浏览器视觉、交互和下载验收仍未完成。
