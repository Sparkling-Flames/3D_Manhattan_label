"""Build the Chinese reverse-route report directly from frozen result tables."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent

def table(d,columns,renames=None,digits=4):
    d=d[columns].copy()
    if renames:d=d.rename(columns=renames)
    def val(x):
        if pd.isna(x):return '缺失'
        if isinstance(x,(float,np.floating)):return f'{x:.{digits}f}'
        return str(x).replace('|',' / ')
    lines=['| '+' | '.join(d.columns)+' |','| '+' | '.join(['---']*len(d.columns))+' |']
    lines.extend('| '+' | '.join(val(x) for x in r)+' |' for r in d.itertuples(index=False,name=None))
    return '\n'.join(lines)

def main():
    pop=pd.read_csv(HERE/'partition_population_summary.csv');pop=pop[pop.layer.eq('ordinary_manual')]
    repl=pd.read_csv(HERE/'fusion_analysis/replacement_summary.csv');repl=repl[repl.threshold_deg.eq(9)&repl.metric.eq('abs_B8L2_change')]
    comp=pd.read_csv(HERE/'fusion_analysis/composition_summary.csv');comp=comp[comp.threshold_deg.eq(9)&comp.metric.eq('abs_B8L2_change')]
    forward=pd.read_csv(HERE/'forward_swaps/summary.csv');forward=forward[forward.label_metric.eq('B8L2')&forward.panel.eq('common_Q_T_all_three_difficulties')&forward.difficulty_panel.eq('all')&forward.family.eq('merged_difficulty_within_QT')&forward.outcome.eq('abs_B8L2_change')]
    control=pd.read_csv(HERE/'conditional_dtype/summary.csv');control=control[control.k.eq('all')&control.label.eq('fine_dtype_merged')&control.outcome.eq('abs_B8L2_change')]
    transfer=pd.read_csv(HERE/'transfer/pair_transfer_summary.csv');transfer=transfer[transfer.panel.eq('all')&transfer.threshold_deg.eq(9)]
    swap=pd.read_csv(HERE/'swap_transfer/summary.csv');swap=swap[swap.k.eq('all')&swap.outcome.eq('abs_B8L2_change')]
    prefix=pd.read_csv(HERE/'prefix_analysis/balanced_minus_largest_summary.csv');prefix=prefix[prefix.threshold_deg.eq(9)&prefix.k.isin([8,12,16,24])&prefix.metric.eq('B8L2')]
    cases=json.loads((HERE/'CASE_CATALOG.json').read_text())['cases']
    report=f'''# v2 反向标法簇与人员组队研究：实算报告

## 主判断

**目前最强的证据是：同图实际标法簇能够解释固定背景换人和部分固定人数构成变化；历史人员Q/T/难度画像对这些变化的事前预测较弱。** 这两个结论可以同时成立。局部簇支持“这张图上的机制诊断”，不能直接晋升为永久人员类型。

人员粗类仍适合描述交付质量和时间资源；难度细类可以保留为有限、可解释的候选，但本路线不足以认定同细类人员通常可完全互换。具体字段必须分开：本轮比较了 `Q2_B8L2`、`QT_B8L2`、`difficulty_type_B8L2`（原始三难度模式）和 `fine_dtype_merged_B8L2`（按支持量合并后的QT×难度细类）。旧 `fine_candidate` 的 hard_adaptation 不是同一对象，本报告没有把它混成上述细类。

同QT内跨合并难度细类的变化有部分增量；**控制粗Q二分内部仍存在的连续β幅度后，增量大幅减弱且区间跨0。** 不能把重新找回的连续Q差异全部归功于“困难图专长”。实际当图簇解释换人影响的增量则更大，并在同一具体QT类内仍可观察到。所有这些均未通过看融合结果反调分类阈值。

## 1. 实际范围及证据边界

仓库固定在 main 提交 `82c6164b0d4630de5316199c92aa405930973168`。读取逐份审计证据及融合代理快照，逐份核对质量资格、对象ID、人员、冻结点和绑定参考。229个质量池共7302份，主层普通Manual为5719份、177图、22栋；其余52池独立分层，未将门洞/半自动/特殊条件并入主效应。

不同人员来源并未构成独立“模拟人”。普通Manual图上支持k≥8/12/16/24分别为175/171/170/164图；没有把缺资格记录补零，也没有假设每图35人。记录级分母、团队尝试、实际不同团队对、图和建筑分别保存。

- 全质量池：121515个实际作答对；普通Manual：92438对，其中71378对点对数相同，可计算整份绑定环距离。
- 逐成员归属：29208行=7302份×2阈值×2方法；点数不同的距离为空且分开聚类。
- 主固定背景实验：普通Manual175图、22栋，270370个实际不同单人替换团队对。两个阈值的540740行是同一批实际替换的两套解释标签，不是翻倍的真人证据。
- 局部簇oracle请求：37932个，含15056个同k构成团队和22876个真实前缀端点；708条完整入场路径。所有成员及种子在 `ORACLE_REQUESTS.json.gz`。
- 读到并重放已审计数据，不等于独立复现原始采集、所有人工审核和本地历史源生成过程。本路线没有新作视觉裁定。

## 2. 距离、优化与9°/12°的限制

主距离直接复用main的 `paired_split_research.study.angular` 与 `cyclic`：每个点对保持上下绑定，保持声明环序，只允许共同循环位移，不允许主分析整环反向，更不允许上下点各自匹配。对每一共同位移计算所有顶/底端点球面角距离的最大值，再取最小位移结果。图像坐标为1024×512，沿用原函数的竖向半像素中心约定。

全局亲近度优化沿用 `build_cluster_review_20261018.affinity_partition` 的目标：同簇两两距离≤τ；最大化保留的亲近权重 `(1-d/τ)^2` 总和。实现仅做等价的许可图连通分解：已完全连通分量直接达到非负权重上界，其余用相同二元传递性MILP。每分量60秒上限、一HiGHS线程、gap目标0。不是把融合过程充当聚类。

229池共2390个分量/阈值实例：2057个可直接证明上界，333个MILP均返回最优、gap0，未发生回退。48个真实小子池与main函数及41609个可行分区穷举目标比较，最大浮点差约3.55×10⁻¹⁵；530个源距离/循环检查差为0。对116个较小非完全分量检查了同目标另一最优解，未发现；其余217个较大分量没有证明最优解唯一，不能写“所有归属唯一稳定”。

普通Manual分簇实况：

{table(pop,['method','threshold_deg','clusters','singletons','image_equal_largest_share','image_equal_cluster_count'],{'method':'方法','threshold_deg':'阈值°','clusters':'整簇数','singletons':'单例簇数','image_equal_largest_share':'图等权最大簇占比','image_equal_cluster_count':'图等权簇数'})}

全局法在自己的亲近度目标上更优，但9°时单例542个，反而多于完整链接468个。算法目标不能代替语义合理性。9°全局法和完整链接的共同归属在13830/92438对、125/177图上不同；12°为6251对、50图。9→12°全局法有10312对新合并，同时有222对在39图反而被拆开；这是非层次全局优化的真实结果，不能把它画成简单合并树或把全部归属变化叫成人员类型改变。

9月归档代码的主度量是固定声明点对顺序的ERP像素距离，循环匹配是敏感性；像素距离还做8位舍入。其25.6像素视觉验证不能转成当前9°球面/绑定循环的已验证结论。本轮维持9°/12°两个固定观察窗，没有逐图择优。

### 底部y、三维和环方向

保持上下绑定而允许整环反向的独立敏感性仅影响普通Manual4图；9°共同归属变300对，12°变505对。声明过环序仍可能存在方向表示问题，因此保留主定义与整环反向对照，不擅自改环。

角度近不保证投影范围近：B6ByNegPMKs-18的W108/W126端点距离8.267°，底面IoU仅0.07146，平均高度棱柱IoU0.04146。底面近也不等于高度近：uNb9QFRL6hY-65的W037/W128底面IoU0.95090，但棱柱IoU0.76365。完整候选分母及实际对象ID已保存，前例出自62496个≤9°真实作答对，后例来自6202个底面IoU≥0.95对。

仅作诊断的底部y扰动显示：普通Manual距地平线≥5°的27888个有效点对，+1像素的投影半径相对变化中位数约1.51%；距地平线<5°的83点对（11图、33人）中位数约7.64%。没有修改源坐标，也没有据此将3D权重混入主距离。棱柱IoU采用平均高度且相机高度为规范单位，并非真实完整室内体积或实测米制误差。

## 3. 固定背景：簇内与跨簇单人替换

事前冻结的实用联合容忍为：两队均完整、相同输出节点数、|ΔB8|≤2、底面1-IoU≤0.05、绑定循环端点变化≤3°。另保留1/5分、0.02/0.10、2°/5°敏感性。共享连接及细节保留有更严的独立字段；联合容忍成立仍不是语义等价或质量正确。

主匹配固定同图、同k、同背景、同参考、同融合，并要求换入两人点对数相同。先在每个可比较背景/点数层中算跨簇减簇内，再聚合到图和建筑，区间为建筑bootstrap3000次。没有将失败队从尝试分母移除。

9°跨簇减簇内的绝对B8变化：

{table(repl,['k','images','measurable_images','buildings','building_equal_difference','low','high','left_attempts','right_attempts'],{'images':'有匹配图','measurable_images':'质量可比图','buildings':'建筑','building_equal_difference':'跨簇−簇内 |ΔB8|','low':'区间下限','high':'区间上限','left_attempts':'簇内尝试','right_attempts':'跨簇尝试'})}

对应联合稳定率差在k8/12/16/24为−0.128/−0.106/−0.064/−0.061；k24底面差异的建筑均值略负且区间较宽，不能声称所有人数和指标都单向。各k的匹配图不同，`*_sensitivity_panels.csv` 另给共同可匹配图集合及三难度，避免把覆盖变化当成纯人数效应。

即使固定为同一个具体的外楼QT类，9°跨簇差异仍存在，例如k12的|ΔB8|增加0.573，区间[0.290,0.871]，联合稳定率下降约0.100。说明人员全局QT类仍没有捕获该图位置、局部结构及投票边界信息；这不是同QT类“无用”的证明，而是其用途边界。

分布也否定绝对可互换：9°k12簇内替换47129次，有分数46855次，|ΔB8|中位数0.542、95分位5.480；跨簇同点数16822次，有分数16168次，中位数1.168、95分位9.351。簇内联合稳定率按尝试为81.6%，按建筑均权为77.7%；跨簇为60.1%和66.9%。这是有尾部、有人数/场景条件的倾向，不能由p值或均值推出“换人无影响”。

## 4. 固定人数与构成比例

成员抽样完全不看Q、时间、GT分数或融合结果：固定大簇优先、簇均衡、能支持时单一大簇，每个构成向量取4个具体成员变体，种子2026101909及每子实验哈希种子已保存。

全部比较72,027行；356个同集合碰撞保留明细，但不冒充更换具体人的实验。为了区分比例与换人幅度，主对照同时固定k、换出换入人数turnover以及成员点数直方图，再比较“构成相同但成员不同”和“构成不同”。严格条件后只有79图/18栋有任一9°匹配机会，而不是177图全体。

9°改变构成减保持构成的|ΔB8|变化：

{table(comp,['k','images','measurable_images','buildings','building_equal_difference','low','high','left_attempts','right_attempts'],{'images':'有匹配图','measurable_images':'质量可比图','buildings':'建筑','building_equal_difference':'变构成−同构成 |ΔB8|','low':'区间下限','high':'区间上限','left_attempts':'同构成尝试','right_attempts':'变构成尝试'})}

地面差的建筑均值依次为0.01093/0.00533/0.00448/0.00174；k24质量差反向且区间跨0，保留为反例。12°的严格匹配只剩38/37/33/34图和12/12/11/11栋，不能当成与9°同覆盖的优劣试验。

房间权重是实际限制：只用仓库原始声明且 `physical_same=支持` 的156组，不按同楼或传递补房间，不造未关联图的单例房间。9°k12的组成质量差在39个有分数组/16栋变为0.513，区间[−0.087,1.092]；底面差0.00279的区间也跨0。相比单人固定背景差异，这项构成结论的支持更薄、对权重更敏感。组数不是独立样本量，区间仍按建筑重采样。

## 5. 真实入场过程

708条oracle全路径覆盖177图，逐个实际前缀重新调用冻结融合；22,168个oracle转移与22,168个随机路径转移均保存。包含相同转移在不同路径重复出现，唯一实际前后团队对43963，不能把重复路径当独立真人。最终成员集合相同得到同一融合是集合型算法的性质，不能称“历史顺序依赖”；各中途前缀内容不同才是此处检验的对象。

9°簇均衡入场减大簇优先入场，在相同k的B8差：

{table(prefix,['k','attempted_images','measurable_images','difference','low','high'],{'attempted_images':'尝试图','measurable_images':'有两队质量图','difference':'均衡−大簇优先B8','low':'区间下限','high':'区间上限'})}

冻结多数融合下，均衡入场在早期可能分散投票、损失连接，不能把多样性自动当作改进。k≥4的9°大簇优先路径完整→不完整9/5011步，均衡38/5011步；共享未改身份因阈值/票数结构掉出分别62和217步。更多成员既可能修正，也可能暂时减少输出或损失质量。人数低于4、两人延后等原融合规则独立标明。

来源时间按已有真实记录求和，仅在所有成员来源时间齐全时有完整总成本；同目标时间单独记录。例如k8两种路径的来源成本只有107/175图可比，不能将不全和当真实总成本，更不能用来源时间补同目标时间。不同旧新时间来源的解释由人员画像主报告给出。

## 6. 正向人员类如何解释这些现象

标签均在目标建筑以外学习。Q2有支持才分类，QT还需来源时间支持，三难度型要求简单/中等/困难各至少6个任务和3栋。包含`unknown`的标签不作为能力类别；`not_split`是已知难度但父QT缺足够可分子类时的合并结果，不是失败。

固定具体QT父类后，跨 `fine_dtype_merged_B8L2` 与同细类替换的质量差（两人三难度均有支持的共同面板）：

{table(forward,['k','images','measurable_images','buildings','difference','low','high'],{'images':'有匹配图','measurable_images':'质量可比图','buildings':'建筑','difference':'跨细类−同细类 |ΔB8|','low':'区间下限','high':'区间上限'})}

这些数值小于事前单次变化2分容忍，且k16区间宽，不能把少量均值差包装为人人可替代。Q2内再分来源快慢对该换人变化指标的增量通常弱，但时间维度仍有资源成本意义；本报告不以换人预测一个指标否定效率。

为避免把粗Q二分残余幅度误称为难度效应，另作明确的解释性诊断：在同QT、同背景、同点数层内去均值，固定建筑→图→k→层→人员对权重，对跨难度细类同时控制换入双方连续β均值和绝对差，再并列加来源T均值和绝对差；没有改类或阈值。全k合并后的 `fine_dtype_merged` 系数：

{table(control,['adjustment','images','buildings','pairs','cross_dtype_coefficient','low','high'],{'adjustment':'连续控制','images':'图','buildings':'建筑','pairs':'有分数且有类内外对照对数','cross_dtype_coefficient':'跨细类系数','low':'区间下限','high':'区间上限'})}

因此同细类更稳的部分表象由连续Q残余差异解释；加入连续Q/T后剩余增量尚不足以独立确认。原始 `difficulty_type` 与合并型也并非同结果：原始模式的质量变化证据更弱，而调整后的联合稳定率有反向关联，表明简单的一条“跨细类必更不稳定”叙事不成立。详见完整k/难度、B8/D10标签重分和未知分母。

## 7. 楼外迁移：可事前预测什么

预测共簇/最大簇成员时，测试人员画像排除目标楼；训练样本的人员画像同时排除外层目标楼和该训练图本身所属楼，使用27720行双排除特征，避免训练端读取自身答卷Q。固定Logistic/Ridge与列集，无结果驱动的阈值搜索。训练权重按建筑和图归一，数值缺失采用训练内编码并保留缺失指示；原始表的未知不被改写。

9°预测实际共簇的楼外Brier（177图、22栋、92438实际对）：

{table(transfer,['model','building_equal_brier','mean_image_auc'],{'model':'特征','building_equal_brier':'建筑均权Brier','mean_image_auc':'图内AUC的建筑均值'})}

QTD较QT仅减0.000268，区间[−0.000872,0.000301]；12°仅减0.000199，区间亦跨0。历史Q能提供有限信息；时间/难度细化对这一个目标的增量薄，行为变量也没有稳定增加最大簇预测的能力。不能把两路相同Q来源重复加权成独立证据。

初始“人员对历史共簇率”没有条件化难度，表现明显较差。为审查这个坏基线而做的**后续诊断**，仅把历史限定同一冻结难度，收缩强度保持5；9°Brier变0.15097，对难度先验差−0.00887、区间[−0.01531,−0.00237]；12°为0.10932，差−0.00998、区间[−0.01543,−0.00449]。无序人员对规范化不改变结果，主要问题是不同难度的基准簇率混合。这提示“特定难度的历史相容关系”比独立人员Q标签更有前景，但它属于看到坏基线后的诊断，未再次宣称新盲测，也没有自动变成新的已验证选人策略。

进一步预测真实固定背景换人造成的|ΔB8|，普通Manual175图、22栋、270370个团队对，质量缺失不补值：

{table(swap,['model','MSE','RMSE','MAE'],{'model':'特征','MSE':'楼外MSE','RMSE':'楼外RMSE','MAE':'楼外MAE'})}

Q/QT/QTD历史特征几乎没有超过已知难度+k的基线，QTD−QT的MSE差0.0086、区间跨0。实际当图9°簇关系与背景簇比例的oracle则将MSE从27.5868降到26.5561，差−1.0307，区间[−1.6787,−0.4573]；联合几何稳定的Brier从0.17390降到0.16185，20/22栋改善。知道目标答案后的解释能力，不能冒充事前人员画像的选人成果；这正是两条路线应分开回答的结果。

## 8. 版本和计量不能合成“升级提升”

固定v1普通Manual1258份、103图、20栋，用当前冻结坐标/相同方法重算，对本地历史归属在206个图×阈值状态、19980对中共同归属变化为0；历史文件作为待核查线索附来源，不声称是此前Pro正文缺失的完整返回ZIP。

新37份旧记录取得原人数门资格后，v2旧普通Manual为1295份、129图、21栋，仅加这37份不改变v1原对的共簇判断。加入新人到既有图的人群池，旧坐标/Q不变，仍会使9°342/9990旧对、12°387/9990旧对换共同归属，分别26图和18图；这是全局分区依赖观测人员池，不是旧人能力变化。

固定人员只将B8换D10的计量变化，与用D10重新学习人员标签并重分组的变化在本目录明细中分列。距离聚类本身从未使用B8/D10，因此不因分数高低重定簇。完整个人Q/T效率、严重排除、Semi净改善/残留与scope裁定机会由主报告对应证据表给出；本路线里的行为率仅是独立解释变量，不是综合质量扣分。

## 9. 少量需要人的判断和采用建议

`CASE_CATALOG.json`提供10个整簇/团队对照，含成员开关所需准确身份和请求ID。主自动案例包括同簇而大变的yqstnuAEVhm-31、跨簇而大变的UwV83HsGsw3-09、跨簇而几乎不变的x8F5xyUWy9e-03，以及输出稳定却B8约5.7的反例。界面应同时看ERP、BEV、规范三维和原参考，不能只看局部端点或只看底面。

节点差候选UwV83HsGsw3-22的4人簇平均相对β+3.84，但人员β分别−0.408、0.310、14.987、0.470；不能标题化成“4个高Q人员共同漏标”。该簇4点、参考6点，当图均B8约40.62，需判断真实结构遗漏还是参考分点/范围差异，当前只是代理。

本轮可采用：冻结9°/12°局部簇作为解释和复核工具；Q/T画像及有限难度细类保留支持/边界标签；用建筑外、固定背景、共同k图、原声明组权重评价组队。

继续探索：同难度人员对历史相容关系、带支持量的困难图细类、目标图实际簇结构如何决定多数融合过程。它们有具体信号，但不应被赋予永久人群或普适可互换的意义。

本轮不应采用：将来源相同的多个Q重复加权；把速度/Semi/scope/严重排除压进通用质量总分；将当图簇当事前人员类；自动认定全局亲近度比完整链接更符合语义；仅凭稳定或不显著就宣布互换无影响；把重复组合、同房猜测或缺失时间作为额外真人证据。

## 10. 运行证据、复现与未验证项

入口见 `README_ZH.md`、各注册JSON与代码。所有核心几何/评分均继承冻结输入，原图的可用性不决定能否重算几何。最初派生gzip交错写入、三份预测gzip截断、布尔相减及全k汇总权重问题均在交付前检查中发现并修复；根因已知与未知分别记于 `REPLAY_RECOVERY.json`，保留原日志，不把异常隐藏为顺利运行。最终跨进程完整gzip CRC、行数、修复预测与原内存汇总一致性见 `FINAL_VALIDATION.json`。

未完成的事项明确保留：没有重做全部采集导出或人工审核；没有新的全体视觉gold遗漏裁定；没有以反向发现重新调人员类再宣称验证；没有把全部大MILP的最优解唯一性都证明；没有在这批探索之后获得新的独立建筑盲测。使用现有v2资料已经完成以上实算，这些限制不应被当成要求新采集先行的理由。
'''
    (HERE/'REPORT_ZH.md').write_text(report,encoding='utf-8')
    print(json.dumps(dict(report='REPORT_ZH.md',characters=len(report),case_count=len(cases)),ensure_ascii=False))

if __name__=='__main__':main()
