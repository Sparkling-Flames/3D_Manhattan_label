#!/usr/bin/env python3
"""Build the self-contained Chinese research report from frozen result tables.

This renderer does not fit parameters, change labels, repair points, or select references.
Run from any directory: python top_structure_20261012/build_report.py
"""
from pathlib import Path
import base64
import csv
import datetime as dt
import hashlib
import html
import json

ROOT = Path(__file__).resolve().parent


def read_json(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def read_csv(path):
    with (ROOT / path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def fmt(value, digits=2):
    if value is None or value == '':
        return '—'
    return f'{float(value):.{digits}f}'


def table(headers, rows):
    esc = lambda x: html.escape(str(x))
    return ('<div class="tablewrap"><table><thead><tr>' + ''.join('<th>' + esc(x) + '</th>' for x in headers)
            + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + esc(x) + '</td>' for x in row) + '</tr>' for row in rows)
            + '</tbody></table></div>')


def figure(path, caption):
    p = ROOT / path
    mime = 'image/png' if p.suffix == '.png' else 'image/jpeg'
    return '<figure><img loading="lazy" src="data:' + mime + ';base64,' + base64.b64encode(p.read_bytes()).decode() + '" alt="' + html.escape(caption, quote=True) + '"><figcaption>' + caption + '</figcaption></figure>'


