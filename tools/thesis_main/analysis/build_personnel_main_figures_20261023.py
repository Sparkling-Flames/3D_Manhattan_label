"""将已核人员结果制作为研究台汇报图；不重评分、融合或拟合类别。"""
from pathlib import Path
import json
import textwrap
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/workers/personnel_main_figures_v2_20261023'
MIX = 'research/workers/personnel_mixture_comparison_20261022'
POP = 'research/workers/personnel_population_curves_v2_20261023'
AUDIT = 'research/statistics/same_room_rebuilt_audit_20261023/results'
COLORS = ['#216D91', '#D17A35', '#41876D', '#865E9E', '#B84950', '#89939C']
DIFF = {'简单': '#41876D', '中等': '#D17A35', '困难': '#865E9E'}
FIGURES = []
FONT = Path('C:/Windows/Fonts/msyh.ttc')
if FONT.exists():
    font_manager.fontManager.addfont(str(FONT))
    plt.rcParams['font.family'] = font_manager.FontProperties(fname=str(FONT)).get_name()
plt.rcParams.update({'font.size': 11, 'axes.unicode_minus': False, 'svg.fonttype': 'path',
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.labelcolor': '#243746', 'text.color': '#243746',
                     'xtick.color': '#52616B', 'ytick.color': '#52616B',
                     'axes.titleweight': 'bold', 'figure.facecolor': 'white'})


def read(path):
    return pd.read_csv(ROOT / path, low_memory=False)


def local(name):
    return pd.read_csv(OUT / 'data' / name, low_memory=False)


def export_data(frame, name):
    frame.to_csv(OUT / 'data' / name, index=False, encoding='utf-8-sig')
    return f'data/{name}'


def canvas(rows=1, cols=1, size=(14, 8)):
    fig, axes = plt.subplots(rows, cols, figsize=size, squeeze=False)
    fig.subplots_adjust(left=.12, right=.96, bottom=.20, top=.79, wspace=.42, hspace=.72)
    return fig, axes


def finish(fig, fid, group, title, finding, reading, support, sources, tables, terms, rank='main'):
    fig.suptitle(title, x=.055, y=.955, ha='left', fontsize=20, weight='bold')
    fig.text(.055, .887, '\n'.join(textwrap.wrap(finding, 70)), fontsize=12, va='top')
    fig.text(.055, .105, '\n'.join(textwrap.wrap(reading, 83)), fontsize=10, va='top')
    fig.text(.055, .035, support, fontsize=9, color='#65737E')
    for ext in ['png', 'svg']:
        fig.savefig(OUT / 'figures' / f'{fid}.{ext}', dpi=180, facecolor='white')
    plt.close(fig)
    FIGURES.append(dict(id=fid, group=group, title=title, finding=finding, reading=reading,
                        support=support, image=f'figures/{fid}.png', vector=f'figures/{fid}.svg',
                        source_paths=sources, data_paths=tables, term_ids=terms, priority=rank,
                        display='static_saved_result', data_release='v2'))


def classification():
    schemes=local('CLASSIFICATION_SCHEMES.csv'); people=local('CLASSIFICATION_MEMBERS.csv')
    assert len(people)==248 and people.groupby('scheme_id').size().eq(62).all()
    fig, aa=canvas(2,2,(15,10));fig.subplots_adjust(left=.24,wspace=.9,hspace=.65)
    for ax, scheme in zip(aa.flat,schemes.itertuples()):
        d=people[people.scheme_id.eq(scheme.scheme_id)].groupby(['fine_label','name_zh'],dropna=False).size().reset_index(name='n').sort_values('fine_label')
        bars=ax.barh(range(len(d)),d.n,color=[COLORS[i%5] if c!='unknown' else '#B6BDC4' for i,c in enumerate(d.fine_label)])
        ax.set_yticks(range(len(d)),[f'{r.fine_label}  '+textwrap.fill(r.name_zh,13) for r in d.itertuples()],fontsize=9)
        ax.invert_yaxis();ax.set_xlim(0,40);ax.set_xlabel('人员数（跨图总名单）');ax.set_title(scheme.scheme_name_zh,loc='left',fontsize=12)
        ax.bar_label(bars,padding=4);ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
    finish(fig,'F1_class_rosters','F1','01 先看有哪些类，再看具体人员',
           '四套方案衡量不同历史特征；每套都保留证据不足的人员。Semi结构细层与父类关系另见名单。',
           '这是ALL全历史描述名单；同一个人在不同方案中可以属于不同类别。实际组合实验读取目标建筑对应的楼外标签。',
           '四套各62人；已知人数依次59、57、59、54。名单、类定义与训练支持可逐人查看。',
           schemes.source_file.unique().tolist(),['data/CLASSIFICATION_MEMBERS.csv','data/CLASSIFICATION_SCHEMES.csv'],['taxonomy_all','taxonomy_lobo','condition_manual','condition_semi'])
    centers=local('CLASSIFICATION_CENTERS.csv')
    features=[('complex_turn_history','复杂结构转折残差（个）'),('q_history','历史质量残差（Q分）'),('t_history','历史耗时残差（自然对数）')]
    fig, aa=canvas(1,3,(15,7));fig.subplots_adjust(left=.12,wspace=.48)
    for ax,(feature,label) in zip(aa.flat,features):
        d=centers[centers.scheme_id.eq('manual_joint_qt')&centers.feature.eq(feature)&centers.known].sort_values('fine_label')
        ax.barh(d.fine_label,d.value,color=COLORS[:len(d)]);ax.axvline(0,color='#7A8791',lw=.8);ax.invert_yaxis()
        ax.set_title(label,fontsize=12);ax.grid(axis='x',alpha=.15)
        for i,r in enumerate(d.itertuples()):ax.text(r.value,i,f' {r.value:+.2f}',va='center',ha='left' if r.value>=0 else 'right',fontsize=10)
        lo,hi=ax.get_xlim();ax.set_xlim(lo-(hi-lo)*.22,hi+(hi-lo)*.25)
    finish(fig,'F1_joint_features','F1','01 分类依据：质量接近的人，速度和标法仍可不同',
           'Manual联合类同时保留结构、历史Q与时间差异；J1/J2/J3历史Q相近，但转折与耗时明显不同。',
           '残差表示相对同图基准的偏离，0为基准；三列量纲不同。复杂结构机会C用于历史解释，人工难度D另行分层。',
           'ALL描述性类中心；由个人建筑等权历史形成，不是目标图结果。具体特征处理见分类说明。',
           centers.source_file.unique().tolist(),['data/CLASSIFICATION_CENTERS.csv'],['history_residual','structure_context_c','q_history','time_history','recorded_time'])


