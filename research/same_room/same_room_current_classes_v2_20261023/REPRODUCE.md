# 同房包本地接续

在仓库根运行：

```powershell
.venv/Scripts/python.exe -X utf8 research/statistics/pro_return_review_20261023/audit_scripts/audit_independent.py research/same_room/same_room_current_classes_v2_20261023
.venv/Scripts/python.exe -X utf8 research/statistics/pro_return_review_20261023/audit_scripts/audit_reuse_capacity.py research/same_room/same_room_current_classes_v2_20261023
```

脚本直接读取四份端点，无需先生成完整合并表；结果写到所传包目录的`INDEPENDENT_*`，已采用副本保存在独立核验专题。若后续需要作者分析接口，可以依照[source_original/REPRODUCE.md](source_original/REPRODUCE.md)执行拼接/重汇总，原代码及其环境说明保留。

新增实验优先从精确成员设计、保存的端点和既有楼外标签出发。原作者结果与本地修正分别标识，主预算和全人数分母不要混用；同房建筑只是分层/留出单位，不代替房间直接关系。