def main():
    scores = read_csv('analysis/results/candidate_scores_39.csv')
    cases = {r['old_case_id'] or r['new_case_id']: r for r in scores}
    ranking = {r['method']: r for r in read_csv('analysis/fair_comparison/old24_rank_summary.csv')}
    calibrated = {r['method']: r for r in read_json('analysis/fair_comparison/old24_two_cutpoint_calibration_summary.json')}
    border = {r['method']: r for r in read_json('analysis/fair_comparison/borderline_scenario_summary.json')}
    assert len(scores) == 39 and len(ranking) == len(calibrated) == 15
    assert int(ranking['Q_v11']['inversions']) == 42 and int(ranking['Q_no_topS']['inversions']) == 19
    assert abs(float(cases['T20']['Q_v11']) - 16.721627812823) < 1e-8
    main_sha = read_json('inputs/main_head.json')
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    methods = [
        ('Q_v11', '旧 v1.1'), ('Q_floor_iou', '底面 IoU ×100'), ('Q_official_iou3d', '官方 3D IoU ×100'),
        ('Q_no_topS', '去顶部 S'), ('Q_IHC_h050', 'IHC：顶底 S 都去掉'),
        ('Q_quarter_topS', '顶部权重 1/4'), ('Q_top_1_16', '顶部权重 1/16'),
        ('Q_max_old', 'max(旧顶部，高度)'), ('Q_max_quarter', 'max(1/4 顶部，高度)'),
        ('Q_no_top_stage13', '去顶部＋原 stage13'), ('Q_top_1_16_stage13', '1/16 顶部＋原 stage13'),
        ('Q_split_equal', '全局/中心化局部，均用 0.5'), ('Q_split_local025', '全局 0.5 / 局部 0.25'),
        ('Q_no_top_Xrms8', '去顶部＋输入 X_RMS /8°'), ('Q_no_top_Xmax8', '去顶部＋输入 X_max /8°')]
    comparisons = []
    for key, name in methods:
        r, c = ranking[key], calibrated[key]
        comparisons.append([name, r['inversions'] + '/164', r['same_image_inversions'] + '/2',
                            str(c['total_held_absolute_step_loss_min']) + '–' + str(c['total_held_absolute_step_loss_max']),
                            fmt(cases['T20'][key]), str(border[key]['all_borderline_obvious']['inversions']) + '/54'])

    parts = []
    def add(text):
        parts.append(text)

    add(r'''<header><div class="eyebrow">室内全景布局标注 · 独立质量研究</div>
<h1>顶部与结构惩罚如何组合和校准</h1>
<p class="lead">有证据调整旧顶部项的地位；尚没有证据把一种新总分及其等级阈值定为唯一答案。</p>
<p class="meta">研究轮次标识：20261012。实际读取与计算发生于 2026-10-11 UTC；文件名中的轮次标识不代表另一天的观测。实际 main：<code>38e259c043fed0817307dbc3d21c6dba06bd6662</code>。</p>
<p>本报告先完成指定的高度、结构组合、输入表示、资格、定向复核及固定融合示范，再开展精确高度幅度与支持范围诊断。所有建议属于独立研究分支，尚未替换正式质量算法或共识流程。</p></header>
<nav><a href="#findings">主要发现</a><a href="#sources">输入与资格</a><a href="#definition">机制定义</a><a href="#t20">T20 与控制</a><a href="#candidates">候选比较</a><a href="#representation">共享 x</a><a href="#review">人工复核</a><a href="#exploration">自由探索</a><a href="#decision">建议与冻结条件</a><a href="#reproduce">复现</a></nav>
<section id="findings"><h2>1. 哪些已证实，哪些只是倾向</h2>
<div class="callout"><p><strong>已证实：</strong>T20 的严罚主要来自顶部球面边界项的尺度与组合；H 已捕捉其整体低顶，D/F 并非主要扣分来源。单纯用 max 去掉疑似重复项不能解决 T20。共享 x 确实抹掉当前输入中的一部分方位差，事后 D/F 无法恢复。平均型高度指标与有限求积也确有局部尖峰盲区。</p>
<p><strong>有支持的倾向：</strong>以最终重建结果为主的研究，应降低顶部投影距离对总分的支配程度，并把当前输入质量单列。去顶部 S 在旧 24 份不确定判断中的相容性改善较稳定，但不足以证明同图人员排序更好。</p>
<p><strong>仍需人工判断：</strong>低顶与广泛起伏应如何权衡；T09/T22 的范围缺失与斜跨哪份更差；S071/S107 是否达到严重；T07 的当前输入错配感是否应改变总质量，或另列输入质量。没有为这些问题替用户生成新标签。</p></div>
<p>三条关键反例限制推荐力度。第一，去顶部 S 后 T09/T22 新出现与旧判断相反的同图顺序。第二，局部高度强化不能包办严重结构错误：9 份条件可算严重中 8 份在三个显示尺度上的支持均为 0，但这不表示 Hcenter 或局部起伏本身严格为 0。第三，X_max 入分在旧 24 份上看似最少逆序，但受高影响案例、等级扰动与冗余共线点影响，不能据此冻结 8°。</p>
<p class="source">新计算证据：analysis/results/、analysis/fair_comparison/、mechanisms/results/、representation/results/、exploration/results/。原人工回执及最新文字覆盖分开保存。</p></section>
<section id="sources"><h2>2. 实际输入、版本及分析资格</h2>
<h3>2.1 本轮确实读到了什么</h3>
<p>已读取上述 main 的 12 个指定审核、选样及参考限制文件，逐文件核对 Git blob 与 SHA256；读取两份历史 ZIP 的实际字节和内部清单，并复用冻结代码与坐标。最新对话 8 项澄清另存 <code>inputs/USER_CLARIFICATIONS_THIS_TURN.txt</code>，没有假定它们全部已同步到仓库。T25 采用“仅 A”，原回执不改；T20 没有目标分数或新等级。</p>
<p>四份基础包均实际可访问，已查内部清单、CRC、图片 ID、尺寸及 SHA256。前三份为 99＋64＋98＝261 张不同原图，均为 2048×1024；跨包图片 ID 与图片内容哈希无重复。它们含 259 张研究原图与 2 张仅参考用途原图。扩展包包含分析材料及 23 张分析 PNG，没有原图库。261 张做了解码和字节核验，本轮逐图视觉检查聚焦 6 张原图、7 份作答；不能将技术解码写成看过全部 261 张。</p>''')
    add(table(['实际读取的包', '字节数', 'SHA256（前 16 位；完整值见清单）'], [
        ['quality_representation_severe_research_20261011.zip', '67,163,604', '0ab95337296d4ff94'],
        ['quality_calibration_research_20261011.zip', '70,189,424', 'ca67b40f30646dd03'],
        ['pro_quality_original_images_01_of_03.zip', '184,403,061', '06ec16424246e667'],
        ['pro_quality_original_images_02_of_03.zip', '124,304,472', 'b1096d854c58f5f4'],
        ['pro_quality_original_images_03_of_03.zip', '182,549,824', '99832bc14bb4279f1'],
        ['pro_quality_expanded_data_20261007.zip', '24,016,602', '301dc72a3f34ad735']]))
    add(r'''<p>本轮没有缺少指定 ZIP。交付包为离线最小研究包，含所需数值链、代码、标签和 6 张原图，并不重复附上约 491 MB 的三份原图库；完整原包与 261 张图片的核验清单随包保留。历史四空间基线提交 <code>2738f98cde6e47f111b24bd5f8037d3ef49094c9</code> 及之前数值对齐属于历史输入，不能冒称本轮重新开发或独立验证。</p>
<h3>2.2 标签、适用性、可计算性分别计数</h3>''')
    add(table(['层级', '记录', '严重 / 犹豫 / 未审', '不同图片', '楼栋'], [
        ['收到的严重筛选',115,'25 / 11 / 79',69,18],
        ['按已有 OOS、门洞交界等暂缓 17 份后',98,'22 / 11 / 65',59,17],
        ['再去掉原留出暴露记录（与上一步有 1 份重叠）',85,'19 / 11 / 55',51,14],
        ['再沿用图片级既有 hold',81,'16 / 11 / 54',47,14],
        ['有条件可算完整分数',65,'9 / 6 / 50',44,12],
        ['实际进入标签数值对照',39,'旧 24 ＋严重 9＋犹豫 6',30,14]]))
    add(r'''<p>旧 24 份分布为 2 可接受、10 轻微、12 明显、0 严重，来自 18 张图片、11 栋楼、14 位人员；仍有 6 份旧空间匹配回执，未被拼成质量等级。当前 39 份数值对照涉及 16 位人员、23 个已知房间标识；另有 8 份／5 图缺房间标识。原分组中有楼栋替代房间的情况，17 个分析组不等于 17 个物理房间。9 份严重来自 7 图、7 栋楼、4 人，类型集中，7 份只有三对角点且重建轮廓不包相机；可算不等于环及参考已经人工验收。</p>
<p>81 份通过已知障碍筛选的记录中，仅 S024、S041、S064、S083 有显式范围标记，其中前三份未审，S083 为犹豫且缺完整几何；其他记录的 not_recorded 不作“适用已确认”。65 份中的 50 未审仅作可算性计数，不进入负例或等级比较。未恢复的 7 严重为 S007、S023、S029、S042、S046、S092、S104；5 犹豫为 S026、S044、S073、S083、S109。缺失分数均为空，不是零分。</p>
<p>W019 的 14 份无已知范围障碍记录仍缺可靠显式配对，其中 6 严重、5 犹豫、3 未审。没有把相邻点或按 y 排序强制当成配对。校准授权不恢复其正式人员资格，也不把其所有作答预设最差。</p>
<h3>2.3 留出暴露与参考限制</h3>
<p>保留原暴露 14 份：S003、S010、S011、S019、S022、S030、S049、S053、S056、S062、S074、S077、S080、S106。原留出共有 282 份／9 组，其中 4 组有暴露，覆盖原 179 份；其余 5 组／103 份没有被本轮认证为干净测试集。14 份不用于参数校准，也没有悄悄重划留出。</p>
<p>沿用错误 GT、hold、excluded 和已接受多空间规则。T21/T22 仍按原 GT 范围，未增加“较小也合理”的参考。T30 的 D、W031/W034 的狭长延伸证据及未确认顶界状态不被本轮改写；不采用最大最终 Q 选参考，不借旧顶界给新底面伪造完整 3D IoU。本轮高度比较只在已有完整固定参考上进行，且明确是条件比较。</p>
<p class="source">证据：inputs/source_verification.json；inputs/archive_inventory_this_turn.json；inputs/image_inventory_this_turn.json；evidence/results/qualification_ledger_115.json、count_units.csv、holdout_exposure_preserved.json；main_snapshot 中原回执和覆盖。</p></section>
<section id="previous"><h2>3. 42/164 → 19/164 到底支持什么</h2>
<p>本轮独立复算与上一轮一致：旧公式 42 对逆序，去顶部 S 为 19 对。164 是不同旧等级之间的题对数量，来自 24 份相关、经过选例的主观判断；不是 164 个独立样本。其中只有 2 对同图：旧式 0 对逆序，去顶部出现 1 对；其余 162 对跨图为 42 → 18。25 对改善全部跨图，另有 2 对恶化，分别是同图 T09/T22 与跨图 T21/T16。</p>
<p>删除 T20 后，分母为 150，对应逆序仍为旧式 30、去顶部 18。逐图删去后的“去顶部减旧式”介于 −24 与 −9；按既有组或楼栋移除介于 −24 与 −5。收益不是 T20 单点造成，却仍主要证明旧开发标签下跨图片总排序的相容性改善，不能证明人员定位能力、公平性、同图排序或泛化均已改善。</p>
<p>全 24 份都允许相邻档摇摆，复用 46 个单题变化与 1013 个双题变化的有限情景；无评论题也可变化，不设概率。去顶部相对旧式的逆序差在单题情景为 −29～−9，双题为 −33～−1。这个方向在该有限扰动族较稳定。相反，新方案之间的优势通常很小：局部 0.25 相对去顶部在双题情景为 −4～＋1，X_max 为 −15～＋7。情景频数不是置信概率，也不要求一个方法在所有任意改档中获胜。</p>
<p class="source">新复算：evidence/results/prior_ranking_*；analysis/sensitivity/adjacent_label_sensitivity_summary.csv、group_case_omissions.csv。所有旧 24 的评论、绝对质量、与参考差距保留在历史证据层；T05 的“已标点好但漏角”和 T12 的“难图相对表现”不被压缩为一个无噪声标量真值。</p></section>
<section id="definition"><h2>4. Hmean、Hlocal、H*、F 与顶部 S 的精确定义</h2>
<p>相机高度单位为 h，固定地板在 y＝−1。下面墙高从地板量起，不是相机以上顶界高度，也不是实测米。对 1024×512 ERP：</p>
<div class="formula">β＝π(y<sub>b</sub>/512−1/2)，r/h＝cot β<br>α＝π(1/2−y<sub>t</sub>/512)，墙高/h＝1＋(r/h)tan α</div>
<p>不同 top y 可以对应同一水平顶面；同一个 top y 也会因底点改变而产生不同墙高。不能把 ERP 顶部折线“向下”直接称为三维低顶。</p>''')
    add(table(['量', '对象、采样与归一化', '能响应什么 / 主要限制'], [
        ['Hmean', '各自按底周长精确积分线性墙高，|μa−μg|/μg', '整体均高差；不直接区分局部高低互抵'],
        ['Hlocal', '双向各 4096 个底周长中点，投影到对方最近有限底边并插值墙高；均方平均、开方、除 μg', '整体＋局部；不同范围可能匹配到不同墙'],
        ['H*', 'max(Hmean,Hlocal)', '保留均高守卫；不是两个高度量相加'],
        ['F（评分用 flat）', '自身底周长 512 点，拟合最佳水平顶界，使仰角残差 RMS 最小，单位度', '自身顶界不平；无 GT，整体平行升降可为 0'],
        ['St / Sb', '沿球面短弧长度各取 2048 中点；到对方全部短弧并集的最近角距离，双向算术平均，单位度', '顶部/底部投影差；不是逐点配对，也不是位置距离 RMS'],
        ['D（补充）', '自身底边长度加权的方向残差 RMS；相对最佳共同轴，方向按 90° 周期，单位度', '斜跨造成的非曼哈顿性；规整地漏掉凹区可能接近 0']]))
    add(r'''<p>Hlocal 的等距最近目标采取最大垂直残差平方，并以浮点容差稳定等距判断；这防止数组次序或取最有利边改变结果，不能赋予语义同墙对应。辅助代码里另有一个大写 F 代表底面欧氏曲线距离；本报告评分的 F 明确取字段 <code>flat</code>，两者未混用。</p>
<div class="formula">μ＝Σ ℓ<sub>i</sub>(h<sub>i</sub>＋h<sub>i+1</sub>)/(2Σℓ<sub>i</sub>)<br>
H<sub>local</sub>²＝{E<sub>a</sub>[(h<sub>a</sub>−h<sub>g</sub>(π<sub>g</sub>))²]＋E<sub>g</sub>[(h<sub>g</sub>−h<sub>a</sub>(π<sub>a</sub>))²]}/(2μ<sub>g</sub>²)<br>
H*＝max(Hmean,Hlocal)</div>
<p>公式中的 E 表示“对方括号内残差的平方取期望”，代码按中点求积实现。当底面完全一致且 GT 为恒高时，连续积分满足 Hlocal²＝Hmean²＋σa²/μg²。直接再把 Hmean² 与 Hlocal² 相加会在此条件下重复全局误差；现有 max 没有这种代数重复。不同范围时该等式不成立，本轮真实 39 份中 S015、S040 的 Hmean 守卫实际占主导。</p>
<div class="formula">L<sub>D</sub>＝D²/(D²＋25)，L<sub>F</sub>＝F²/(F²＋4)<br>
C＝1−0.075(L<sub>D</sub>＋L<sub>F</sub>)<br>
Q<sub>v1.1</sub>＝100 I C / [1＋(St²＋Sb²)/32＋(H*/0.5)²]</div>
<p>D 与 F 各自最多降低 C 的 7.5%，合计最多 15%。F 数值很大不代表总分将被无限压低。4°是旧顶底 RMS 合成 S 的数学半损失尺度；单独顶部项或底部项的尺度是 √32≈5.657°。D＝5°、F＝2°是各自饱和损失的一半，不是已经认可的人类容忍度。</p>
<p class="source">代码核查：冻结 scope_engine/core/quality_v11.py、height_revision/height_revision.py、legacy_geometry/audit_geometry.py 与 geometric_components.py、validity/strict_geometry.py。39 份 H 重算与冻结值完全一致。完整积分与采样公式见 mechanisms/REPORT_ZH.md。</p></section>
<section id="t20"><h2>5. T20：能定位主因，不能反推一个目标分数</h2>
<p>T20 底面 IoU＝0.924506，官方 3D IoU＝0.714118；St＝11.588276°，Sb＝0.787850°；Hmean＝0.233596，Hlocal＝0.233905；D＝2.172113°，F＝0.540498°。它以整体低顶为主：自身高度标准差／GT 均高约 0.01040，中心化后的 Hcenter＝0.01066。</p>''')
    add(table(['旧分母或消融', '数值', '解释'], [
        ['顶部 St²/32','4.196504','压低分数的主导项'],
        ['高度 (H*/0.5)²','0.218846','整体低顶已有响应'],
        ['底部 Sb²/32','0.019397','贡献较小'],
        ['旧 Q / 完全去 D,F','16.7216 / 17.0110','D/F 只扣约 0.2894 分'],
        ['max(顶部，高度)','17.4232','去重式组合几乎不解决主导尺度'],
        ['顶部权重 1/4 / 1/16','39.7303 / 60.5640','仍有投影处罚，数字不是人工目标'],
        ['去顶部 / 全局0.5＋局部0.25','73.3926 / 73.3191','保留整体低顶处罚，局部项在本例很小']]))
    add(r'''<p>因此可以排除“原 F 特别大”及“高度代码完全忽略全局低顶”作为 T20 的解释。也没有发现足以解释分数差异的采样问题：8 份关键真实作答提高样本数后，Hlocal 最大变动 7.63×10⁻⁶，F 4.91×10⁻⁵°，St 1.55×10⁻⁵°。</p>
<p>更准确的判断是：顶部投影距离与三维相对高度在本例共同响应，但几何含义和尺度不同；旧组合让投影项占主导。删除 St 是改变评价对象的权重，不是修复一个已经证实的数值 bug。单凭 T20 不能宣布 St 全局冗余。</p>''')
    add(figure('review/figures/B05_geometry.jpg','T20（盲审代号 B05）：冻结共享 x 后几何重新等比例绘制；绿色为固定参考，蓝色为作答。两个正交三维视角使用同一物理尺度。其低顶不因删除 St 而变成正确。'))
    add(r'''<h3>5.1 相同相对高度错误，水平尺度改变</h3>
<p>控制参考墙高和底面形状，只改变房间水平尺度；作答墙高均为参考的 0.8 倍，整体顶界水平。没有给控制样本人工等级。</p>''')
    add(table(['水平尺度', 'Hmean＝Hlocal', 'St / °', '旧 Q', '去顶部 Q'], [
        ['0.5','0.2','9.3758','25.5947','86.2069'],['2','0.2','7.7953','32.6911','86.2069'],['10','0.2','1.9365','78.2968','86.2069']]))
    add(r'''<p>同样 20% 的三维墙高误差被旧分从 25.59 到 78.30 不均匀处罚；反向升高 20% 也有不同角度响应。这是投影与物理结果度量混用的条件效应。若研究最终重建质量，降低 St 可减少这类差异；若研究人员投影定位，丢掉全部投影误差又会遗漏目标信息。不能把“几何敏感”解释成免罚。</p>
<h3>5.2 均高正确仍须处罚局部不平</h3>
<p>下列控制底面完全一致，参考墙高 2.4h，误差幅度 0.72h，各自精确平均墙高仍为 2.4h。Hmean 约为零，但原 Hlocal、F、St 全有响应。</p>''')
    synthetic = {r['case_id']: r for r in read_csv('analysis/results/candidate_scores_synthetic.csv')}
    mean_rows=[]
    for key,label in [('equal_mean_tilted_plane_amp0.72','两低两高的斜平面'),('equal_mean_alternating_corners_amp0.72','高低角交替')]:
        r=synthetic[key]
        mean_rows.append([label,fmt(r['Hlocal'],4),fmt(r['flat']),fmt(r['Q_v11']),fmt(r['Q_no_topS']),fmt(r['Q_top_1_16']),fmt(r['Q_split_local025'])])
    add(table(['控制', 'Hlocal', 'F / °', '旧 Q', '去顶部', '1/16 顶部', '局部 0.25'],mean_rows))
    add(r'''<p>局部单独控制可在几乎不追加处罚 T20 的同时，明显压低大范围斜顶，这是它值得保留为专项候选的几何依据。但控制中的 43.71 或 62.79 不是人类等级；当前真实临界例混有其他错误，尚不足以把局部尺度 0.25 认证为正确权重。</p>
<h3>5.3 局部尖峰、采样、点数、补偿与地平线</h3>
<p>三角尖峰高 1.44h、参考均高 2.4h，支持底周长比例从 0.2 缩小至 0.00002 时，精确局部 RMS 本来就按 √p 缩小；极窄时 4096 点还会完全漏采。最后一例 Hlocal 数值为 0，H* 仅由 Hmean 留下 6×10⁻⁶；将同一峰移到恰好命中的相位，H* 升到 0.009375。St 尚有约 0.40887° 响应，却只让旧 Q 比去顶部低约 0.52 分。H/F 不完整，St 也没有独自解决局部极错。</p>
<p>同一三维线性剖面严格共线加 1 或 40 点，当前 H、F、St 与 Q 在浮点容差内稳定；反例来自官方 IoU 的角点均高代理：非平顶上给低边或高边加 40 点，同一几何曲线的官方值可由 100 变为 72.73 或 78.57。该控制超出恒高房间的理想适用性，说明必须保留基线的定义，而不是据此一概否定它。</p>
<p>底角向地平线移动、top 像素不动时，顶部投影 St 可为零，而重建高度已改变。只移动一个底角 1px，在尺度 0.5、2、10、50 下，去顶部 Q 依次为 99.32、98.26、89.57、23.84。去 St 没有解决 T03 类型的底点深度放大。解析导数为 d(r/h)/dyb＝−(π/512)[1＋(r/h)²]。另一个控制用 top 的变化补偿墙高，使 H/F 约零，但底面 IoU 仍为 0.7440，去顶部 Q 为 73.69；保留范围损失是必要的。</p>
<p>当底面范围变化，最近边不保证为同一墙。构造的等距墙控制只移动 10⁻⁶h 即可切换最近墙，高度 RMS 在约 0.4213 与 0.5348 之间变化；原总分已很低，不能夸大为真实人类等级翻转。固定分量上的连续评分不保证从坐标到分数处处连续。</p>
<p>另一个条件反例把非平顶作答自身作为完全相同参考，H 与 St 均为零，旧 F 仍使 Q 约为 92.67–93.34。它说明自身平顶约束与相对参考一致性不是同一目标。未借此恢复任何已排除真实场景。</p>
<p class="source">全部 71 项预先限定控制、70 可算＋1 跨地平线不可算、各坐标与逐例结果保存在 mechanisms/results/；控制无人工等级。新结果与 8 例采样复核见 mechanisms/CONTROL_CONCLUSIONS_ZH.md。</p></section>
<section id="candidates"><h2>6. 少量可解释组合，同等校准预算</h2>
<h3>6.1 候选与参数的几何含义</h3>
<p>令 A＝100IC，b＝Sb²/32，t＝St²/32，z＝(H*/0.5)²。保留旧式、底面 IoU、作者代码官方 3D IoU、上一轮去顶部及 IHC；比较有限顶部权重 γ∈{0,1/16,1/4,1}、max 组合、全局/局部拆分及两个输入 X 探针。没有扩大原 66 组网格，也没有用求根次数冒充独立临界样本数。</p>''')
    add(table(['候选族', '计算式', '如何解释'],[
        ['有限顶部权重','A/(1+b+γt+z)','γ=1/4、1/16 对应单顶半损失尺度 11.314°、22.627°；γ=0 不使用顶部投影项'],
        ['max 组合','A/[1+b+max(γt,z)]','连续、非减分母、分支处有折点；屏蔽较小损失项，可能减轻共同响应，也可能遮掉独立错误，不能削弱主导大项'],
        ['Hcenter','临时墙高剖面减去 μa−μg 后，沿用同一最近底边机制计算 Hlocal','源坐标不改；不同范围时不是纯方差，也不一般与 Hmean 正交'],
        ['全局/局部拆分','A/[1+b+(Hmean/0.5)²+(Hcenter/s)²]，s∈{0.5,0.25}','分别给均高与中心化残差设置相对高度尺度；0.25 不是人类阈值'],
        ['stage13 两种组合','仅把 C 换成 Cstage，顶部 γ=0 或 1/16','复用历史函数，看过第一批结果后的追加开发探针，非未见数据预注册'],
        ['输入 X 两探针','Q去顶部/[1+(X/8°)²]','只适用于有当前平均前配对输入的原始输入质量；融合端点无来源时为空']]))
    add(r'''<p>Hcenter 核验 109 个有效真实/控制剖面：仅作答墙高整体加 0.3h，以及作答与参考墙高同时乘 1.7 时，相应不变量成立，源点哈希不变；这不声称涵盖任意三维平移或全部几何缩放。S071 的 Hlocal²−Hmean²−Hcenter² 绝对差约 0.01851，不能包装成精确正交分解。全局/局部同用 0.5 与去顶部在旧 24 的排序完全相同；增加表示复杂度尚无排序增益。</p>
<div class="formula">α(u)＝0.15＋0.30 clip((u−1)/2,0,1)<br>
Cstage＝1−0.5[α(D/5) L<sub>D</sub>＋α(F/2) L<sub>F</sub>]</div>
<p>stage13 在 D＝5～15°、F＝2～6° 逐渐加重，再维持系数，C 的极限下界由 0.85 变成 0.55。它连续、对固定 D/F 单调，导数有折点；这些转折来自历史数学尺度，不是新验证的人类转折。现有证据没有证明它比平滑罚项值得增加分阶段解释成本。</p>
<p>上述平方/饱和函数对固定非负分量的行为可解释，误差增大不会提高对应候选分数；但 I、角度、高度随坐标一起改变，真实坐标路径可能补偿、换最近墙或改变范围，不能声称总流程沿任何“像素误差量”都单调。</p>
<h3>6.2 排序、分数尺度、等级切点分开评价</h3>
<p>每种方法对旧 24 份都只校准两个有序切点，按同样 11 栋楼留一楼做开发集内部检验，共 15×11＝165 折。训练端所有最优切点区间都保留，测试端不挑最有利阈值。下表“档差总量”是 24 次留组预测的绝对等级步数之和，其范围来自训练最优切点不唯一，不是置信区间。按一档计一步只是本次统一的比较损失，不表示用户主观档间距已经等距校准。由于候选设计看过开发证据，它仍不是最终独立泛化成绩；旧 95/85/50 未沿用作公平性基准。</p>
<p>末列只是假设 6 份可算犹豫均落“明显”的 54 对条件排序，全部跨图。它帮助显示技术取舍，不是真实新标签、误报率或成功标准。</p>''')
    add(table(['方法','旧24逆序','同图逆序','同预算档差总量','T20分数','犹豫全明显情景'],comparisons))
    add(r'''<p><strong>对比的实质：</strong>去顶部的 19/164 与 3–7 档差具有较好的简洁性；底面 IoU 已有 24/164，说明复杂公式不能只与旧严罚式对比。顶部 1/16 的 22/164、5–10 没有证明折中自动更好。max 未解决主要问题。stage13 虽把逆序降到 16 或 18，档差却为 6–11；排序收益不是等级校准收益。X 两式在此小开发集的档差最低，却受输入对象不同、点数稳定性和高影响例限制。</p>
<p>9 份条件严重的旧分在 2.20～9.50，去顶部在 3.46～17.51；它们没有因去 St 被整体放到旧 24 份前面。旧式、去顶部、1/16、拆分及 stage13 在这组跨问法的 9×24＝216 对桥接中都没有逆序，而单底面及官方 IoU 各有 7 对、IHC 有 3 对。但这不是 216 个独立验证，不是“全部严重必须低于其他案例”的通用目标，也没有估计未审样本的误报率。类型偏倚使这组正例不足以区分多数公式。</p>
<p>IHC 去掉底部 S 后，在“犹豫全明显”的情景中出现 12/54，对照去顶部的 2/54，固定 yq 融合端点也被明显放宽。现有证据没有支持连底部项一起删除；这里不把该情景当决定性人类标签，而是保留其结构损失反例。</p>
<h3>6.3 真正的临界变化，不是伪阈值</h3>
<p>有限 γ 家族中，T09/T22 的分数交叉为 γ≈0.405373；T20/S034 为 γ≈0.094046。这是两个已给定案例的代数排序交叉，既不是惩罚起点，也不是质量等级切点。T20 与 S034 的复核题只问顶部处罚，而两例还有不同底面和采集方式，不能用该回答直接拟合总 Q 的 γ 界限。</p>
<p>64 个可算犹豫相邻情景来自 6 份在“明显/严重”间的变化，其中全严重情景没有跨等级题对，不能把它算作完美分类胜利。S071 的改档可使“局部 0.25 相对去顶部”的逆序差改变 4 对，“stage13 相对去顶部”改变 3 对；S107 可使后者改变 2 对。S032/S052 各只改变这些比较 1 对，S034/S079 不改变这几项严重/明显相容性排序，但 S034 仍对全局与局部顶部处罚有信息。5 份缺几何犹豫不能以强制配对加入这 64 情景。</p>
<p class="source">analysis/protocol_before_candidate_results.json；protocol_structural_addendum_before_results.json；candidate_functions.py；fair_comparison/；sensitivity/。附加 stage13 已明确为适应性的开发探查。独立审阅重建了全部 165 折的最优损失与可行预测集合，结果一致。</p></section>
<section id="representation"><h2>7. 保留当前输入错误，不混淆版本与重建</h2>
<h3>7.1 共享 x 出现在评分之前</h3>
<p>当前正式流先保留原导出，再应用已有删点、补点、配对和改序，得到 before_preprocessing_points。既有 links_zero_based 绑定当前点身份；每对 x 取周期最短弧中点、y 不变，得到 preprocessed_points；ordered_source_* 索引再形成 points_1024x512 的交替环消费视图。quality_v11.score_geometry 使用冻结 top3d/bottom3d，I、St、Sb、H*、D、F 以及官方 IoU 均在共享后结果上计算，没有恢复平均前误差。</p>
<p>consolidate_research_input 验证中点、完整配对与索引视图；apply_quality_review_20261010 按操作回放修改；materialize_current_research_input 区分确认环与默认未审环。本轮 3022 个合法既有配对记录的中点及环视图身份检查均通过，但合法配对不等于全部经过人工配对审查。</p>''')
    add(table(['层', '用于什么', '本轮处理'], [
        ['original_export_points','原始导出与历史错误追溯','保持原字节，不直接当当前输入扣分'],
        ['before_preprocessing_points','当前编辑后、平均前的输入','X 残差及原始球面边界从此层读取'],
        ['preprocessed_points','保留点身份的共享后坐标','验证周期中点和 y 不变'],
        ['points_1024x512 / 冻结三维','当前环与标准化后结果质量','不按 GT 最近角重新配对或换序']]))
    add(r'''<p>3152 条中，3022 条有合法既有 ERP 配对、86 无配对、43 当前空点、1 越界；2401 条有被平均归零的非零方位差。这是表示机械计数，不是 2401 份严重或错误。32 条原导出与当前输入不同：17 删除、6 补点、9 当前为空；被修复的旧错误不再次进入当前罚项。</p>
<p>开发描述池采用正确资格过滤后为 907 条、83 图、19 栋楼、24 人；其中 143 条有显式范围适用标记，764 条未知，未被认证全部可正式使用。645 条当前输入 X 非零，只作现象计数。原留出只核对机械身份和暴露，未计算新的质量幅度用于调参。</p>
<div class="formula">δ<sub>i</sub><sup>px</sup>＝((x<sub>b,i</sub>−x<sub>t,i</sub>＋512) mod 1024)−512<br>
δ<sub>i</sub><sup>deg</sup>＝δ<sub>i</sub><sup>px</sup>·360/1024<br>
X<sub>RMS</sub>＝√mean(δ²)，X<sub>max</sub>＝max|δ|</div>
<p>差值是上下成对方位不一致，单位为度；不是墙偏离铅垂的实体三维角度。对跖中点不唯一时拒绝，配对缺失时为未知。源点的同角色证据、遮挡、真实斜棱或全景未调平都会影响解释，非零不是坏标注的通用判据。</p>
<h3>7.2 有新增信息，但直接入分证据仍脆弱</h3>
<p>控制中一对上下各反向移 8px 后，共享结果仍与参考完全相同，Q＝100，D/F≈0；X_RMS＝2.8125°、X_max＝5.625°。两种 X/8° 候选分别变为 89.00 与 66.92。这证明残差信息不能由 D/F 恢复，不证明应扣 11 分或 33 分。共同移动、仅 top 移动、仅 bottom y 移动、周期接缝和非法对跖分别检验，不能把它们当同一种扰动。</p>
<p>在局部连续方位坐标中，两个端点相对同一竖直参考的等权平方误差满足 (et²＋eb²)/2＝m²＋δ²/4，m 为平均误差。该恒等式解释丢失信息，不赋予两端相等可靠性。8°只是与旧角度半损失尺度在小角、近地平线条件下对应的有限探针，不是边界均值指标的精确恒等权重。</p>
<p>本轮重新计算 922 条原始球面边界。907 条描述池中，原始综合 S 比共享 S 大、小、相同分别为 367、278、262；将旧 S 直接换成原始 S、其他参数不动，旧 24 的逆序只从 42 变 41。原始边界提供不同输入信息，但没有足够收益支持直接替换所有评分表示。</p>
<p>新增 X 与既有分量可能共同响应。907 条上 X_RMS 与 D、F 的 Spearman 约 0.445、0.548，相关性不是独立性或重复计罚证明；仅 top 移动同时改变平均 x、重建与 X 的控制，也显示不能机械相加并宣称完全互补。相反，上下反向抵消的控制确有处理后指标完全不响应的分量。</p>
<p><strong>冗余点反例必须保留。</strong>同一输入曲线在好边加 40 个共线配对，X_RMS 从 2.8125 降为 0.8480°，共享 Q 不变；在另一段加点，X_RMS 变 3.6082°，X_max 从 5.625 变 6.0514°，共享旧 Q 也从 100 变 98.2268。按点取 max 只在新增残差不超旧极值时稳定；共享后逐点投影再连线与先细分曲线不交换。不能声称这两个 X 总分天然对冗余点稳定。</p>
<h3>7.3 T07 是高影响真实例，也有混杂</h3>
<p>T07 去顶部为 74.70，加入 X_RMS 后 63.45、X_max 后 47.07；X_max 对旧 24 共修正 6 对、损失 1 对，其中 3 对修正牵涉 T07。局部原图却显示上、下角分别靠近两个相邻参考转角，共享 x 生成中间竖线，同时有底点 y 偏差、局部转折未表达及壁炉附近分段问题。它是结构对应与定位混合案例，不是独立水平误差的纯验证。没有重新配对来获得更高分。</p>''')
    add(figure('review/figures/B07_details.jpg','T07（B07）：橙色为当前平均前输入，蓝色为共享后，绿色为固定参考。两个相邻转角之间的压缩不能由“上下 x 差多少”单独解释。'))
    add(r'''<p>89 份原严重筛选的冻结画面实际显示共享后的坐标，另外 26 份非冻结显示原导出。不能因为原选样文件保存 raw_annotation_sha256，就声称审核者在全部题目中已看过平均前 x。当前复核材料明确把两层同时呈现。</p>
<p class="source">本轮输出 representation/results/；对应来源代码 study_x/source/。原始 S 与 X 控制见 controlled_x_*、raw_boundary_*；新 X 入分及高影响对见 analysis/representation_and_pool/。独立诊断建议已获真实与受控证据支持，总分尺度尚未冻结。</p></section>
<section id="review"><h2>8. 只问能改变技术决定的少量问题</h2>
<p>用户盲审版有 7 份作答、6 张原图、22 张图、5 组问题，最后一组可选。隐藏题号映射、人员、方法、分数与预期答案；允许相近、介于两档、不确定及参考有问题。原图默认展开，当前平均前后叠线、局部放大、底面和两个正交 3D 视图俱全。图均为冻结结果重绘，未把辅助预览或中心化统计当成新正式重建。七份共 35 对现有配对，反投影最大误差约 1.14×10⁻¹³px。</p>''')
    add(table(['问题 / 作答', '需要判断', '回答如何影响技术决定'], [
        ['P01：T22 / T09（B01/B02），同图', '整体哪份更接近合理质量；也可相近/问题不同/无法判断', 'T22 更好支持当前范围与斜跨权衡不足；T09 更好削弱旧单题逆序反例；相近提示不宜用该对拟合 γ'],
        ['P02：S071（B03）', '明显、介于两档、严重，及主要可见问题', '若偏严重，增强局部或结构的候选更可接受；若偏明显，需防止混合错误导致整体压得过低。不能把回答当纯高度阈值'],
        ['P03：S107（B04）', '原固定淋浴间范围下，门外延伸与点位问题的严重程度；可指出参考问题', '直接约束结构阶段加重的代价；ERP 低 y 直觉不得替代真实高度核查'],
        ['P04：T20 / S034（B05/B06）', '仅比较顶部问题应受处罚的程度，可无法排序', '区分全局低顶与局部高低；支持进一步检验 Hcenter 独立尺度，不直接给总 Q 次序或 γ 阈值'],
        ['P05：T07（B07），可选', '看平均前点位是否改变对处理后结果的整体评价，或应分别报告', '帮助决定 X 是否属于总分对象。若分别评价更合理，优先保留输入/结果双报告']]))
    add(r'''<p>S032、S052、S079 可暂缓，不阻止候选推进：本轮它们对主要候选差距的相邻档影响较小；不能把“低选例优先级”写成已经合格。5 份未恢复配对的犹豫先保留待定，若要用于三维校准，应先取得原标注关系或有效的人工配对记录。无需用户先重审全部 11 或 115 份。</p>
<p>S107 的原图核查有重要修正：新增门外 top 点的 ERP y 较大，重建相机以上高度却为 +0.88568h，高于其他点 +0.50432～+0.59506h。底点落在洗手柜立面附近而非可见墙地交界，实际角被遮挡。它混有对象范围和底点深度，不是纯 top 点错。S071 同样混合范围、漏角、斜跨及高度。</p>''')
    add(figure('review/figures/B01_B02_same_scale_geometry.jpg','同图 T22（B01）与 T09（B02）：跨两份共用坐标轴范围和视角。图像长宽比不替两份分别自适应缩放。范围缩短与斜跨属于不同错误，当前标量权衡正待复核。'))
    add(r'''<p class="source">用户版 review/review_blind_user_20261012.html；研究版 review/review_researcher_20261012.html；所有新答卷字段为 null。此批已曝光开发材料不作新独立测试。</p></section>
<section id="fusion"><h2>9. 回接人员与固定融合结果：方法选择会改变解释</h2>
<p>本轮找到了 3 个不同图片的已保存完整几何端点，共 4 个展示行（yq 的自动/协助行几何相同）；比较其 67 份成员作答，来自 24 人。338 对成员坐标与当前正式输入逐项相同，最大差为 0px；没有重新运行融合、增加人数或换成员。全部仍条件于当前固定参考与环状态。</p>''')
    add(table(['固定端点', '人数', '旧 Q', '去顶部 Q', '1/16 顶部 Q', '旧→去顶部，端点高于成员数'], [
        ['B6ByNegPMKs-11',23,'37.72','67.74','64.53','17/23 → 15/23'],
        ['yqstnuAEVhm-31',21,'17.17','25.69','24.92','13/21 → 13/21'],
        ['wc2JMjhGNzB-59',23,'62.60','84.34','82.55','17/23 → 22/23']]))
    add(r'''<p>67 份成员在各自同图内共有 716 对，其中 10 对旧同分；706 对旧严格次序中，改去顶部后 129 对反转，分别为 37、5、87 对。数字显示分数定义足以改变同图人员与融合相对位置，不证明新顺序更正确。匿名人数总曲线或人员长期水平不能从三个端点推导。</p>
<p>yq 端点 F≈1.02°，但 D≈21.42°，仍有漏角及长斜跨；去顶部为 25.69，进一步去底部 S 的 IHC 升到约 54.30。规整的顶面不足以代表结构正确，单纯降低顶部或删除全部边界都需要检查结构代价。</p>
<p>端点没有独立的平均前人员输入层，X 两候选在端点处为 null，不把共享 x 的天然一致当成人类完美输入。下一步若要研究人数曲线，最少需要已有、冻结的各 k / 成员组成输出：成员 ID 与版本、点位与环、GT 版本及范围/顶界状态、分组、失败状态、代码与几何哈希、人工介入日志。现有三个端点不足以恢复真实人数轨迹；本轮未重做融合。</p>
<p class="source">evidence/results/fixed_fusion_*、fixed_demo_*；repo_snapshot/analysis_results/consensus_delivery_20261008/。固定作者代码 IoU 与新计算最大差约 1.67×10⁻¹⁵。</p></section>
<section id="exploration"><h2>10. 指定问题完成后的自由探索：精确幅度＋影响周长</h2>
<p>自由探索在 A/B/C 及必要数值任务完成后开始，阶段标记记录为 2026-10-11 14:40:30 UTC。只提出一项有验证的新建议：在审核详情并列报告精确高度幅度和超过若干显示尺度的底周长比例，暂不增加新罚项。</p>
<div class="formula">A<sub>range</sub>＝(max h<sub>a</sub>−min h<sub>a</sub>)/μ<sub>g</sub><br>
A<sub>peak</sub>＝max |h<sub>a</sub>−μ<sub>a</sub>|/μ<sub>g</sub><br>
P<sub>a</sub>(τ)＝长度比例{|h<sub>a</sub>(s)−μ<sub>a</sub>| &gt; τμ<sub>g</sub>}，τ∈{0.10,0.20,0.40}</div>
<p>沿既有底边线性墙高与 ±τμg 的交点精确积分，计算量 O(角点数)，不使用全周采样网格；参考自身幅度和支持也列出。所谓精确是分段线性模型内的解析积分，仍受输入、范围和重建假设限制。显示尺度不是合格、严重或人工容忍度。</p>
<p>70 项有效控制＋39 份真实剖面共 109 份有效输入，另 1 项不可算保留空值。327 项环反向、循环起点及严格共线加点不变性最大差 3.55×10⁻¹⁵；36 项三角峰独立解析核对最大差 5.55×10⁻¹⁷。同样高达 GT 均高 60% 的窄峰始终显示幅度 0.6，同时保留非常小的支持范围。最窄例 P(0.10)＝0.00166665% 底周长，不随采样相位消失；不会把局部窄峰和广泛同幅错误混同。</p>''')
    add(table(['真实例', 'Hmean', '高度跨度/μg', '超过0.10μg的底周长', '新增解释'],[
        ['T20','0.23360','0.04244','0','整体低顶，局部起伏小'],
        ['S034','0.11343','0.18742','0.07459%','最大偏差仅略过显示尺度，不宜据小支持取消处罚'],
        ['S107','0.02437','0.23863','12.95164%','均高小不能代替范围和局部核查'],
        ['S071','0.35144','0.70095','83.30880%','广泛高度起伏，但混有结构范围'],
        ['T19','0.00363','0.78003','76.30586%','均值互抵；旧 Hlocal、F 已响应，诊断增加可读范围'],
        ['S001（已确认严重）','0.04538','0.03406','0','反例：严重结构问题可以没有明显高度起伏']]))
    add(figure('exploration/figures/real_height_amplitude_support.png','开发实例的幅度与支持。三个显示尺度只是可读几何刻度；0 支持不代表合格。参考自身列同时保留，不将非平顶参考差异掩掉。'))
    add(r'''<p><strong>失败与成本：</strong>9 严重中 8 份三个支持均为 0；这是它不能作严重筛选器的直接反例，而不是一个新分类器的漏报率。非平顶参考与自身完全相同也可显示大幅度、大支持，不能当相对参考错误。底点近地平线而 top 未动，也可产生很大重建跨度，不能归咎于人员把 top 画歪。不同范围改变周长权重。算法成本低，无训练数据需求，收益限于可观察性和表示稳定性，未证明提高总分排序或人员分类。</p>
<p class="source">exploration/exact_height_support.py、run_exact_height_support.py、results/amplitude_support_all_110_rows.csv、representation_invariance_327.csv、triangular_spike_analytic_checks.csv。无新增质量分数或人工标签。</p></section>
<section id="decision"><h2>11. 优先方案、可用范围与最少冻结证据</h2>
<h3>11.1 当前可以推进的三个决定</h3>
<ol><li><strong>重建总分先保留两个小方向：</strong>去顶部 S 作为最简主研究候选；全局 0.5／中心化局部 0.25 作为“低顶不过度、广泛起伏仍可更重”的专项候选。它们都有可运行代码、真实对照与受控结果，但后一尺度仅为研究探针，尚不正式部署。1/16 顶部保留为投影内容是否仍需进入总分的对照，不把折中视为自动更优。</li>
<li><strong>立即改研究报告层：</strong>当前编辑后平均前的周期 X 残差、原始球面边界、来源与配对状态，与共享后重建质量分开呈现。物理范围/对象状态另列。这个修改保留真实信息，已在 T07、受控反向移动及 907 描述记录中验证；不把非零残差自动变成处罚。</li>
<li><strong>高度解释加入精确幅度/支持诊断：</strong>保留 Hmean、Hlocal、F 的既有内容，并补上极窄峰的可读幅度与范围。暂不加入新总分惩罚。它的失败案例和 O(n) 成本均已核验。</li></ol>
<p>暂不优先采用 max 去重、IHC 删两项、stage13 或 X/8° 自动入总分。它们没有全部被否定；目前各自的新增收益不足以覆盖明显失败或解释成本。无需拟合复杂有序模型：旧 24 个不确定开发标签加 9 个类型偏倚严重正例，不能识别许多高度、结构、图片条件与人员效应系数。当前两个切点的公平简单校准已经显示不唯一性，漂亮拟合不会补上参考验收和同图标签缺口。</p>
<h3>11.2 哪些参数已有支持，哪些还不能冻</h3>''')
    add(table(['项目','现在可支持的范围或性质','仍不能据此确定'],[
        ['顶部 γ','{0,1/16,1/4,1} 有限族已复算；相对旧 γ=1，降低其主导作用有开发证据','唯一 γ；0.405373 等单对交叉不是通用人类界限'],
        ['全局/局部高度尺度','0.5 与局部 0.25 对应可解释相对 RMS 半损失；局部独立控制在合成斜顶上有效','0.25～0.5 不是已认证人类容忍区间，端点间未做连续最优搜索'],
        ['D/F 分阶段','5→15°、2→6° 的函数连续单调且极限明确','缺人类转折证据，旧24同预算档差不支持优先替换'],
        ['输入 X','周期残差有信息；必须绑定当前版本、配对与遮挡解释','8°、RMS或max的唯一选择及默认权重'],
        ['质量等级','所有方法用同样两个切点预算做了开发留楼检验','旧95/85/50、最低合格线、严重等级切点均未冻结'],
        ['自由诊断 τ','0.10/0.20/0.40 是已有解析实现的显示刻度','不是人工等级阈值或全局质量分类器']]))
    add(r'''<h3>11.3 冻结论文方法的最少下一步</h3>
<p>第一，完成本包 P01～P04 的定向复核，P05 可选；优先解决同图范围/斜跨、混合严重边界及全局/局部顶部权衡，不要求全库重审。第二，把拟参与比较的 9 严重、6 犹豫及对应参考做有限范围与环验收；不自动消除其 not_recorded。第三，补少量同图或相近条件的真对照，覆盖“完整规整但稍偏”“均高对但广泛斜顶”“局部尖峰”“漏凹角却规整”，且至少包含经审核的非严重对照，才有资格讨论严重误报。</p>
<p>第四，在这些开发复核后冻结最多两个标量候选、输入版本及参考选择规则，再审计原留出暴露史并进行分组验证；当前 103 份不能直接认证干净，也不能重新挑一个有利测试集。每组和每图作为相关单位报告，不把题对当独立样本。第五，明确论文主分衡量最终重建结果，输入定位与任务对象状态另报，避免把投影条件放大都称作人员三维不规整。若将来做人员长期水平与波动，需要人员跨图覆盖；同图重复噪声另需重复标注数据，当前不能完整分解。</p>
<p>这些是具体未闭合证据，而不是要求无限补样。已有数值足以推进可运行候选、诊断层与小复核；不足之处主要集中在少数主观取舍、参考适用性和独立验证。</p></section>
<section id="reproduce"><h2>12. 复现、保留边界与来源</h2>
<p>独立交付目录包含配置、冻结源输入、当前审核覆盖、逐例结果、图册与代码。根目录运行 <code>python run_reproduction.py</code>：在新的工作目录中校验输入、重算指定数值链，并与交付期望结果比较；从不覆盖随包历史分数或原始点。依赖及可选重绘步骤见 <code>README_ZH.md</code> 与 <code>requirements.txt</code>。外部原图库的完整字节核验另有清单及入口，需要原 6 个 ZIP；最小包自身可复算数值并重绘 6 张选定原图。</p>
<p>主要入口：<code>analysis/candidate_functions.py</code> 只接收分量、不含人员ID或标签；<code>mechanisms/centered_height.py</code> 计算中心化参考残差；<code>exploration/exact_height_support.py</code> 无评分。<code>analysis/INDEPENDENT_REVIEW.json</code> 记录独立审阅及防护修复；<code>FILE_MANIFEST_SHA256.json</code>、复现日志和逐例 CSV/JSON 可追溯每项结论。</p>
<p><strong>实际封包复现：</strong>2026-10-11 UTC 已在新的独立目录执行 22 个固定步骤，含数值链、6 原图的盲审/研究版重绘及固定融合端点图。104 个 JSON/CSV、65,359 个数值比较全部一致，最大数值差为 0，输入文件未变。这证明代码与交付可再现，不证明质量定义或人类阈值已经成立；复现没有重读未随包的全部原图 ZIP。</p>
<p>明确没有做的工作：没有恢复禁止参考、补造未确认顶界、给 W019 强制配对、给未审查记录加负标签、替用户修改等级、重新融合、从单端点构造人数曲线、用留出挑参数或建立复杂人员因果模型。原数据、旧回执、旧公式结果及正式资格均保留。</p>
<h3>原论文与作者代码</h3>
<p>官方 HoHoNet 的代码要求上下共享 x，使用固定相机高度、底面交并与<strong>角点平均高度的恒高棱柱代理</strong>计算 3D IoU；不等于任意非平顶真实体积交并比。本轮采用冻结作者提交 <code>2bbc0866789cf7ad728064bc52aaf1d11b67c885</code>，与当前作者代码定义核对，并保留其 LICENSE。基线与新公式有同等等级校准预算。[L1]</p>
<ol class="references"><li id="l1">[L1] Cheng Sun, Min Sun, Hwann-Tzong Chen. <em>HoHoNet: 360 Indoor Holistic Understanding With Latent Horizontal Features.</em> IEEE/CVF CVPR, 2021, pp. 2573–2582. <a href="https://arxiv.org/pdf/2011.11498">论文 PDF</a>；<a href="https://github.com/sunset1995/HoHoNet/blob/2bbc0866789cf7ad728064bc52aaf1d11b67c885/eval_layout.py">冻结作者评估代码</a>。本轮已读取作者代码及 arXiv 全文 HTML；CVF PDF 直开失败，未假称读到该直链字节。</li>
<li>[L2] Cheng Sun, Chi-Wei Hsiao, Min Sun, Hwann-Tzong Chen. <em>HorizonNet: Learning Room Layout With 1D Representation and Pano Stretch Data Augmentation.</em> IEEE/CVF CVPR, 2019, pp. 1047–1056. <a href="https://arxiv.org/pdf/1901.03861">论文 PDF</a>。边界及角点的一维表示提供表示背景，不构成原始质量必须共享 x 的依据。</li></ol>
<p>文献事实与代码定义在此标注为来源事实；原人工选择和旧结果为历史证据；表格及对照为本轮实际计算；推荐优先级为研究判断；人工阈值、总体严重发生率及泛化仍未识别。</p></section>''')
    css = '''
    :root{--ink:#172b3a;--muted:#526675;--accent:#137f80;--line:#d7e1e8;--paper:#fff;--soft:#edf5f5}
    *{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#eef2f5;color:var(--ink);font:17px/1.85 system-ui,-apple-system,"Noto Sans CJK SC","Microsoft YaHei",sans-serif}
    main{max-width:1220px;margin:30px auto;padding:50px 58px;background:var(--paper);box-shadow:0 8px 42px #1c3a5010}h1{font-size:40px;line-height:1.25;margin:14px 0 22px}h2{font-size:28px;line-height:1.4;margin:0 0 25px;border-bottom:2px solid var(--accent);padding-bottom:13px}h3{font-size:22px;margin:32px 0 13px}p{margin:14px 0}.eyebrow{font-size:14px;color:var(--accent);letter-spacing:.08em}.lead{font-size:22px;line-height:1.65;font-weight:650}.meta,.source,figcaption{color:var(--muted);font-size:14px}.source{border-left:3px solid var(--line);padding:6px 12px;overflow-wrap:anywhere}
    nav{display:flex;flex-wrap:wrap;gap:10px 22px;padding:20px 0;margin-bottom:25px;border-block:1px solid var(--line)}a{color:#096974;text-decoration:none}a:hover{text-decoration:underline}section{margin:48px 0 65px;scroll-margin-top:20px}.callout{background:var(--soft);border-left:5px solid var(--accent);padding:10px 22px}.formula{background:#f3f6f9;border:1px solid var(--line);padding:17px 22px;margin:23px 0;line-height:2;font-size:17px;overflow-wrap:anywhere}
    .tablewrap{overflow-x:auto;margin:24px 0}table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.6}th,td{padding:12px 13px;border:1px solid var(--line);text-align:left;vertical-align:top}th{background:#e9f1f4;font-weight:650}tbody tr:nth-child(even){background:#f9fbfc}code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.85em;overflow-wrap:anywhere;background:#eef2f5;padding:2px 4px}li{margin:13px 0}figure{margin:30px 0}img{width:100%;height:auto;border:1px solid var(--line)}figcaption{margin-top:9px}.references{font-size:15px;overflow-wrap:anywhere}footer{margin-top:45px;border-top:1px solid var(--line);font-size:13px;color:var(--muted);padding-top:15px}
    @media(max-width:760px){body{font-size:16px}main{margin:0;padding:27px 20px}h1{font-size:31px}h2{font-size:25px}h3{font-size:20px}th,td{padding:10px 9px;min-width:80px}.lead{font-size:20px}}
    @media print{body{background:white}main{box-shadow:none;margin:0;padding:0;max-width:none}nav{display:none}section{break-before:auto}h2,h3{break-after:avoid}figure,tr{break-inside:avoid}a{color:inherit}img{max-height:240mm;object-fit:contain}}
    '''
    output = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>顶部与结构惩罚研究｜轮次 20261012</title><style>' + css + '</style></head><body><main>' + '\n'.join(parts) + '<footer>报告构建时间（UTC）：' + html.escape(now) + '。此 HTML 自包含图像，无需网络即可阅读。科学结果以随包冻结表及复现记录为准。</footer></main></body></html>'
    (ROOT/'quality_top_structure_report_20261012.html').write_text(output, encoding='utf-8')
    findings = {
        'schema':'top_structure_conclusions_v1','round_id':'20261012','created_at_utc':now,
        'main_sha':'38e259c043fed0817307dbc3d21c6dba06bd6662',
        'new_user_grades_created':0,'formal_algorithm_replaced':False,'fusion_recomputed':False,
        'evidence_counts':{'old_quality':24,'conditionally_scorable_severe':9,'conditionally_scorable_pending':6,'numeric_labeled_records':39,'images':30,'buildings':14,'synthetic_valid':70,'synthetic_unavailable':1,'unlabeled_development':907,'images_in_technical_archive_check':261,'selected_visual_originals':6},
        'primary_research_candidates':['Q_no_topS','Q_split_local025'],
        'projection_content_control':'Q_top_1_16',
        'immediate_diagnostic_recommendations':['current_edited_pre_average_cyclic_pair_residual_with_source','separate_input_and_processed_result_quality','exact_height_amplitude_and_perimeter_support'],
        'not_recommended_as_default_yet':['Q_max_old','Q_max_quarter','Q_IHC_h050','Q_no_top_stage13','Q_top_1_16_stage13','Q_no_top_Xrms8','Q_no_top_Xmax8'],
        'grade_cutpoints_frozen':False,'human_penalty_thresholds_frozen':False,'holdout_clean_certified':False,
        'critical_reviews':['T09/T22','S071','S107','T20/S034','T07_optional'],
        'old24_ranking':{'v11':42,'no_top':19,'denominator_pairs':164,'independent_pairs':False,'same_image_pairs':2,'same_image_v11_inversions':0,'same_image_no_top_inversions':1},
        'candidate_summary':[{'method':m,'name':n,'inversions':int(ranking[m]['inversions']),'held_development_step_loss_range':[calibrated[m]['total_held_absolute_step_loss_min'],calibrated[m]['total_held_absolute_step_loss_max']]} for m,n in methods],
        'limitations':['selected_noisy_labels','protocols_not_interchangeable','unreviewed_are_not_negatives','geometry_and_reference_conditional','severe_type_bias','group_exposure_preserved','synthetic_not_human_error_distribution','global_and_local_heights_not_orthogonal_for_general_footprints']}
    (ROOT/'CONCLUSIONS_MACHINE_READABLE.json').write_text(json.dumps(findings,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'report':str(ROOT/'quality_top_structure_report_20261012.html'),'bytes':len(output.encode()),'tables':output.count('<table>'),'figures':output.count('<figure>'),'methods':len(methods)},ensure_ascii=False))


if __name__ == '__main__':
    main()
