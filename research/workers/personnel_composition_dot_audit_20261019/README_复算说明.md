# 独立审查材料

先读 `独立代码审查_人员组合_20261019.md`。三个 dot_* 子目录分别包含类别、统计、原生融合审查；这些是本次新执行的证据，不是复制 Pro 原先的审查结论。

## 内容及边界

原研究包 SHA：730da5c4c7744e87773a5e78f99dec764318d724346e967e925ab64191226cf3。
本包不再附 42.4 MB 原研究包、源仓库、虚拟环境、583,261 队缓存或全部可重建请求。数值重拟合输出、小表和案例重放 JSON 保留；大型筛查融合输出保留生成方法和完成收据。

## 重跑

脚本保留实际执行的原文，里面的绝对工作目录不是你电脑的路径。可使用附带 `run_relocated_audit.py`，它只替换工作目录前缀，不改算法。将新原包解压到你选择的 ROOT/extracted/，使 ROOT/extracted/personnel_composition_study_20261019 存在。

按原包 analysis/REPRODUCE_ZH.md 恢复固定源码与依赖到 ROOT/source_repository、ROOT/restored。请求重建输出到 ROOT/dot_replay_audit/requests。运行此包脚本会将新结果写在脚本旁边，若要保留本次收据请先复制整个审查包。

小表独立汇总示例：

    python run_relocated_audit.py --root /你的/ROOT --script dot_effect_audit/recompute.py
    python run_relocated_audit.py --root /你的/ROOT --script dot_effect_audit/check_full_tables.py
    python run_relocated_audit.py --root /你的/ROOT --script dot_effect_audit/extra_sensitivities.py

这些命令只需原包小表；实际成员控制和逐人删除脚本还需上述精确重建的区块请求。筛查审查的独立脚本见 dot_class_audit/independent_screen_recompute.py，参数用 --help 查看；需先使用原包 fusion_runner.py 从重建的 SCREEN_REQUESTS.json.gz 新算筛查输出。类别完整拟合命令见原包第6节与对应报告，不能用精度较低的汇总CSV替代原始冻结证据。

本包的脚本工作目录重定位入口已实际重跑小表检查；并不声称所有代码在任意操作系统上已测试。细节、浮点容差与未复算范围见三个技术报告。
