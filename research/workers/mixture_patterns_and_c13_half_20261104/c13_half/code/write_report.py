"""Write the task report and conclusion ledger from the saved statistics."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import pandas as pd
from design import ROOT,OUT,COMMIT,csv,write_json,sha

def table(df,cols,names=None):
    names=names or cols
    lines=['| '+' | '.join(names)+' |','| '+' | '.join(['---']*len(cols))+' |']
    for r in df.to_dict('records'):
        vals=[]
        for c in cols:
            x=r[c]
            if isinstance(x,float):x='—' if pd.isna(x) else f'{x:+.3f}'
            vals.append(str(x))
        lines.append('| '+' | '.join(vals)+' |')
    return '\n'.join(lines)

def main():
    s=pd.read_csv(OUT/'analysis/SUMMARY.csv');sup=pd.read_csv(OUT/'analysis/SUPPORT.csv')
    s=s[((s.study=='main_8_4')&(s.support=='ABC_valid'))|((s.study=='paired_6_3')&(s.support=='all_four_valid'))]
    def cell(study,direction,metric,stratum_type='all',stratum='all'):
        return s[(s.study==study)&(s.direction==direction)&(s.metric==metric)&(s.stratum_type==stratum_type)&(s.stratum==stratum)].iloc[0]
    comparisons=[]
    for study,direction in [('main_8_4','C1_to_C3'),('main_8_4','C3_to_C1'),('paired_6_3','C1_to_C3'),('paired_6_3','C3_to_C1')]:
        z=cell(study,direction,'Q_GS');q=cell(study,direction,'Q_class_shift');w=cell(study,direction,'Q_W');cross=cell(study,direction,'Q_cross')
        comparisons.append(dict(条件=('8人换4人' if study=='main_8_4' else '6人换3人，共同四端点'),方向=direction.replace('_to_','→'),支持=f'{int(z.images)}图/{int(z.buildings)}楼',
                                W=w.image_equal_mean,跨类变化=cross.image_equal_mean,GS=z.image_equal_mean,
                                GS区间=f'[{z.cluster_bootstrap_low:+.3f}, {z.cluster_bootstrap_high:+.3f}]',质量位移=q.image_equal_mean,
                                质量位移区间=f'[{q.cluster_bootstrap_low:+.3f}, {q.cluster_bootstrap_high:+.3f}]',质量位移为正图=f'{int(q.positive_images)}/{int(q.images)}'))
    main_table=table(pd.DataFrame(comparisons),['条件','方向','支持','W','跨类变化','GS','GS区间','质量位移','质量位移区间','质量位移为正图'])
    diff=[]
    for study in ['main_8_4','paired_6_3']:
        for difficulty in ['简单','中等','困难']:
            z=cell(study,'C1_to_C3','Q_GS','difficulty',difficulty);q=cell(study,'C1_to_C3','Q_class_shift','difficulty',difficulty)
            diff.append(dict(条件='8/4' if study=='main_8_4' else '6/3共同支持',难度=difficulty,支持=f'{int(z.images)}图/{int(z.buildings)}楼',GS=z.image_equal_mean,质量位移=q.image_equal_mean,质量位移为正图=f'{int(q.positive_images)}/{int(q.images)}'))
    diff_table=table(pd.DataFrame(diff),['条件','难度','支持','GS','质量位移','质量位移为正图'])
    room=[]
    for kind in ['卧室','卫浴','厨房与用餐','工作与学习','起居与休闲','通行与连接','未登记']:
        z=cell('paired_6_3','C1_to_C3','Q_class_shift','room_type',kind)
        room.append(dict(房间用途=kind,支持=f'{int(z.images)}图/{int(z.buildings)}楼',质量位移=z.image_equal_mean,质量位移为正图=f'{int(z.positive_images)}/{int(z.images)}'))
    room_table=table(pd.DataFrame(room),['房间用途','支持','质量位移','质量位移为正图'])
    bc=pd.read_csv(OUT/'analysis/BALANCED_COMPONENT_SUMMARY.csv');bc=bc[bc.direction=='C1_to_C3'];component=[]
    for m,label in [('IoU3D100','3D IoU×100（升高为好）'),('iou_2d','2D IoU（升高为好）'),('S_bottom_deg','底边角位置误差°（降低为好）'),('dir','方向误差°（降低为好）'),('Hmean','Hmean（降低为好）'),('Hcenter','Hcenter（降低为好）'),('nodes','输出节点数'),('ref_node_recall_9','参考节点几何召回率，9°')]:
        a=bc[(bc.study=='main_8_4')&(bc.metric==m+'_class_shift')].iloc[0];b=bc[(bc.study=='paired_6_3')&(bc.metric==m+'_class_shift')].iloc[0]
        component.append(dict(分项=label,主8_4=a.image_equal_mean,共同6_3=b.image_equal_mean))
    component_table=table(pd.DataFrame(component),['分项','主8_4','共同6_3'],['分项','8/4 C1→C3','6/3共同支持 C1→C3'])
    bg=pd.read_csv(OUT/'analysis/FIXED_BLOCK_BACKGROUND_CLASS_CONTROL_SUMMARY.csv')
    bg=bg[(bg.study=='paired_6_3')&(bg.support=='all_four_valid')&bg.same_D_class_vector]
    forward=bg[bg.direction=='C1_to_C3'].iloc[0]
    bgdetail=pd.read_csv(OUT/'analysis/FIXED_BLOCK_BACKGROUND_CLASS_CONTROL.csv.gz')
    bgall=bgdetail[(bgdetail.study=='paired_6_3')&(bgdetail.direction=='C1_to_C3')&(bgdetail.support=='all_four_valid')]
    bgsame=bgall[bgall.same_D_class_vector]
    final=json.loads((OUT/'audit/FINAL_VALIDATION.json').read_text());kernel=pd.read_csv(OUT/'analysis/KERNEL_DIAGNOSTIC_SUMMARY.csv')
    report=f'''# DSTRUCT K3：C1↔C3 严格 50% 替换补充结果

## 核心结论

**缺失的 C1↔C3 严格 50% 替换已实际补齐。** 当前人员容量支持 8 人换 4 人：C1→C3 覆盖全部 24 张可行图，C3→C1 覆盖全部 4 张可行图。两方向在 8/4 下没有共同图片，因此另补了 36 图、10 楼的 6 人换 3 人双向共同背景对照。总计 **3,200 个登记 ABC 事件、4,992 个精确团队端点**；4,898 个有正式 Q，94 个真实无连接状态完整保留。

结果显示一个明确且有支持范围的规律：**在本轮可行图上，将半数 C1 替换为 C3，通常提高融合质量，且跨类变化通常超过同类换人。** 8/4 前向质量位移平均 +10.165 分、中位 +6.419 分，22/24 图为正；6/3 共同支持上 C3 背景团队比 C1 背景团队平均高 +7.865 分，32/36 图为正。建筑等权后分别为 +6.474、+6.146，方向保持；去掉任一建筑后方向也保持。这些结果既不由少数反例推翻，也不把 C3 改名为普适“高质量类”。

8/4 反向的 GS 为 −0.346，主要来自一张图的 C3 类内成员波动很大；同一方向四张图的质量位移全部为负，表明 C1 换入使 Q 降低。**GS 是否为正、Q 是升是降、同类成员是否稳定，是三个不同问题。** 在同图、同 D、同四端点的 6/3 对照中，两方向 GS 分别为 +3.269、+3.955，跨类额外变化的结论得到补充支持。

本补充测的是固定人数下的替换端点。它本身不检验按人数增长的趋近 GT 曲线，也不证明更短的实际标注时间；这些结论需要接回原有共识曲线研究。来源：[主统计](analysis/SUMMARY.csv)、[逐图结果](analysis/IMAGE_METRICS.csv.gz)、[支持登记](analysis/SUPPORT.csv)、[端点运行回执](endpoints/RUN_RECEIPT.json)。

## 1. 为什么采用 8/4，并另补共同 6/3

本轮使用固定提交 `{COMMIT}` 的正式 v2.1 融合输入和当前 DSTRUCT K3 楼外标签。先对 206 个普通 Manual 主目标池逐一核验了当前 RAW 与正式池的实际人员集合、对象 ID、参考版本、预处理后坐标、上下点共享 x、已有劳动时间数值及来源。没有重新整理原始坐标，没有把 F2/F9 坐标候选推广到本轮，也没有重分类型。

严格 ABC 需要 A=D∪X、B=D∪Y、C=D∪Z，D/X/Y/Z 两两不交，X、Y 同为源类，Z 为目标类，|X|=|Y|=|Z|=m，且 n=2m。由此需要源类至少 2m 人、目标类至少 m 人、总池至少 4m 人。

| 当前正式容量 | C1→C3 | C3→C1 |
| --- | --- | --- |
| m≥5 的严格 50% 替换 | 0 图 | 0 图 |
| 8/4 | 24 图、10 楼 | 4 图、3 楼 |
| 8/4 两方向共同图 | 0 图 | 0 图 |
| 6/3 四纯块共用 D 的共同图 | 36 图、10 楼 | 同一 36 图、10 楼 |

因此，不能在当前人员容量下伪造 14/7 的 C1↔C3，也不能只把一个 AC 差值取负号充当反向严格 ABC。新的 8/4 与旧 14/7 C2→C3 同时改变了类别对和 n/m，不能把数值差全部解释成“类别距离”。容量来源：[POOL_CAPACITY.csv.gz](design/POOL_CAPACITY.csv.gz)、[SOURCE_AUDIT.csv.gz](design/SOURCE_AUDIT.csv.gz)。

设计在首次新融合之前冻结，种子为 **20261104013**：8/4 每图、每方向固定 16 套 XYZ，分别抽 2 个不同 D；6/3 每图固定 8 套两块 C1（P/Q）与两块 C3（R/S），各抽 2 个共同 D。每个共同 D 保存四端点 D+P、D+Q、D+R、D+S；每方向都使用两个目标块，各自有真实同类控制。共 576 个四端点束、2,304 个 6/3 ABC 事件。

选择过程只使用类标签、人员 ID 与容量，不读 Q/T 或已有端点成败，也没有按显著性追加重复。D 从剩余可用人员中均匀抽取，允许背景含多类；各方向背景分布受真实容量限制。主 8/4 中，前向 502/768、反向 110/128 个 D 恰好由 4 个 C2 组成。完整 D/X/Y/Z 与精确团队键均可逐条追踪。[设计](design/DESIGN.json)；[事件](design/EVENTS.csv.gz)；[团队请求](design/REQUESTS.csv.gz)；[共同四端点束](design/PAIRED_BUNDLES.csv.gz)。

融合沿用正式 MV50 阈值 `ceil(n/2)`，在本轮偶数人数下等于 4/3 票。因此，一整块 m 人共同支持的节点可以单独达到入选阈值。这是半数替换可能改变结构和连接状态的具体机制条件；本轮没有把它改成严格大于半数的投票规则。[节点阈值验收](audit/FINAL_VALIDATION.json)。

## 2. 主结果、方向与支持

W=|QB−QA|；跨类变化=(|QC−QA|+|QC−QB|)/2；GA=|QC−QA|−W；GS=跨类变化−W。另报告带符号质量位移 QC−(QA+QB)/2，正值表示换入类质量较高。GS>0 本身只表示跨类引起更大变化，不直接等于质量改善。

{main_table}

区间为 10,000 次按建筑整簇重采样的 95% 百分位区间；主均值先平均共同目标块，再平均 D、XYZ 块和图片。重复团队、重复背景没有被当作独立图样本。6/3 方向共用同一套建筑抽样，其带符号位移互为相反数是共同端点设计的代数关系，不是两次独立复现；W 和 GS 各自使用相应源类的同类控制。

8/4 前向 768 个登记事件中 728 个三端同时有 Q，反向为 113/128；均保留全部 24/4 张图。6/3 的 576 个共同四端点束中，547 个四端都可评；每方向 1,094 个有效 ABC 事件覆盖全部 36 图。若仅要求各方向自己的三端可评，分别有 1,095、1,118 事件，GS 为 +3.292、+3.985，接近共同四端点的 +3.269、+3.955。没有用额外可评端点静默扩大某一方向的主分母。[SUPPORT.csv](analysis/SUPPORT.csv)、[PAIRED_FOUR_SUMMARY.csv](analysis/PAIRED_FOUR_SUMMARY.csv)。

## 3. 难度与场景中的规律

在两个设计中，C3 换入的平均质量优势均随当前官方难度上升而扩大。简单图也有正平均效应；困难图并非唯一贡献来源。

{diff_table}

这是本轮可行图上的条件差异。困难层分别只有 3 图，6/3 的困难层来自 2 楼；不能把它写成已经识别了“难度对效应的因果作用”。两种人数规模出现相同的梯度，且简单层本身也支持正向规律，值得在现有研究中作为主要发现解释。[难度分层](analysis/SUMMARY.csv)；[逐图支持](analysis/IMAGE_SUPPORT.csv)。

以 6/3 的共同四端点域比较房间用途，得到：

{room_table}

房间用途来自正式 `IMAGE_TYPE_INDEX.csv` 的 `room_type`，不是输入里的 `scene=clear/unflagged`。卧室的支持最广，平均 +4.087 分、10/13 图为正；卫浴平均 +13.132 分、4/4 图为正。起居与休闲的 7 图全部为正，但来自同一楼，应表述为该楼这一组场景的规律。通行与连接只有 3 图，均值受一张困难图影响较大，2/3 图为正。用途与几何难度并非独立抽样因素，不能仅凭这张表断定房间用途本身导致差异。[分层表](analysis/SUMMARY.csv)；源表：`research/statistics/room_type_similarity_scoping_20261027/IMAGE_TYPE_INDEX.csv`。

## 4. 改善落在哪些质量分项

下表使用与主质量位移相同的对称基线：C−(A+B)/2。所有分项都限制在正式 Q 的同一共同支持上。

{component_table}

前向改善同时出现在平面重合、底边角位置、方向和高度误差；平均节点数只增加约 0.18/0.21 个。因而这组现象不宜概括成“C3 多加几个节点就得高分”：很多图片的节点数量不变，而位置和轮廓仍有改善。分项相互有关，以上是输出差异的定位，不是各机制的独立因果贡献分解。[分项汇总](analysis/BALANCED_COMPONENT_SUMMARY.csv)；[分项逐图](analysis/BALANCED_COMPONENT_IMAGE.csv)。

## 5. 反例究竟说明什么

8/4 C3→C1 的反向 GS 小幅为负，来源可以定位：

| 图片 | W：同类变化 | 跨类变化 | GS | 质量位移 |
| --- | --- | --- | --- | --- |
| B6ByNegPMKs-47 | 11.485 | 12.747 | +1.263 | −10.703 |
| jtcxE69GiFV-13 | 10.469 | 6.753 | −3.717 | −5.052 |
| jtcxE69GiFV-23 | 0.785 | 1.642 | +0.857 | −1.608 |
| uNb9QFRL6hY-82 | 2.549 | 2.761 | +0.212 | −2.742 |

`jtcxE69GiFV-13` 的 C3 同类换人本来就引起很大变化，因此跨类变化没有超过同类基线；但换入 C1 后质量仍降低。不能把这个 GS 反例写成“C3 的质量优势反转”，也不能因前向更强就假设两个不同图片域的方向效应对称。[逐图结果](analysis/IMAGE_METRICS.csv.gz)。

8/4 前向只有 `uNb9QFRL6hY-65`（−4.964）和 `B6ByNegPMKs-11`（−2.518）两图质量位移为负。共同 6/3 有 4 个质量反例：`S9hNv5qa7GM-15`（−0.636）、`uNb9QFRL6hY-65`（−1.674）、`uNb9QFRL6hY-68`（−2.398）、`yqstnuAEVhm-27`（−2.507）。这些反例限定了“通常更好”的范围，未改变图均值、中位数及建筑敏感性中的主要方向。

C3 的类内 W 在共同 6/3 下均值 5.825，C1 为 6.511，但 36 图中有 21 图的 C3 类内 W 更大。因此当前证据支持“这组 C3 背景组合的平均 Q 较高”，不支持“C3 在每张图上都更稳定”。类别比例之外，具体成员仍然重要。[共同四端点逐图](analysis/PAIRED_FOUR_IMAGE.csv)、[共同四端点汇总](analysis/PAIRED_FOUR_SUMMARY.csv)。

另对固定 XYZ、只换两套共同 D 的结果进行了接续：在 6/3 四端共同支持上，质量位移随 D 变化的绝对差平均为 4.505 分。在两套 D 都可评的 {len(bgall)} 块中，有 {int(bgall.Q_class_shift_sign_flip.sum())} 块质量位移翻号（直接按块计 {100*bgall.Q_class_shift_sign_flip.mean():.1f}%，按图片等权汇总为 13.0%）。进一步限制 D 的类别计数向量完全相同，前向仍有 **{int(forward.blocks)} 块、{int(forward.images)} 图**；质量位移绝对差平均 **{forward.Q_class_shift_absolute_difference:.3f} 分**，其中 {int(bgsame.Q_class_shift_sign_flip.sum())} 块翻号（直接按块计 {100*bgsame.Q_class_shift_sign_flip.mean():.1f}%，图片等权翻号率为 **{100*forward.Q_class_shift_sign_flip:.1f}%**）。这表明背景中的具体成员会改变同一替换操作的效果，不能仅用比例解释全部波动。[背景类别计数控制](analysis/FIXED_BLOCK_BACKGROUND_CLASS_CONTROL_SUMMARY.csv)、[逐块明细](analysis/FIXED_BLOCK_BACKGROUND_CLASS_CONTROL.csv.gz)。

## 6. 连接、可评支持与可见核分开记录

4,992 个新端点中，94 个没有自动连接；全部原因为 `no_source_ring_covering_all_selected_nodes`。冻结节点坐标及票数仍保存在失败端点的自动状态中。它们没有被当作 Q=0，也没有被人工猜序。与旧 focused 30,166 个正式端点、另 163,859 条相关旧请求及 57 个已批准人工端点逐一求精确团队交集后，均为 0；因此本补充全部是同等自动处理，人工辅助身份没有命中，不混入主估计。[缓存核查](audit/CACHE_AUDIT.json)、[补充请求核查](audit/ADDITIONAL_CACHE_REQUEST_AUDIT.json)、[失败端点](analysis/FAILED_ENDPOINTS.csv.gz)。

在共同 6/3 中，1,152 个 C1 替换块背景团队有 32 个无 Q（2.778%），1,152 个 C3 背景团队有 1 个无 Q（0.087%）。这是连接/可评机会的区别；前述 +7.865 分质量优势来自共同可评支持，不含把失败记零的隐含奖励。[端点支持表](analysis/PAIRED_ENDPOINT_SUPPORT_SUMMARY.csv)。

独立几何验收显示：4,898 个正式可评几何全部共享上下 x、底面无自交、面积非零、相机位于多边形内部；337 个相机不在多边形可见核。**这不是一个新增的正式无效判据：48 个冻结参考里有 7 个参考本身也不满足该核条件。** 当前研究保留完整参考形状，不能用额外核规则剔除其困难局部，再把结果称为原任务。

作为明确标注的附加诊断，若要求所比较端点都在可见核内，8/4 前向剩 668 事件、22 图，GS=+4.585、质量位移=+7.716；6/3 共同域剩 501 个四端点束、33 图，双向 GS=+1.798/+2.951，C3−C1 Q=+6.132，29/33 图为正。效应幅度缩小，主要方向保持；主结论继续使用原正式可评分母。[完整几何审计](audit/GEOMETRY_AUDIT.csv.gz)、[参考核检查](audit/REFERENCES_KERNEL.csv)、[额外核内敏感性](analysis/KERNEL_DIAGNOSTIC_SUMMARY.csv)。

## 7. 时间与“更快达成共识”

本轮保留原始冻结记录的合法时间及来源。48 池共 1,642 条原答：旧 v1 的 684 条中 335 条有源时间；用户已处理记录 958 条均有源时间。4,992 个端点中 1,460 个队的源时间全知且正，400 个队同时满足全员同一时间来源。旧缺失没有被填零，也没有重新解释新用户处理时间为原日志重放时间。[时间输入](inputs/CURRENT_TIME_INDEX.csv.gz)、[端点标量](endpoints/ENDPOINT_SCALARS.csv.gz)。

对三臂要求全部同源且各人记录全知：8/4 两方向均没有共同时间事件；6/3 前向仅 8 事件/1 图，反向仅 12 事件/3 图。共同四端点同时满足该条件的只有 4 个束。固定 D 下同源替换块的劳动差另存，不与混源全队总秒数混写。因此，本补充不能给出普遍节时结论；它已经给出清楚的质量与连接证据。固定 n 的替换效应也不能直接等同于进入顺序或共识曲线更早到达 GT。[TIME_SUPPORT.csv](analysis/TIME_SUPPORT.csv)、[TIME_SUMMARY.csv](analysis/TIME_SUMMARY.csv)。

## 8. 图、验证与复现

- [严格 50% GS 总览](figures/C13_STRICT_50PCT_GS.png)：全部逐图点、建筑整簇区间与真实分母，保留反例。
- [变化幅度与质量方向](figures/C13_CHANGE_VS_QUALITY.png)：GS 与带符号质量位移分别展示。
- [可追溯的 ABC 完整底面](figures/C13_TRACEABLE_ABC_CASES.png)：强改善、质量反例、反向 GS 反例各一张。图内事件按接近图片平均效应选择，不挑该图最优事件；[精确事件](analysis/ILLUSTRATIVE_EVENT_TRACE.csv.gz)、[全部几何和参考](analysis/ILLUSTRATIVE_CASES.json.gz)可复查。

正式 native 融合和评分代码未改。运行前以旧正式缓存中 3 个不同难度的成功端点及 1 个无连接端点做数值一致性检查，最大差 1.42×10⁻¹⁴；随后 4,992 个端点均实际计算并保存完整终态/失败状态。最终检查了节点票数阈值、成员对象 ID、参考、坐标、全部设计及源文件 hash、逐事件 W/GA/GS、逐图计权与 Q 公式。B8L2/D10 独立公式最大残差均为 2.84×10⁻¹⁴。[native 一致性](audit/NATIVE_PARITY.json)、[最终验收](audit/FINAL_VALIDATION.json)、[运行版本](audit/RUNTIME_VERSIONS.json)、[官方源依赖恢复回执](audit/ENGINE_IMPORT_RECEIPT.json)。

在仓库根目录运行：

```bash
python research/workers/mixture_patterns_and_c13_half_20261104/c13_half/code/run_native.py --jobs 4
python research/workers/mixture_patterns_and_c13_half_20261104/c13_half/code/analyze.py
python research/workers/mixture_patterns_and_c13_half_20261104/c13_half/code/validate_delivery.py
python research/workers/mixture_patterns_and_c13_half_20261104/c13_half/code/diagnostics.py
python research/workers/mixture_patterns_and_c13_half_20261104/c13_half/code/plots.py
python research/workers/mixture_patterns_and_c13_half_20261104/c13_half/code/case_panels.py
python research/workers/mixture_patterns_and_c13_half_20261104/c13_half/code/write_report.py
```

`run_native.py` 精确读取已冻结的请求，并按池断点恢复，已完成端点会复用。本地输出不可替代或覆盖旧自动/人工辅助实验。`design.py` 拒绝覆盖已冻结设计，避免看过结果后改抽样。全部输入、统计和审计均随本补充保存；底层融合依赖指向上述固定提交下的仓库文件。统计图同时提供 PNG、SVG 和 PDF。

## 可接入 v2.1 的结论条目

见 [CONCLUSION_LEDGER.csv](CONCLUSION_LEDGER.csv)。本补充没有修改分类、Q/T 选队规则、进入策略、大池曲线或旧 14/7 实验；它增加的是 C1↔C3 当前可行的严格 50% 替换证据、共同支持解释和原结论适用条件。
'''
    (OUT/'REPORT_ZH.md').write_text(report,encoding='utf-8')
    readme='''# C1↔C3 严格 50% 替换：已完成补充

完整结果、方法、反例解释和逐条来源见 [REPORT_ZH.md](REPORT_ZH.md)。

本目录是固定提交 `48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b` 下的新增研究结果。当前 DSTRUCT K3、当前普通 Manual 主目标、现成 LOBO 标签；没有重分类、改坐标或覆盖旧实验。

## 已完成内容

- 8 人换 4 人：C1→C3 24 图、C3→C1 4 图，两个方向分别采用真实严格 ABC。
- 6 人换 3 人：36 图、10 楼的共同四端点设计，解决 8/4 两方向零共同图的问题。
- 3,200 个事件、4,992 个唯一团队端点；4,898 有正式 Q、94 个自动无连接。
- 同等自动处理；57 个已批准人工端点精确命中 0，不混入辅助处理。
- 完整分项、难度/房间用途、劳动来源、连接支持、固定块/背景成员效应、可见核诊断及数值验收。

主要表：[SUMMARY.csv](analysis/SUMMARY.csv)、[PAIRED_FOUR_SUMMARY.csv](analysis/PAIRED_FOUR_SUMMARY.csv)、[SUPPORT.csv](analysis/SUPPORT.csv)、[CONCLUSION_LEDGER.csv](CONCLUSION_LEDGER.csv)。

## 复现与验证

在 HOHONET 仓库根目录运行；代码使用当前目录相对仓库的位置识别路径，不依赖本次运行的绝对路径。

```bash
python research/workers/mixture_patterns_and_c13_half_20261104/c13_half/code/run_native.py --jobs 4
python research/workers/mixture_patterns_and_c13_half_20261104/c13_half/code/analyze.py
python research/workers/mixture_patterns_and_c13_half_20261104/c13_half/code/validate_delivery.py
python research/workers/mixture_patterns_and_c13_half_20261104/c13_half/code/diagnostics.py
python research/workers/mixture_patterns_and_c13_half_20261104/c13_half/code/plots.py
python research/workers/mixture_patterns_and_c13_half_20261104/c13_half/code/case_panels.py
python research/workers/mixture_patterns_and_c13_half_20261104/c13_half/code/write_report.py
```

`design.py` 在已冻结设计存在时拒绝覆盖。`run_native.py` 按池精确恢复已存端点；本轮来源与设计 hash 均已锁定。主均值按目标块→背景→替换块→图片汇总；建筑等权与建筑整簇区间另列。缺 Q 从未记零，T 仅在明确记录来源与合法支持内比较。

最终检查：[FINAL_VALIDATION.json](audit/FINAL_VALIDATION.json)。完整文件校验与体积：[DELIVERY_MANIFEST.json](DELIVERY_MANIFEST.json)。图提供 PNG、SVG 和 PDF；端点保存最终完整几何，失败端点另保留自动融合状态及节点坐标/票数。
'''
    (OUT/'README.md').write_text(readme,encoding='utf-8')
    ledger=[
        ('C13_50PCT_CAPACITY','条件变化','C1↔C3严格50%已补齐；当前最大双向可行方案8/4，m≥5无可行图','8/4前24图10楼、反4图3楼；6/3共同36图10楼','当前ordinary_manual主目标、当前LOBO','design/POOL_CAPACITY.csv.gz|design/DESIGN.json'),
        ('C13_CROSS_EXCESS','保持','共同6/3中跨类变化大于对应同类变化','GS C1→C3 +3.269；C3→C1 +3.955；图均值/建筑敏感性方向保持','547个四端点束，36图10楼','analysis/SUMMARY.csv|analysis/PAIRED_FOUR_SUMMARY.csv'),
        ('C13_QUALITY_DIRECTION','保持','C3换入在多数可行图提高融合Q；反向质量位移为负','8/4 +10.165、22/24图正；6/3 +7.865、32/36图正','当前n/m和支持域，不等于C3普遍高质量类型','analysis/SUMMARY.csv|analysis/IMAGE_METRICS.csv.gz'),
        ('C13_REVERSE_GS','条件变化','8/4反向GS约零且受一图大类内波动影响，不作双向对称性结论','GS −0.346；jtcx-13 W10.469、cross6.753；四图质量位移全负','8/4反向4图3楼，和前向零共同图','analysis/IMAGE_METRICS.csv.gz'),
        ('C13_DIFFICULTY','条件变化','C3换入优势在中难图更大，两种n/m均出现梯度','8/4质量位移简单5.299、中等14.588、困难28.740；6/3 5.089/12.670/23.234','困难各3图，非难度因果识别','analysis/SUMMARY.csv'),
        ('C13_SCENE','条件变化','卧室广支持正向；卫浴与起居组更大，但用途与难度/建筑仍关联','6/3卧室13图6楼 +4.087；卫浴4图3楼 +13.132；起居7图1楼 +12.153','房间用途来源IMAGE_TYPE_INDEX，不混用scene状态','analysis/SUMMARY.csv'),
        ('C13_STABILITY','需改写','较高平均Q不等于C3每图类内更稳定','C3 W均值5.825<C1 6.511，但21/36图C3 W更大','共享四端点共同域','analysis/PAIRED_FOUR_IMAGE.csv|analysis/PAIRED_FOUR_SUMMARY.csv'),
        ('C13_BACKGROUND_MEMBERS','保持','固定替换块下，更换具体背景成员仍改变效应，不能只解释比例','6/3两D质量位移绝对差均值4.505；同D类别计数向量的控制另附','有限两背景、固定块的描述性比较','analysis/FIXED_BLOCK_BACKGROUND_CLASS_CONTROL_SUMMARY.csv'),
        ('C13_CONNECTION_SUPPORT','条件变化','分别报告连接和共同支持Q，失败不计零','共有94无连接；共同6/3 C1背景团队32/1152无Q、C3为1/1152','同等自动处理，57人工精确命中0','analysis/PAIRED_ENDPOINT_SUPPORT_SUMMARY.csv|audit/CACHE_AUDIT.json'),
        ('C13_KERNEL_DIAGNOSTIC','幅度变化','额外核内约束缩小幅度，主要方向保持，不改官方评分门槛','8/4前向22图GS4.585/Q7.716；6/3共同33图GS1.798/2.951、Q6.132','7个冻结参考本身非相机星形，不能把核规则升格为资格','analysis/KERNEL_DIAGNOSTIC_SUMMARY.csv|audit/REFERENCES_KERNEL.csv'),
        ('C13_LABOR_SPEED','尚不能判断','本端点实验不能证明普遍省时或共识曲线更早到GT','8/4三臂全同源时间支持0；6/3共享四端点全同源仅4束','不把固定n替换效应当进入曲线速度','analysis/TIME_SUPPORT.csv|audit/ADDITIONAL_DIAGNOSTICS.json')
    ]
    csv(OUT/'CONCLUSION_LEDGER.csv',pd.DataFrame(ledger,columns=['claim_id','status','conclusion','evidence','scope','source_files']))
    manifest=[]
    for p in sorted(OUT.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts and p.name not in ('DELIVERY_MANIFEST.json',):
            manifest.append(dict(path=str(p.relative_to(OUT)),bytes=p.stat().st_size,sha256=sha(p)))
    write_json(OUT/'DELIVERY_MANIFEST.json',dict(source_commit=COMMIT,root='research/workers/mixture_patterns_and_c13_half_20261104/c13_half',files=manifest,total_bytes=sum(x['bytes'] for x in manifest)))
    print('Report, conclusion ledger and manifest written:',len(manifest),'files')

if __name__=='__main__':main()