def configuration_panel(ax,d,title,code='M3.1'):
    class_keys=sorted(set().union(*(json.loads(x) for x in d.class_counts)))
    if class_keys==['M1.1','M2.1','M3.1'] and d.class_counts.map(lambda x:json.loads(x)['M1.1']).eq(0).all():
        d=d.assign(x=d.class_counts.map(lambda x:json.loads(x)[code])).sort_values('x')
        labels=[str(v) for v in d.x];xlabel='较多转折角色人数 / 全队20人'
    else:
        d=d.assign(sort_key=d.class_counts.map(lambda x:tuple(json.loads(x).get(k,0) for k in class_keys))).sort_values('sort_key')
        labels=['/'.join(str(json.loads(x).get(k,0)) for k in class_keys) for x in d.class_counts]
        xlabel='全队类别人数向量：'+' / '.join(class_keys)
    x=np.arange(len(d))
    for i,r in enumerate(d.itertuples()):
        if r.scorable_teams>=2:
            ax.plot([i,i],[r.B8L2_p05,r.B8L2_p95],color='#8CB9CB',lw=1.5)
            ax.plot([i,i],[r.B8L2_p25,r.B8L2_p75],color=COLORS[0],lw=7,solid_capstyle='butt')
        ax.scatter(i,r.B8L2_mean,color='#D17A35',s=34,zorder=4)
        ax.annotate(f'{r.scorable_teams}/{r.teams}',(i,1),xycoords=('data','axes fraction'),xytext=(0,5),textcoords='offset points',ha='center',fontsize=8)
    ax.set_ylim(0,100);ax.set_ylabel('质量Q（0-100）');ax.set_xticks(x,labels,rotation=45 if len(d)>8 else 0,fontsize=8)
    ax.set_title(title,loc='left',fontsize=12,pad=28);ax.grid(axis='y',alpha=.15)
    ax.set_xlabel(xlabel,fontsize=9,labelpad=12)


def mixture():
    pieces=[]
    for name in ['manual_structure','manual_small_separation','semi_structure','semi_null','semi_failure','manual_joint','semi_joint']:
        p=f'{MIX}/configurations/EXAMPLE_{name}_ALL_CONFIGURATIONS.csv';d=read(p)
        assert d.panel_id.nunique()==1 and d.teams.sum()==924 and (d.teams==d.scorable_teams+d.failed_teams).all()
        cols=['example_id','configuration_id','panel_id','image','building','condition','difficulty','n','method','tier','class_counts','background_class_counts','teams','scorable_teams','failed_teams','failure_rate']
        cols += [c for c in d if c.startswith('B8L2_') or c in ['fusion_turn_n_mean','recorded_time_total_seconds_mean']]
        pieces.append(d[cols].assign(source_file=p))
    all_rows=pd.concat(pieces,ignore_index=True);export_data(all_rows,'MIXTURE_EXAMPLE_CONFIGURATIONS.csv')
    for fid,names,title,subtitle in [
        ('F2_manual',['manual_structure','manual_small_separation'],'02 配比改变与配比内换人，是两层不同的变化','Manual结构类：困难图7y-21的配比趋势明显；pa4-18的四个完整配比格均值接近。'),
        ('F2_semi',['semi_structure','semi_failure'],'02 Semi：同时看分布与失败','7y-13的配比和成员均有明显差异；Z6-10九格共有205/924队不可评分。'),
        ('F2_joint',['manual_joint','semi_joint'],'02 联合类：保留完整配比，解释成员差异','Manual 7y-21有16格，Semi B6-22有24格；每个有限面板均包含12选6的924个成员集合。')]:
        fig,aa=canvas(2,1,(15,11));fig.subplots_adjust(left=.09,right=.95,top=.81,bottom=.20,hspace=1.0)
        for ax,name in zip(aa.flat,names):
            d=all_rows[all_rows.example_id.eq(name)]
            configuration_panel(ax,d,f'{d.condition.iloc[0].capitalize()} · {d.image.iloc[0]} · n={d.n.iloc[0]} · {len(d)}格')
        finish(fig,fid,'F2',title,subtitle,
               '橙点=均值，粗线=P25-P75，细线=P05-P95，图上数字=可评分/全部团队。线段是格内成员分布，不是均值置信区间；单队格不画波动线。',
               '固定背景D后12选6；每面板完整924队。类别向量属于该建筑楼外折，不能套用ALL同号类名。',
               all_rows[all_rows.example_id.isin(names)].source_file.unique().tolist(),['data/MIXTURE_EXAMPLE_CONFIGURATIONS.csv'],['composition_cell','distribution_band','taxonomy_all','taxonomy_lobo','score_failure'],rank='supplement' if fid=='F2_joint' else 'main')
    fig,aa=canvas(1,2,(14,7))
    for ax,name in zip(aa.flat,['semi_null','semi_failure']):
        d=all_rows[all_rows.example_id.eq(name)].reset_index(drop=True)
        if name=='semi_null':
            ax.plot(np.arange(1,len(d)+1),d.B8L2_mean,'o-',color=COLORS[0]);ax.set_ylim(0,100);ax.set_ylabel('配比格平均Q（0-100）')
            ax.text(.05,.12,f'全部8格均值范围\n{d.B8L2_mean.min():.3f} - {d.B8L2_mean.max():.3f}',transform=ax.transAxes)
            ax.set_title('X7-05：改配比后的Q差异很小',fontsize=12)
        else:
            ax.bar(np.arange(1,len(d)+1),100*d.failure_rate,color='#B84950');ax.set_ylim(0,100);ax.set_ylabel('不可评分团队比例（%）')
            ax.set_title('Z6-10：各配比失败率不同',fontsize=12)
        ax.set_xlabel('完整配比格编号（精确向量见原表）');ax.grid(axis='y',alpha=.15)
    finish(fig,'F2_counterexamples','F2','02 弱差异与失败也是完整结果的一部分',
           '相同的分类框架，在另一些图片上表现为几乎无Q差异，或主要改变失败风险。',
           '左图使用0-100完整Q轴，避免放大0.025分的格间范围；右图以全部团队为分母，失败没有填为Q=0。',
           'Semi结构方法族；两面板各924队，8格/9格；它们不是同一张图或相同类别分区。',
           all_rows[all_rows.example_id.isin(['semi_null','semi_failure'])].source_file.unique().tolist(),['data/MIXTURE_EXAMPLE_CONFIGURATIONS.csv'],['score_failure','composition_cell'])


