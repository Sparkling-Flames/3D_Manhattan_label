#!/usr/bin/env python3
"""Render the frozen forward-profile results as a self-contained Chinese report."""
import argparse
import html
import json
from pathlib import Path

import pandas as pd


def table(frame, digits=3):
    return frame.to_html(index=False, border=0, classes='data', na_rep='—',
                         float_format=lambda x: f'{x:.{digits}f}', escape=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, default=Path('work_v2_20261019/profiles'))
    out = ap.parse_args().out
    cmp = pd.read_csv(out/'paired_model_comparison.csv')
    info = pd.read_csv(out/'fine_information_controls.csv')
    persons = pd.read_csv(out/'人员画像与候选细类60人.csv')
    membership = pd.read_csv(out/'fine_dtype_membership.csv')
    efficiency = pd.read_csv(out/'efficiency_within_person_diagnostics.csv')
    audit = json.loads((out/'AUDIT_CHECKS.json').read_text())
    main_cmp = cmp[cmp.metric.eq('B8L2') & cmp.baseline.eq('FE') &
                   cmp.model.isin(['joint20', 'joint0', 'joint80', 'centered_mean',
                                   'rank_calibrated', 'raw_mean', 'class_Q2', 'class_Q3']) &
                   cmp.difficulty.eq('all')].copy()
    main_cmp = main_cmp[['model','n','images','buildings','improvement_percent','ci_low','ci_high','improved_buildings']]
    main_cmp['model']=main_cmp['model'].replace({'joint20':'三难度部分汇聚 λ20','joint0':'三难度独立 λ0','joint80':'三难度部分汇聚 λ80','centered_mean':'同任务中心差均值','rank_calibrated':'同任务百分位（训练校准）','raw_mean':'原始个人均分','class_Q2':'Q2 二类中心','class_Q3':'Q3 三类中心'})
    main_cmp.columns = ['候选','作答','图片','建筑','MSE降低%','区间下界%','区间上界%','改善建筑数']
    dif_cmp = cmp[cmp.baseline.eq('FE') & cmp.model.eq('joint20')][
        ['metric','difficulty','n','images','buildings','improvement_percent','ci_low','ci_high']].copy()
    dif_cmp['difficulty']=dif_cmp['difficulty'].replace({'all':'整体','easy':'简单','medium':'中等','hard':'困难'})
    dif_cmp.columns = ['计量','难度','作答','图片','建筑','MSE降低%','区间下界%','区间上界%']
    fine_parent = cmp[cmp.metric.eq('B8L2') & cmp.baseline.eq('class_QT_theta') &
                      cmp.model.eq('class_fine_dtype') & cmp.difficulty.eq('all')][
        ['baseline','model','n','images','buildings','improvement_percent','ci_low','ci_high']]
    fine_control = info[info.metric.eq('B8L2') & info.difficulty.eq('all') &
                        ((info.baseline.eq('class_QT3') & info.model.eq('class_fine_dtype')) |
                         (info.baseline.eq('FE') & info.model.eq('FE_plus_fine_dtype_delta'))) ][
        ['baseline','model','n','images','buildings','improvement_percent','ci_low','ci_high']]
    fine = pd.concat([fine_parent,fine_control],ignore_index=True)
    names={'class_QT_theta':'Q2×T2 的分难度中心','class_QT3':'Q3×T3','class_fine_dtype':'Q2×T2×难度类型','FE':'连续全局任务调整Q','FE_plus_fine_dtype_delta':'连续Q＋細类共有难度偏差'}
    fine['baseline']=fine['baseline'].replace(names);fine['model']=fine['model'].replace(names)
    fine.columns = ['基线','候选','作答','图片','建筑','MSE降低%','区间下界%','区间上界%']
    members = membership[membership.metric.eq('B8L2') & membership.scheme.eq('fine_dtype')][
        ['label','workers','members','images','buildings','status']].copy()
    members.columns = ['候选细类','人数','实际成员','支持图数（并集）','支持建筑（并集）','状态']
    eff = efficiency[efficiency['sample'].eq('all_positive') & efficiency.outcome.eq('B8L2') &
                     efficiency.panel.isin(['source_manual_v1','source_manual_new','target_manual_418'])][
        ['panel','adjustment','n','images','buildings','effect_for_doubling_seconds','doubling_ci_low','doubling_ci_high']].copy()
    eff['panel']=eff['panel'].replace({'source_manual_v1':'旧来源普通Manual','source_manual_new':'新来源普通Manual','target_manual_418':'同目标Manual（重叠子集）'})
    eff['adjustment']=eff['adjustment'].replace({'task_FE':'只调任务','task_and_worker_FE':'任务＋人员'})
    eff.columns = ['时间面板','调整方式','作答','图片','建筑','时长加倍关联Q差','区间下界','区间上界']
    display_cols = ['人员','来源','普通Manual图数','普通Manual建筑数','B8L2均分','B8L2低10分位',
                    '任务调整Q效应','源时间中位秒','源时间相对三类','难度类型候选','困难图数','困难建筑数',
                    '困难实际均分','困难调整Q','困难减简单效应','困难减中等效应','细类候选',
                    '细类留建筑标签一致率','边界与缺失说明']
    all_people = table(persons[display_cols].copy(), 2)
    person_json = persons.to_json(orient='records',force_ascii=False).replace('<','\\u003c')
    audit_text = html.escape(json.dumps(audit,ensure_ascii=False,indent=2))
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>v2 人员 Q、T 与难度：独立复算</title><style>
:root{--ink:#162d39;--muted:#556873;--line:#dbe5e9;--bg:#f3f7f8;--teal:#137f87;--warm:#b96336}*{box-sizing:border-box}body{margin:0;font:16px/1.75 system-ui,'Microsoft YaHei',sans-serif;color:var(--ink);background:var(--bg)}main{max-width:1280px;margin:auto;padding:32px 28px 70px}h1{font-size:32px;line-height:1.3;margin:0 0 16px}h2{font-size:24px;margin-top:0}h3{font-size:18px}p{margin:12px 0}section{background:white;border:1px solid var(--line);border-radius:12px;padding:24px;margin:22px 0}header{padding:18px 0}nav{display:flex;gap:14px;flex-wrap:wrap;font-size:14px}a{color:#0c718b;text-decoration:none}a:hover{text-decoration:underline}.meta,.muted{color:var(--muted);font-size:14px}.tag{display:inline-block;background:#e1f1f0;padding:3px 9px;border-radius:6px;font-size:13px}.note{border-left:4px solid var(--warm);padding:10px 16px;background:#fff6ef}.good{border-left:4px solid var(--teal);padding:10px 16px;background:#edf7f7}.scroll{overflow:auto;margin:16px 0}.data{border-collapse:collapse;width:100%;font-size:14px;line-height:1.5}.data th,.data td{text-align:left;border-bottom:1px solid var(--line);padding:10px;vertical-align:top}.data th{background:#eef4f5;white-space:nowrap}.data tr:hover td{background:#f8fbfc}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}.card{border:1px solid var(--line);border-radius:9px;padding:16px;background:#fafcfc}.card strong{font-size:25px;color:#0a6e79;display:block}.card small{font-size:14px;color:var(--muted)}select,input{border:1px solid #bdcdd4;border-radius:6px;padding:9px;font:inherit;background:white}input{min-width:270px}code{font-size:13px;background:#eef3f5;padding:2px 5px;border-radius:4px}pre{white-space:pre-wrap;font-size:13px;line-height:1.5;background:#f3f7f8;padding:16px;border-radius:8px}li{margin:8px 0}#person-summary p{margin:7px 0}svg text{font:13px system-ui,sans-serif}#people-table .data{min-width:2100px}summary{cursor:pointer;color:#0c718b;font-weight:600}footer{font-size:14px;color:var(--muted)}@media(max-width:650px){main{padding:18px 12px}section{padding:18px}h1{font-size:26px}}</style>
<main><header><span class="tag">GitHub main 冻结输入 · v2 · 普通 Manual 主层</span><h1>人员 Q、T 与难度：独立复算</h1>
<p>核心判断：保留连续任务调整 Q 与有限难度适应画像，粗类用于沟通，细类作为本轮团队构成试验的候选。难度带来小幅建筑外增益；把连续画像压成类别会丢信息。人员细类能否解释换人和融合，必须由团队实验另行回答。</p>
<div class="meta">输入提交 <code>82c6164b0d4630de5316199c92aa405930973168</code>；规则在新 v2 融合结果之前冻结。本文全部表格由实际输出自动嵌入，可离线打开。</div>
<nav><a href="#decision">采用判断</a><a href="#coverage">覆盖</a><a href="#methods">方法与隔离</a><a href="#validation">楼外结果</a><a href="#fine">细类增益</a><a href="#people">60 人画像</a><a href="#time">效率</a><a href="#version">v1 / v2</a><a href="#replay">复现入口</a></nav></header>
<section id="decision"><h2>1. 采用判断与评价框架</h2>
<div class="scroll"><table class="data"><tr><th>内容</th><th>本轮判断</th><th>用途与限制</th></tr>
<tr><td>绝对 Q + 同任务调整 Q</td><td>采用为基础画像</td><td>均值、中位数、低尾、波动和分项描述实际交付；任务效应 β 描述相对同任务同伴。二者并列，不加权为两份独立证据。</td></tr>
<tr><td>部分汇聚难度 θ</td><td>采用为连续候选与组队试验输入</td><td>λ=20 比全局 β 的建筑等权相对预测 MSE 降低约 1.26%；简单图无收益，困难方向支持有限。保留三个难度、两种困难对照与支持量。</td></tr>
<tr><td>Q3 与 QT 粗类</td><td>可用于解释，不能替代连续值</td><td>Q3 为 β 的 ±3 分，QT 为 Q2×相对 T2；边界者同时显示区间。Q2 单独压缩损失明显，不作总榜或永久人群。</td></tr>
<tr><td>Q×T×难度类型</td><td>保留未合并与合并两种探索候选</td><td>相对四类 QT 有改善，但与已冻结 Q3×T3 的单人预测基本持平；收益相当部分来自恢复 Q 幅度。稀疏类型不凑人、不反调阈值。</td></tr>
<tr><td>独立三难度模型</td><td>不采用为主线</td><td>本轮 λ=0 总体略退；旧开发集“难图约 4.9%”也仅 3/9 栋改善。部分汇聚更符合现有支持量。</td></tr>
<tr><td>T、Semi、scope、排除</td><td>分轴保留，不揉进 Q 或一个总分</td><td>T 是效率与成本；Semi 纠错须有机会和初始化；scope 的倾向、相容裁定、空间选择分开；剔除证据不把同一事件再罚一次。</td></tr></table></div>
<p class="note">这些阈值是本轮冻结的研究候选和工程容忍尺度，并非已获用户批准的正式生产规则。无显著差异不等于人员可互换；相同 Q 也不等于几何、局部结构与失败状态相同。根模块逐条文本复核的 25 份排除候选中，22 份有具体缺陷意见、2 份为人工强偏离陈述，均未新定统一严重等级；W001 的 UwV83HsGsw3-08 还存在 scope/OOS 归因待定，已在逐人表注明。这次文本核对不是新的独立视觉严重错误金标准。</p></section>
<section id="coverage"><h2>2. 输入、分母和已验证边界</h2><div class="grid"><div class="card"><strong>10,439 / 261 / 62</strong><small>库存作答 / 图片 / 人员 ID</small></div><div class="card"><strong>7,302 / 196 / 60</strong><small>正式质量作答 / 图片 / Q 画像人员</small></div><div class="card"><strong>5,719 / 177 / 22</strong><small>普通 Manual 作答 / 图片 / 建筑</small></div></div>
<p>主层简单 3,751 份 / 114 图 / 22 栋，中等 988 / 32 / 16，困难 980 / 31 / 15。旧普通 Manual 为 1,295 份（固定 v1 的 1,258 加新准入 37），新批 4,424 份。门洞、Semi 与其它层的绝对分项另见 <a href="worker_panel_descriptions.csv">逐层逐人表</a>，没有混成同一个任务池均分排名。</p>
<p>全量 60 人中总体 Q 支持充分 59 人；源时间 57 人；同目标时间 21 人；三个难度都达到支持门的 54 人。W022 只有 2 份、1 图、1 栋，画像和建筑外预测均标证据不足。库存 W019、W026 没有 Q 资格，单列为缺失，不能补零。</p>
<p>来源时间全库存 9,236 份＝旧审计继承 2,019＋新处理报告 7,217。源时间画像使用独立有效时间资格的普通 Manual 6,250 份 / 206 图 / 58 人；其中 1,025 份无 Q 资格仍可提供时间证据，未补回质量。Q 与源时间共同可用 5,225 份；同目标时间只有 440（Manual 418、Semi 22），从未以来源时间代填。</p>
<p>冻结难度沿用人工审核及其来源：177 图中 175 图明确记载“Codex 逐张全景总览复核，非盲法”，另 2 图该字段未填。评级者曾接触作答，不能称独立盲评难度；本轮没有用融合输赢重调难度。</p>
<p class="muted">输入核对与评分读取是从仓库已审计冻结证据起步。本模块复现统计与人员模型，不声称独立重建了依赖本地历史源的整个采集清洗流程，也不声称视觉审查了缺失原图。</p></section>
<section id="methods"><h2>3. 方法、支持门与建筑外隔离</h2>
<p>任务键为同一图片、条件、参考 ID、参考版本。Q 模型以同任务内中心化消去任务截距，再求人员效应，使用人员等权零和锚点；这与仅减去简单／中等／困难三个均值不同。百分位采用平均同分排名，保留胜负次序，但丢失分差幅度，且会随同伴构成和人数改变。任务中心化、百分位和任务 FE 都来自同一份几何 Q，不能重复加权。</p>
<pre>全局模型：min Σ_task Σ_worker (Q − 任务截距 − β_worker)²，Σ β = 0。
难度模型：min 同任务残差平方和 + λ Σ_worker Σ_difficulty (θ_worker,d − 该人三难度θ均值)²。
主 λ=20；预先固定 λ=0 / 5 / 80 与全局 ridge=5 作对照。
Q 与各难度支持：≥6 个唯一任务且 ≥3 栋建筑；时间支持相同。
Q3：β≤−3 / −3&lt;β&lt;3 / β≥3。相对 T3：log 时间效应&lt;−log1.25 / 中间 / ≥log1.25。</pre>
<p>逐一留出 22 栋建筑；该栋的实际个人 Q 不进入其画像、类别或选人。主要检验目标是<strong>同任务相对质量</strong>：目标 Q 减去同任务其它可评人员的均值；预测为该人员训练外效应减去这些人员训练外效应的均值。测试 Q 只构造评价目标，不充当绝对预测截距。另存只用训练难度截距的事前绝对 Q 预测，二者分开。</p>
<p>比较两个模型时，先匹配完全相同的可评作答，再在共同同伴集合重建目标和两次预测。先图内平均，再楼内图平均，最后建筑等权；区间按 22 栋建筑重抽 2,000 次。训练未见人员、时间缺失及难度不足均保留标志。反向模型的训练画像进一步双排除目标建筑和训练样本所在建筑，输出 27,720 行双排除人员特征。</p>
<p>原直接房间组仅使用 original 且 physical_same=支持的声明，未作关系传递。156 原组中本面板 144 图进入 80 可评组，只有 33 组有至少 2 张可评图，47 组仅 1 图，另 33 图无组。当前筛选没有图跨组重复，但同楼依赖仍在；组等权是描述性敏感性，组数不是独立样本量。</p></section>
<section id="validation"><h2>4. 建筑外实算：有限难度信息有用，收益较小</h2>
<p>下表正值代表相对质量预测 MSE 降低，全部使用每对模型完全相同的作答与同伴分母。全局 FE 主基线 MSE 为 214.621；5717 份可评作答覆盖 177 图、22 栋，2 份 W022 作答未冒充有历史支持的预测。</p><div class="scroll">__MAIN_TABLE__</div>
<p>联合 λ=20 在 15/22 栋改善；λ=80 也为小幅正增益，独立难度 λ=0 不占优。原始均分、同任务中心化和校准百分位在本轮较均衡的新池里与 FE 差距很小，不足以证明哪一个普遍更好，也不使不同任务池直接均分排名变得合理。</p>
<div class="scroll">__DIFF_TABLE__</div>
<p class="note">困难 B8L2 的区间下界接近 0，D10 困难区间跨 0；不能把 2.46% 包装成稳固的大幅专长效果。简单、中等、困难没有合并成非难图；本轮仍支持保留连续难度信息和有限候选类型，而非三个互不相关模型。</p></section>
<section id="fine"><h2>5. 细类是否增加新信息</h2>
<p>多难度类型依次定义为：三难度相对同伴均 ≥3 分；困难 θ≥3 且困难−简单、困难−中等均 ≥3；两个差均 ≥3 的“难图相对上升、同伴优势不足（θ难&lt;3，未必绝对低）”；两个差均 ≤−3；其余混合或接近常态。各难度证据不足为 unknown。<strong>“三难度相对同伴较强”不等于三难度绝对分数都高。</strong></p>
<p>最初的 QT×困难相对上升/下降规则过于稀疏，没有 QT 父类满足“至少两个子类各 ≥3 人”的拆分门。没有降低阈值凑人，而是在未见新融合结果前，把已定义多难度类型作为另一有限细分；保留其稀疏原型和合并版。unknown 只进入覆盖表，不构造一个可能恰好辨认单人的能力类型。</p>
<div class="scroll">__FINE_TABLE__</div>
<p>未合并 fine_dtype 对四类 QT 的表观增益约 7.52%，但对 Q3×T3 几乎为零（−0.019%，区间 −0.987 至 0.911）。说明许多细类收益只是恢复被 Q2 压缩掉的 Q 幅度。保留连续 β，再加细类共有难度偏差，仍有约 0.75% 增益；这比完整连续 θ 弱，适合作解释，不足以证明类别是最佳预测器。</p>
<p>这些是单人质量预测的检查，未把它当成“团队构成是否有用”的唯一标准。固定人数改变构成、固定构成换成员、固定背景逐人替换、真实逐人加入的结果，由独立团队与反向分簇输出回答。</p>
<details><summary>展开：所有未合并候选细类及真实成员</summary><div class="scroll">__MEMBERS__</div></details>
<p>W017 是唯一 hard_specialist 候选，不能提供这一个类型的两名不同人员类内交换证据；保留为稀疏候选有助于观察实际贡献，不能把单人的行为叫已验证人群规律。Q−fast 与 Q−slow 大类中仍有很多“混合”成员，类型不足以解释其全部作答差异。</p></section>
<section id="people"><h2>6. 逐人画像与边界</h2><label>人员 <select id="worker"></select></label><div id="person-summary"></div>
<p>W002 的困难绝对均分与同伴优势均较强；W017 困难实际均分约 60.10，但 θ 困难约 +5.02，困难相对自身简单和中等分别 +7.05、+5.73，是相对专长候选。W033 的困难−中等只有 +1.89，不能沿旧线索称作同样强的困难专长。W006 困难实际均分约 48.54，困难相对同伴 θ≈−2.87；相对自身中等上升不等于困难绝对质量高。W021、W027 的中等支持不足，仍保留连续估计但不强行归入全难度类型。</p>
<p>W108 与 W114 的困难相对简单、中等均下降；W125 是下降方向候选但对简单差的区间跨 0，边界更大。源时间相对较快且三难度相对较强的候选为 W002、W109、W126，但低尾仍需单独看，不能把类别当成每张图高质量保证。</p>
<p><a href="人员画像与候选细类60人.csv">下载含完整支持、区间、证据及缺失的 60 人表</a> · <a href="库存中无Q画像人员2人.csv">库存无 Q 资格的 2 人</a></p>
<label>筛选人员表 <input id="search" placeholder="输入人员 ID、来源、难度类型等"></label><div class="scroll" id="people-table">__PEOPLE__</div></section>
<section id="time"><h2>7. 效率：时间来源、阈值、结构和尾部</h2>
<p>固定 60/180 秒改为 90/240 秒时，57 名时间支持充分人员中 15 人变类；一分钟不是已批准阈值。任务调整 T3 有 17 快、20 中、20 慢、3 未知。固定秒数直观，却受任务构成影响；相对速度更适合本轮同任务比较，但旧/新来源与人员 cohort 完全重合，没有一个人跨两种来源，不能靠模型声称两者已校准。</p>
<p>下表“只调任务”描述同任务人员间关联；“再调人员”描述去除该人整体快慢与整体 Q 后的剩余关联。它不是让某人多花时间的因果收益。来源不同分开估计；同目标时间是稀疏重叠诊断。</p><div class="scroll">__EFFICIENCY__</div>
<p>删掉每个来源 1% 和 99% 时间尾部后，新来源人员内时长加倍关联 Q 从 +1.025 变为 +1.002，旧来源从 +0.312 变为 +0.315，方向未由极端值主导。主人员 Q/T 效应 Spearman 仅约 0.092，不能总体认定慢者好。对源时间 1%/99% 缩尾仅 W035 的 T3 从慢到中间；在同任务与人员内进一步诊断点对数后，仅 W122 的 T3 慢到中间，两者均接近阈值。</p>
<p>在人员内模型，时长加倍与最终点对数旧 +0.305、新 +0.398 关联；点数确会混杂效率解释。同任务 GT 点数是常数，因此最终点数和有符号 GT 点数差给出完全相同斜率，是重复信息。绝对点数差也只是结构 proxy，未审核为遗漏金标准；不能凭更少点认定偷懒，或更多点认定修好了。</p>
<p class="note">440 份同目标时间与其来源时间逐份相等，完全重叠，不是独立验证样本。Manual 418 份加入人员 FE 后关联区间跨 0；Semi 22 份只有 3 图/3 栋，不支持泛化效率判断。详细覆盖和完整尾部对照见 <a href="efficiency_within_person_diagnostics.csv">效率诊断表</a>。</p></section>
<section id="version"><h2>8. v1 固定记录、扩池和 B8/D10 的独立比较</h2>
<p>固定 v1 的 1,911 份 B8/D10 分数及参考身份均复核一致，最大差约 1.42×10⁻¹⁴（浮点/CSV 精度）；既有 1,048 份开发集任务调整 Q 与 source/target T 模型独立重放至约 10⁻¹³。原“按难度独立拟合难图约改善 4.9%”实为 4.883%、219 份/18 图/9 栋且仅 3/9 栋改善；全难度 943 份/81 图/19 栋反而退约 1.35%，已确认而非照抄。</p>
<p>旧记录新增质量资格 37 份、17 人、26 图、8 栋单独列账；不是重新打分。W017 与 W029 的 Q2 相对零点标签随 v2 人员池改变，固定旧 24 人锚点后，W017 从 −0.002 到 +0.085，主要是零点与边界问题，不能说能力下降；W029 从 +0.351 到 −0.359 也仍接近边界。原答百分位随新增同伴的变化另存逐份记录。</p>
<p>仓库现有 v2 同任务百分位画像精确复现（差小于 10⁻¹⁵），其分位粗类为 9 高、48 中、2 低、1 未知。本轮 β±3 类为 15 高于同伴、19 接近、25 低于同伴、1 未知；29 人类别不同主要是定义和阈值不同，不等于纠正了 29 个误分。</p>
<p>B8→D10 固定成员计量不改变全量 Q2、QT、多难度类型及 fine_dtype 标签；Q3 只有 W008、W021 从高于同伴进入近同伴边界。B8/D10 本轮同成员分差、换计量后重学标签/选人、旧/新人时间来源敏感性分别保留，不能合成一个“升级提升”。</p>
<p><a href="v1_existing_effect_replication.csv">既有模型独立复现</a> · <a href="v1_original_separate_difficulty_replay.csv">旧难度方法精确重放</a> · <a href="v1_fixed_answers_peer_pool_shift.csv">固定旧答同伴池变化</a> · <a href="worker_metric_class_sensitivity.csv">B8 / D10 标签变化</a></p></section>
<section id="replay"><h2>9. 复现入口、文件和限制台账</h2><pre>python reproduce_forward_profiles.py --repo /path/to/frozen/repo \
    --out /path/to/new/output \
    --evidence /path/to/audit/person_evidence_62.csv</pre>
<p>环境：Python 3.12.14、NumPy 2.3.5、pandas 2.2.3、SciPy 1.17.0。仅复算本模块所需统计；根审计的独立行为证据表用于最终左连接，不参与 Q、T 或类别训练。运行入口将登记与规则复制到新目录，每步写日志、退出状态、代码与输入摘要。</p>
<ul><li>定义与修订：<a href="REGISTRATION.json">主登记</a>、<a href="REGISTRATION_DTYPE_EXTENSION.json">难度类型扩展</a>、<a href="VALIDATION_REVISIONS.json">共同同伴比较的实现纠正</a>、<a href="FOLD_SCHEMA.json">训练外画像接口</a>。</li>
<li>逐人/逐折：<a href="full_profiles.csv">60 人完整画像</a>、<a href="fold_profiles.csv">1320 行留建筑画像</a>、<a href="nested_fold_features.csv">27720 行双排除画像</a>、<a href="fold_training_membership_audit.csv">训练成员审计</a>。</li>
<li>逐答/逐图/逐楼：<a href="validation_predictions.csv.gz">全部候选逐份预测</a>、<a href="validation_per_image.csv">逐图误差</a>、<a href="validation_per_building.csv">逐楼误差</a>、<a href="paired_model_comparison.csv">共同同伴配对比较</a>。</li>
<li>误差表不同模型的可评人员可能不同；模型优劣以共同同伴重建后的配对表为准。全量画像用于描述，团队预测必须读取 heldout_building 对应行，不能取 FULL 标签。</li>
<li>稀疏人员、缺时间、无 Semi 错误机会、无 scope 相容金标准、不同参考/空间以及个人剔除均保留缺失状态。已审核预处理、参考和环序未被覆盖；未做全采集流程独立再生产，未做新原图视觉审核，未运行新采集。</li></ul>
<details><summary>展开：可读模型审计证据</summary><pre>__AUDIT__</pre></details></section>
<footer>本页提供正向人员画像与可复核证据。组队构成、标法簇、固定背景替换、失败及共识几何结果在团队与反向模块中单独解释；不能用本页的单人预测改进替代它们。</footer></main>
<script>const people=__PERSON_JSON__;const esc=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const fmt=(x,n=2)=>x==null?'—':typeof x==='number'?x.toFixed(n):String(x);const sel=document.getElementById('worker');people.forEach(p=>{let o=document.createElement('option');o.value=p['人员'];o.textContent=p['人员']+' · '+p['难度类型候选'];sel.appendChild(o)});
function show(){let p=people.find(x=>x['人员']===sel.value);if(!p)return;let rows=['简单','中等','困难'].map(d=>{let v=p[d+'调整Q'];let n=p[d+'图数'],b=p[d+'建筑数'],s=p[d+'支持充分'];let w=Math.min(125,Math.abs(v??0)*4);let x=(v??0)<0?170-w:170;return `<tr><td>${d}</td><td>${fmt(p[d+'实际均分'])}</td><td>${fmt(p[d+'同任务百分位'])}%</td><td><svg width="335" height="32" aria-label="相对Q"><line x1="170" y1="1" x2="170" y2="31" stroke="#91a8b2"/><rect x="${x}" y="8" width="${w}" height="15" rx="2" fill="${(v??0)>=0?'#14888e':'#ba7547'}"/><text x="5" y="21">${fmt(v)}</text></svg></td><td>${n} 图 / ${b} 栋${s?'':'；证据不足'}</td></tr>`}).join('');document.getElementById('person-summary').innerHTML=`<h3>${esc(p['人员'])} · ${esc(p['细类候选'])}</h3><div class="grid"><div class="card"><strong>${fmt(p['B8L2均分'])}</strong><small>普通 Manual 绝对均分；低10分位 ${fmt(p['B8L2低10分位'])}，标准差 ${fmt(p['B8L2标准差'])}</small></div><div class="card"><strong>${fmt(p['任务调整Q效应'])}</strong><small>任务调整相对 Q；区间 [${fmt(p['Q效应区间下界'])}, ${fmt(p['Q效应区间上界'])}]，${p['普通Manual图数']} 图 / ${p['普通Manual建筑数']} 栋</small></div><div class="card"><strong>${fmt(p['源时间中位秒'],1)} 秒</strong><small>来源时间中位数；${esc(p['源时间相对三类'])}，${esc(p['来源'])}，${p['源时间画像份数']} 份</small></div></div><div class="scroll"><table class="data"><tr><th>难度</th><th>实际均分</th><th>同任务百分位</th><th>部分汇聚 θ</th><th>支持</th></tr>${rows}</table></div><p>困难−简单 ${fmt(p['困难减简单效应'])} [${fmt(p['困难减简单区间下界'])}, ${fmt(p['困难减简单区间上界'])}]；困难−中等 ${fmt(p['困难减中等效应'])} [${fmt(p['困难减中等区间下界'])}, ${fmt(p['困难减中等区间上界'])}]。</p><p>细类留建筑标签一致率 ${fmt(100*p['细类留建筑标签一致率'],1)}%；同目标时间 ${p['同目标时间画像份数']} 份 / ${p['同目标时间画像建筑数']} 栋。${esc(p['边界与缺失说明'])}</p><p class="muted">数值是全量描述；目标建筑事前组队必须使用 fold_profiles 中排除该楼的历史画像。绝对分数、同伴相对效应和相对自身的难度变化是三个视角。</p>`;}sel.addEventListener('change',show);sel.value='W017';show();document.getElementById('search').addEventListener('input',e=>{let q=e.target.value.trim().toLowerCase();document.querySelectorAll('#people-table tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))});</script></html>'''
    for key,value in {'__MAIN_TABLE__':table(main_cmp),'__DIFF_TABLE__':table(dif_cmp),
                      '__FINE_TABLE__':table(fine),'__MEMBERS__':table(members),
                      '__PEOPLE__':all_people,'__EFFICIENCY__':table(eff),
                      '__AUDIT__':audit_text,'__PERSON_JSON__':person_json}.items():
        page=page.replace(key,value)
    target=out/'FORWARD_REPORT_ZH.html'
    target.write_text(page,encoding='utf-8')
    print('wrote',target,'people',len(persons),'bytes',target.stat().st_size)


if __name__=='__main__':
    main()
