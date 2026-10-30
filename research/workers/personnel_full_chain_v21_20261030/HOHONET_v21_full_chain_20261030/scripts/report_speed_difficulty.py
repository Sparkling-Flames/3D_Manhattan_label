#!/usr/bin/env python3
"""Render the computed matched-person study and self-contained raw-case viewer."""
import base64,gzip,hashlib,html,json
from pathlib import Path
import numpy as np
import pandas as pd
import speed_difficulty as m

P=m.OUT

def table(d):
    def f(v):
        if isinstance(v,(float,np.floating)):
            return '—' if pd.isna(v) else f'{v:.4f}'
        return str(v).replace('|','\\|')
    return '\n'.join(['| '+' | '.join(map(str,d.columns))+' |',
        '| '+' | '.join(['---']*len(d.columns))+' |']+
        ['| '+' | '.join(f(v) for v in row)+' |' for row in d.itertuples(index=False,name=None)])

def selected(s,method='TARGET_DSTRUCT_K3',condition='manual',origin='new'):
    return s[(s.method==method)&(s.condition==condition)&(s.origin==origin)]

def main():
    s=m.read(P/'CURRENT_MATCHED_SUMMARY.csv');long=m.read(P/'CURRENT_SAME_PEOPLE_SUMMARY.csv')
    old=m.read(P/'V2_FROZEN_SAME_PEOPLE_SUMMARY.csv');fixed=m.read(P/'V21_FIXED_V2_SAME_PEOPLE_SUMMARY.csv')
    bridge=m.read(P/'CURRENT_ON_V2_FINE_PAIR_SAME_PEOPLE_SUMMARY.csv')
    cases=m.read(P/'CASES_EXACT_PAIRS.csv');val=json.loads((P/'VALIDATION.json').read_text())
    headline=[]
    cohorts=[('v2原63对（冻结）',old,'V3_JOINT_QT_FINE'),('当前Q/资格，固定原63对',fixed,'V3_JOINT_QT_FINE'),
             ('当前TARGET K3全部105对',long,'TARGET_DSTRUCT_K3'),
             ('当前TARGET K3与旧精确配对图片交集52对',bridge,'TARGET_DSTRUCT_K3')]
    for name,df,method in cohorts:
        for metric in ['turn_n','short_turn_edges','B8L2']:
            r=selected(df,method).set_index('metric').loc[metric]
            headline.append({'支持':name,'指标':metric,'成员对':int(r.valid_pair_rows),'人员':int(r.workers),
                             '困难−简单均差':r['mean'],'正':int(r.positive),'负':int(r.negative),'零':int(r.zero)})
    headline=pd.DataFrame(headline);m.save(headline,'PAPER_FIXED_PEOPLE_BRIDGE.csv')
    # Exact original values are reaggregated and checked, not copied into results.
    assert old[(old.method=='V3_JOINT_QT_FINE')&(old.condition=='manual')&(old.origin=='new')&(old.metric=='turn_n')].iloc[0].positive==42
    assert abs(headline.iloc[0]['困难−简单均差']-.335362)<1e-6
    z=selected(s);z=z[z.cohort.eq('all_current_support')&z.difficulty.isin(['简单','中等','困难'])]
    core=z[z.metric.isin(['turn_n','short_turn_edges','near_straight_nodes_5deg','B8L2','D10','log_time_peer_delta'])]
    core=core[['difficulty','metric','images','buildings','image_equal_mean','building_equal_mean','positive_images','negative_images','zero_images','image_p10']]
    m.save(core,'PAPER_TARGET_K3_DIFFICULTY.csv')
    methods=long[(long.condition=='manual')&(long.origin=='new')&long.metric.isin(['turn_n','short_turn_edges','B8L2'])]
    methods=methods[['method','metric','valid_pair_rows','workers','mean','median','positive','negative','zero']]
    bw=m.read(P/'SAME_PEOPLE_SAME_BUILDING_BUILDING_SUMMARY.csv')
    bw=selected(bw);bw=bw[bw.metric.isin(['turn_n','short_turn_edges','B8L2','D10','log_time_peer_delta','unmatched_ref_9'])]
    member=m.read(P/'FIXED_PEOPLE_LEAVE_ONE_WORKER.csv');building=m.read(P/'FIXED_PEOPLE_LEAVE_ONE_BUILDING.csv')
    ranges=[]
    for label,df in [('删一人',member),('删一楼',building)]:
        for metric,g in selected(df).groupby('metric'):
            ranges.append({'敏感性':label,'指标':metric,'最小均差':g.pair_equal_mean.min(),'最大均差':g.pair_equal_mean.max(),
                           '剩余配对最少':int(g.remaining_pairs.min()),'剩余配对最多':int(g.remaining_pairs.max())})
    ranges=pd.DataFrame(ranges);m.save(ranges,'PAPER_MEMBER_BUILDING_SENSITIVITY.csv')
    cohorts_q=[]
    for name,file in [('v2值','V2_ON_CURRENT_SUPPORT_SUMMARY.csv'),('v2.1值','V21_FIXED_V2_PAIRS_SUMMARY.csv')]:
        d=selected(m.read(P/file),'V3_JOINT_QT_FINE')
        d=d[d.metric.eq('B8L2')&d.difficulty.isin(['简单','困难'])&d.cohort.isin(['same_pairs_Q_common','same_pairs_newly_Q_scorable','same_v2_pairs_current_legal'])].copy()
        d['version']=name;cohorts_q.append(d)
    q=pd.concat(cohorts_q)[['version','cohort','difficulty','valid_pair_picture_rows','images','buildings','building_equal_mean','positive_images','negative_images']]
    m.save(q,'PAPER_V2_CURRENT_Q_SUPPORT.csv')
    v1=selected(s,origin='v1');v1=v1[v1.cohort.eq('all_current_support')&v1.difficulty.isin(['简单','困难'])&v1.metric.isin(['turn_n','B8L2','log_time_peer_delta'])]
    semi=selected(s,'V3_JOINT_QT_FINE','semi');semi=semi[semi.cohort.eq('all_current_support')&semi.difficulty.isin(['简单','中等','困难'])&semi.metric.isin(['turn_n','B8L2','log_time_peer_delta'])]
    casecols=['case_id','image_code','worker_fast','worker_slow','current_difficulty','turn_n_difference','short_turn_edges_difference','B8L2_difference','D10_difference','unmatched_ref_9_difference','log_time_peer_delta_difference']
    text='''# v2.1 同类近历史Q快慢人员 × 难度：当前下游接续

来源冻结为 `13a7861334749805a86dc19e9ea79fcaa71020c0`。本模块是原答与人员匹配研究，新增融合、评分、分类拟合和人员均为 **0**。TARGET K3/K2、OPPJOINT K3/K4 是本轮工作分析对象，不作用户尚未决定的最终选型。

## 1. 可以采用的判断

**v2原来那批具体快慢人员在困难时，慢者相对增加转折和短边的多数规律仍成立；它不是“当前全部同类快慢人员都会如此”的结论。** 固定旧63对后，42对的转折优势增加、44对的短边优势增加，原答表达数值与v2一致。更新质量与资格后，困难相对简单的慢−快Q差为−2.4960，26/63对为正。较多表达不能直接写成更正确或更高Q。

当前TARGET K3按既有楼外Q/T面板重新匹配形成105对，转折变化55/105为正，短边59/105为正，但配对均值仅+0.0198和+0.0103。**在与旧配对图片重合的52对中，仍保留+0.2485转折（37/52正）、+0.2892短边（39/52正）**。因此必须共同解释人员对、图片支持、历史近Q条件和类别关系的变化，不能把前后差别仅归给分类名称。

记录时长的区分远比“慢者普遍多画/升质”稳定。新来源Manual、当前TARGET K3同类近Q匹配中，简单130/130图和困难35/35图的慢−快记录对数时间差为正，对应建筑等权几何时间比分别约2.34和2.41。普通Manual旧来源和Semi自身标签另列。

## 2. 匹配和合法支持

沿用v2原规则：同图、同一合法主目标、同条件、同来源与同时间口径；两人当前楼外相对历史Q差不超过3分、调整历史时间比至少1.5；由楼外历史决定快慢，不按当前图Q或时间挑人。Q/T来自已经归档的v2.1 `joint_history_classification/ALL_METHOD_LABELS_LOBO.csv.gz`，Q按同图同行中心化、再图内与楼等权；时间在同图、来源、时间口径内中心化。使用其既有 `qt_supported` 门槛，不填未知历史，不重新拟合类别。TARGET/OPPJOINT只改变“同类”的条件，使用同一Q/T匹配面板。

使用当前 `quality_inventory.csv`、当前参考目录和正式原答结构表核对资格、目标及分项。旧行为库存中73份在当前不具组队来源资格（64排除、9待定），只保留旧档案身份，不进入当前合法匹配；旧10339条匹配记录实际受此影响为8条，全部来自旧来源粗/细重复层。原新来源Manual4195条细类记录均仍合法。原答几何可评与Q可评单列，缺Q不是0或融合失败。

当前输出共有 **52851个方法×有向人员对×图片条目**，对应 **14528个不同实际有向人员对图片**。同一原答被不同类别方案选中不算独立重复。具体成员、楼外折、类别、历史Q/T、对象ID、参考、来源和每项差都保存在 `CURRENT_MATCHED_PAIRS.csv.gz`；跨方法重叠见 `MATCH_METHOD_OVERLAP.csv.gz`。

## 3. 先固定v2人员和图片，再看扩展支持

下表方向统一为 `(慢−快)困难 − (慢−快)简单`。每个有向人员对在简单和困难各至少2图；先人员对内按楼等权，再对人员对等权。人员对会共享人员，不作为独立实验重复。原63与当前105不是相同的全部人员对和图片集合；共同52还要求旧精确人员对图片、当前类别关系和当前近Q/时间匹配条件同时成立。

'''+table(headline)+'''

`PAPER_FIXED_PEOPLE_BRIDGE.csv` 回连三组逐对源表。当前TARGET的105对在更严格的“每项指标都至少2张有效简单图和2张有效困难图”下仍全部保留，结论不依赖某对只有1张可评分困难图。其它方法和旧设计的逐指标严格支持在 `STRICT_TWO_VALID_IMAGES_PER_DIFFICULTY.csv`。

### Q更新与Q支持扩展应分开

固定原新来源Manual细类的共同Q支持，简单111图的建筑等权Q差从+0.0426变+0.0394，困难27图从−0.4793变−0.4801，变化很小。全部当前可评分支持加入了原来缺Q的记录，困难层新增3图来自同一栋uNb9，新增部分的图等权Q差+8.8480。它使固定旧配对的困难图总体均值变为+0.0722，但不等于63个固定人员对的困难−简单关系都改善。

新增困难图是 `uNb9QFRL6hY-18`、`uNb9QFRL6hY-26`、`uNb9QFRL6hY-59`，共5条精确人员对图片。新增简单层16图、6楼，Q差−0.7657，7图正、9图负。全难度合计新增363条原细类配对Q记录、26图、11楼，范围保留在下表。原冻结Q与当前Q各自使用明确分母。

'''+table(q)+'''

当前V3联合细类的旧4195条新来源Manual配对中，3429条仍同类，4004条仍近Q，3318条满足全部当前匹配；这些条件重叠，不能相减成互斥原因。精确关系见 `V2_PAIRS_CURRENT_SUPPORT_AND_MATCHING.csv` 与 `V2_FIXED_PAIR_CURRENT_RESULTS.csv.gz`。新的分类/历史匹配改变研究支持，没有改变原始作答。

## 4. 当前TARGET K3同类内部：逐图难度与具体人员对回答不同问题

以下为新来源普通Manual。方向是同图慢−快，先图片内平均所有合法人员对，再保留图片等权和建筑等权两个均值。最后三列保留正、负、零图片数；表达计数没有“正就是更好”的含义。记录时间一项为自然对数差，其指数才是几何时间比。

'''+table(core)+'''

困难35图，转折图片均值14正、15负、6零；Q为16正、19负，图片等权−1.2848、建筑等权−0.1197。简单图大多数转折没有变化，仍有Q和时长差。因此“速度差稳定”与“结构差不普遍”可以同时成立。近历史Q也不保证每一目标图近Q，更不保证难度变化后质量优势不变。

全部31项结果还包括B8L2、D10、底面IoU、底面角误差、方向误差、平均及中心高度误差、三维代理、未对应参考角、遗漏/外扩、面积/高度、有效转折、短边、近共线点、位置匹配和记录时长。它们在 `CURRENT_MATCHED_SUMMARY.csv` 使用各自有效分母、分布和低尾；逐图逐楼表可独立重聚合。

### 方法互补与实际支持

下表仍为固定有向人员对的困难−简单关系，不能按其最大差值重新决定主分类。

'''+table(methods)+'''

TARGET K2/K3提供结构类内对照，OPPJOINT提供联合画像类内对照，V3联合粗细保留历史链条。当前Manual V3联合粗/细产生同一匹配集合，其两行不能当两份独立证据。比较方法时使用相同的Q/T历史门槛，但不同“同类”限制会改变成员和图片支持；本表不是公平独立试验的分类排行榜。

## 5. 同一人员对、同一建筑与成员敏感性

当前TARGET K3新来源有814个“人员对×建筑”上下文，涉及35人、15楼；每个上下文在该楼内至少有一张简单和困难图片。814不是814个独立人员对或房间。对上下文等权，转折变化+0.0508、Q−0.7346；按楼等权则分别−0.0188和+0.5061。如下表，Q仅7/15楼为正；均值和多数方向均应保留，不能用其中一个替代另一个。

'''+table(bw)+'''

上述对照固定具体人员和楼外类别/历史折，但简单与困难仍是不同照片，不能解释成只操作了难度。对应全部上下文及楼均值在 `CURRENT_SAME_PEOPLE_SAME_BUILDING.csv.gz`、`SAME_PEOPLE_SAME_BUILDING_BUILDING_EFFECTS.csv`。

逐一排除成员或建筑后，TARGET K3的转折、短边和Q均值会跨零，记录时间增幅、遗漏和外扩方向相对稳定。下表删人只删除包含该人的已保存配对；删楼重算剩余简单/困难支持并重新要求各至少2图，不重新训练类别或历史。

'''+table(ranges)+'''

这说明全当前105对的微小平均表达变化依赖具体成员/图片条件；并没有抹掉旧63和交集52中的多数规律。查看反例时应追到具体成员与图，不能把均值近零改写成“所有人都无差别”。

## 6. 旧来源Manual与Semi补充

旧来源Manual使用同一TARGET K3条件，但记录口径保持继承的审计时长，不与新来源时间直接合并。简单Q多为慢者较高（46/62图正），困难则8/21图正、13/21负，建筑等权−5.7368。这样的条件响应不能被新来源的总体均值覆盖。

'''+table(v1[['difficulty','metric','images','buildings','building_equal_mean','positive_images','negative_images','zero_images']])+'''

Semi只用自己的当前V3联合标签和终稿。新来源支持19张简单图、4张中等图，没有困难层固定配对的充分机会；不把缺困难支持填零或否定Semi用途。简单Q为7正、12负，时长19/19图仍为慢者较长。

'''+table(semi[['difficulty','metric','images','buildings','building_equal_mean','positive_images','negative_images','zero_images']])+'''

## 7. 可直接查看的完整原答案例

打开 [CASES_VIEWER.html](CASES_VIEWER.html)：内嵌5张真实原图、三组简单/困难原答、当前完整参考、精确角点和所有分项。原图使用既有Release按成员字节范围取得并核对CRC、大小与SHA256。原答来自与当前提交同blob的263池快照，所有案例参考点与当前参考目录逐点核对。

案例在完整结果之后按正、负和小Q差预定义层选取人员对，并在同一建筑内选择符合该局部方向、接近层内中位的图片组合；它们用于解释，不重新估计总体比例。全部候选及精确取值在逐对源表，选型身份在 `CASE_INDEX.csv`。

'''+table(cases[casecols])+'''

- **VFua-04，W134与W125：更多结构表达、Q下降。** 有效转折4→10、短边0→4，未对应参考角比例0.7143→0.2143；B8L2却69.8247→44.9738，方向误差3.3498°→13.5928°，记录时长24.389→286.279秒。底面图可见慢者更多折点与斜连接，不能把补点直接等同正确定位。人工可看原图中横坐标约286–349/1024区域，对照W125第5–8号角点，判断镜面、柜体与实体墙角的关系；本轮没有修改正式参考。
- **pa4-10，W127与W107：多表达与相对改善，但两者仍低Q。** 转折4→6，底面IoU0.2528→0.5021，遗漏0.7472→0.4707，B8L2 7.8700→18.6411；仍有大片参考结构缺失，不能称完整正确补画。当前困难图中慢者用时更长，所配简单pa4-48上历史慢者实际反而略快，说明历史速度是人员倾向。
- **VFua-10，W111与W121：Q变化小，结构细节与劳动仍变。** 两份均12个有效转折，短边6→4，Q46.1227→45.4470。底面IoU与三维代理改善，同时底面/方向角误差变差，分项相互抵消；记录时长145.126→374.145秒。不能把总Q差不到1分写成两份标注等同。

这些是原答比较，不含新的团队融合票账；对融合投票/连接的机制判断应接第一阶段半队及既有ABC证据。尚需人工的是原图语义上的“哪一处是实际墙角/镜像/柜体”，不是数值差和成员身份。

## 8. 论文采用与复现

可采用表述：**在相同楼外类别、接近历史质量且来源相同的人员中，记录劳动仍有稳定差异。特定固定人员对在困难图片上相对增加结构表达的多数规律可以保留，但这种增加不等价于更高质量，并随匹配人员和图片支持改变。当前结构分类内的全部配对总体效应较小，原支持交集仍显示较清楚的多数补画响应。**

本模块补齐了此前“未找到等价验收”的实际下游研究，不要求新增人员、房间、同房ABC或重跑融合。分类最终选择仍由完整人群模拟证据与用户研究判断决定。

复现顺序：`python scripts/speed_difficulty.py`，`python scripts/speed_difficulty_explain.py`，`python scripts/report_speed_difficulty.py`。脚本相对本轮根目录读取最小源表；原图获取脚本单列在本模块 `code/`，已有本地原图可直接复用。`DESIGN_BEFORE_RESULTS.json`、`RUN_MANIFEST.json`、`VALIDATION.json`、`CASE_VALIDATION.json` 保留设计、源哈希、同目标/来源/楼外/精确成员检查和案例几何核对。

关键文件：

| 文件 | 可回答的问题 |
|---|---|
| `V2_FIXED_PAIR_CURRENT_RESULTS.csv.gz` | 每条旧匹配在当前资格、Q、类别/历史条件下怎样变化 |
| `CURRENT_MATCHED_PAIRS.csv.gz` | 当前每个方法的全部具体匹配、折、类别、来源、历史和31项差 |
| `CURRENT_MATCHED_SUMMARY.csv`、`*_IMAGES.csv.gz`、`*_BUILDINGS.csv.gz` | 全支持、旧Q图片支持、新Q图片支持及分母、方向、幅度、低尾 |
| `CURRENT_SAME_PEOPLE.csv.gz` | 同一有向人员对跨难度的每项差和确切支持图片 |
| `CURRENT_ON_V2_FINE_PAIR_PICTURES.csv.gz`、`*_SAME_PEOPLE.csv.gz` | 原配对图片与当前类别/历史条件交集，不把支持变化归成单一分类效应 |
| `CURRENT_SAME_PEOPLE_SAME_BUILDING.csv.gz` | 同人同楼条件对照，明确上下文统计单位 |
| `FIXED_PEOPLE_LEAVE_ONE_WORKER.csv`、`FIXED_PEOPLE_LEAVE_ONE_BUILDING.csv` | 共享成员/建筑影响和保留支持 |
| `RECORDS_CURRENT_WITH_PROVENANCE.csv.gz` | 每份原答当前资格、Q/结构/劳动分母和几何来源 |
| `CASES_MINIMUM_RAW_GEOMETRY.json.gz`、`CASES_VIEWER.html` | 所选完整原图、原答、参考与分项直接核对 |
| `PAPER_*.csv` | 本说明表格的直接源，数值可逐项回连 |

'''
    (P/'README.md').write_text(text,encoding='utf-8')
    data=json.loads(gzip.decompress((P/'CASES_MINIMUM_RAW_GEOMETRY.json.gz').read_bytes()))
    data['photos']={code:base64.b64encode((P/'originals'/(code+'.png')).read_bytes()).decode() for code in sorted({c['image_code'] for c in data['cases']})}
    data['figures']={c['case_id']:base64.b64encode((P/(c['case_id']+'.png')).read_bytes()).decode() for c in data['selection']}
    viewer='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>HOHONET v2.1 快慢配对原答</title><style>