def exchange_design():
    fig,aa=canvas(1,2,(15,8));left,right=aa.flat
    left.axis('off')
    for y,label,block,col in [(.76,'A 原队','X：原替换成员',COLORS[0]),(.47,'B 同类换人','Y：同构成\n其他成员',COLORS[0]),(.18,'C 跨类换人','Z：不同构成\n替换成员',COLORS[1])]:
        left.text(0,y+.08,label,fontsize=13,weight='bold')
        for xx,ww,txt,cc in [(.31,.30,'D\n相同保留成员','#DDE7EC'),(.65,.33,block,col)]:
            left.add_patch(FancyBboxPatch((xx,y),ww,.21,boxstyle='round,pad=.01',facecolor=cc,edgecolor='none'))
            left.text(xx+ww/2,y+.105,txt,ha='center',va='center',fontsize=11,color='white' if cc==col else '#243746')
    right.axis('off');right.text(.0,.83,'同一图片、同一条件、同一总人数n',fontsize=14,weight='bold')
    right.text(.0,.61,'相同实际替换人数m；D/X/Y/Z互斥\nX、Y的类别人数构成相同，Z改变构成\nX/Y/Z均可包含多个类别',fontsize=13,linespacing=1.8)
    right.text(.0,.27,'方向：C-A、B-A、C-B\n幅度：|B-A| 对比 (|C-A|+|C-B|)/2\n直接A/C：保留比较，单独标明没有B',fontsize=12,linespacing=1.8)
    finish(fig,'F3_design','F3','03 用严格匹配，把换成员与换类别分开',
           '模拟的是独立作答后的人员组合：从同一真实人员池重新组合，不假设参与者讨论或重复作答。',
           'A/B/C只是团队名称。D为保留成员，不是难度或方向误差。图形示意不指定实际m；实验按真实类别容量选规模。',
           '普通图片严格ABC共85条件；直接AC另有461条件、m=4-20。同房n=5-24、m=5-8作为跨视角扩展。',
           ['docs/thesis_main/人员分类与构成不确定性_研究组织与比较清单_20261022.md'],[],['strict_abc','direct_ac','team_n','prefix_k','replacement_m','replacement_ratio_r','background_d','extra_symmetric_abc'])


