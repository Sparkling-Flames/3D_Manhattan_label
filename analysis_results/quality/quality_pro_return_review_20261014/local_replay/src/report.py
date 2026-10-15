"""Assemble the Chinese research report from actual run outputs."""
from core import *
from compare import csv_dump
from collections import Counter
import html

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(str(v) for v in r)+' |' for r in rows])
def n(x,d=3):return 'NA' if x is None else f'{x:.{d}f}'

def main():
    allrows=read(ROOT/'results/effective_use_ledger.json')['records'];by={r['record_id']:r for r in allrows};summary=read(ROOT/'results/FINAL_summary.json');cs=read(ROOT/'results/ordinary_candidate_components.json');csummary=read(ROOT/'results/ordinary_candidate_summary.json');ms=read(ROOT/'results/mechanism_summary.json');ps=read(ROOT/'evidence/frozen_source_hashes.json');bench=read(ROOT/'results/iou3d_evidence_comparison.json');ht=read(ROOT/'results/height_attribution.json')['records']
    cases=[('P01／较小而规整','R02015'),('P01／较大而歪斜','R00637'),('J01 A','R03346'),('J01 B','R03347'),('J04','R03274'),('C02 A','R03351'),('C02 B','R03350'),('T20','R00397'),('P04 局部不平','R00418'),('L01 A','R01609'),('L01 B','R02297'),('Q02 A','R02200'),('Q02 B','R00990'),('Q03 A','R01501'),('Q03 B','R01191')]
    casetable=table(['对象','ID','旧尾项 g=1','本次输入现工作版','WQ-LS08','同参考3D IoU×100'],[[label,rid,n(cs.get(rid,{}).get('historical_tail12_g1',{}).get('score')),n(by[rid]['current_Q']),n(by[rid]['working_Q']),n(by[rid]['iou3d_pct'])] for label,rid in cases])
    layers=[('普通全部','ordinary'),('明确普通子层','ordinary_explicit'),('沿用条件许可子层','ordinary_conditional'),('严重例外','severe'),('门洞全部条件数值','doorway_conditional125'),('门洞回归子层','doorway_regression117')]
    layerstable=table(['层','份数','当前均分','工作均分','变化中位数','变化最大值','≥5分变化数'],[[title,summary[k]['n'],n(summary[k]['current']['mean']),n(summary[k]['working']['mean']),n(summary[k]['delta']['median']),n(summary[k]['delta']['max']),summary[k]['increase_ge5']] for title,k in layers])
    st=[r for r in allrows if r['source_layer']=='severe'];sevtable=table(['ID','图片','人员','角点对数','当前Q','工作Q','3D IoU×100'],[[r['record_id'],r['image_code'],r['worker_id'],r['annotation_pairs'],n(r['current_Q']),n(r['working_Q']),n(r['iou3d_pct'])] for r in st])
    at=[]
    for name in ['current_hill08','historical_tail12_g1','historical_simple8_g1','loss_sum','max_floor','product_height','product_all','nearest_normal_hill','ray_normal_hill','loss_sum_no_direction','loss_sum_no_boundary','loss_sum_no_overlap']:
        x=csummary[name];at.append([name,x['layers']['ordinary']['available'],n(x['layers']['ordinary']['delta']['mean']),n(x['evidence']['P01_margin']),len(x['evidence']['weak_grade_inversions'])])
    candidate_table=table(['候选','普通可算数','均值变化／对现版','P01 偏好边际','24项派生弱等级逆序'],at)
    door=read(INPUT/'data/supplement.json')['doorway_images'];dt=[]
    for r in door:
        # The supplied supplement stores canonical image identity under image.
        code=r['image']['image_code'];iid=r['image']['image_id']
        rr=[v for v in allrows if v['source_layer']=='doorway' and v['image_id']==iid]
        assert rr and set(r['records'])=={v['record_id'] for v in rr}, 'doorway_report_identity:'+code
        ss=[v for v in rr if v['working_Q'] is not None]
        dt.append([code,len(ss),len(rr)-len(ss),'仅范围条件诊断，不用于细调' if iid== 'B6ByNegPMKs_d2dcbd73533446dcaf50e6be98c30386' else '条件回归；不升级正式资格' if ss else '保持暂缓',n(np.mean([v['current_Q'] for v in ss])) if ss else 'NA',n(np.mean([v['working_Q'] for v in ss])) if ss else 'NA'])
    assert len(dt)==17 and sum(v[1] for v in dt)==125 and sum(v[2] for v in dt)==92
    doortable=table(['图片','条件可算','暂缓','本轮用途','当前均分','工作均分'],dt)
    hw=[]
    for rid in ['R00397','R00418','R01609','R02297','R03274']:
        for name in ['current','working','working_global1','working_local02']:
            z=next(r for r in ht if r['record_id']==rid and r['candidate']==name)
            hw.append([rid,name,n(z['height_loss'],5),n(z['fixed_working_nonheight_drop']),n(z['actual_height_drop']),n(z['complete_Q'])])
    heighttable=table(['ID','条件','高度损失H','固定工作版非高度项扣分','实际完整式高度扣分','完整Q'],hw)
    text=f'''# 全景布局质量评分初步校准：WQ-LS08 研究工作版

2026-10-14。研究对象是固定参考下的处理后几何质量，不是原始点击正确率、人员正式资格或融合算法。本文数值来自本包 `results/` 的实际运行结果；继承的人评原件全部保留在 `frozen_input/`。推荐是研究工作约定，不是独立验证通过或正式算法替换。

## 1. 结论与使用决策

**推荐 WQ-LS08-20261014。修改总分组合，保留当前底边、方向及高度损失的尺度。普通阶段已冻结；门洞阶段实际比较后，不追加参数变化。**

设 I 为底面 IoU，Sb 为双向球面底边平均距离（度），D 为自身共同正交轴下按边长加权的 RMS 方向残差（度）。Hm 是相对于参考周长均高的整体均高偏差绝对值；Hc 是去均高后、按既定最近底边对应计算的相对局部高度残差。

```text
B  = Sb² / 32
Ld = 1.5 D² / (D² + 37.5)
H  = (Hm / 0.8)² + (Hc / 0.25)²

Q_work = 100 I / [1 + I (B + Ld + H)]
       = 100 / [1/I + B + Ld + H]   （I > 0）
```

完整输入且I=0 时取严格极限0；输入或几何非法返回 unavailable，不能补0；缺少任一高度量或可信顶界时完整Q为空，仅另报底面分。参数为 `iou_power=1`，`boundary_scale=√32=5.6568542495°`，`direction_scale=√37.5=6.1237243570°`，`direction_cap=1.5`，`global_scale=0.8`，`local_scale=0.25`，所有相应损失幂为2；没有四次尾项，没有新增二维主罚项或统一90°角点罚项。

具体配置：[普通冻结](configs/ordinary_frozen.json)、[最终配置](configs/WORKING_FINAL.json)。纯评分实现位于 [src/core.py](src/core.py)，单例入口为 [src/score_cli.py](src/score_cli.py)。

该选择的主要收益是去除“范围不重合×所有其他误差”的额外放大，使已保留相当二维/底面接近信息的混合错误不至于被这一交互再次压低；保留P01明确偏好及严重端与轻微例的已知分离。主要代价是低IoU时自身规整性对最终分数的相对影响减弱，C02差距略变大、部分同图排序变化、严重例外也涨分。D的结构语义盲区没有修复；J01没有获得绝对分数量表的验证。

## 2. 本轮实际执行了什么

交接依据是上传的 READY 包，不是历史 PENDING 文件或此前会话中未核验的执行声明。`CURRENT_STATUS.md`、最新版 `PRO_TASK.md`、人工原回执与 amendment_01 均实际读取。Q02/Q03完整质量排序未建立不等于尚未审核；历史 `awaiting_receipt` 未覆盖当前状态。

源 ZIP 共 {ps['file_count']} 个文件，大小 {ps['archive_bytes']:,} 字节，SHA-256：

`{ps['archive_sha256']}`

已执行 ZIP CRC、原件逐文件SHA-256，以及工作副本与源ZIP119文件逐字节一致性核验。源引擎、GT、坐标、原始回执未改；全体新结果写到独立目录。详见 [源文件清单](evidence/frozen_source_hashes.json)。

实际运行分四层：

|执行层|本轮完成|含义与限制|
|---|---:|---|
|提供包的启动检查|583份存储metrics重评分，误差0；J04＋2个底点＋7个菱形重建|不是全量几何复算的替代|
|所有可评分真实配对从点重建|574普通＋9严重＋10历史＋125门洞＝718配对|保持各层隔离，同一输入、同一参考、同一环序；不是718份普通训练|
|全体对象输入链核验|907对象；902可重建，5保留不可用|逐对象核对周期平均x、y不变、源点身份、点对、顺序及几何；不声称运行了项目3152全量loader|
|既有控制重新测量|34底点＋110高度＋7菱形＝151|34份从原控制点重建；110份高度及7份菱形从所供显式几何重新测量，不冒称都由ERP点重建|

902对象的最大几何差约8.88×10⁻¹⁶；真实配对核心指标最大误差小于3.2×10⁻¹⁴。718配对及151控制均得到完整数值，没有用旧保存分数代替本轮测量。计算细节为底边球面采样2048、高度双向采样各4096；新增最近方向诊断每方向1024、方位射线诊断2048，不是新的人类容差参数。[对象核验](results/object_and_input_audit.json)、[普通重建](results/ordinary_reconstruction.json)、[门洞重建](results/doorway_reconstruction.json)、[控制重建](results/control_reconstruction.json)。

随后进行了35种普通候选/单机制消融/宽范围敏感性计算，再冻结普通版；之后才新计算125门洞并比较10种门洞方案。最后回查574普通及9严重。还运行了21个机制控制、112个密集底点状态和3066个从真实输入派生的诊断状态。**派生状态不是新增真人作答，控制通过不是人评通过。**

另在全新目录完整执行 `reproduce.py`：实际重建、比较、控制、冻结、门洞、回归和测试全部顺序运行，810条最终用途记录一致、所有可评分记录的最终Q误差为0。见 [完整重跑回执](logs/CLEAN_FULL_REPRODUCTION.json)。新增50项测试通过；其结论是算术、资格及来源合同通过，不是量表效度证明。

特别纠正版本混用：普通/严重原行 `components` 保存的是旧四次尾项结果；本次输入的现工作版必须读 `stage/COARSE.json` 中 `hill_global08`。本轮对所有组统一重新算当前式及候选式，未把旧尾项7.25误称成现在仍用的J04分数。

## 3. 为什么改组合，而不是继续加方向尾项

现工作版为 `Q_current=100I/(1+B+Ld+H)`。令 O=1/I−1、K=B+Ld+H，则

```text
100 / Q_current = 1 + O + K + O·K
100 / Q_work    = 1 + O + K
```

原式隐含额外的O·K交互。一次底点偏移可以同时改变范围、墙方向、球面底边和三维高度；当前证据并未验证这些同时发生时还需要额外乘积放大。新式去掉该交互，但保留I、Sb、D、Hm和Hc，不是用“二维点多数正确”直接抵扣一个坏点。

这也解释新分数为什么整体上升：

```text
Q_work − Q_current = 100 I K (1−I) / [(1+I K)(1+K)] ≥ 0
```

因此**总体涨分是代数性质，不是人评准确率提升的证据**。新式满足Q≤100I，I=0不给分；在其余指标完全无误时，每个单因素的响应与当前式完全一致。没有把0—100包装为正确百分比或严重程度的等距量表。对已有五项指标，主分只增加常数级算术变化，不新增几何匹配开销；额外诊断不属于主评分必需步骤。

[候选总览](results/ordinary_candidate_summary.json)、[完整逐项分数](results/ordinary_scores_long.csv)：

{candidate_table}

35候选并非同时拟合全部机制：先检查D的测量替代，随后单独比较组合，再做逐个参数及删除项的归因。方向cap探索0.75/1/2/3，方向尺度4/8/12°，底边尺度4/8/12°，整体高度尺度0.5/0.65/1/1.2，局部尺度0.15/0.20/0.30/0.40；详细配置保存在 `configs/ordinary_candidates.json`，没有把历史小网格当边界，也没有按弱等级自动选唯一最优。

删除D使P01反向，说明仅依靠重合与高度不能保留当前明确的几何优先取舍。`max_floor` 使用 max(O,B)，均分上升更多，但在O大于B时继续恶化Sb完全不影响分数，形成硬屏蔽区；这不是本轮希望增加的性质。乘法高度/全乘法仍保留或增加组合放大，没有用分数降低就自动判其错误，但不能解决当前提出的量表问题。

多数邻近尺度都能通过少数旧偏好。这表示参数并不被这些意见唯一识别；本轮采用已有中等强度，改变一个有机制理由的交互，避免同时改多项让归因丢失。没有依据因门洞预期较差而把方向重新加重。

## 4. 底点、菱形与方向族盲区：测量问题确实存在

### 4.1 准备包的狭长矩形已实际复算

|bottom-y RMS像素|IoU|D|矩形转角偏离90° RMS|旧尾项完整Q|当前完整Q|工作完整Q|
|---|---:|---:|---:|---:|---:|---:|
|8|0.8031|18.8196°|43.6192°|9.3945|32.1340|36.4387|
|16|0.6232|11.4384°|65.6612°|16.8598|21.6376|28.6955|

**当前hill08已经消除了这组完整Q逆序，不能将它宣传为本轮新式独有的修复。**本轮新式保留这一性质，并在密集控制中复查。112状态中108有效，4个大幅负向底点落入表示域外而明确不可用；旧尾项有14个上升步，简式有13个，当前式和工作式均为0。[密集与机制控制](results/mechanism_controls.json)、[汇总](results/mechanism_summary.json)。

共同轴、方向族和长度要分开看。正向控制共同轴约82.27°→14.09°；其镜像负向为7.73°→75.91°，只是坐标/扰动符号差异。负向控制的短边权重约0.1237→0.1647，不能假定权重不变；但固定参考轴并沿用当前权重，残差仍20.34°→18.15°，固定参考权重仍18.34°→14.65°。**只固定轴或只冻结权重都不能阻止族塌缩。**参考边族同时固定后，当前权重残差变为20.34°→34.55°。

8像素时相邻边落在不同族，16像素时四边全部落入同族，墙角趋于平行却离“任一轴”更近。这个语义盲区不能通过更重尾项修好。逐边方位、残差、权重和族保存在 [axis_family_decomposition.json](results/axis_family_decomposition.json)。

### 4.2 等边菱形的正确RMS定义

四条边保持单位长，锐夹角θ；自由轴、自由族的D=½min(θ,90°−θ)。参考固定轴但仍允许换族时，RMS是min(θ,90°−θ)/√2，**不是L1的½形式**。参考轴与已知边族均固定时为(90°−θ)/√2；只放开整体轴但锁定族为(90°−θ)/2。这些定义在独立代码中实算核对。

θ=45°→30°时I≈0.5174→0.3535、D=22.5°→15°，四边权重始终1/4，足以排除“必然由权重改变引起”的解释。完整Q的旧尾项3.192→4.580反升；当前13.437→6.700、工作20.906→14.075均下降。**这组完整Q包括Sb及完整几何测量，不能与原先只含I＋D的消融数值混写。**

### 4.3 真实普通数据中的对应情况与负结果

先在同图同参考的真实作答中寻找严格对应：作答与参考均四角、参考D<0.05°，IoU差>0.02，D反向差>1°，矩形转角误差又恶化>5°。共检查3069个同图配对，找到0个满足全部条件的配对。**不能据合成反例宣称真实作答普遍发生同样反转。**该负结果也不证明真实数据没有其他形式的结构问题。

再做固定上下x、topy、配对和环序的底点路径诊断。仅438份具有同点数且唯一周期经度对应；136份不强猜对应。每份7个状态，共3066，出现330个I下降而D下降窗口，涉及164份原作答。其起点仍含真实x/topy误差，范围语义也不因经度配对自动相同，因此不赋予人类单调性标签。

其中R00637是具体机制例：底点路径t=0.75→1.0（1.0是原作答）时，I约0.8043→0.7581，D约11.52°→9.95°，矩形转角误差38.51°→43.35°；工作Q39.949→39.527仍下降。它支持在真实几何附近确实存在族/转角的测量问题，但不是两份真人作答的优劣裁决。

更广的330窗口中，当前式完整Q上升108次、工作式110次，均涉及65份原作答。**新式没有在这个混合诊断上全面胜过当前式。**部分其他项可能改善，不能将这些窗口一律叫质量逆序；同样不能只挑已知控制通过率证明成功。[真实派生路径](results/real_bottom_trajectories.json)、[严格配对搜索](results/actual_direction_counterpatterns.json)。

### 4.4 为什么暂不新增统一结构项

尝试了两种参考方向诊断，未直接采用。按双向最近底边匹配朝向，574份都可算，但同一个矩形仅均匀缩小到0.6倍，D仍0°、最近边朝向差却约40.17°；最近几何点并不总是对应同一面墙。固定原强度直接替代D还使P01反向。这是具体实现的负结果，不证明所有参考朝向方法不可能成功。

同方位首交边朝向差对上述纯缩放为0°，但49/574份因多重射线交点而无法作为完整环的替代；不能为了算得出就扔掉被遮挡的已声明边。这一替代也未保留P01。它们保留为诊断，不加入主Q。

还验证了共线细分、循环起点、反向环、接缝与凹形自比较，不为所有真实点统一处罚偏离90°。锁定参考族只有在边语义对应可信时才可使用；本轮没有以一个自动对应器悄悄获得这种认证。

有两个未解决的实质边界必须保留。第一，正交窄分支遗漏可以D=0，宽0.1h、深3h的合成分支遗漏仍获工作Q92.705（I=0.9756）；本轮没有把它定为人工“严重”，但现式显然不是拓扑完整性的充分度量。第二，D是自身规整性，不是纯参考距离：合法非正交同形例在域外诊断中I=1仍只得52.265，不能用于这种目标；普通70份参考中最大自身D约1.2073°，该参考自比的混合Q约94.686，不是100。这一继承性质已明示，不能把Q称为满足自同一性或适用于任意合法几何的距离。

## 5. J04、J01与二维信息

J04原图、固定几何叠加、同尺度三维已实际打开查看。最大底点偏移位于第一对底点，相对明确经度对齐参考的bottom-y偏差约21.133像素；它占四个bottom-y平方误差的{100*ms['J04_largest_bottom_y_squared_error_share']:.2f}%。其余x/topy并非完全无误，不能说“只有一个点错误，其他绝对正确”。

在不写回输入的诊断副本中，仅恢复这个bottom-y：D19.424°→2.206°、I0.6802→0.9284；工作Q33.534→78.134。逐一恢复另外三处bottom-y没有相同改善。这个干预支持“单个底点经三维投影放大”的主导机制；不证明作者心理原因，也没有以修后作答参加校准。[逐点干预](results/J04_interventions.json)。

原J04在旧尾项为7.254、当前版27.078、本轮33.534。当前至工作版只改变组合，方向损失仍约1.3644，是主要结构扣分来源；高度损失约0.04405，实际高度降分0.483→0.503。由此，本轮没有用高度控制伪装成底点修正，也没有设Q≥10或任何该题目标分。

现有Sb约1.819°，方位底边RMS约7.646像素，最大差约22.774像素；这说明原指标保留了部分二维接近信息，但均值压缩了集中度。新增报告最大值和最差10%边界诊断，仍不入主分。边界采样不要求点数相等，周期射线避免接缝直线匹配；多交点时标记歧义、不以首交可见边冒充完整环。没有用很多正确点平均掉异常后再给奖励分。

J01 A的I较小、整体高度偏差较大，而自身D较低；新式从28.715/29.505变为36.347/34.780，表明组合交互足以改变绝对分数及轻微排序，**不表示建立了A优于B的人评事实，也不能宣布35分已符合人的绝对尺度**。原照片和三维都已看过，当前图像证据不足以把人类“分数似乎偏低”转成一个具体评分锚点。

[图证：J04原图叠加](figures/J04_overlay.png)、[J04同尺度三维](figures/J04_3d.png)、[J01叠加](figures/J01_overlay.png)、[J01三维](figures/J01_3d.png)。原图不是生成图，几何未编辑；单位h为相机高度，非真实米。

## 6. 整体高度与局部不平的取舍

本轮没有再把global_scale从1调到0.8：**输入现工作版已经是0.8**。本轮保留0.8和0.25，分别报告高度损失、固定工作版非高度背景下的降分、实际完整式降分。

{heighttable}

T20历史旧尾项g=1高度实际降分3.5256；当前hill08为5.3230，工作式为5.0626。工作式仍比那次被评论的3.5256稍重，但比现工作版少约0.2604，属于组合造成的边际变化，不是高度系数被调弱。固定工作版非高度背景，把g从1改为0.8时，其降分3.3541→5.0626；这是可以归因于高度强度的对照。

P04局部例H损失0.09737高于T20整体例0.08708；在共同完美非高度背景下对应扣分也更高。两例真实底面/方向不同，实际高度边际扣分可以反向，不能拿不同分母下的降分作为P04分项意见的判错标准。原“如果我没看错”的不确定性保留。

L01工作版B−A约4.011，当前约4.127；全域局部加重到0.20会扩大为约4.954，没有足够新证据支持这种额外拉开。局部0.15、整体0.5等更强候选也实际比较，不能仅凭24项派生弱等级都无逆序就采纳。保留中等强度，既不消除局部项，也不恢复旧顶部投影重罚。

110高度控制全部重新测量并评分；整体升降、两侧倾斜、孤立角点与混合误差分开保存。相同几何底面下，Hm测全局偏移，Hc测中心化起伏；参数使相同相对分量大小时局部项比全局项更强，但**不将“同相对RMS”“同峰值”“同像素误差”宣称为同主观严重度**，更不保证任何幅度下结构永远优先。[高度归因JSON](results/height_attribution.json)、[CSV](results/height_attribution.csv)。

## 7. 普通阶段：已知收益和不能隐藏的代价

{layerstable}

574普通覆盖70图、19建筑；207份明确普通来自19图，367份沿用条件许可来自51图，后者没有被升级为逐图认证正常。普通分数变化按图片等权均值+2.547、按建筑等权+2.612，不能仅按574行把大建筑权重放大。82份涨≥5，0份涨≥10；这些只是变化切片，不是新等级阈值。最大的变化集中于wc2-60等低重合/混合错误图，不是处处同幅提升。[图/建筑表](results/FINAL_by_image_building.csv)。

同图同参考的普通记录中有40个两两排序与当前式不同；与3D IoU有916个两两符号不同。它们是相关的作答对而非独立样本，未取得人评的配对不计为胜负。当前和工作式均满足11弱等级派生出的24个轻微/明显比较；工作版严重9×轻微3的27项比较也未逆序。按证据建筑留一只是开发敏感性，没有重新拟合/重新盲测，也没有重新切原留出。

具体重点案例完整对照：

{casetable}

P01边际18.980→16.562，仍保留明确偏好但减少规整性优势；C02差距由约0.893变为2.843，仍无权说这就是“足够接近”。J01轻微排序翻转不当成功标签；C01/C03/C04、P04/T20/L01均为来源受限旁证，没有混进574主池。J02撤回的偏好不优化，J03参考不确定也未被补造成质量标签。

本轮可支持的是：一个机制清楚的工作组合，通过了现有算术/边界与有限开发约束，并给出了合理的中等扣分响应。不能支持的是：总体准确率提升若干个百分点、真实严重度等距、所有人员排名更准、泛化到未曝光建筑已经验证。

## 8. 九份严重例外：逐份、逐图而非混为普通

{sevtable}

九份涉及7图/7建筑，rPc-09占三份；角点对数等混合错误保留，没有伪装成9次纯方向实验。其工作Q约8.056—20.343，高于当前约3.308—12.339；“仍低于已标轻微例”是有限约束通过，不是证明绝对严重界限正确。当前人员排除状态全部保留，不能把校准例外变成独立融合投票资格。W019/W026缺可信配对者没有被猜配对恢复。

[严重逐份分项](results/FINAL_severe.csv)、[按图汇总](results/FINAL_by_image_building.csv)。

## 9. 门洞阶段：完成条件比较，追加参数变化为零

普通冻结文件生成后才执行门洞重建与新候选评分；冻结依赖哈希全部再次核对。125份条件完整评分均重新算通，92份继续NA并保留具体限制。对第一阶段参数做了cap1.25/1.75、Sb尺度5/6.5、global0.75/0.85、local0.225/0.275的单参数邻近比较，加现工作版和普通冻结版共10项。[门洞候选](configs/doorway_candidates.json)、[普通/严重/门洞联合回归](results/doorway_fine_normal_regression.csv)。

逐图用途如下；“条件可算”绝不是新的语义或正式资格认证。

{doortable}

12个可算图的原图已通过3张原图联系表实际打开，另外Q01/Q02原图叠加与三维已查看；这是范围与结构上下文核查，不冒称对全部125份逐角点视觉认证。5个全部暂缓图没有为了取得分数而解除参考/人员/留出限制。原图与依据表保留在 `frozen_input/photos/` 和 `data/supplement.json`。

Q01对小房间与较大范围均已认可，精确小房间参考没有随回执提供。当前907对象仅有该图大范围原GT；另外实际读取了一个历史联合包的三个具体路由/参考登记JSON，其中没有该图ID，不是只搜索后凭空声称没有资料。[逐字节搜索记录与原件](evidence/Q01_reference_search.json)。不能外推“整个Library或GitHub绝对不存在小参考”。

因此125条件数值均保留，但Q01所在图8份不用于参数取舍；其余117份、11图、6建筑作条件回归。R03332的 `conditional_large_ref_Q` 可复现，`same_target_worker_quality_Q` 明确为空；不能用它的大参考低分给合法小范围定低质量，也没有借大范围顶面或用作答自身当GT。

Q02 A的D≈8.838°、Hc≈0.08384；B的D≈4.750°、Hc≈0.02786。B自身更规整的补充意见与这些分项相容；A的I和3D IoU更高，正好说明不能把分项相容偷换成完整质量真值。工作Q约34.031/36.932，仅条件结果。Q03 B在中间角的局部观察保留，但它的整体范围和高度有不同代价；完整Q36.178/33.395没有被要求强行翻转。用户不能肉眼分高度不是精确平局，也不是测量必须相等。

没有新的合法完整排序支持某个邻近参数胜出，因此最终沿用普通冻结配置，**门洞后的参数修改={{}}，574普通与9严重相对普通冻结Q最大差为0**。这不是没跑门洞，也不叫“门洞独立验证通过”；是完成条件比较后决定不额外调整。

门洞仍保留高分例R02113：当前约95.985、工作约96.023。既没有为了符合“门洞低分”压它，也没有把门洞整体分布较低当成评分正确的证据。117回归层均值变化约+5.798大于普通+2.404，主要是相同代数交互在低I/大损失区域更强，不能解释为门洞质量本身提高。

## 10. 同参考3D IoU：有优势，也有明确失败

所有主对照使用相同处理后点、同参考、同计算资格，3D IoU并非模型重新预测结果。实际调用冻结 `traditional_metrics.py`，其HoHoNet口径是底面交并面积加顶点均高的棱柱代理：

```text
IoU3D = A_intersection·min(hA,hG)
        / [A_A·hA + A_G·hG − A_intersection·min(hA,hG)]
```

hA/hG为顶点平均墙高，不是本评分Hm使用的周长均高；有局部起伏时它也不是精确非平顶实体体积IoU。完整对照列按该明确定义命名，不能把不同3D指标混成一个“真3D”。

3D IoU的P01偏好边际为{bench['P01_margin']:.4f}，与当前明确人评相反；11弱等级的24项派生比较有{len(bench['weak_grade_inversions'])}项逆序。新式在这些有限开发约束上更符合意见，但这些数量少且反复曝光，不支持全面优于3D IoU。

独立的固定底面交替高低控制还显示：顶点均高不变时3D IoU=1，即使Hc约0.1155、新式Q约82.4。这证明此3D IoU对某些局部不平有盲区；不等于真实样本中的每种局部起伏都更严重。另一方面，它测体积重合很直接、没有本轮D族解释，也不需要给主观规整性选强度；应长期旁列，尤其检查方法对范围与高度的取舍。[IoU证据对照](results/iou3d_evidence_comparison.json)。

外部出处仅用于该基准背景，不作为本轮公式得到文献认证：Cheng Sun, Min Sun, Hwann-Tzong Chen (2021). **HoHoNet: 360 Indoor Holistic Understanding With Latent Horizontal Features.** *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition*, 2573–2582。官方页面：https://openaccess.thecvf.com/content/CVPR2021/html/Sun_HoHoNet_360_Indoor_Holistic_Understanding_With_Latent_Horizontal_Features_CVPR_2021_paper.html 。官方PDF：https://openaccess.thecvf.com/content/CVPR2021/papers/Sun_HoHoNet_360_Indoor_Holistic_Understanding_With_Latent_Horizontal_Features_CVPR_2021_paper.pdf 。本轮没有以论文图表支持额外人类尺度结论；可复算的对照实现以包内冻结源码为准。

## 11. 复现、交付结构与失败记录

建议在独立环境安装后运行：

```bash
python -m pip install -r requirements.txt
python reproduce.py --output ../quality_reproduced
python src/score_cli.py --record R03274 --rebuild
python src/score_cli.py --record R03332
python -m pytest -q tests
```

`reproduce.py`拒绝覆盖已存在目录；默认从点重建全部718配对，重跑控制和比较，依次冻结普通版/门洞比较/普通回归。`--figures`另生成图示。单例不加`--rebuild`时明确标为存储metrics重评分。复现不需要fresh clone、GitHub、Library或被忽略的source_package；必要源引擎、原图、回执和历史参考搜索原件均随包。

`requirements.txt`给出依赖，`requirements-lock.txt`记录本机实测版本。实际环境Python3.13.5、NumPy2.3.5、SciPy1.17.0、Shapely2.1.2。未声称所有平台和软件版本都已测试。

关键文件：`FINAL_ordinary.csv`574行、`FINAL_severe.csv`9行、`FINAL_doorway.csv`217行（92行NA）、`FINAL_historical_only.csv`10行；逐例各候选分项见`*_scores_long.csv`；按图/建筑见`FINAL_by_image_building.csv`；来源/参考见`input_source_reference_manifest.csv`与`effective_use_ledger.json`。三维静态图有网格、轴、刻度与统一h尺度；继承的`frozen_input/REVIEW.html`可离线旋转，但本轮未完成浏览器交互测试，不把文件存在写成页面已视觉验收。

执行中确有故障但已恢复：ZIP语义检索无结果后改为读取原字节；一个辅助查看脚本误把控制列表当字典，按实际schema修正；机制大批命令遭20/60秒工具超时，另一次流式session不受支持，随后固定线程数完整运行并保存日志；首次图示写入发生PermissionError，修正工作图目录权限后重跑全部图示。一个中间几何差报告字典重名只能保留最后参考数组，已修正逐对象键，并用独立907对象逐数组审计补闭环，902对象全部核对，未据不完整摘要声称全量通过。没有未解决的主数值执行错误。外部CVF正文直开403、官方raw代码缓存未命中不影响离线计算，论文元数据由官方搜索结果核实；未把这些读取失败写成文献不存在。

## 12. 后续论文可以使用什么，仍不能声称什么

可用：固定参考及明确处理链下的连续研究Q、分项损失、同参考3D IoU、原始x诊断及限制账本。人员分析应在合法参考/可比较条件中汇总；融合输出可用同一冻结评价函数，但必须独立满足几何及参考条件。缺顶面仅底面，不能靠另一参考补完整Q。全部已曝光反馈只作开发；原留出不重切、不回写、不宣称盲测。

不可声称：D已经测全墙间结构；窄分支缺失被充分处罚；J01绝对量表已校准；某个分数就是普遍“轻微/明显/严重”切点；Q是正确概率或可以直接当人员投票权；同分差表示同严重度；适用于合法非正交/多底面/有孔洞目标；在未来人群、未来建筑或融合结果上已验证提升。研究工作版不能自动变成正式人员资格算法。

**本轮工作版不需要重复审核Q02/Q03，也不以新增人审才能启动或交付。**唯一明确待办是：当要量化Q01/R03332这个合法小房间时，需要独立的精确小范围底面及其自身可信顶界（或明确只评底面）。这改变它能否进入同目标质量评价，不改变本轮已经完成的普通校准和117份条件门洞回归。若既有小参考随后可定位，应先核对身份/版本与来源，不按Q最高选择。

最终推荐仍是 **WQ-LS08-20261014：仅去除范围亏损与其他损失的乘法交互；Sb、D、整体高度0.8、局部高度0.25保留；门洞追加参数变化为零。**它提供一个可以立即复算和锁定使用的中等复杂度工作指标，同时把结构盲区、目标范围不确定和绝对量表证据不足留在明确的限制字段里。
'''
    # Keep numeric precision readable in the narrative.
    text=text.replace(f"{100*ms['J04_largest_bottom_y_squared_error_share']:.2f}%",f"{100*ms['J04_largest_bottom_y_squared_error_share']:.2f}%")
    (ROOT/'REPORT_ZH.md').write_text(text,encoding='utf-8')
    try:
        import mistune
        body=mistune.create_markdown(escape=True, plugins=['table'])(text)
    except ImportError:
        # No extra dependency required to read the complete report.
        body='<pre style="white-space:pre-wrap;font:16px/1.7 sans-serif">'+html.escape(text)+'</pre>'
    (ROOT/'REPORT_ZH.html').write_text('<!doctype html><html lang="zh"><meta charset="utf-8"><title>WQ-LS08 质量校准</title><style>body{max-width:1100px;margin:40px auto;padding:0 24px;font:16px/1.75 system-ui,sans-serif}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #bbb;padding:7px;text-align:left}pre{overflow:auto;padding:16px;background:#f6f6f6}h1,h2,h3{line-height:1.3;margin-top:1.5em}a{overflow-wrap:anywhere}</style>'+body+'</html>',encoding='utf-8')
    print('Chinese report',len(text),'characters written')
if __name__=='__main__':main()
