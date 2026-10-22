#!/usr/bin/env python3
"""Prepare readable adoption tables and a scientific figure from saved results.

No new labels, target selection, fusion or scoring. Conditions retain their
planned / exploratory identity. Exact combinatorial capacities stay strings.
"""
from __future__ import annotations
import hashlib, json, math, os
from decimal import Decimal
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
AN = HERE / 'analysis'

def atomic_csv(path, df):
    tmp = path.with_name(path.name + '.partial')
    df.to_csv(tmp, index=False, encoding='utf-8-sig')
    os.replace(tmp, path)

def exact_int(v):
    return int(Decimal(str(v)))

def one(df, **kw):
    d = df
    for k, v in kw.items():
        d = d[d[k].eq(v)]
    assert len(d) == 1, (kw, len(d))
    return d.iloc[0]

def main():
    eff = pd.read_csv(AN / 'EFFECTIVE_CONDITIONS.csv')
    bg = pd.read_csv(AN / 'BACKGROUND_CONDITIONS.csv')
    diff = pd.read_csv(AN / 'DIFFICULTY_CONDITIONS.csv')
    time = pd.read_csv(AN / 'TIME_QUALITY_COMMON_SUPPORT.csv')
    common = pd.read_csv(HERE / 'COMMON_ABC_COMPARISON.csv')
    cap = pd.read_csv(HERE / 'CAPACITY_AND_COVERAGE.csv.gz', dtype=str)
    cap = cap[cap.status.eq('available')].set_index('cell_id', drop=False)
    vectors = pd.read_csv(HERE / 'COUNT_VECTOR_COVERAGE.csv.gz', dtype=str)
    condition_specs = []
    for m in [4, 7]:
        condition_specs.append((f'STR_MAIN_M{m}', eff,
            dict(study_group='main_n20', source_role='TURN/K3/E2', m=m, n=20),
            '全部可行 ABC 背景人数向量', '预登记方向和规模',
            '主要采用：较广覆盖的定向升质' if m == 4 else '主要采用：有容量时的较大类别块升质'))
    for band, label, decision in [
        ('low_0_to_1_3', 'D 中较多转折成员不超过 4/13', '优先采用的内部条件：较多转折背景较少时补充'),
        ('middle_1_3_to_2_3', 'D 中较多转折成员为 5—8/13', '风险补充：不作为该方向的默认升质条件')]:
        condition_specs.append((f'STR_M7_BG_{band}', bg,
            dict(study_group='main_n20', source_role='TURN/K3/E2', m=7, n=20, background_target_band=band),
            label, '预定义分层；采用建议由本轮目标结果形成', decision))
    for level in ['简单', '中等', '困难']:
        for m in [4, 7]:
            decision = {
                ('简单', 4): '主要采用：覆盖较广', ('简单', 7): '主要采用：较大替换规模升质更明显',
                ('中等', 4): '优先于 m7：升质支持较普遍', ('中等', 7): '条件采用：多数楼改善，图片支持较弱',
                ('困难', 4): '专项采用：收益与失败同时突出', ('困难', 7): '专项采用：支持小、收益大；结构须成套获得支持'
            }[(level, m)]
            condition_specs.append((f'STR_M{m}_{level}', diff,
                dict(study_group='main_n20', source_role='TURN/K3/E2', m=m, n=20, difficulty=level),
                f'{level}图；全部可行 ABC 背景人数向量', '预定义难度分层；内部评价', decision))
    for m in [4, 5, 6]:
        condition_specs.append((f'STR_REVERSE_M{m}', eff,
            dict(study_group='main_n20', source_role='TURN/K3/E3', m=m, n=20),
            '全部可行 ABC 背景人数向量；m5/m6 为各图最大容量子集' if m > 4 else '全部可行 ABC 背景人数向量',
            '预登记反方向',
            '保留探索：容量子集有正向收益，但失败较多、固定 A 规模趋势不一致' if m == 6 else '不作为默认升质方向；保留换类风险证据'))
    condition_specs.append(('STR_NEW_ONLY_M4', eff,
        dict(study_group='new_only_n20_recorded_time', source_role='TURN/K3/E2', m=4, n=20),
        '仅新来源正式人员；全部可行 ABC 背景人数向量', '预登记同来源补充域',
        '保留补充：多数图升质，记录时间小幅增加'))

    rows = []
    stat_fields = [
        'registered_events', 'unique_physical_triples', 'unique_endpoints',
        'images_total', 'buildings_total', 'backgrounds_total', 'count_vectors_observed',
        'all_three_Q_events', 'same_B8L2_mean', 'same_B8L2_event_n', 'same_B8L2_image_n', 'same_B8L2_building_n',
        'cross_B8L2_mean', 'cross_B8L2_event_n', 'cross_B8L2_image_n', 'cross_B8L2_building_n', 'net_B8L2_mean',
        'net_B8L2_event_n', 'net_B8L2_image_n', 'net_B8L2_images_positive',
        'net_B8L2_building_n', 'net_B8L2_buildings_positive',
        'common_quality_within_abs_mean', 'common_quality_cross_abs_mean',
        'common_quality_within_abs_event_n', 'abs_Q_change_advantage_mean',
        'abs_Q_change_advantage_buildings_positive', 'abs_Q_change_advantage_building_n',
        'net_D10_mean', 'net_IoU3D100_mean', 'net_iou_2d_mean',
        'net_S_bottom_deg_mean', 'net_dir_mean', 'net_Hmean_mean', 'net_Hcenter_mean',
        'net_omission_mean', 'net_extension_mean', 'net_nodes_mean', 'net_fusion_turn_n_mean',
        'net_ref_node_recall_5_mean', 'net_ref_edge_recall_5_mean',
        'A_failure_mean', 'B_failure_mean', 'C_failure_mean', 'C_failure_event_n',
        'A_unique_failed_endpoints', 'B_unique_failed_endpoints', 'C_unique_failed_endpoints',
        'net_loss_gt10_mean', 'net_loss_gt10_event_n',
        'net_recorded_time_pct_mean', 'net_recorded_time_pct_event_n',
        'net_recorded_time_pct_image_n', 'net_recorded_time_pct_building_n'
    ]
    for cid, df, spec, background, identity, decision in condition_specs:
        r = one(df, **spec)
        source, target = ('常规表达', '较多转折') if r.source_role.endswith('E2') else ('较多转折', '常规表达')
        out = dict(condition_id=cid, classification='V3_BEHAVIOR / TURN/K3', evaluation_condition='Manual',
            label_training='目标建筑之外的 Manual 历史；原标签冻结复用', tier='coarse',
            source_role=r.source_role, target_role=r.target_role, source_semantics=source, target_semantics=target,
            source_domain=r.source_domain, n=int(r.n), actual_m=int(r.m), replacement_fraction=r.m/r.n,
            class_seat_change=f'{source} -{int(r.m)}；{target} +{int(r.m)}；B 与 A 类别人数不变',
            common_background_rule=background, selection_identity=identity, adoption=decision,
            aggregation='事件→具体 D→背景人数向量→图片→建筑等权',
            quality_direction='正值表示 C 优于 B；误差分项负值为改善',
            time_provenance='同一来源且三队时间完整的库存记录秒数之和；非新测生产耗时')
        for f in stat_fields:
            out[f] = r.get(f, np.nan)
        common_spec=dict(spec)
        common_spec['slice_kind']='difficulty' if 'difficulty' in spec else ('background' if 'background_target_band' in spec else 'overall')
        cr=one(common,**common_spec)
        for f in cr.index:
            if f.startswith('common_ABC_'):
                out[f]=cr[f]
            elif f.startswith(('same_B8L2','cross_B8L2','net_B8L2','same_D10','cross_D10','net_D10')):
                out['ABC_common_'+f]=cr[f]
        # Count exact possible concrete triples for this observed-domain slice.
        cc = cap[(cap.source_domain.eq(r.source_domain)) & cap.source_role.eq(r.source_role) & cap.m.eq(str(int(r.m)))]
        if 'difficulty' in spec:
            cc = cc[cc.difficulty.eq(spec['difficulty'])]
        vv = vectors[vectors.cell_id.isin(cc.index)].copy()
        if 'background_target_band' in spec:
            target_counts = vv.background_stratum.map(lambda x: int(x.split('|')[1]))
            fractions = target_counts / (int(r.n) - int(r.m))
            if spec['background_target_band'] == 'low_0_to_1_3':
                vv = vv[fractions < 1/3]
            else:
                vv = vv[(fractions >= 1/3) & (fractions < 2/3)]
        possible_events = 0
        for v in vv.itertuples(index=False):
            c = cc.loc[v.cell_id]
            s, t, o = map(int, v.background_stratum.split('|'))
            sm = int(c.source_capacity) - s
            tm = int(c.target_capacity) - t
            m = int(c.m)
            possible_events += exact_int(v.possible_backgrounds) * math.comb(sm, m) * math.comb(sm-m, m) // 2 * math.comb(tm, m)
        possible_backgrounds = sum(exact_int(x) for x in vv.possible_backgrounds)
        out.update(feasible_ABC_background_count_vectors=len(vv),
            observed_ABC_background_count_vectors=int(r.count_vectors_observed),
            possible_concrete_backgrounds=str(possible_backgrounds),
            unregistered_concrete_backgrounds=str(possible_backgrounds-int(r.backgrounds_total)),
            possible_unordered_XY_ABC=str(possible_events),
            unregistered_unordered_XY_ABC=str(possible_events-int(r.unique_physical_triples)),
            coverage_interpretation='所选条件人数向量完整；具体成员及 D 为固定规则均衡抽取，未穷尽')
        rows.append(out)
    atomic_csv(HERE / 'RECOMMENDED_CONDITIONS.csv', pd.DataFrame(rows))

    ms = pd.read_csv(AN / 'LINKED_M_SUMMARY.csv')
    fields = [x for x in ms if x in ['path_kind','source_role','target_role','n','m_from','m_to','incremental_actual_m','paths','images','buildings'] or
        x.startswith(('same_B8L2_delta_', 'cross_B8L2_delta_', 'net_B8L2_delta_', 'net_D10_delta_', 'C_failure_delta_', 'net_recorded_time_pct_delta_'))]
    mshort = ms[fields].copy()
    mshort['design'] = '固定 A；X/Y/Z 前缀嵌套；各 m 内三队同 D；m 增加时 D 的源类尾块移入 X'
    mshort['interpretation'] = '规模路径独立层；delta 为终点效果减起点效果，不与主层重复累计'
    atomic_csv(HERE / 'FIXED_A_M_RESPONSE.csv', mshort)

    # Compact component table: each column retains its original denominator.
    comps = []
    for m in [4, 7]:
        r = one(eff, study_group='main_n20', source_domain='all_formal', source_role='TURN/K3/E2', n=20, m=m)
        for metric in ['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension','nodes','fusion_turn_n','ref_node_recall_5','ref_edge_recall_5']:
            stem = 'net_' + metric
            comps.append(dict(n=20,m=m,metric=metric,net_C_minus_B=r.get(stem+'_mean',np.nan),
                event_n=r.get(stem+'_event_n',np.nan), image_n=r.get(stem+'_image_n',np.nan),
                building_n=r.get(stem+'_building_n',np.nan),
                direction='描述性有符号变化' if metric in ['nodes','fusion_turn_n'] else ('负值改善' if metric in ['S_bottom_deg','dir','Hmean','Hcenter','omission','extension'] else '正值改善')))
    atomic_csv(HERE / 'MAIN_QUALITY_COMPONENTS.csv', pd.DataFrame(comps))

    os.environ.setdefault('MPLCONFIGDIR',str(Path(os.environ.get('TMPDIR','/tmp'))/'hohonet_matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig, axs = plt.subplots(2,2,figsize=(12.8,8.8),constrained_layout=True)
    colors={4:'#247ba0',7:'#df703d'}
    buildings=pd.read_csv(AN/'BUILDING_EFFECTS.csv.gz')
    for j,m in enumerate([4,7]):
        d=buildings[(buildings.study_group.eq('main_n20')) & buildings.source_role.eq('TURN/K3/E2') & buildings.m.eq(m)]
        vals=d.net_B8L2.dropna().to_numpy()
        jitter=np.linspace(-.13,.13,len(vals))
        axs[0,0].scatter(j+jitter,vals,color=colors[m],s=36,alpha=.75,label=f'm={m}, 16 buildings')
        mean=vals.mean();axs[0,0].plot([j-.25,j+.25],[mean,mean],color='black',lw=2)
        axs[0,0].text(j+.26,mean,f'{mean:+.2f}',va='center',fontsize=10)
    axs[0,0].axhline(0,color='#777',lw=.8)
    axs[0,0].set(xticks=[0,1],xticklabels=['m=4 (20%)','m=7 (35%)'],ylabel='Net quality change: C - B',title='A. Main n=20: building-level effects')
    for j,m in enumerate([4,7]):
        r=one(eff,study_group='main_n20',source_role='TURN/K3/E2',m=m,n=20)
        vals=[r.common_quality_within_abs_mean,r.common_quality_cross_abs_mean]
        xs=[j-.19,j+.19]
        bars=axs[0,1].bar(xs,vals,width=.34,color=['#8eabb5',colors[m]])
        for x,v in zip(xs,vals):axs[0,1].text(x,v+.07,f'{v:.2f}',ha='center')
    axs[0,1].set(xticks=[0,1],xticklabels=['m=4\nSame / Cross','m=7\nSame / Cross'],ylabel='Absolute quality change vs A',title='B. Magnitude on the same ABC scored support')
    axs[0,1].set_ylim(0,5.1)
    md=pd.read_csv(AN/'LINKED_M_CHANGES.csv.gz')
    md=md[md.path_kind.eq('m4_to_max') & md.source_role.eq('TURN/K3/E2') & md.m_from.eq(4)&md.m_to.eq(7)]
    for j,metric in enumerate(['cross_B8L2_delta','net_B8L2_delta']):
        vals=md.groupby(['building','image'])[metric].mean().groupby('building').mean().dropna()
        axs[1,0].scatter(j+np.linspace(-.13,.13,len(vals)),vals,color=['#577f59','#825c9d'][j],s=36,alpha=.75)
        mean=vals.mean();axs[1,0].plot([j-.25,j+.25],[mean,mean],color='black',lw=2)
        axs[1,0].text(j+.26,mean,f'{mean:+.2f}',va='center')
    axs[1,0].axhline(0,color='#777',lw=.8)
    axs[1,0].set(xticks=[0,1],xticklabels=['Increment of C - A','Increment of C - B'],ylabel='Effect at m=7 minus effect at m=4',title='C. Fixed A, nested blocks: 77 images / 16 buildings')
    for m in [4,7]:
        r=one(time,study_group='main_n20',source_role='TURN/K3/E2',m=m,n=20)
        axs[1,1].scatter(r.net_recorded_time_pct_mean,r.net_B8L2_mean,color=colors[m],s=120)
        axs[1,1].annotate(f'm={m}: {int(r.images_total)} images\nQ {r.net_B8L2_mean:+.2f}; time {r.net_recorded_time_pct_mean:+.2f}%',
            (r.net_recorded_time_pct_mean,r.net_B8L2_mean),xytext=(10,6),textcoords='offset points')
    axs[1,1].axhline(0,color='#777',lw=.8);axs[1,1].axvline(0,color='#777',lw=.8)
    axs[1,1].set(xlim=(-.1,3.7),ylim=(-.2,6.4),xlabel='Recorded time change: C vs B (%)',ylabel='Net quality change: C - B',title='D. Quality / time on matched, single-source support')
    fig.suptitle('Manual structure classes: usual expression -> more turns',fontsize=16,fontweight='bold')
    fdir=HERE/'figures';fdir.mkdir(exist_ok=True)
    fig.savefig(fdir/'STRUCTURE_ADOPTION.png',dpi=180)
    fig.savefig(fdir/'STRUCTURE_ADOPTION.pdf')
    plt.close(fig)
    contract=dict(status='complete',data_release='real_v2',native_calls=0,
        condition_rows=len(rows),aggregation='events -> exact D -> class-count stratum -> image -> building, equal at each level',
        source='saved completed structure analysis, all requested endpoints complete',
        exploratory='Background/difficulty adoption rules selected from internal v2 results; prior categories remain frozen.',
        figure='Main m4 and m7 differ in support; panel C is the paired fixed-A scale comparison; time panel uses common time/Q support.',
        exact_integer_fields='Read capacity strings as decimal integers, never float64.')
    (HERE/'ADOPTION_OUTPUTS.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(contract,ensure_ascii=False))

if __name__=='__main__':
    main()
