# v2.1 full-chain 去重后的复现核查与最小兼容方案

核查对象：GitHub `Sparkling-Flames/3D_Manhattan_label` 的 `main=d4c73943ae58476880bf3ceb7b774e4ec59a95b5`；2026-10-31 03:07 UTC再次读回未变化。只读远端，未创建/管理Work、未编辑既有checkout、未推送。全部新文件仅在本独立scratch目录。

## 结果

**科学交付已显著补齐，但“当前净克隆可直接跑全文档命令”尚不成立。** 不是又缺五条科学结果，而是去重后的路径和发布清单未同步闭合。

1. **确定的运行断点**：`tools/thesis_main/analysis/check_v21_full_chain_20261030.py` 在 `check_headlines()` 内直接读取 `STUDY/source/.../pools/INPUT_SNAPSHOT.json` 与 `TARGET_MAIN_EVENTS.csv.gz`。完整子树无 `HOHONET_v21_full_chain_20261030/source/`。`prepare_half_team.py:12`、`speed_difficulty.py:22`、`selection_stop_prepare.py:15–16`也硬编码该镜像；单改README或只改入口两行不能修复整链。此为远端代码/树静态确证，**不是声称已在完整净克隆实际运行**。
2. **去重异版保留不完整**：README说7份 `source_variants`，实际只有4份历史文档（另有说明README）；缺 `research/data/releases/v2.1/final_classification_downstream/README.md`、`personnel_reselection_dependencies/DEPENDENCIES.csv`及该目录README。已从固定源提交`13a786...`读取历史内容，在本地恢复3份，全部符合原交付`core_MANIFEST.csv`长度及SHA256。
3. **依赖文件漏归档**：REPRODUCE引用`requirements.txt`，远端树中无此文件。已按ENVIRONMENT_LOCK重建110字节，SHA256与原manifest完全相符，不是新拟定版本。
4. **发布清单未重新对账**：原SOURCE_PATH_MAP有1406成员，当前同子树1192文件；其中原清单1147项仍在原路径，259项不在：176个source镜像成员、51原图、3大HTML、21日志、7份repository_update/base/overlay数据文档、1份requirements。前3类有说明；后29项没有清晰的发布去向。源异版缺3份属于176镜像去重后的恢复缺口，不能再加成259中的独立成员。当前树还含45份不在原1406清单的后加文件。
5. **原因已实测**：把main的完整`.gitignore`放入临时空git仓库执行`git check-ignore -v --no-index`：无锚`data`（第6行）忽略内嵌`research/data`；`*.txt`（257行）忽略requirements；`*.log`（65行）忽略日志。该测试没有修改用户仓库。
6. 现存`RERUN_CHECKS.json`是本机历史回执，7项/15表通过；`LOCAL_INTEGRATION_CHECKS.json`同时记录`remote_main_verified=false`、`browser_run_locally=false`。它不能证明当前去重后净克隆通过。

## 不应重新列作“缺科学交付”的事项

- full-chain主线明确五条此前缺完整结果的材料已归档；旧参考评分2651次、5100前缀的本机核查已补齐（本次只审查回执，不重复背书全量运行）。
- 图片难度31池/28图已沿现有图片等级接续；不应再要求重复人工评级。
- 最新closeout顶端说明414项联盟变化中403个可执行联盟端点已补齐、11项为容量；旧279队待补表是历史，不是当前待办。
- 仍需区分：52条同用途旧内折预测未完全复现；最终分类选择与新策略实验；门洞用户交付；局部真实墙体语义；完整冷启动/浏览器发布验收。

## 最小兼容方案

`proposal/stage_v21_full_chain_source.py`是新增适配器，不改作者历史脚本。它先按原manifest逐一解析176个非缓存source身份，顺序为已有镜像→单独异版→仓库根复用，并要求字节数、SHA256都精确符合冻结交付。没有精确版本则失败，不把当前标签/参考替换成历史输入。

通过后只创建新的隔离研究副本，并在其中恢复`source/`布局；不对根仓库或归档目录写回。`--run-checks`可调用原七项检查器，但把输出和临时工作根隔离；两个当前源身份仍从真正仓库根复制进行对比，不伪造一致性。Q/QT输入仍指向原归档只读，输出由旧检查器写到隔离路径。

先把`proposal/restored_source_variants/`下三份原字节文件加回对应归档的`source_variants/`，把`proposal/requirements.txt`加回研究根；确认所用源提交和目前checkout。缺少的7份repository_update文档、21日志仍要另作恢复/排除说明，不声称本方案已补齐。

```bash
# 默认只读预检；失败时退出2，逐项给出缺失/不匹配
python -B stage_v21_full_chain_source.py --repo /path/to/repo

# 新目录必须尚不存在。输出位置不得在历史归档内。
python -B stage_v21_full_chain_source.py --repo /path/to/repo \
  --stage-copy /scratch/v21-frozen-study \
  --run-checks --report-dir /scratch/v21-rerun-report
```

建议用独立环境安装已恢复的requirements，不覆盖现有研究环境。`proposal/ignore-exceptions.txt`只给必需恢复文件添加定点例外，保留原图、大HTML和整source镜像的既定发布策略；它未应用到远端。

## 已做与未做的验证

已通过：10项适配器单元测试（根复用、历史异版优先、原镜像兼容、缺失/错版失败、禁止覆盖、禁止写历史目录、路径穿越拒绝、预检后变化拒绝、检查器隔离和真实当前身份）；原检查器比较器3项测试（浮点容忍、缺失掩码变化拒绝、实质数值变化拒绝）；3份历史异版与requirements共4份原manifest精确匹配；真实.gitignore匹配测试。

未做：176份完整当前源内容的全量预检、七项数值重跑、全部融合重放、真实浏览器验收。本环境没有完整checkout且未安装Shapely；本次没有尝试安装或下载整个研究仓库。没有把模拟夹具测试称为科研结果复现。

复验测试：`python -B -m unittest discover -s full_chain_repro_review_20261031/tests -v`。

## 证据位置

- `evidence/AUDIT_SUMMARY.json`：当前树、原清单及缺失分类；实际比较器测试。
- `evidence/RECOVERY_ATTEMPT.json`：历史异版及requirements精确恢复记录。
- `evidence/IGNORE_PATTERN_CHECK.json`：临时git仓库的实际忽略规则输出。
- `evidence/core_MANIFEST.csv`、`SOURCE_PATH_MAP.csv`、`full_chain_tree.json`：读回证据。
- [固定main入口脚本](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/d4c73943ae58476880bf3ceb7b774e4ec59a95b5/tools/thesis_main/analysis/check_v21_full_chain_20261030.py)
- [full-chain归档](https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/d4c73943ae58476880bf3ceb7b774e4ec59a95b5/research/workers/personnel_full_chain_v21_20261030)
- [当前收尾](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/d4c73943ae58476880bf3ceb7b774e4ec59a95b5/research/data/releases/v2.1/closeout_20261030/README.md)

## 并行工作建议

1. **可直接推进、无需新科学设计**：净克隆source适配、精确版本恢复、七项隔离检查；以7项/15表的新回执及当前commit身份为完成条件。
2. **可独立并行**：发布清单逐成员对账及7份补丁文档恢复/21日志政策说明；区分本地完整包、远端可读材料、远端可复现材料。
3. **独立历史复现研究**：52条旧内折差异逐样本原因归因；不得用它否定已完成当前模型对照，也不得擅自重训替换历史结果。
4. **不抢正在进行的任务**：只读Work看到门洞个人评分/团队曲线在进行，因此本方案不做门洞融合、参考改写或重复团队实验。