body{font:16px/1.65 system-ui,sans-serif;margin:28px auto;max-width:1350px;padding:0 24px;color:#17243a;background:#f7f8fa}h1{font-size:28px}h2{font-size:23px;margin-top:30px}h3{margin:10px 0}.intro,section{background:white;border:1px solid #ccd5df;border-radius:8px;padding:18px;margin:18px 0}.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}.full .two{grid-template-columns:1fr}svg{width:100%;height:auto;background:#e5e7eb}.bev{width:100%;height:auto}.controls label{margin-right:18px}select,button{font:inherit;padding:5px 12px}table{border-collapse:collapse;width:100%;font-size:13px;margin:12px 0}th,td{padding:5px 8px;border-bottom:1px solid #d5dce5;text-align:right}th:first-child,td:first-child{text-align:left}pre{white-space:pre-wrap;word-break:break-all;max-height:460px;overflow:auto;font-size:12px}details{margin:12px 0}.muted{color:#526276;font-size:14px}@media(max-width:900px){.two{grid-template-columns:1fr}}</style>
<h1>同类、近楼外历史Q的快慢人员：原答与当前参考</h1><div class="intro"><p>分类是工作分析对象。快慢由该图所属建筑外的历史确定；这里显示完整数值研究之后选择的正、负及小Q差案例。每例保留同一人员对在同楼简单与困难图上的实际标注。</p><div class="controls"><select id="sel"></select><button id="wide">切换全宽</button><label><input id="reference" type="checkbox" checked>参考（黄）</label><label><input id="fast" type="checkbox" checked>历史快者（青）</label><label><input id="slow" type="checkbox" checked>历史慢者（粉）</label></div><p class="muted">原图显示全部顶部/底部角点及编号，连接顺序见下方精确底面图。Q越高越好，误差指标越低越好；转折/短边更多只表示表达更多。时间为合法同源记录秒数。</p></div><main id="main"></main>
<script id="data" type="application/json">DATAHERE</script><script>
const D=JSON.parse(document.getElementById('data').textContent),S=document.getElementById('sel'),M=document.getElementById('main');
const titles={more_turns_Q_down:'更多转折但Q下降',more_turns_Q_up:'更多转折且Q提高，仍保留低Q事实',same_turns_small_Q:'转折数相同、Q差小，但细节和劳动变化'};
for(const c of D.selection){const o=document.createElement('option');o.value=c.case_id;o.textContent=titles[c.case_id]+'：'+c.worker_fast+' / '+c.worker_slow;S.append(o)}
const ns='http://www.w3.org/2000/svg';function el(n,attrs={}){const e=document.createElementNS(ns,n);for(const[k,v]of Object.entries(attrs))e.setAttribute(k,v);return e}
function photo(c){const s=el('svg',{viewBox:'0 0 1024 512'});s.append(el('image',{href:'data:image/png;base64,'+D.photos[c.image_code],x:0,y:0,width:1024,height:512}));for(const [key,color,points]of [['reference','#ffe066',c.reference.points_1024x512],['fast','#2dd4bf',c.raw_fast.points],['slow','#fb7185',c.raw_slow.points]]){if(!document.getElementById(key).checked)continue;for(let i=0;i<points.length;i+=2){const t=points[i],b=points[i+1];s.append(el('line',{x1:t[0],y1:t[1],x2:b[0],y2:b[1],stroke:color,'stroke-width':1.6,opacity:.8}));for(const p of[t,b])s.append(el('circle',{cx:p[0],cy:p[1],r:2.5,fill:color,stroke:'#111','stroke-width':.5}));const label=el('text',{x:b[0]+3,y:b[1]+12,fill:color,'font-size':12,stroke:'#111','stroke-width':.35,'paint-order':'stroke'});label.textContent=i/2+1;s.append(label)}}return s}
function cell(row,t,head=false){const e=document.createElement(head?'th':'td');e.textContent=t;row.append(e)}function fmt(x){return x===null||x===undefined?'—':typeof x==='number'?x.toFixed(4):x}
function render(){M.replaceChildren();const id=S.value,chosen=D.cases.filter(c=>c.case_id===id),section=document.createElement('section');const h=document.createElement('h2');h.textContent=titles[id];section.append(h);const grid=document.createElement('div');grid.className='two';for(const c of chosen){const d=document.createElement('div'),h=document.createElement('h3');h.textContent=c.image_code+' · '+c.difficulty;d.append(h,photo(c));const p=document.createElement('p');p.className='muted';p.textContent=c.worker_fast+'（历史快） / '+c.worker_slow+'（历史慢） · 该楼外类别 '+c.class_id+' · 历史Q '+fmt(c.history_q_fast)+' / '+fmt(c.history_q_slow)+' · 历史时间比 '+Math.exp(c.history_time_log_slow_minus_fast).toFixed(2);d.append(p);const table=document.createElement('table'),tr=document.createElement('tr');for(const v of['指标','快','慢','慢−快'])cell(tr,v,true);table.append(tr);for(const k of Object.keys(c.metrics_fast)){const row=document.createElement('tr'),a=c.metrics_fast[k],b=c.metrics_slow[k];cell(row,k);cell(row,fmt(a));cell(row,fmt(b));cell(row,a===null||b===null?'—':fmt(b-a));table.append(row)}d.append(table);const det=document.createElement('details'),sum=document.createElement('summary'),pre=document.createElement('pre');sum.textContent='完整原答、参考和身份';pre.textContent=JSON.stringify({object_fast:c.object_fast,object_slow:c.object_slow,reference_id:c.reference_id,raw_fast:c.raw_fast,raw_slow:c.raw_slow,reference:c.reference},null,2);det.append(sum,pre);d.append(det);grid.append(d)}section.append(grid);const img=document.createElement('img');img.className='bev';img.src='data:image/png;base64,'+D.figures[id];img.alt='精确底面几何对照';section.append(img);M.append(section)}
S.onchange=render;for(const id of['reference','fast','slow'])document.getElementById(id).onchange=render;document.getElementById('wide').onclick=()=>document.body.classList.toggle('full');render();
</script></html>'''.replace('DATAHERE',json.dumps(data,ensure_ascii=False).replace('</','<\\/'))
    (P/'CASES_VIEWER.html').write_text(viewer,encoding='utf-8')
    # Verify every embedded panorama and raw object exactly matches its index.
    receipts=json.loads((P/'originals/ORIGINALS_RECEIPT.json').read_text())
    for r in receipts['images']:
        image=(P/'originals'/r['local_path']).read_bytes()
        assert len(image)==int(r['bytes']) and hashlib.sha256(image).hexdigest()==r['sha256']
        cc=[c for c in data['cases'] if c['image_code']==r['image_code']]
        assert cc and all(c['image_id']==r['image_id'] for c in cc)
        assert base64.b64decode(data['photos'][r['image_code']])==image
    m.js('REPORT_VALIDATION.json',dict(report_tables_generated_from_current_csv=True,
        v2_reaggregation_matches_original_63_pair_result=True,embedded_original_images=len(data['photos']),
        original_images_bytes_sha_and_identity_verified=True,case_picture_rows=len(data['cases']),
        no_new_fusion=True,no_new_scoring=True,no_final_classification_adoption=True))
    print('Saved README.md and CASES_VIEWER.html; verified',len(data['photos']),'original panoramas')

if __name__=='__main__':main()
