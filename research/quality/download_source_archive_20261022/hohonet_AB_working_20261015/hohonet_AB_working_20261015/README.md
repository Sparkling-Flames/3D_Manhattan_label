# HOHONET质量双路线调参工作版（2026-10-15）

采用建议：A10用于主分析，B8L2并行用于敏感性与下一批核验。两版都是新的连续评分，不是WQ改名或五档映射。原WQ保留历史对照，正式默认未改变。

入口：[完整报告](REPORT_ZH.md)、[A配置](configs/A_WORKING.json)、[B配置](configs/B_WORKING.json)、[1145逐例结果](results/SCORES_1145.csv)、[案例分项解释](results/REPRESENTATIVE_CASES_AND_ATTRIBUTION.csv)。

## 计算接口

```bash
python -m pip install -r requirements.txt
python score_one.py --model A10 --I 0.829 --Sb 1.6423 --D 6.7291 --Hm 0.0215 --Hc 0.0169
python score_one.py --model B8L2 --I 0.829 --Sb 1.6423 --D 6.7291 --Hm 0.0215 --Hc 0.0169
python reproduce.py --output /path/to/a/new/replay --figures
```

输出目录必须不存在；复现不会覆盖既有回执。依赖版本记录在provenance/ENVIRONMENT.json。普通调参先运行并保存冻结配置，再运行门洞探针和普通回归。下游在参数选择之后运行，不按哪个模型更支持论文选择参数。五档读数标为OPTIONAL，不是本轮采用基础。

Python可直接导入`src/working_models.py`的`score(I,Sb,D,Hm,Hc,params)`、`floor_upper_bound`和`attribution`。缺值不补零；该纯数值API不自动授予资格。

## 参考与分母

1145是当前绑定的完整数值作答；每个record_id唯一。931普通manual条件行、115门洞条件行、10门洞范围暂缓、28两图范围诊断、3普通台阶参考暂缓、39semi次层、9严重例外、10历史旁证分别保存。不能将其合并成1145个同资格训练对象。

`DIFFICULTY_JOIN_1145.csv`有1050行参考ID相同、95行参考ID不同。不同者明确单列；836行/95张图进入普通三类难度描述。相同ID不等于本轮又验证了一次参考几何完全一致。

所有标准化常数属于冻结分项口径；D仍是自身轴规整性，不是参考墙角。详情及残留缺陷见报告。

## 下一批核验

已有本地Codex `hydration_check/NEXT_ORDINARY_REVIEW.html`可原样继续使用，作答几何并不因评价公式改变。`review/PRIVATE_NEXT20_MODEL_KEY.csv`保存两版预测，核验前不要展开；`review/NEXT20_BINDINGS.csv`保留原20卡身份及参考，不重选有利样本。

重新使用已生成20卡（只解析JSON，不执行输入页面脚本）：

```bash
python materialize_review.py --existing-page /path/to/NEXT_ORDINARY_REVIEW.html --output /path/to/new/review
```

从真实仓库loader与原图重新生成：

```bash
python materialize_review.py --repo /path/to/3D_Manhattan_label --images /path/to/images --output /path/to/new/review
```

这两条外部数据路径本执行环境没有相应原图/20卡payload，未宣称已经执行。前者只复核显示ID/图片ID并继承旧几何出处；后者还会复算绑定分项。当前包实际生成的是[两图36卡](review/TWO_IMAGE_REVIEW.html)，含34份几何和2份不可用记录；本地选择原图文件夹后即可看图并记录顶界建议。原图不重复打包。

## 不应做的事

不要逐例取A/B高分；不要挑最高分参考；不要用相同旧切点比较新旧“合格率”；不要将这里的探索性人员相对三组写成正式能力类别；不要把固定融合终点重评分当成重新融合；不要把底面上界当成已核验完整3D分数。

本包全部新结果来自可读数据和实际执行；工具缺口逐项见provenance/NETWORK_AND_COVERAGE.json。完整研究输入仍不是3152全库当前loader的替代品。
