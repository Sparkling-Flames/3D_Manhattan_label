#!/usr/bin/env python3
"""Unify already computed tables, draw scientific figures, build an offline viewer."""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

BASE=Path(__file__).resolve().parent
FIG=BASE/'figures'
WEB=BASE/'workbench'
METHODS=['TARGET_DSTRUCT_K3','RFUSE_GEOM_K2','OPPJOINT_K3','OPPJOINT_K4','TARGET_DSTRUCT_K2']
LABELS={'TARGET_DSTRUCT_K3':'DSTRUCT K3','TARGET_DSTRUCT_K2':'DSTRUCT K2','RFUSE_GEOM_K2':'RFUSE K2','OPPJOINT_K3':'JOINT K3','OPPJOINT_K4':'JOINT K4'}
COLORS=['#586d87','#c17825','#16786a','#865799']

def safe_records(d):
    return json.loads(d.to_json(orient='records',force_ascii=False,double_precision=15))

def normalize_source(s):
    if s in ['all_sources','all_origins']: return 'all'
    if s.startswith(('origin:','origin=')):return s[7:]
    if s.startswith('time:'):return s[5:]
    return s

def unify():
    a=pd.read_csv(BASE/'dstruct/ALL_CLASSES_COMMON_SUPPORT_PROFILE.csv').rename(columns={'images':'n_images','buildings':'n_buildings'})
    b=pd.read_csv(BASE/'rfuse_joint/ALL_CLASSES_COMMON_SUPPORT_PROFILE.csv')
    cols=['method','condition','scope','source_stratum','metric','class_id','difficulty','n_images','n_buildings','image_equal_mean','building_equal_mean']
    d=pd.concat([a[cols],b[cols]],ignore_index=True)
    d['source_stratum']=d.source_stratum.map(normalize_source)
    d['metric']=d.metric.replace({'record_log_time':'log_time','record_time_seconds':'source_active_time_seconds'})
    assert not d.duplicated(cols[:7]).any()
    d.to_csv(BASE/'UNIFIED_COMMON_CLASS_PROFILES.csv',index=False,encoding='utf-8-sig')
    p=pd.read_csv(BASE/'rfuse_joint/Q_T_COMMON_RECORDS_PAIR_SUMMARY.csv')
    c=pd.read_csv(BASE/'team_effects/COMMON_COMPLETE_PANEL_METRICS.csv')
    return d,p,c

def setup_font(font):
    if font:
        font_manager.fontManager.addfont(font)
        name=font_manager.FontProperties(fname=font).get_name()
        plt.rcParams['font.family']=name
    else:
        plt.rcParams['font.family']=['Noto Sans CJK SC','Microsoft YaHei','DejaVu Sans']
    plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,
        'axes.edgecolor':'#a3adb5','axes.labelcolor':'#263342','xtick.color':'#364452',
        'ytick.color':'#364452','text.color':'#172733','figure.facecolor':'#ffffff',
        'axes.facecolor':'#ffffff','svg.fonttype':'path','svg.hashsalt':'HOHONET_current_class_20261104',
        'axes.unicode_minus':False})

def emit(fig,name):
    fig.savefig(FIG/(name+'.png'),dpi=170,bbox_inches='tight',facecolor='white')
    fig.savefig(FIG/(name+'.svg'),bbox_inches='tight',metadata={'Date':None})
    plt.close(fig)

