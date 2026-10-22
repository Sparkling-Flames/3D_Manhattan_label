# 启动诊断与方向机制实验：未完成主池校准

## 结论与交付边界

本包不是574份普通manual与9份严重manual的校准完成包，不能据此推荐主Q工作参数。正常阶段未冻结，门洞阶段未启动，正式算法、GT、人员资格与融合算法均没有被本包修改。
本轮助手侧的工具调用没有提供可审阅的文本或图像返回。以下启动检查结果由实际执行的程序写入文件；它们与助手已经阅读、理解并核验源码不是同一件事。没有把回传问题解释为数据不存在，也没有以旧922份输入代替当前主池或3152份资料。

## 1. 启动程序记录

完整记录见 `startup_results.json`；每条外部命令的参数、目录、退出状态、日志路径均在其中。若进程被超时中断，状态可能停留在最后一次已保存步骤，不能把此状态视为启动全通过。

```json
{
  "support_zip": {
    "path": "/mnt/data/quality_execution_support_20261013(2).zip",
    "bytes": 661845,
    "sha256": "39fec3697df5d82c941b733bc6efdab5b7ea2ca1b0926c420ef0b21cbdf00dba",
    "files": 12,
    "crc_first_bad": null,
    "members": [
      "research/quality_execution_support_20261013/MANIFEST.json",
      "research/quality_execution_support_20261013/README.md",
      "research/quality_execution_support_20261013/VERIFICATION.json",
      "research/quality_execution_support_20261013/verify_support.py",
      "research/quality_parallel_local_20261012/source_package/quality_parameter_calibration_20261012/inputs/calibration_records.json",
      "research/quality_parallel_local_20261012/source_package/quality_parameter_calibration_20261012/scripts/centered_height.py",
      "research/quality_parallel_local_20261012/source_package/quality_parameter_calibration_20261012/source_snapshot/research/quality_scope_comparison_20261010/frozen_engine/core/quality_v11.py",
      "research/quality_parallel_local_20261012/source_package/quality_parameter_calibration_20261012/source_snapshot/research/quality_scope_comparison_20261010/frozen_engine/height_revision/height_revision.py",
      "research/quality_parallel_local_20261012/source_package/quality_parameter_calibration_20261012/source_snapshot/research/quality_scope_comparison_20261010/frozen_engine/legacy_geometry/audit_geometry.py",
      "research/quality_parallel_local_20261012/source_package/quality_parameter_calibration_20261012/source_snapshot/research/quality_scope_comparison_20261010/frozen_engine/legacy_geometry/geometric_components.py",
      "research/quality_parallel_local_20261012/source_package/quality_parameter_calibration_20261012/source_snapshot/research/quality_scope_comparison_20261010/frozen_engine/traditional/traditional_metrics.py",
      "research/quality_parallel_local_20261012/source_package/quality_parameter_calibration_20261012/source_snapshot/research/quality_scope_comparison_20261010/frozen_engine/validity/strict_geometry.py"
    ]
  },
  "snapshot": {
    "path": "/mnt/data/quality_calibration_execution_20261014/support_only_root",
    "head": null,
    "equals_observed_remote_main": false,
    "mode": "support_only_no_current_repository"
  },
  "remote_main_sha": null,
  "step_statuses": {
    "support_validation": "passed",
    "remote_main": "failed",
    "fresh_clone": "failed",
    "support_extraction": "passed",
    "verify_support": "passed",
    "focused_repository_tests": "no_matching_test_paths_in_this_snapshot"
  },
  "probe_status": "audit_finished_not_a_completed_calibration"
}
```

`source_texts/` 只在仓库快照实际读取成功时包含相应材料。目录或文件未出现在本次快照，不等于其在远端或Library中不存在。模块导入与测试的结果保留在日志中；结构清单和测试通过均不自动证明574/9的身份、参考或当前loader语义正确。

## 2. 独立方向实验的定义

所有下述实验均由 `direction_mechanisms.py` 生成，与准备包底点控制、R03274真人作答和正式主Q区分。其参考是居中单位正方形；待测菱形由单位向量 (1,0)、(cosθ,sinθ) 构成，四条边恒为1。
对0<θ≤90°，面积交并比的闭式解为：
`I(θ) = sinθ × (1 − cosθ/4) / (1 + sinθ cosθ/4)`。
固定或自由共同轴且允许每条边自由归入两个正交方向族时，最小平均方向残差均为 `D = 0.5 min(θ,90°−θ)`。因四条边等长，长度加权与不加权相同。故这个反转不依赖边长变化，也不必依赖共同轴重新优化。
这里的打分消融仅为 `q_toy = 100 I / [1 + (D/8)²]`。没有读取并复现正式四次尾项的精确实现，也没有将此简式称为完整主Q。

## 3. 本包程序复算的数值