def exchange():
    exchange_design()
    p=f'{MIX}/exchanges/finite_pair_comparison/FINITE_PAIR_SELECTED_ZH.csv';d=read(p);export_data(d,'EXCHANGE_FINITE_PAIRS.csv')
    q=d[d['指标'].eq('绝对 Q 变化（分）')]
    t=d[d['指标'].eq('绝对 log 记录时间比')]
    fig,aa=canvas(1,2,(17,10));fig.subplots_adjust(left=.18,wspace=.72)
    for ax,x,unit in zip(aa.flat,[q,t],['绝对Q变化（分）','绝对自然对数劳动比']):
        for i,r in enumerate(x.to_dict('records')):
            ax.plot([r['同构成平均幅度'],r['改构成平均幅度']],[i,i],color='#A6B3BC',lw=3)
            ax.scatter(r['同构成平均幅度'],i,color=COLORS[0],s=70,label='同构成换人' if i==0 else None)
            ax.scatter(r['改构成平均幅度'],i,color=COLORS[1],s=70,label='改类别构成' if i==0 else None)
        layer={'coarse':'粗配比','fine_all_changes':'细配比含父类变化','fine_parent_fixed':'固定父类改细配比'}
        ax.set_yticks(range(len(x)),[f"{r['评价条件']} · {'结构' if r['分类']=='结构分类' else '联合'} · {layer.get(r['classification_view'],r['配比层级'])}\nn={r['总人数_n']}, m={r['实际换人数_m']} · 更大 {r['改构成幅度更大图片数']}/{r['可评价图片数']}图" for r in x.to_dict('records')],fontsize=10)
        ax.invert_yaxis();ax.set_xlabel(unit);ax.set_xlim(left=0);ax.grid(axis='x',alpha=.15);ax.legend(loc='upper left',bbox_to_anchor=(0,1.11),ncol=2,fontsize=9)
    finish(fig,'F3_general_magnitude','F3','03 普通图片：换配比与同配比换人的变化幅度',
           'Manual结构类在多数图片上改配比的Q幅度较大，平均分离较小；联合分类对记录时间差异的区分更清楚。',
           '左、右分别按各自质量或时间支持比较；固定实际共同D/m的团队两两配对。时间是变化幅度，不是节时比例；m3/4/6的图片支持不同。',
           '全部12项精选条件；标注为改配比幅度更大的图数/可评图数。完整结果可从原表追溯；不同方法/规模不直接排名。',
           [p],['data/EXCHANGE_FINITE_PAIRS.csv'],['within_cell_variability','absolute_change','time_history','recorded_time'])
    p=f'{AUDIT}/INDEPENDENT_MAIN_RESULTS.csv';d=read(p);d=d[d.method.eq('V3_BEHAVIOR')&d.subset.isin(['ordinary_all','ordinary_mixed','ordinary_mixed_less_half'])].copy();export_data(d,'EXCHANGE_SAME_ROOM_MAIN.csv')
    fig,aa=canvas(1,2,(15,7));fig.subplots_adjust(left=.15,wspace=.45)
    ax=aa[0,0];labels={'ordinary_all':'含纯块的全域','ordinary_mixed':'混合队：D非空','ordinary_mixed_less_half':'混合队：替换少于半队'}
    for i,r in enumerate(d.itertuples()):
        a=getattr(r,'pair_equal__B8L2_within');b=getattr(r,'pair_equal__B8L2_cross')
        ax.barh(i-.16,a,height=.28,color=COLORS[0]);ax.barh(i+.16,b,height=.28,color=COLORS[1])
        ax.text(b+.15,i+.16,f'{b:.2f}',va='center',fontsize=10)
        ax.text(a+.15,i-.16,f'{a:.2f}',va='center',fontsize=10)
    ax.set_yticks(range(len(d)),[labels[r.subset]+f'\n{r.positive_pairs}/{r.pairs}图对更大' for r in d.itertuples()],fontsize=10);ax.invert_yaxis();ax.set_xlim(0,12);ax.set_xlabel('Q变化幅度（分）')
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=COLORS[0],label='同类换人'),Patch(color=COLORS[1],label='跨类调整')],loc='upper left',bbox_to_anchor=(0,1.11),ncol=2,fontsize=9)
    s=read(f'{AUDIT}/INDEPENDENT_RESPONSE_STATES.csv');r=s[s.comparison.eq('CA')].iloc[0]
    state=['same_nonzero','one_response','opposite','both_near_zero'];names=['两视角同向','仅单视角响应','两视角反向','两视角近零']
    ax=aa[0,1];v=[r['eps2_CA_'+k]*100 for k in state];bars=ax.barh(range(4),v,color=[COLORS[2],COLORS[1],COLORS[4],COLORS[5]])
    ax.set_yticks(range(4),names);ax.invert_yaxis();ax.set_xlim(0,55);ax.bar_label(bars,fmt='%.2f%%',padding=4);ax.set_xlabel('分层加权比例（%）');ax.set_title('混合队 C-A：跨视角响应',fontsize=12)
    finish(fig,'F3_same_room','F3','03 同房大块补充：多数图对出现了更大的跨类幅度',
           '混合队跨类额外幅度+1.960分，换少于半队仍有+1.251分；两个视角的变化方向并不总相同。',
           '左图先平均两视角，再配置、图对等权；右图以|ΔQ|>2定义响应，四状态保留全部共同可评支持。更大幅度可以包含升质和降质。',
           '普通Manual结构类：78图对/9楼；半队以下73图对/9楼。Semi本轮没有m>4严格ABC容量。',
           [p,f'{AUDIT}/INDEPENDENT_RESPONSE_STATES.csv'],['data/EXCHANGE_SAME_ROOM_MAIN.csv'],['extra_symmetric_abc','same_room_direct','crossview_response'])
    p=f'{AUDIT}/sensitivity/KEY_PATH_JOINT_METRICS.csv';d=read(p);d=d[d.domain.eq('joint_Q_structure_position')&d.metric.eq('B8L2')&d.comparison.isin(['fixed_A_m5_to_m6','fixed_A_m5_to_m7','pure_to_max'])];export_data(d,'EXCHANGE_SCALE_BACKGROUND.csv')
    fig,aa=canvas(1,1,(14,7));ax=aa[0,0]
    names={'fixed_A_m5_to_m6':'固定原队/总人数\n换5人 → 换6人','fixed_A_m5_to_m7':'固定原队/总人数\n换5人 → 换7人','pure_to_max':'固定替换块XYZ\n无背景 → 最大背景D'}
    for j,(col,label) in enumerate([('pair_equal__B_change','同类队B自身Q变化'),('pair_equal__C_change','跨类队C自身Q变化'),('pair_equal__net_C_minus_B_change','C-B净优势变化')]):
        bars=ax.bar(np.arange(len(d))+(j-1)*.24,d[col],width=.22,label=label,color=COLORS[j]);ax.bar_label(bars,fmt='%+.2f',padding=3,fontsize=10)
    ax.axhline(0,color='#647380',lw=.8);ax.set_xticks(range(len(d)),[names[r.comparison]+f'\n{r.pairs}图对/{r.buildings}楼' for r in d.itertuples()]);ax.set_ylabel('Q变化（分）');ax.set_ylim(-6.4,3);ax.legend(loc='upper left',ncol=3,fontsize=10)
    finish(fig,'F3_scale_background','F3','03 同房扩展：扩大替换块与增加背景是两种操作',
           '常规→较多转折方向：扩大替换块时净优势增加；给同一XYZ加入背景时，净优势减弱。',
           '每个柱组使用该操作的精确共同路径。图对/建筑支持不同，不能把不同组相减当作每增加一人的边际收益。',
           '同房Manual TURN3主方向；历史楼外角色对齐。n、m与背景D均可追溯至原始成员。',
           [p],['data/EXCHANGE_SCALE_BACKGROUND.csv'],['team_n','prefix_k','replacement_m','replacement_ratio_r','background_d','signed_delta'])


