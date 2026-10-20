# 外部输入恢复：快速重放与完整重训

在成果包解压根目录执行，使用包内 `requirements.txt`。下列两条恢复路线二选一；若准备重训，直接选第二条。bootstrap 只恢复并核对继承文件，不重新清洗原始导出，也不自动重跑科学分析。

## 版本分别指什么

- 科学融合源：`82c6164b0d4630de5316199c92aa405930973168`。
- 本轮实际核验的档案仓库提交：`e572eb73bedc4fe9056df838e458bab83c3fa423`。
- 本轮任务文档 main：`445686f8f3cf6039c4ce1f60016cad1d26829044`。

已有仓库须含下面两个归档目录的实际分片，不能只有 Git LFS 指针。当前源码字节不匹配时，bootstrap 会从 Git 读取冻结科学提交；若缺该对象，先补取该提交。最终以归档逐件 SHA 校验为准。

```bash
PERSONNEL_REPO=/absolute/path/to/3D_Manhattan_label
```

## 一、只重放案例或 17,726 支核心团队

使用 `pro_personnel_v2_archive_20261019/bootstrap.py`（简称 pro_archive）。它的输出参数是 **`--workspace`**，目标必须尚不存在；应恢复到 `restored/work_personnel_typing_A_20261019/recovered`，不是直接恢复到 `restored`。

```bash
python "$PERSONNEL_REPO/research/workers/pro_personnel_v2_archive_20261019/bootstrap.py" \
  --repository "$PERSONNEL_REPO" \
  --workspace "$PWD/restored/work_personnel_typing_A_20261019/recovered"

python reproduce.py cases --restored restored --work ../replay_cases
python reproduce.py core --restored restored --work ../replay_core --jobs 3
```

`cases` 重放 10 个案例的 39 支不同团队；`core` 重放 17,726 支核心团队。两者的精确成员输入已在成果包中，外部恢复提供冻结融合／评分程序。无需恢复旧 A 的全部事件档案，也不用下载原图全集。bootstrap 保持默认 `verify`，无需 `--execute` 或 `--stage all`。

## 二、重建全部正向画像，或重训反向类别

使用 `personnel_type_discovery_next_20261019/bootstrap.py`（简称 A_archive）。它的参数是 **`--output`**，输出根必须全新或为空；它会自行建立 `work_personnel_typing_A_20261019/`。不要覆盖快速路线已经填入内容的 `restored`；需要并存时另选空目录，正向入口相应改变 `--restored`。

```bash
python "$PERSONNEL_REPO/research/workers/personnel_type_discovery_next_20261019/bootstrap.py" \
  --repository "$PERSONNEL_REPO" --output "$PWD/restored"

python reproduce.py forward --restored restored --work ../replay_forward
```

A_archive 默认从同一仓库寻找 pro_archive，无需先运行后者。仅恢复 pro_archive 不足以重建全部 F 画像；完整恢复还提供这些继承输入：

- `work_personnel_typing_A_20261019/forward/build_features.py`；
- `work_personnel_typing_A_20261019/recovered/repo_main_20261019/research/statistics/v2_evidence_audit_20261019/records.json.gz`；
- `work_personnel_typing_A_20261019/recovered/work_v2_20261019/profiles/run_profiles.py`。

正向入口按本说明同目录的 `FORWARD_FEATURE_INPUTS.json` 核 SHA，重新估计 10 栋历史楼画像和候选类。反向重训还需 A 的 79 份历史逐池事件，以及可由本轮历史请求→冻结融合→`reverse/extract_native_history.py` 重建的新历史配对表。原反向入口按研究根目录的 `restored/` 布局读取；详细命令见 `interchangeability_20261020/reverse/REVERSE_REPRODUCTION_ZH.md`，逐件输入 SHA 见其同目录的 `REVERSE_RECOVERY_INPUTS.json`。

完整 A 恢复约产生 1.56GB 临时文件，属外部重建输入，不应再装进精简成果包。案例／核心重放、精确成员设计重建、完整画像重估、反向重新学习是不同复现层级；前两项通过不代表后两项已执行。