def figures(d,p):
    FIG.mkdir(exist_ok=True)
    zz=d[(d.method=='TARGET_DSTRUCT_K3')&(d.condition=='manual')&(d.scope=='primary')&(d.source_stratum=='all')]
    fig,axes=plt.subplots(1,3,figsize=(14.8,5.8))
    fig.subplots_adjust(left=.065,right=.98,top=.72,bottom=.21,wspace=.26)
    fig.text(.065,.94,'DSTRUCT：困难图上的局部结构差异更清楚',fontsize=20,fontweight='bold')
    fig.text(.065,.875,'当前楼外类别；普通 Manual 主目标；每张图先比较三类，再对图片等权',fontsize=11,color='#52616e')
    grades=['简单','中等','困难']
    for ax,metric,title in zip(axes,['B8L2','turn_n','short_turn_edges'],['个人 Q（B8L2，分）','有效转折数','短墙段数']):
        for i,cl in enumerate(['C1','C2','C3']):
            sub=zz[(zz.metric==metric)&(zz.class_id==cl)].set_index('difficulty').loc[grades]
            yy=sub.image_equal_mean.to_numpy()
            ax.plot(range(3),yy,color=COLORS[i],label=cl,lw=2.3,marker='o',ms=6)
        ax.set_xticks(range(3),grades);ax.set_title(title,loc='left',pad=15,fontsize=13)
        ax.grid(axis='y',color='#e6eaf0',lw=.8);ax.set_axisbelow(True)
        if metric=='B8L2':ax.set_ylim(35,100)
        elif metric=='turn_n':ax.set_ylim(3.7,9.3)
        else:ax.set_ylim(-.05,2.2)
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,ncol=3,loc='upper right',bbox_to_anchor=(.975,.86),frameon=False)
    fig.text(.065,.105,'三类共同支持：简单 129 图，中等 37 图，困难 35 图。不同难度使用各自的同图共同支持。',fontsize=10,color='#52616e')
    fig.text(.065,.055,'短墙：边长占周长 <4%，两端转角 ≥15°。来源：dstruct/ALL_CLASSES_COMMON_SUPPORT_PROFILE.csv',fontsize=9,color='#52616e')
    emit(fig,'F01_DSTRUCT_difficulty_original_profiles')

    keep=[('TARGET_DSTRUCT_K3','C2','C3','DSTRUCT C3−C2','#176e9b','o'),
          ('RFUSE_GEOM_K2','C1','C2','RFUSE C2−C1','#21836a','D'),
          ('OPPJOINT_K4','C1','C2','JOINT K4 C2−C1','#965eaa','s')]
    fig,axes=plt.subplots(1,2,figsize=(14.8,7))
    fig.subplots_adjust(left=.075,right=.975,top=.74,bottom=.22,wspace=.18)
    fig.text(.075,.95,'同一批原答的 Q 与记录劳动，呈现不同的类别关系',fontsize=19,fontweight='bold')
    fig.text(.075,.89,'每个点内部严格同图、同参考、同来源、同一批正时间原答；各类对的图片支持单列',fontsize=11,color='#52616e')
    for ax,origin,title in zip(axes,['new','v1'],['new：用户处理后报告时间','v1：已审计继承时间']):
        ax.axhline(0,color='#c1c8ce',lw=1);ax.axvline(0,color='#c1c8ce',lw=1)
        for method,ca,cb,label,color,marker in keep:
            g=p[(p.method==method)&(p.class_A==ca)&(p.class_B==cb)&(p.condition=='manual')&(p.scope=='primary')&(p.difficulty=='ALL')&p.source_stratum.str.startswith(origin+'|')]
            if g.empty:continue
            row=g.iloc[0];x=100*(row.image_equal_geometric_time_ratio-1);y=row.image_equal_delta_Q
            ax.scatter([x],[y],s=95,c=color,marker=marker,zorder=3)
            off=(-115,27) if (origin=='new' and method.startswith('TARGET')) else ((-130,-43) if method.startswith('RFUSE') else ((15,12) if x<0 else (15,-17)))
            txt=f'{label}\nQ {y:+.2f}；T {x:+.1f}%\n{int(row.n_images)} 图 / {int(row.n_buildings)} 楼'
            ax.annotate(txt,(x,y),xytext=off,textcoords='offset points',fontsize=10,color=color,
                arrowprops=dict(arrowstyle='-',color=color,lw=.7),ha='left',va='center')
        ax.set_xlim(-24,14);ax.set_ylim(-3.2,22)
        ax.set_title(title,loc='left',pad=17,fontsize=13)
        ax.set_xlabel('几何平均时间比 − 1（%）',labelpad=10)
        ax.grid(color='#edf0f3',lw=.7);ax.set_axisbelow(True)
    axes[0].set_ylabel('同图 Q 差（分）',labelpad=10)
    fig.text(.075,.12,'正 Q 表示后一类质量更高；正 T 表示后一类记录劳动更长。JOINT C1/C2 的 Q 图均值接近，时间方向一致。',fontsize=10,color='#52616e')
    fig.text(.075,.07,'RFUSE 没有 v1 双类共同时间支持。Q/T 完整类对与建筑等权结果：rfuse_joint/Q_T_COMMON_RECORDS_PAIR_SUMMARY.csv',fontsize=9,color='#52616e')
    emit(fig,'F02_same_records_quality_and_time')

