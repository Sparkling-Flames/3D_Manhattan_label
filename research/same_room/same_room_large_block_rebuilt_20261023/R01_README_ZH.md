# R01：新登记精确ABC设计与冻结执行代码

这是遗失新大块设计后的新实验登记，不是恢复旧111054端点。

固定main e92abe8631d7f01dc192ee796b46f295ece37a6d；设计版本same_room_strict_abc_rebuilt_20261023_v1。
62676个严格ABC、311333个唯一端点请求、76个冻结池。原生计算已启动，本包只交付已冻结设计与执行环境，不声称请求已经全部完成。

普通Manual结构：78图对、9楼，m5–8，1398个n/m配置；其它层与联合Q/T分别保存。Semi在采用直接关系中没有m>4严格ABC容量。

解压到任意目录，进入本专题相对路径。安装engine/requirements.txt后运行：

```bash
python engine/native_team_runner.py --requests design/ENDPOINT_REQUESTS.csv.gz --output native_endpoints --jobs 6 --chunk-size 500
```

engine/frozen_repo只保留执行必要的固定版本代码和小型冻结输入，不含原图全集、虚拟环境或旧端点缓存。每500端点保存标量及完整几何/身份组状态，完成回执后才视为有效checkpoint。

先读design/DESIGN_PLAN_ZH.md、DESIGN_MANIFEST.json与LEGALITY_RECEIPT.json。精确成员在design/STRICT_ABC_EVENTS.csv.gz，路径在FIXED_A_SCALE_PATHS.csv.gz和DESIGN_PATH_LINKS.csv.gz。

最终新结果与条件/重抽分析将另包交付，使用相同设计与请求hash。本包不会被静默改成旧研究恢复件。