def difficulty():
    raw=local('DIFFICULTY_RAW_EXPRESSION.csv');spread=local('DIFFICULTY_MIXTURE_SPREAD.csv');ex=local('DIFFICULTY_EXCHANGE_DIRECTIONS.csv')
    fig,aa=canvas(1,3,(16,8));fig.subplots_adjust(left=.075,right=.98,wspace=.40)
    d=raw[raw.condition.eq('manual')&raw.source.eq('all')&raw.metric.eq('turn_n')&raw.status.eq('available')].set_index('difficulty').loc[list(DIFF)]
    bars=aa[0,0].bar(d.index,d.building_equal_mean,color=list(DIFF.values()));aa[0,0].bar_label(bars,fmt='%+.2f',padding=4);aa[0,0].set_ylim(0,2.8);aa[0,0].set_title('原答：高/低转折角色差',fontsize=12);aa[0,0].set_ylabel('平均转折数差（个，楼等权）')
    for i,r in enumerate(d.itertuples()):aa[0,0].text(i,-.37,f'{r.images}图/{r.buildings}楼',ha='center',fontsize=9)
    x=spread[spread.condition.eq('manual')&spread.method.eq('V3_BEHAVIOR')&spread.tier.eq('coarse')&spread.n.eq(20)&spread.metric.eq('B8L2')]
    for j,(measure,label) in enumerate([('cell_mean_span','配比格间均值跨度'),('median_within_cell_iqr','典型格内IQR')]):
        z=x[x.measure.eq(measure)].set_index('difficulty').loc[list(DIFF)]
        bars=aa[0,1].bar(np.arange(3)+(j-.5)*.32,z.building_equal_mean,width=.30,label=label,color=COLORS[j]);aa[0,1].bar_label(bars,fmt='%.1f',padding=3,fontsize=9)
    aa[0,1].set_xticks(range(3),list(DIFF));aa[0,1].set_ylabel('Q分（楼等权）');aa[0,1].set_title('构成与成员波动都变大',fontsize=12);aa[0,1].legend(loc='upper left',fontsize=8);aa[0,1].set_ylim(0,15)
    for i,r in enumerate(z.itertuples()):aa[0,1].text(i,-2.0,f'{r.images}图/{r.buildings}楼',ha='center',fontsize=9)
    z=ex[ex.figure_role.eq('main')&ex.metric.eq('net_B8L2')]
    for j,(label,g) in enumerate(z.groupby('direction_zh')):
        xx=[list(DIFF).index(t) for t in g.current_difficulty]
        aa[0,2].plot(xx,g.display_value,'o',label=label.replace('联合：',''),color=COLORS[j])
        for x0,r in zip(xx,g.itertuples()):aa[0,2].annotate(f'{r.display_value:+.2f}\n{r.images}图/{r.buildings}楼',(x0,r.display_value),xytext=(0,9 if r.display_value>=0 else -31),textcoords='offset points',ha='center',fontsize=8)
    aa[0,2].set_xticks(range(3),list(DIFF));aa[0,2].set_xlim(-.3,2.3);aa[0,2].set_ylim(-6,12);aa[0,2].axhline(0,color='#A4AFB7',lw=.8);aa[0,2].set_ylabel('跨类C - 同类B的Q差（分）');aa[0,2].set_title('联合类：方向随难度改变',fontsize=12);aa[0,2].legend(loc='upper left',fontsize=8)
    finish(fig,'F4_difficulty','F4','04 难度把标法差异、成员波动和换类方向连接起来',
           '困难图中结构角色差与配比内波动更大；某些历史质量角色的换入方向会随当前难度反转。',
           '难度沿用人工主线，未用Q重新分难度。左/中/右是不同支持的描述比较；右为Manual联合n20/m3，不能解释成只改变难度的因果效应。',
           '左：楼外角色原答；中：n20结构粗类；右：严格ABC。Semi与全部分项、失败支持保留于数据表。',
           [f'{MIX}/difficulty/README.md',f'{MIX}/configurations/DIFFICULTY_SPREAD_SUMMARY.csv'],['data/DIFFICULTY_RAW_EXPRESSION.csv','data/DIFFICULTY_MIXTURE_SPREAD.csv','data/DIFFICULTY_EXCHANGE_DIRECTIONS.csv'],['difficulty_d','structure_context_c','distribution_band','signed_delta'])