HTML=r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HOHONET v2.1 当前类别：原答、共识与混合</title>
<style>
:root{--ink:#192c35;--muted:#566975;--line:#d9e2e7;--accent:#126d61;--back:#f2f5f6;--blue:#246d9b}
*{box-sizing:border-box}body{margin:0;color:var(--ink);font:16px/1.75 system-ui,"Microsoft YaHei",sans-serif;background:var(--back)}
header,main,footer{max-width:1320px;margin:auto;padding:24px 32px}header{padding-top:46px;padding-bottom:14px}h1{font-size:36px;line-height:1.25;margin:6px 0 18px}h2{font-size:25px;line-height:1.4;margin:0 0 20px}h3{font-size:19px;margin:24px 0 10px}p{margin:10px 0 18px}a{color:var(--accent);text-underline-offset:3px}nav{display:flex;gap:10px 22px;flex-wrap:wrap;border-top:1px solid var(--line);padding:15px 0}nav a{text-decoration:none;font-weight:600}.kicker{color:var(--accent);font-size:13px;font-weight:700;letter-spacing:.04em}.intro{font-size:18px;max-width:1050px}.muted{color:var(--muted);font-size:14px}.section{background:white;border:1px solid var(--line);border-radius:10px;padding:28px 30px;margin:0 0 25px}.lead{border-left:4px solid var(--accent);padding-left:18px}.controls{display:flex;gap:18px;flex-wrap:wrap;margin:18px 0 10px}.controls label{display:block;color:var(--muted);font-size:13px}.controls select{display:block;min-width:150px;max-width:260px;background:#fff;border:1px solid #a8bac3;border-radius:4px;padding:8px 10px;color:var(--ink);font:inherit}.tablewrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:10px 12px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}th:first-child,td:first-child{text-align:left}th{font-weight:600;background:#f2f6f6}td.note{white-space:normal;text-align:left;min-width:240px}tr:last-child td{border-bottom:0}.figure{margin:20px 0 4px}.figure img{display:block;width:100%;height:auto;border:1px solid #edf0f2}.figure figcaption{font-size:13px;color:var(--muted);margin-top:10px}.links{display:flex;flex-wrap:wrap;gap:10px 22px}.button{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;padding:10px 16px;border-radius:5px;font-weight:600}.grid{display:grid;grid-template-columns:1fr 1fr;gap:22px}.note-box{background:#f4f8f9;padding:14px 18px;border-radius:6px}.facts{display:grid;grid-template-columns:repeat(4,1fr);gap:15px;margin:22px 0}.fact{border-top:2px solid var(--accent);padding-top:9px}.fact strong{display:block;font-size:24px}.fact span{font-size:13px;color:var(--muted)}.empty{padding:22px;color:var(--muted)}footer{font-size:13px;color:var(--muted);padding-bottom:40px}code{font-family:ui-monospace,Consolas,monospace;font-size:.9em;overflow-wrap:anywhere}button{cursor:pointer}noscript{display:block;padding:20px;background:#fff3d6}@media(max-width:760px){header,main,footer{padding-left:16px;padding-right:16px}.section{padding:21px 17px}h1{font-size:29px}.grid{grid-template-columns:1fr}.facts{grid-template-columns:repeat(2,1fr)}th,td{padding:9px}.controls select{min-width:120px}}
</style></head><body>
<header><div class="kicker">HOHONET v2.1 · 当前类别解释 · 2026-11-04</div>
<h1>人怎样标注，差异怎样进入共识与混合人群</h1>
<p class="intro">当前 DSTRUCT、RFUSE 与 JOINT 已有清楚的解释用途。局部结构、位置、质量和记录劳动之间的关系各有特点；类别配比、具体成员与共同背景共同影响融合结果。</p>
<div class="facts"><div class="fact"><strong>6,512</strong><span>普通 Manual 主目标原答</span></div><div class="fact"><strong>206 / 22</strong><span>原答图片 / 建筑</span></div><div class="fact"><strong>174</strong><span>三体系相同团队的共同面板</span></div><div class="fact"><strong>4 张原图</strong><span>简单、中等、困难与跨楼附例</span></div></div>
<nav><a href="#original">原答画像</a><a href="#qt">同源 Q/T</a><a href="#examples">完整标注</a><a href="#teams">团队与混合</a><a href="#read">报告与来源</a></nav></header>
<main>
<section class="section" id="original"><h2>1. 类别在原答中有什么区别</h2>
<p class="lead">DSTRUCT 在 201 张三类共同图片上的平均 Q 为 <strong>64.97 / 66.91 / 80.97</strong>。C3 的困难图结构保留更多，位置误差更小。RFUSE 的较高困难结构响应类也有相近的原答联系。JOINT 同时组织质量与劳动特征，其编号不构成稳定的低、中、高质量梯度。</p>
<div class="controls"><label>当前分类<select id="method"></select></label><label>作答方式<select id="condition"><option value="manual">Manual</option><option value="semi">Semi（Manual 类别迁移）</option></select></label><label>目标范围<select id="scope"><option value="primary">主目标</option><option value="other_admitted">其他合法目标</option></select></label><label>难度<select id="difficulty"><option value="ALL">全部难度</option><option>简单</option><option>中等</option><option>困难</option></select></label></div>
<p id="method-note" class="muted"></p><div id="profile" class="tablewrap"></div>
<p class="muted">每个指标先取同图、同合法目标中的类均值，再对图片等权。每个方法内部使用全部类别共同支持；不同方法的图数可以不同。时间在下一节按共同原答单独比较。</p>
<figure class="figure"><a href="../figures/F01_DSTRUCT_difficulty_original_profiles.svg"><img src="../figures/F01_DSTRUCT_difficulty_original_profiles.png" alt="DSTRUCT 三类在简单、中等、困难图中的质量、转折和短墙段均值"></a><figcaption>结构特征用于形成 DSTRUCT；楼外 Q、位置与时间用于补充解释。<a href="../dstruct/REPORT_ZH.md">DSTRUCT 完整报告与类内分布</a></figcaption></figure>
</section>
<section class="section" id="qt"><h2>2. 同一批原答的 Q 与记录劳动</h2>
<p>质量较高不必对应大幅更长的记录劳动。JOINT K4 的 C2 相对 C1，在 new 来源 162 图上 Q 差仅 −0.133 分，几何时间比 0.885；v1 来源 87 图上 Q 差 +0.678 分，时间比 0.834。不同类对和来源的关系全部保留在表中。</p>
<div class="controls"><label>记录来源<select id="source"><option value="new">new：用户处理后报告时间</option><option value="v1">v1：已审计继承时间</option></select></label></div>
<div id="qt-table" class="tablewrap"></div>
<p class="muted">沿用上方分类、方式、目标及难度选择。每行 Q/T 都来自相同的正时间原答；差值为后一类减前一类，T 比大于 1 表示后一类更长。算术秒差与几何时间比分列。</p>
<figure class="figure"><a href="../figures/F02_same_records_quality_and_time.svg"><img src="../figures/F02_same_records_quality_and_time.png" alt="DSTRUCT、RFUSE、JOINT 的同记录同来源质量差与时间比"></a><figcaption>不同来源及类对各有支持范围；本图展示三种有解释意义的关系，完整类对可在上表和 CSV 中查看。</figcaption></figure>
</section>
<section class="section" id="examples"><h2>3. 在同一张原图上看完整标注</h2>
<p>典型例按照各类的结构与位置特征中位接近度选择，每类至多两人；K4 C3 在这四图上各只有一人并全部展示，选样不使用 Q/T。三张主图来自同一建筑的楼外模型折，另有跨楼附例及近共线诊断对照。图册保留上下边界、原顺序、参考、底面、个人 Q 分项与记录时间。</p>
<p><a class="button" href="../examples/index.html">打开可离线切换的完整原图图册</a> <a class="button" href="../examples/index.html#method=OPPJOINT_K4">直接查看 JOINT K4 四类</a></p>
<p>第 10 批在相同四图新增 K4 的 28 个展示位。图册现有 92 个典型位、1 个近共线附例、39 个不同原答，原统计数值保持。<a href="../examples/JOINT_K4_SUPPLEMENT.html">K4 补充说明与全部个人指标</a></p>
<figure class="figure"><a href="../examples/figures/jtcxE69GiFV-26__DSTRUCT.png"><img src="../examples/figures/jtcxE69GiFV-26__DSTRUCT.png" alt="困难图 jtcxE69GiFV-26 上 DSTRUCT 三类各两人的完整标注"></a><figcaption>困难图：图中 DSTRUCT C3 两个典型原答均保留 8 个转折、3 段短墙；其他典型原答为 5–6 个转折、0–1 段短墙。Q 与 T 在类内仍有差异。例图解释具体标法，整体结论由同图统计支持。</figcaption></figure>
<figure class="figure"><a href="../examples/figures/jtcxE69GiFV-26__JOINT_K4.png"><img src="../examples/figures/jtcxE69GiFV-26__JOINT_K4.png" alt="同一困难图 JOINT K4 四类完整标注和个人质量劳动指标"></a><figcaption>JOINT K4：C4 两例保留 8 转折、3 短墙；C1 为 9/6 转折，C2 为 5/6，C3 唯一成员为 4。完整原答把结构、位置与劳动放在同图观察，既有总体 Q/T 仍由原共同支持统计回答。</figcaption></figure>
<p class="links"><a href="../examples/README.md">选图、选人及逐图解释</a><a href="../examples/SELECTED_RECORDS.csv">展示对象、坐标身份与分项</a><a href="../examples/figures/near_collinear_W114_W116.png">同为六对点的近共线对照</a></p>
</section>
<section class="section" id="teams"><h2>4. 类别、比例、成员与背景怎样影响团队</h2>
<div class="grid"><div><h3>严格 ABC：幅度与方向</h3><p>DSTRUCT 14 人换 7 人，当前合法辅助版的对称跨类额外 Q 变化为 <strong>+3.441 分</strong>，50/69 图为正；C−B 为 <strong>+6.712 分</strong>，65/69 图为正。多数图的转折额外变化为零，质量差还来自边界、方向、高度与面积分项。</p></div><div><h3>直接 AC：均值与变化分布</h3><p>RFUSE 20/4 的 Q 平均差为 <strong>+2.934</strong>，77/82 图为正。JOINT K3 20/10 的均值为 <strong>+0.297</strong>，但平均绝对变化为 <strong>3.282</strong>，42 图升、40 图降，表明方向抵消。</p></div></div>
<h3>完全相同的既有团队集合</h3><div id="team-table" class="tablewrap"></div>
<p class="muted">共同支持为 174 面板、32 图、21 楼；每面板完整覆盖 924 支已存在团队。Q 有效 159,655 队次；时间为 130 面板、31 图、116,966 个同源有效队次。方差先按面板、池、图片、建筑汇总，再计算份额；K3/K4 分区细化本身也会影响份额。</p>
<figure class="figure"><a href="../team_effects/COMMON_TEAM_COMPOSITION_VARIANCE.svg"><img src="../team_effects/COMMON_TEAM_COMPOSITION_VARIANCE.png" alt="当前分类在相同有限团队集合上的配比间及同配比成员方差"></a><figcaption>类别配比对 Q、结构和劳动有实际影响；同配比的具体成员仍解释大部分波动。<a href="../team_effects/REPORT_ZH.md">严格 ABC、联盟、成员、背景和同房的完整解释</a></figcaption></figure>
<div class="note-box"><strong>困难图同时放大两种差异。</strong> DSTRUCT 配比间 Q 方差由简单图的 1.081 增至困难图的 14.758，同配比成员方差由 5.496 增至 81.682。份额近似不变与绝对差异扩大同时成立。</div>
<p>完整联盟、固定比例换成员、固定替换块换背景分别保留其实际人数与支持。主目标全部已分类人员合并队在 169/205 图上弱于至少一支纯类队，这是事后完整组合的观察；具体选员和进入策略仍使用各自已有实验。</p>
</section>
<section class="section" id="read"><h2>5. 完整报告、逐类表与复现入口</h2>
<p class="links"><a class="button" href="../REPORT_ZH.html">阅读完整整合报告</a><a href="../README.md">研究目录说明</a><a href="../basis/CLASS_ORIGINAL_TEAM_TABLES.md">三体系逐类总表</a><a href="../basis/CLASS_ORIGINAL_TEAM_MATRIX.csv">逐类矩阵 CSV</a><a href="../METHODS_AND_METRICS.md">预处理、来源、权重与特征定义</a></p>
<div class="grid"><div><h3>人员与原答</h3><p class="links"><a href="../basis/README_ZH.md">当前建类依据与容量</a><a href="../basis/WORKER_ROSTER_ALL.csv">ALL 描述名单</a><a href="../UNIFIED_COMMON_CLASS_PROFILES.csv">全部同图全类画像</a><a href="../rfuse_joint/REPORT_ZH.md">RFUSE / JOINT 解释</a><a href="../rfuse_joint/Q_T_COMMON_RECORDS_PAIR_SUMMARY.csv">全部同源共同 Q/T</a></p></div><div><h3>团队、版本与引用</h3><p class="links"><a href="../team_effects/UNIFIED_EVIDENCE_MATRIX.csv">2,084 条团队条件与出处</a><a href="../CONCLUSION_LEDGER.csv">逐条采用判断</a><a href="../SOURCE_INDEX.csv">固定版本完整来源</a><a href="../../../data/releases/v2.1/CURRENT_RESEARCH_BASIS.md">v2.1 当前研究口径</a><a href="../../../statistics/research_explorer_v1_r2_20261017/index.html">返回原研究台</a></p></div></div>
<p class="muted">本轮补充画像和已有团队重聚合，不改变分类、原答、参考、坐标或评分。当前类别的进入顺序与劳动分配用途，仍按相应实际应用证据判断。历史自动结果和固定节点人工辅助结果保留各自身份。</p>
</section></main>
<footer>来源固定提交：<code>48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b</code>。界面数据内嵌，不依赖在线请求；PNG/SVG、CSV、代码及完整原图随目录提供。</footer>
<noscript>交互表需要 JavaScript。全部静态科研图、原图图册板及报告仍可直接打开。</noscript>
<script id="research-data" type="application/json">__DATA__</script>
<script>
const data=JSON.parse(document.getElementById('research-data').textContent);
const $=id=>document.getElementById(id);const fmt=(v,n=3)=>(v===null||v===undefined||v===''||!Number.isFinite(Number(v)))?'—':Number(v).toFixed(n);
const methods=data.methods;for(const [key,label] of Object.entries(methods)){const o=document.createElement('option');o.value=key;o.textContent=label;$('method').append(o)}
function controls(){return {method:$('method').value,condition:$('condition').value,scope:$('scope').value,difficulty:$('difficulty').value}}
function selected(row,c){return ['method','condition','scope','difficulty'].every(k=>row[k]===c[k])}
function table(headers,rows){return '<table><thead><tr>'+headers.map(t=>'<th>'+t+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(t=>'<td>'+t+'</td>').join('')+'</tr>').join('')+'</tbody></table>'}
function draw(){const c=controls(),k=Number(c.method.slice(-1)),cls=Array.from({length:k},(_,i)=>'C'+(i+1));
const rows=[];for(const [metric,label,scale,dp] of data.metrics){const zz=data.profiles.filter(r=>selected(r,c)&&r.source_stratum==='all'&&r.metric===metric);if(!zz.length)continue;const values=cls.map(cl=>{const r=zz.find(z=>z.class_id===cl);return r?fmt(r.image_equal_mean*scale,dp):'—'});rows.push([label,...values,zz[0].n_images+' / '+zz[0].n_buildings]);}
$('profile').innerHTML=rows.length?table(['指标',...cls,'图 / 楼'],rows):'<p class="empty">这个条件没有全部类别共同的有效支持；对应逐类及两类支持见 CSV。</p>';
$('method-note').textContent=data.notes[c.method];
const q=data.qt.filter(r=>selected(r,c)&&r.source_stratum.startsWith($('source').value+'|')).sort((a,b)=>(a.class_A+a.class_B).localeCompare(b.class_A+b.class_B));
$('qt-table').innerHTML=q.length?table(['比较','Q 差（分）','几何 T 比','算术 T 秒差','图 / 楼','Q 正向图'],q.map(r=>[r.class_B+' − '+r.class_A,fmt(r.image_equal_delta_Q),fmt(r.image_equal_geometric_time_ratio),fmt(r.image_equal_delta_T_seconds,1),r.n_images+' / '+r.n_buildings,r.Q_positive_images+' / '+r.n_images])):'<p class="empty">该来源与条件没有两类共同的正时间原答支持。</p>';
}
for(const id of ['method','condition','scope','difficulty','source'])$(id).addEventListener('change',draw);
const tr=[];for(const m of data.teamMethods){const values=data.teamMetrics.map(metric=>{const r=data.teams.find(r=>r.method===m&&r.metric===metric);return r?fmt(100*r.between_share,2)+'%':'—'});tr.push([methods[m],...values])};$('team-table').innerHTML=table(['当前分区','Q 配比间份额','转折份额','短边份额','log 劳动份额'],tr);draw();
</script></body></html>'''

def workbench(d,p,c):
    WEB.mkdir(exist_ok=True)
    notes={
        'TARGET_DSTRUCT_K3':'DSTRUCT K3：按训练困难结构中心排序；未直接输入 Q/T。当前主分类，ALL 名单 10/37/12 人。实际图片使用目标楼外标签。',
        'TARGET_DSTRUCT_K2':'DSTRUCT K2：当前结构分类的粗分描述。保持已有 K2，不由本表重新选择分类。',
        'RFUSE_GEOM_K2':'RFUSE K2：按训练困难融合结构响应排序；GEOM 输入不直接包含 Q/T。ALL C2 为 4 人，实际 LOBO 每折 4–6 人，跨折累计不等于每图容量。',
        'OPPJOINT_K3':'JOINT K3：结构、边界、Q 和 T 的联合画像。Q/T 已参与训练；本表为楼外原答表现。C 编号是各折训练 Q 中心顺序。',
        'OPPJOINT_K4':'JOINT K4：更细的联合画像。历史训练 Q/T 差异是分类依据，楼外同图同源差异补充解释。C3 不代表一组跨折不变的“慢者”。'}
    metrics=[['B8L2','Q：B8L2（分）',1,2],['turn_n','有效转折数',1,3],['short_turn_edges','短墙段数',1,3],['near_straight_nodes_5deg','近共线点数',1,3],['unmatched_ref_9','参考未匹配（%）',100,2],['matched_boundary_abs_deg','匹配边界绝对偏差（度）',1,3],['iou_2d','底面 IoU',1,3],['S_bottom_deg','底边位置误差（度）',1,3],['dir','方向误差（度）',1,3],['Hmean','全局高度相对误差（%）',100,2],['Hcenter','局部高度相对误差（%）',100,2],['omission','遗漏面积比例（%）',100,2],['extension','延伸面积比例（%）',100,2]]
    # The viewer compares levels only on all-class common support, not mixed per-class support.
    ds=d[d.source_stratum.eq('all') & d.metric.isin([v[0] for v in metrics])]
    cp=c[c.metric.isin(['B8L2','fusion_turn_n','fusion_short_turn_edges','log_record_time_sum'])].copy()
    # Preserve source metric names; detect actual existing labels rather than guess.
    turns=next(x for x in c.metric.unique() if x in ['fusion_turn_n','turn_n','floor_turn5_n'])
    short=next(x for x in c.metric.unique() if x in ['fusion_short_turn_edges','short_turn_edges','floor_short_edge_03_n'])
    labor=next(x for x in c.metric.unique() if 'log' in x.lower() and 'time' in x.lower())
    tm=['B8L2',turns,short,labor];cp=c[c.metric.isin(tm) & c.summary_axis.eq('all') & c.summary_value.eq('all')].copy()
    data=dict(methods={m:LABELS[m] for m in METHODS},metrics=metrics,profiles=safe_records(ds),
        qt=safe_records(p),teams=safe_records(cp),notes=notes,teamMetrics=tm,teamMethods=METHODS[:4])
    text=json.dumps(data,ensure_ascii=False,allow_nan=False,separators=(',',':')).replace('</',r'<\/')
    (WEB/'DATA.json').write_text(text+'\n',encoding='utf-8')
    (WEB/'index.html').write_text(HTML.replace('__DATA__',text),encoding='utf-8')
    (WEB/'README.md').write_text('# 当前类别研究台\n\n直接双击 `index.html`。核心数据内嵌，图与图册使用相对路径，不需要本地 HTTP 服务。按分类、作答方式、目标和难度切换原答表；Q/T 再按合法时间来源切换。\n\n复现：仓库根运行 `python research/workers/current_class_interpretation_20261104/build_synthesis.py --font <可用中文字体路径>`。PNG/SVG 已随包提供。\n',encoding='utf-8')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--font');args=ap.parse_args()
    d,p,c=unify();setup_font(args.font);figures(d,p);workbench(d,p,c)
    print(json.dumps(dict(unified_profile_rows=len(d),QT_conditions=len(p),figures=2,offline_workbench=str(WEB/'index.html')),ensure_ascii=False))

if __name__=='__main__':main()
