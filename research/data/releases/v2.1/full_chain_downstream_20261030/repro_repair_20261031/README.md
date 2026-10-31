# 去重归档后的隔离复现修复

2026-10-31。按用户授权应用外部提案，经are-you-sure复核后增加Windows长路径支持与隔离发布输入验收。修复只连接历史源码/输入和发布清单，不改变人员标签、参考、原答或科研算法。

**最终验收：** 176项历史输入精确匹配、10项适配器测试通过；七项隔离数值运行和15张表全部通过，最大差约1.14×10⁻¹³。临时副本已清理。见[最终回执](FINAL_CHECKS.json)和[逐表对照](checks/RERUN_CHECKS.json)。修复尚未提交或推送。

## 已实施

1. 新增`tools/thesis_main/analysis/stage_v21_full_chain_source.py`，按原清单检查176项非缓存source文件；依次使用准确的历史镜像、source_variants、仓库根对应文件，不以新版近似替代。SHA用于本次明确授权的历史版本匹配，未扩展为全仓库校验。
2. 放行已有但被忽略的3份历史版本、requirements和7份repository_update历史文档。后者只作证据归档，不应用其中的旧补丁。
3. [原1406成员发布去向](PUBLICATION_MEMBER_MAP.csv)：1147原路径跟踪、176经适配器恢复、8项原路径发布修复（7文档加requirements）、51原图/3内嵌原图页面/21历史执行日志保留本地。source_variants的3文件另属去重恢复材料，不重复计入1406。
4. [忽略规则验证](IGNORE_REPAIR_CHECKS.json)确认11个修复载荷路径可跟踪；未放开全部research/data、原图或日志。

## 如何复现

先正常获取仓库所需LFS对象。本次发现`EVENT_GEOMETRY_COMMON_SUPPORT.csv.gz`在Git对象中是132字节LFS指针；按指针OID和大小核对了本机现存对象后用于隔离副本。见[LFS记录](LFS_MATERIALIZATION.json)。没有重新联网验证下载服务。

在仓库根运行预检：

```powershell
python -B tools/thesis_main/analysis/stage_v21_full_chain_source.py --repo .
```

预检通过后，以新的空目录运行隔离复算（目标目录不得已存在）：

```powershell
python -B tools/thesis_main/analysis/stage_v21_full_chain_source.py --repo . --stage-copy .repro_study --run-checks --report-dir .repro_report
```

Windows路径自动使用长路径形式。历史目录不写入；检查仍调用原有科学脚本，不改变数值比较逻辑。阶段目录包含独立复制的source，不使用指向历史输入的软链接。

## 本轮验证范围

以当前HEAD `d4c73943ae58476880bf3ceb7b774e4ec59a95b5`的Git blob构造最小隔离发布副本，添加本轮明确修复的4项运行载荷并补齐1项已核对LFS对象。它没有借用本机被忽略的source镜像。Git archive受本机MSYS权限限制，改用git cat-file读取同一HEAD对象，未切换到当前工作区文件冒充发布数据。

[预检](SOURCE_PREFLIGHT.json)176/176精确匹配。适配器10项测试通过，覆盖版本失配、越界路径、禁止覆盖、隔离当前源身份比较和拷贝间源变化。数值运行结果以`checks/RERUN_CHECKS.json`为准；最终状态记录于FINAL_CHECKS.json。

这属于本地HEAD发布形态加本轮修复的隔离重建，不是修复已推送后的远端新克隆验收，也不是全库原生融合重放。原图/浏览器页面验收未开展；52条同用途旧模型复现问题未由本轮自动解除。

## 研究推进建议

[are-you-sure复核与修订设计](RESEARCH_PRIORITY_REVIEW.md)：Q-only定向公平对照优先，大池策略按用途选择，同房新ABC暂缓。候选工作快照与论文最终分类分开；本轮未启动这些新实验。