def late_population_figures():
    base=f'{POP}/late_population_20261024'
    q=read(f'{base}/CURVE_SUMMARY.csv')
    changes=read(f'{base}/LATE_COMPARISONS.csv')
    exports=[('CURVE_SUMMARY.csv','NATURAL_CURVES_FIXED_COHORTS.csv'),
             ('LATE_COMPARISONS.csv','NATURAL_LATE_COMPARISONS.csv'),
             ('LATE_IMAGE_CHANGES.csv','NATURAL_LATE_IMAGE_CHANGES.csv'),
             ('COHORT_IMAGES.csv','NATURAL_COHORT_IMAGES.csv')]
    for source,target in exports:export_data(read(f'{base}/{source}'),target)
    terms=['q_b8l2','q_p10','q_sd','v_floor_population','score_failure','prefix_k']
    tables=['data/NATURAL_CURVES_FIXED_COHORTS.csv','data/NATURAL_LATE_COMPARISONS.csv',
            'data/NATURAL_LATE_IMAGE_CHANGES.csv','data/NATURAL_COHORT_IMAGES.csv']
    for minimum,fid,title,finding,note in [
        (30,'F5_natural','05 固定157图：单人基线与3—30人完整过程',
         '3→6人平均Q +5.18分，155/157图提高；后续Q增益较小，困难图可回落而底面波动继续下降。',
         '固定N≥30：简单105图、中等25图、困难27图。每图24条自然顺序；图片集合不随k变化。'),
        (35,'F5_late35','05 固定92图：单人、早段到35人的完整过程',
         '30→35人：共同可评91图平均Q +0.23分；失败率0.72%→1.09%。满员成员波动归零是设计结果。',
         '固定N=35：简单71图、中等13图、困难8图；35人困难Q仅7/8图可评，失败率仍按8图计算。')]:
        fig,aa=canvas(2,3,(16,10));fig.subplots_adjust(left=.07,wspace=.38,hspace=.65,top=.80,bottom=.18)
        for ax,metric,label in zip(aa.flat,['Q','P10','SD','V','failure'],
                                  ['平均质量Q（分）','图内低尾P10（Q分）','图内质量波动SD（Q分）','底面形状波动V（0-1）','不可评分比例（%）']):
            for diff,color in DIFF.items():
                z=q[q.cohort_min_n.eq(minimum)&q.difficulty.eq(diff)&q.k.notna()].sort_values('k')
                active=z.policy_deferred.eq(0)
                complete=z[metric+'_images'].eq(z.images)
                values=z[metric]*(100 if metric=='failure' else 1)
                ax.plot(z.k,values.where(active&complete),color=color,label=f'{diff} · {z.images.max()}候选图',lw=2,marker='o',ms=2.8)
                partial=active&~complete&values.notna()
                ax.scatter(z.loc[partial,'k'],values[partial],facecolors='white',edgecolors=color,s=22,zorder=4)
            ax.axvspan(1.65,2.35,color='#cbd5e1',alpha=.35,zorder=0)
            ax.set_title(label,fontsize=12);ax.set_xlabel('人数k（1人原答，2人未计算）',fontsize=9);ax.set_xticks([1,3,6,10,15,20,25,30]+([35] if minimum==35 else []));ax.grid(alpha=.15)
            if metric in ['Q','P10']:ax.set_ylim(0,100)
            ax.legend(fontsize=8,loc='best')
        ax=aa[1,2];ax.axis('off');ax.text(0,.98,'固定图片，分开看几种结果',fontsize=13,weight='bold',va='top')
        message=('固定157图平均Q变化\n3→6：+5.18 · 155图提高\n6→10：+1.73 · 139图提高\n10→20：+1.43 · 135图提高\n20→30：+0.76 · 125图提高\n\n困难27图3→6均升质\n失败6.94% → 12.65%\n6→10 Q−0.89，V有25图下降\n10→20 Q−0.25，V有26图下降' if minimum==30 else
                 '30→35人共同可评图片Q变化\n简单 +0.02 · 52/71图提高\n中等 +1.01 · 7/13图提高\n困难 +0.87 · 4/7图提高\n\n困难满员仍有1/8图不可评分\n满员全部顺序使用同一批人\nSD、V为0不证明接近参考')
        ax.text(0,.80,message,fontsize=9.5,va='top',linespacing=1.35)
        finish(fig,fid,'F5',title,finding,
               '1人是原答基线；灰带2人未运行（原实验设定），不计成功/失败。实线仅连全候选图有效的点；空心点部分可评。Q/P10/SD先图内汇总再图等权；失败另用全部路径，V为有效底面的两两差异。',
               note,[f'{base}/README.md',f'{base}/CURVE_SUMMARY.csv',f'{base}/LATE_COMPARISONS.csv'],tables,terms)
    z=changes[changes.cohort_min_n.eq(30)&changes.comparison.eq('30_to_full')]
    fig,aa=canvas(1,3,(16,7));fig.subplots_adjust(left=.10,wspace=.65,top=.73,bottom=.25)
    for ax,metric,title in zip(aa.flat,['Q','P10','failure'],['平均质量Q（分）','图内低尾P10（Q分）','不可评分比例（%）']):
        d=z[z.metric.eq(metric)].set_index('difficulty').loc[list(DIFF)]
        factor=100 if metric=='failure' else 1
        for i,(diff,r) in enumerate(d.iterrows()):
            a,b=r.from_mean*factor,r.to_mean*factor
            ax.plot([a,b],[i,i],color=DIFF[diff],lw=2)
            ax.scatter(a,i,color=COLORS[0],label='30人' if i==0 else None,s=50)
            ax.scatter(b,i,color=COLORS[1],label='各图满员' if i==0 else None,s=50)
            ax.annotate(f'{a:.2f} → {b:.2f}',(max(a,b),i),xytext=(5,7),textcoords='offset points',fontsize=9)
        ax.set_yticks(range(3),[f'{diff} · {int(r.common_images)}图' for diff,r in d.iterrows()],fontsize=10)
        ax.invert_yaxis();ax.set_ylim(2.6,-.6);ax.set_title(title,fontsize=12);ax.legend(fontsize=9,loc='lower left');ax.grid(axis='x',alpha=.15)
        ax.set_xlim((0,5) if metric=='failure' else (45,110))
    finish(fig,'F5_full','F5','05 从30人到各图实际满员：同图比较质量与失败',
           '满员为各图实际30—35人。Q比较保留两端可评156图：平均+0.29分；全部157图中仍有1图满员失败。',
           'Q/P10使用共同可评图片；失败使用全部图片。满员时所有顺序汇到同一团队，SD/V=0是有限池设计事实，不是误差消失。',
           '普通Manual固定N≥30的157图；质量共同域156图。满员困难26/27可评，简单105/105、中等25/25。',
           [f'{base}/README.md',f'{base}/LATE_COMPARISONS.csv'],tables,terms)


