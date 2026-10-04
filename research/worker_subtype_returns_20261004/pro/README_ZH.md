# 人员子类与真实组合研究交付

入口：`REPORT_ZH.html`（图表已内嵌，可离线打开）或`REPORT_ZH.md`。

本包使用冻结提交`ad12d64d3567235e5691f9142d045df63b38b4e4`。包含当前完整24×10参考评分矩阵、两张24人地面几何摘录、高人数台账摘录，以及新增可复算研究。不是完整仓库，也不是44张高人数图的全量重算。

主要新增：不均等Q分型与嵌套留建筑检验；校准名单不确定性传播；精确同k抽组、无重叠抽组、增一／增二及换人；原始下一人差异与重新融合变化分离；两图全部真实六人组合；带失败的固定47图方法覆盖。

当前T/S/B的来源溯源与接入要求保留，但没有完成当前逐行绑定和新数值验证。不得把该缺口标为零或从本包推出四轴类型已经成立。没有原图、没有新视觉GT裁决、没有修改人员权重。

## 运行

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python run_all.py --out /path/to/NEW_output
```

已有兼容环境可先直接运行测试；requirements是本次已测版本快照，不要求仅为版本号重装。

完整复算可能需数分钟。指定目录已存在时立即拒绝，避免覆盖。核心计算为精确枚举或有限池概率，不依赖随机种子。已测版本记录在`environment.json`；跨版本运行需重新执行测试。

本轮35项测试通过；全部数值阶段在第二个新目录重新计算，41个工件匹配。包装脚本首次连续运行受200秒环境时限中断，剩余阶段随后分别完成。见`logs/full_reproduction.txt`、`logs/reproduction_comparison.json`。未声明全仓库回归通过。

## 接入当前本地数据

```bash
python src/run_local.py --input inputs/one_image_geometry.json --classes example_classes.json --out /path/to/NEW_local_output
```

`example_classes.json`是真实两组12人的楼外Q例子，不是T/S/B示意假数据。`run_local.py`也接受当前`images/annotations`结构。分类清单必须明确当前实际作答ID、人员、单一条件、类别、校准建筑和特征来源；目标建筑不得参与校准。任何当前选中人员不可计算就保留整组选中名单与失败状态，不静默缩池。该入口不验证本地声明的视觉判断或初始化来源是否真的正确；需本地提供可审计的来源链。

## 主要文件

`results/nested_summary.csv`与`nested_method_choices.csv`：内层选择、外层评价的Q预测；分数是图内相对参考分数，不是绝对质量或共识IoU。

`results/disjoint_learning_summary.csv`：互不重叠校准建筑下的类别稳定性；不可确定的中位数平局保留在明细。

`results/*_area.csv`、`*_transitions.csv`、`*_annotation_vs_fusion.csv`：固定名单内的形状、联合人员过程和下一名原始作答。面积分母与IoU不同，先读`FIELD_GUIDE_ZH.md`。

`results/*_six_person_all_sets.npz`：全部真实六人ID组合及两规则IoU、面积；配比汇总与同配比成员方差另见CSV。

`results/calibration_propagation_summary.csv`：名单改变如何继续影响六人结果，目标图不参与分类。

`results/high_support_scope_summary.csv`和`fixed47_coverage_by_k.csv`：来源台账的高人数范围及方法覆盖；不是全量几何重跑。

`src/restore_*.py`：从已实际读取的连接器数值恢复小输入的记录脚本，不是重新采样或图像修复。正式复算使用已冻结的`inputs/`，不需要执行这些恢复脚本。

`SOURCE_MANIFEST.json`：出处、准确字节匹配与数值摘录的区别。`MANIFEST.sha256.json`：本交付文件校验，不等同源仓库全包校验。