θ=45°：I=0.5174282499，D=22.5000000000°，简式消融分数=5.8071736951。
θ=30°：I=0.3534813463，D=15.0000000000°，简式消融分数=7.8279606105。
两次独立运行的结果文件逐字节一致：True。测试与第二次运行退出码：0。
共运行90个等边菱形控制、150个另外构造的底点控制；其中可计算150个，不可评价0个。后者记录具体原因，未赋0分冒充有效结果。
这些底点控制不是准备包控制，不能声称复现了用户给出的8→16像素、Q约9.39→16.86链条；逐例及逐边记录是独立机制探索。

## 4. 修正候选与负结果

候选一是仅放松方向项强度。网格结果见 `toy_direction_strength_sweep.csv`。这能消除某些简式控制反转，但只是减少错误测量的影响，并未修复“方向族塌缩”本身；真实方向错误会同时被宽容。因此该网格不用于选择主Q参数。
候选二是在已知且可信的跨参考边对应下固定方向族。对本控制，残差变为 `(90°−θ)/2`，随变扁增加。代码对未确认的对应直接报错；缺点、多点或不同非冗余点数不会猜配对。其副作用是绝对参考方向也会处罚整体刚性旋转，而自由共同轴残差不会，可能与IoU重复计罚。
候选三是参考条件下的有符号转角差，在本控制中试验 `max(D, mean_turn_error/2)`，避免简单相加重复处罚。这能针对本控制补充墙间结构，但并非可直接部署的通用结构项：真实停止点、对应歧义、不同分段及合法非正交边界仍需资格门控。
反例检验显示：若合法非正交参考与作答完全相同，自身Manhattan方向D仍可能大于0，而参考转角差为0。因此直接对所有样本套用 `max(D,结构差)` 仍可错误处罚合法结构；本包不推荐该组合为工作版本。凹角采用有符号转角，禁止把270°凹角当成偏离90°的错误。共线冗余点会先规范化；长度加权方向对分段不变，不加权方向则不具备这一一般保证。

## 5. 单底点投影诊断的有限结果

独立控制固定原始方位角，只改一个底点的纵坐标，再由同一相机高度重建半径。设下视角v=π(y/H−1/2)，半径ρ=h/tan(v)，则 `dρ/dy = −hπ/(H sin²v)`。接近地平线时同一像素误差能造成更大的空间偏移；这是可直接推导的投影机制，不是已经核实的R03274归因。
代码旁列逐方位角的底边像素差，包括平均值、95%分位数和采样最大值。连续射线与环形角度避免逐顶点数量相等的要求，并能检验接缝与共线冗余点；但只支持单一可见底边函数。遇到多重射线交点会限制评价，不会默默选取一个空间。最大值属于有限采样诊断，不宣称精确Hausdorff距离，也未加入主Q。
本包没有R03274原图或其经过核实的几何，不能把合成控制解释为该题的视觉或几何核查；没有为R03274设置目标分数。

## 6. 未完成的明确项目

574+9当前身份及参考核查、207/367分层、准备包底点控制的输入→几何→分项→总分复算、至少一份真人作答复算、3152当前loader、原图视觉核查、110份历史高度控制、T20/P04/L01/J02最新原话回接、正常样本方向反转频率、同资格现用3D IoU对照、按图及建筑集中度、原留出回归、门洞纳入名单及细调，均未由本包完成。
本包中的等高棱柱3D IoU只是在共同高度区间下与底面IoU相等的合成对照，不是执行了仓库现用3D IoU。来源受限历史案例没有混入manual主池；OOS没有参与调参。

## 7. 是否推荐工作版本

不能推荐经本轮校准的工作版本，具体原因是当前主池执行与参考链尚未获得可审阅核验，非“参数不唯一”或泛称证据不足。正式版本应保持未修改状态；这不等于确认其当前参数合适。
本轮可支持的机制判断限于：方向族自由归属可造成结构塌缩时D反而降低；应先修复或限定方向/结构测量，再研究惩罚强度。不能据此声称该问题在真人主池普遍、已改善R03274、已满足高度意见，或某候选全面优于3D IoU。
下一步的最小阻塞是恢复工具的可审阅源码、运行结果与图像返回；随后利用现存574+9准备材料执行正常阶段，不需要先新增人工复审。

## 8. 复现

仅复现独立机制实验（仅需Python标准库）：

```bash
python direction_mechanisms.py --test --output reproduced_synthetic
```

重做启动诊断（需要git、网络及仓库读取权限；相关依赖需要numpy、scipy、shapely、pytest）：

```bash
python startup_probe.py inputs/quality_execution_support_20261013.zip
```

注意：启动程序的git回退使用公开HTTPS；若仓库需要认证而本地未配置凭据，它会保存实际git错误并退到support-only检查，不会将该检查称为当前仓库全量核验。`startup_probe_first_submitted.py` 保存本轮最初提交执行的原始脚本；便携版只调整输入与运行目录获取，不把便携版当成另一份已运行证据。

完整文件清单为MANIFEST.json。ZIP的逐项解压及哈希复验回执在压缩包旁的 `.verification.json`。文件完整性通过与算法校准完成是两种不同结论。
