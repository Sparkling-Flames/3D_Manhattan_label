"""Render saved sensitivity/control results without changing scientific inputs."""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .quality_validation_followup_20261107 import OUT


def main():
    figures=OUT/'figures';figures.mkdir(exist_ok=True)
    control=pd.read_csv(OUT/'CONTROL_RESPONSE_MATRIX.csv')
    fig,axs=plt.subplots(2,4,figsize=(14,7),layout='constrained')
    titles={'translation':'Horizontal translation','global_height':'Uniform ceiling shift','local_height':'Opposite local height shifts',
            'wall_shift':'Single wall displacement','corner_omission':'Progressive concave-corner removal',
            'spurious_corner':'Inserted protruding corner','rotation':'Rigid layout rotation','collinear_split':'Collinear edge subdivision'}
    for ax,(family,g) in zip(axs.flat,control[control.room_scale.eq(1)].groupby('family')):
        for metric,style in [('B8L2','o-'),('D10','s--'),('IoU3D100','^:')]:
            ax.plot(g.severity,g[metric],style,label=metric,markersize=4)
        ax.set_title(titles[family],fontsize=10);ax.set_ylim(0,103);ax.set_ylabel('Score (0–100)')
        unit='Rotation (rad)' if family=='rotation' else 'Removal fraction' if family=='corner_omission' else 'Displacement / camera height'
        if family=='collinear_split':unit='Repeated subdivision control'
        if family=='corner_omission':
            ax.set_xticks([0,.05,.15,.30],['0','1/6','1/2','1'])
        ax.set_xlabel(unit,fontsize=9);ax.grid(alpha=.2)
    axs.flat[0].legend(fontsize=8)
    fig.suptitle('Score responses to controlled layout changes at a fixed room scale',fontsize=14)
    for ext in ['png','svg','pdf']:fig.savefig(figures/f'control_responses.{ext}',dpi=300)
    plt.close(fig)
    natural=pd.read_csv(OUT/'NATURAL_SUMMARY.csv');half=pd.read_csv(OUT/'HALF_SUMMARY.csv');onset=pd.read_csv(OUT/'ONSET_SUMMARY.csv')
    n=natural[natural.difficulty.eq('ALL')&natural.metric.isin(['B8L2','D10','IoU3D100'])]
    h=half[half.version.eq('manual_assisted')&half.n.eq(14)&half.metric.isin(['B8L2','D10','IoU3D100'])]
    o=onset[onset.tolerance.eq(2)&onset.metric.isin(['B8L2','D10','IoU3D100'])]
    def table(frame,cols):return frame[cols].to_markdown(index=False,floatfmt='.3f')
    text='''# 独立人评准备、固定团队评分敏感性与几何响应（2026-11-07）

两项计算已完成；新一轮人工评价材料已制作，尚未招募或收回答案。正式Q、参考、分类与原团队没有变更。新增结果用于解释评分选择的影响，不挑选最有利参数，不用人工偏好拟合Q。

- [离线调查工作台](human_review/index.html) · [可发给评阅者的ZIP](独立人工调查_固定题集_20261107.zip)：30对整体质量评价；有缺陷多选项；无练习、把握程度和独立结构对应题。全景标注、2D底面和3D布局同时显示。
- [发放与回收说明](human_review/README.md)：同一固定题集分发，每人使用独立匿名编号；本人参与题自报回避，回收后检查每题至少3份判断。
- [固定的尺度与支持设计](SENSITIVITY_DESIGN.json)、[字段合同](FIELD_CONTRACT.md)、[实际验证](CHECKS.json)。

## 1. 已有验证怎样衔接

|证据|版本与用途|本次处理|
|---|---|---|
|[25对真实人评及控制](../quality_independent_validation_20261024/README.md)|历史v2，有曝光和解释边界|保留原判断；不充作新的独立人评。本轮不抽历史练习题|
|[固定端点多指标](../personnel_metric_dependence_20261024/README.md)|v2，同房/人数/策略与方向置零|保留，补当前v2.1主人数与半队的尺度敏感性|
|[48池138团队共同面板](../../data/releases/v2.1/fusion_common_panel/README.md)|相同团队/输出的墙线、medoid、Lee比较，v2.1参考接续|已有比较入口，无新增方法或团队；Polygon Consensus未在本轮实施|
|本轮96条几何控制|8类×3个房间尺度×4级，含基准与不变性对照|几何重新测量并保存，B8L2/D10/体积代理/深度等并列；不代表96个独立场景|
|本轮人评材料|当前主目标原答；全Manual，三个普通难度各9图、另3门洞；门洞作答在439保留名单内|只完成材料和回收工具，不能报告一致率或正确率|

## 2. 固定团队评分敏感性

固定B8L2五分项测量；分别将整体高度、局部高度、方向、底边尺度乘0.75/1.25，其余保持，另列D10及均高体积IoU。共10个Q公式规格与1个体积代理，均保留。它们是有限的单参数敏感性，不是所有评分体系的保证，也不是重新标定的正式分数。

原五分项回代B8L2/D10先逐记录核对。自然人数固定相同路径的两个端点以及各指标共同有效支持；半队固定208合法事件的A/B/C共同支持。自动版与固定坐标人工辅助版分别计算，未纳入F2/F9坐标候选。B8L2、D10与IoU3D100都标0—100，但其1分不表示等价物理偏差，不能按效应绝对大小评判指标优劣。

### 自然人数：方向保留，幅度随指标变化

'''+table(n,['metric','interval','statistic','images','mean_delta','positive','negative'])+'''

3→6使用206图；20→30使用171图。早段平均升质、后段低尾改善与SD下降在全部预设尺度变体中均保留。难图20→30在B8L2共同路径中平均−0.104，但P10+4.255、SD−4.556（27图）。

这不是用新数值覆盖原边际曲线：原报告20→30的+0.500、P10+2.848、SD−2.031按各人数自身可评路径汇总；这里先固定两端共同路径，B8L2对应+0.502、+2.844、−2.005。支持差异已记录于[NATURAL_SUPPORT.csv](NATURAL_SUPPORT.csv)，逐图配对见[NATURAL_FIXED_PATH_CHANGES.csv](NATURAL_FIXED_PATH_CHANGES.csv)。独立于Q的已有几何波动证据见[人数研究](../../workers/image_response_v21_20261101/README.md)，本轮没有重新计算几何波动。

### 半队：总体跨类额外变化与指定方向升质保持

'''+table(h,['metric','estimand','images','mean','positive','negative'])+'''

14/7的全部尺度变体总体GA、GS、C−B均为正，单图例外仍在。完整自动/辅助及20/7结果见[HALF_SUMMARY.csv](HALF_SUMMARY.csv)和[逐事件共同支持](HALF_COMMON_EVENTS.csv.gz)。20/7是35%替换。本次C−B也要求A/B/C共同，因此辅助20/7为53图、3.008分；原专项只要求B/C的54图、4.214分保持原估计对象，不能互相覆盖。

### 小变起点：难度层次保持，具体人数依赖量表

保留原规则：尾段至少max(5,ceil(0.15N))人，各人数至少64条共同有效路径，尾段均值最大差不超过容差。2分结果如下：

'''+table(o,['metric','difficulty','registered_images','found','median_onset'])+'''

在10个Q规格中，简单图的找到起点数118—123/130、中位8—11人；中等23—26/39、中位14—17人；困难14—15/37、中位16—18.5人。分层是在各规格成功找到起点的子集内描述，不能把条件中位数直接视为同图配对效应。不同量表的“2分”不等效；保留1/2/3/5容差全表，并逐图记录起点缺失，不能将未找到记为满员或0。**简单图通常更早出现小变阶段，但不存在由本轮支持的统一停标人数。**

## 3. 几何响应矩阵及发现

![固定尺度的控制响应](figures/control_responses.png)

[96条测量矩阵](CONTROL_RESPONSE_MATRIX.csv)、[方向/单调性汇总](CONTROL_RESPONSE_SUMMARY.csv)、[全部控制几何](CONTROL_GEOMETRIES.json.gz)。房间尺度为相机高归一后的1/2/4倍；横移和单墙位移按相机高的0/.05/.15/.30，刚体旋转按弧度，凹角去除按0/1⁄6/1⁄2/1的插值比例。三尺度共用同一形状，不是三批独立真实房间。

- 不变性对照：完全相同以及增加共线分段，B8L2均为100。不是点越多分越高。
- 局部顶高一增一减：保持顶点均高，均高体积IoU约100，B8L2随局部误差降至92.406；完整布局深度指标也有响应。该非对称底面的采样整体高度残差不是严格0，已保留测量值，没有强行清零。
- 整体高度、单墙位移、平移、旋转、突出的新增角点，在这组控制中的B8L2随预设变化下降。
- **渐进抹去凹角并非全过程单调：** 尺度1时B8L2为100→82.802→51.589→55.033；同时IoU持续下降，方向残差约0→3.196→10.258→8.325度。最终一步结构更缺，但方向项改善，带来总分回升。该结果说明复合取舍，不可笼统声称任意缺陷加重总分必然下降。没有据此改权或删除反例。
- 局部/整体高度系数比10.24来自(0.8/0.25)²，只在两种归一残差数值相等时成立，不等于同一物理缺陷或总分差放大10.24倍。

尚不覆盖的类型：跨目标空间选择、遮挡下的墙体真实性、镜面/柜体混淆、相机不可见核和严重自交的物理判定。它们需要目标规则/原图判断，不能只用合法几何扰动自证。按用户最新要求，本轮调查整体质量及可指认缺陷，不实施独立结构对应核验。

## 4. 本轮是否还要补更多实验

两项定向计算已覆盖当前主要人数、半队、阈值及几何响应问题，不需要重新选型或重跑全库融合。按用户要求，不预先收集人员编号，直接发送同一固定随机题集。建议3—5位熟悉任务、来源不局限高Q/C3的人员独立试做，再完成每题至少3份判断；是否达到覆盖以实际回收为准，回避/漏答导致的缺额逐题列出。无人员名单时不能自动证明所有本人参与题已排除，以回避选项和后续核对记录。先独立作答，后讨论分歧；分歧用于定位具体对应/缺陷，不用于追调Q。

结构近邻方法对照属于另一项实验。本轮未下载或实施Polygon Consensus，也没有联系评阅者。人工评价之后，只有后续原图证据表明具体机制问题或某条主要结论依赖特定尺度，才需要进一步定向补算。

## 复现

```powershell
python -X utf8 -m tools.thesis_main.analysis.quality_validation_followup_20261107 --part all
python -X utf8 -m tools.thesis_main.analysis.build_independent_review_20261107
python -X utf8 -m tools.thesis_main.analysis.report_quality_validation_followup_20261107
python -m pytest tests/test_quality_validation_followup_20261107.py -q
```

页面所有图片内嵌，按离线ZIP交付。最新浏览器和字段检查以CHECKS.json为准；尚未回收真实人评。分数在初次好/中/差判断后可查看，保存看分前快照与最终判断；不能把看分后的修改当作独立盲评。
'''
    (OUT/'README.md').write_text(text,encoding='utf-8')


if __name__=='__main__':main()