def population():
    p=f'{POP}/stability_rebuilt_20261023/results/NATURAL_IMAGE_CURVES_REBUILT.csv.gz';d=read(p);d=d[d.pool_n.ge(20)&d.k.between(3,20)]
    q=d.groupby(['condition','layer','difficulty','k']).agg(images=('image','nunique'),buildings=('building','nunique'),Q=('Q_mean','mean'),P10=('Q_p10','mean'),SD=('Q_sd_ddof1','mean'),failure=('score_failure_nonpolicy_rate','mean'),attempts=('paths_attempted','sum'),scorable=('quality_valid_paths','sum')).reset_index()
    v=read(f'{POP}/results/PREFIX_GEOMETRY_VARIATION.csv.gz');v=v[v.pool_n.ge(20)&v.policy.eq('natural_random')&v.k.between(3,20)]
    vv=v.groupby(['condition','layer','difficulty','k']).agg(V=('V_floor_mean','mean'),V_images=('V_floor_mean','count'),V_pairs=('V_floor_valid_pairs','sum')).reset_index()
    q=q.merge(vv,on=['condition','layer','difficulty','k'],validate='one_to_one');export_data(q,'NATURAL_CURVES_FIXED_N20.csv')
    old=read('research/statistics/pro_return_review_20261023/population/NATURAL_RECOMPUTED.csv')
    old=old[old.k.between(3,20)];joined=q.merge(old,on=['condition','layer','difficulty','k'],suffixes=('','_old'),validate='one_to_one')
    for col in ['Q','P10','SD','failure','V']:np.testing.assert_allclose(joined[col],joined[col+'_old'],atol=1e-7,equal_nan=True)
    late_population_figures()
    fig,aa=canvas(2,2,(14,9));fig.subplots_adjust(hspace=.62)
    for row,layer in enumerate(['ordinary_semi','doorway_manual']):
        for diff,z in q[q.layer.eq(layer)].groupby('difficulty'):
            name=('门洞单列' if layer=='doorway_manual' else diff)+f' · {z.images.max()}图'
            for col,metric in enumerate(['Q','failure']):aa[row,col].plot(z.k,z[metric]*(100 if metric=='failure' else 1),label=name,lw=2,color=DIFF.get(diff,COLORS[4]))
        for col in range(2):
            aa[row,col].set_title(('Semi普通图' if row==0 else 'Manual门洞')+' · '+('平均Q' if col==0 else '不可评分比例'),fontsize=12)
            aa[row,col].set_xlabel('参与人数k');aa[row,col].set_ylabel('Q分' if col==0 else '%');aa[row,col].set_xticks([3,6,10,15,20]);aa[row,col].legend(fontsize=9);aa[row,col].grid(alpha=.15)
            if col==0:aa[row,col].set_ylim(0,100)
    finish(fig,'F5_conditions','F5','05 Semi和门洞保持各自的过程与支持',
           '门洞17图10→20人的平均Q下降约3.07分，增加人数没有普遍消除边界问题；Semi不套用Manual结论。',
           'Q按每图可评分路径汇总，失败按全部尝试汇总；因此两条曲线的分母有不同用途，不能把失败填成质量0。',
           '固定N≥20人员池；Semi简单/中等分开、困难暂无支持。门洞沿用独立层，不按曲线强改成困难图。',
           [p],['data/NATURAL_CURVES_FIXED_N20.csv'],['condition_manual','condition_semi','doorway','score_failure','q_b8l2'])
    p=f'{AUDIT}/population/POLICY_COMMON_POOL_SUMMARY.csv';policy=read(p);export_data(policy,'POLICY_COMMON_POOL_RESULTS.csv')
    ci=read(f'{POP}/stability_rebuilt_20261023/results/POLICY_EARLY_STABILITY.csv')
    ci=ci[ci.policy_support.eq('common_four_policy_pools')&ci.metric.eq('paired_Q_delta')&ci.weighting.eq('image_equal')&ci.resampling.eq('building_resampling_fixed_paths')&ci.difficulty.eq('全部')]
    names={'joint_highq_first':'历史Q较高类优先','structure_moreturn_first':'较多转折类优先','joint_fast_first':'较快类优先','structure_dominant_first':'人数最多结构类优先'}
    fig,aa=canvas(1,2,(15,7));fig.subplots_adjust(left=.17,wspace=.60)
    for ax,layer in zip(aa.flat,['ordinary_manual','ordinary_semi']):
        d=policy[policy.layer.eq(layer)].set_index('policy').loc[list(names)]
        z=ci[ci.layer.eq(layer)].set_index('policy').loc[list(names)]
        ax.errorbar(d.image_equal,range(4),xerr=[d.image_equal.to_numpy()-z.percentile_2_5.to_numpy(),z.percentile_97_5.to_numpy()-d.image_equal.to_numpy()],fmt='o',color=COLORS[0],capsize=4)
        ax.set_yticks(range(4),[names[k]+f'\n{r.positive_images}/{r.scored_images}图提高' for k,r in d.iterrows()],fontsize=10);ax.invert_yaxis();ax.axvline(0,color='#A4AFB7');ax.set_xlim(-5,11);ax.set_xlabel('相对同一自然路径的平均ΔQ（分）');ax.set_title(f'{layer.split("_")[1].capitalize()} · {d.pools.iloc[0]}图/{d.buildings.iloc[0]}楼',fontsize=12)
    finish(fig,'F5_policy','F5','05 改变进入顺序，可以改变前半程表现',
           'Manual高Q、多转折角色优先有多数图支持；Semi同一规则没有复现总体升质。满员时成员相同，差值为零。',
           '点=图等权前半程平均差；线=2,000次建筑整块重抽的95%范围。先配对同base/k，再图内k平均。共同图片池不等于每个前缀五队全可评。',
           '前半程3≤k≤floor(N/2)；Manual157图/22楼，Semi21图/11楼；每策略对应8条自然基路径。',
           [p,f'{POP}/stability_rebuilt_20261023/results/POLICY_EARLY_STABILITY.csv'],['data/POLICY_COMMON_POOL_RESULTS.csv'],['entry_order','bootstrap_interval','taxonomy_lobo'])
    p=f'{AUDIT}/population/COMMON_TIME_RESULTS.csv';t=read(p);t=t[t.layer.eq('ordinary_manual')];export_data(t,'POLICY_COMMON_QT.csv')
    f=read(f'{AUDIT}/population/COMMON_TIME_FAILURE_EFFECTS.csv');export_data(f,'POLICY_COMMON_TIME_FAILURE.csv')
    d=t.pivot(index='policy',columns='metric',values='image_equal').loc[list(names)]
    fig,aa=canvas(1,2,(15,7));fig.subplots_adjust(left=.09,wspace=.48)
    ax=aa[0,0]
    for i,(pol,r) in enumerate(d.iterrows()):
        xx=(r.time_ratio-1)*100;yy=r.Q_delta;ax.scatter(xx,yy,s=100,color=COLORS[i]);ax.annotate(names[pol]+f'\nQ {yy:+.2f}，劳动 {xx:+.1f}%',(xx,yy),xytext=(8,10 if i!=1 else -33),textcoords='offset points',fontsize=10)
    ax.axhline(0,color='#A4AFB7',lw=.8);ax.axvline(0,color='#A4AFB7',lw=.8);ax.set_xlim(-30,31);ax.set_ylim(-5,10);ax.set_xlabel('记录劳动变化（%）');ax.set_ylabel('同支持平均Q变化（分）')
    z=f[f.layer.eq('ordinary_manual')&f.metric.eq('priority_score_failure_nonpolicy')].set_index('policy').loc[list(names)]
    natural=f[f.layer.eq('ordinary_manual')&f.metric.eq('natural_score_failure_nonpolicy')].image_equal.iloc[0]
    ax=aa[0,1];vals=[natural,*z.image_equal]*np.array(100);bars=ax.barh(range(5),vals,color=['#89939C',*COLORS[:4]]);ax.bar_label(bars,fmt='%.2f%%',padding=4);ax.set_yticks(range(5),['自然顺序',*names.values()],fontsize=10);ax.invert_yaxis();ax.set_xlim(0,4.5);ax.set_xlabel('图等权失败率（%）')
    finish(fig,'F5_time_tradeoff','F5','05 效率用途：把质量、劳动和失败放在相同支持下看',
           '高Q优先在这批共同支持上升质但略增劳动；快角色减少约22.4%记录劳动，同时保留Q代价和失败变化。',
           '左图要求五队共同可评且时间语义相同，共4,304单位；右图使用全部4,613个共同时间尝试。均为分层平均，不是全库总时间相除。',
           '普通Manual67图/18楼；时间是已有记录劳动人秒，不是现实并行交付时长；Semi没有同等共同时间支持。',
           [p,f'{AUDIT}/population/COMMON_TIME_FAILURE_EFFECTS.csv'],['data/POLICY_COMMON_QT.csv','data/POLICY_COMMON_TIME_FAILURE.csv'],['recorded_time','common_qt_support','score_failure'])


def mechanisms():
    p=f'{POP}/cases/CASE_PRIMARY_SUMMARY.csv';d=read(p);export_data(d,'MECHANISM_CASES.csv')
    names={'early_structure_recovery':'结构票数补足','same_nodes_position_improvement':'同角点数，定位改善','low_plateau_with_less_member_variation':'波动缩小，Q仍低平台','persistent_structure_gap':'持续缺少结构','declining_mean_with_less_variation':'门槛/身份变化造成退化'}
    fig,aa=canvas(1,2,(16,8));fig.subplots_adjust(left=.18,right=.98,wspace=.22)
    ax=aa[0,0]
    for i,r in enumerate(d.itertuples()):
        ax.plot([r.from_B8L2,r.to_B8L2],[i,i],color=COLORS[2] if r.delta_B8L2>=0 else COLORS[4],lw=3)
        ax.scatter(r.from_B8L2,i,color=COLORS[0],s=55);ax.scatter(r.to_B8L2,i,color=COLORS[1],s=55)
        ax.text(102,i,f'{r.delta_B8L2:+.1f}',va='center',fontsize=10)
    ax.set_yticks(range(len(d)),[names[r.role]+f'\n{r.case} · {r.k_from}→{r.k_to}人' for r in d.itertuples()],fontsize=10);ax.invert_yaxis();ax.set_xlim(0,117);ax.set_xlabel('单条实际路径前后Q（蓝→橙）');ax.grid(axis='x',alpha=.15)
    ax=aa[0,1];ax.axis('off')
    rows=[]
    for r in d.itertuples():
        rows.append([r.case[:3]+'-'+r.case.split('-')[-1],f'{r.from_nodes}→{r.to_nodes}',f'{r.threshold_from}→{r.threshold_to}',f'{r.from_iou_2d:.2f}→{r.to_iou_2d:.2f}',f'{r.from_S_bottom_deg:.2f}→{r.to_S_bottom_deg:.2f}',f'{r.from_dir:.2f}→{r.to_dir:.2f}'])
    table=ax.table(cellText=rows,colLabels=['实例','节点数','票数门槛','底面IoU','底边距离°','方向残差°'],cellLoc='center',loc='center',bbox=[0,.05,1,.90]);table.auto_set_font_size(False);table.set_fontsize(9)
    for (row,col),cell in table.get_celld().items():
        cell.set_edgecolor('#D7E0E6');cell.set_facecolor('#EAF0F4' if row==0 else 'white')
    finish(fig,'F6_mechanisms','F6','06 回到真实原答：人员怎样改变共识',
           '结果变化可来自结构支持、位置中位数、投票门槛与连接；单看总分无法区分这些机制。',
           '每行是保存的一条精确路径，不代表该图全部顺序。研究台应能继续打开原图、完整个人标注、融合几何和票账。全部分项保留于案例表。',
           '五个探索解释例；既有24条自然顺序背景另存。同房G130/G172正反例作为对应的补充入口。',
           [p],['data/MECHANISM_CASES.csv'],['consensus_mv50','consensus_mv50','median_position','q_b8l2','iou_floor_i','bottom_sb','direction_residual','height_hmean','height_hcenter'])


def main():
    (OUT/'data').mkdir(parents=True,exist_ok=True);(OUT/'figures').mkdir(exist_ok=True)
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--population-only',action='store_true',help='仅更新人数图，保留其余已保存图版')
    args=parser.parse_args()
    if args.population_only:
        previous=json.loads((OUT/'FIGURE_MANIFEST.json').read_text(encoding='utf-8'))['figures']
        late_population_figures()
        replacements={f['id']:f for f in FIGURES}
        ordered=[]
        for f in previous:
            if f['id'] not in ['F5_late35','F5_full']:ordered.append(replacements.get(f['id'],f))
            if f['id']=='F5_natural':ordered.extend([replacements['F5_late35'],replacements['F5_full']])
        FIGURES[:]=ordered
    else:
        classification();mixture();exchange();difficulty();population();mechanisms()
    term_ids={t['id'] for t in json.loads((OUT/'GLOSSARY.json').read_text(encoding='utf-8'))['terms']}
    for f in FIGURES:
        assert set(f['term_ids']) <= term_ids, (f['id'], set(f['term_ids']) - term_ids)
        assert all((ROOT/p).exists() for p in f['source_paths'])
        assert all((OUT/p).exists() for p in f['data_paths']+[f['image'],f['vector']])
    (OUT/'FIGURE_MANIFEST.json').write_text(json.dumps(dict(version='personnel_main_figures_v2_20261023',figures=FIGURES),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    pd.DataFrame([{k:v for k,v in f.items() if k not in ['source_paths','data_paths','term_ids']} for f in FIGURES]).to_csv(OUT/'FIGURE_INDEX.csv',index=False,encoding='utf-8-sig')
    interface_path=OUT/'CONSUMER_INTERFACE.json'
    interface=json.loads(interface_path.read_text(encoding='utf-8'))
    for group in interface['groups']:
        group['figure_ids']=[f['id'] for f in FIGURES if f['group']==group['id']]
    new_names=['NATURAL_CURVES_FIXED_COHORTS','NATURAL_LATE_COMPARISONS','NATURAL_LATE_IMAGE_CHANGES','NATURAL_COHORT_IMAGES']
    interface['tables']=[t for t in interface['tables'] if t['id'] not in new_names]
    for name in new_names:
        path=OUT/'data'/f'{name}.csv';frame=pd.read_csv(path)
        interface['tables'].append(dict(id=name,path=path.relative_to(ROOT).as_posix(),rows=len(frame),columns=list(frame.columns)))
    interface['validation']['figures']=len(FIGURES)
    interface_path.write_text(json.dumps(interface,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'生成 {len(FIGURES)} 张研究台图（PNG/SVG）及对应小表；实际来源与路径断言通过。')


if __name__=='__main__':
    main()
