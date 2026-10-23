#!/usr/bin/env python3
"""Readable main-direction scale/background contrasts from saved path effects.

No fusion, new order/team selection, refit, or new path endpoint is computed.
The broadest ordinary Manual structural direction is shown as an explanation;
the full scheme/direction results remain in PATH_OVERALL_RESULTS.csv.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd

STRUCTURE_METRICS=['B8L2','D10','fusion_turn_n','fusion_short_turn_edges',
 'fusion_redundancy_n','S_bottom_deg','dir','Hmean','height_mean_ratio']
EFFECTS=['A_change','B_change','C_change','net_C_minus_B_change','extra_amplitude_change']
META=['path_transition_id','study_type','comparison_tags','method','condition','ordinary_comparable',
 'source_role_key','target_role_key','source_class','target_class','pair_key','building','groups',
 'm_small','m_large','n_small','n_large','Q_common12','time_common12','QT_common12']
FAILURE=['score_failure_fraction12','incomplete_fraction12']+[
 r+'_'+k for r in 'ABC' for k in ['new_score_failure_fraction','recovered_score_fraction',
 'new_incomplete_fraction','recovered_complete_fraction','Q_loss_gt5_fraction','Q_gain_gt5_fraction']]
CFG=['pair_key','building','source_class','target_class','m_small','m_large','n_small','n_large']
LABELS={'fixed_A_m5_to_m6':'固定A：m5→6','fixed_A_m5_to_m7':'固定A：m5→7',
 'fixed_A_m5_to_m8':'固定A：m5→8','pure_to_half':'固定XYZ：纯块→半队替换',
 'half_to_first_below_half':'固定XYZ：半队→首次少于半队',
 'first_below_half_to_max':'固定XYZ：首次少于半队→最大D',
 'pure_to_max':'固定XYZ：纯块→最大D','half_to_max':'固定XYZ：半队→最大D'}

def boolean(s):return s.fillna(False).astype(str).str.lower().isin(['true','1','1.0'])

def aggregates(df,columns):
    cfg=df.groupby(CFG,dropna=False,observed=True)[columns].mean().reset_index()
    pairs=cfg.groupby(['pair_key','building'],observed=True)[columns].mean()
    buildings=pairs.groupby('building',observed=True)[columns].mean()
    row={}
    for c in columns:
        v=pairs[c].dropna()
        row['pair_equal__'+c]=float(v.mean())
        row['building_equal__'+c]=float(buildings[c].mean())
        row['supported_pairs__'+c]=len(v)
        row['positive_pairs__'+c]=int((v>0).sum())
        row['negative_pairs__'+c]=int((v<0).sum())
    return row,cfg,pairs

def write_report(out,supports,metrics,failures,states):
    def num(x):return '—' if pd.isna(x) else f'{x:+.3f}'
    def pct(x):return '—' if pd.isna(x) else f'{100*x:.2f}%'
    ss={r['comparison']:r for r in supports}
    mm={(r['comparison'],r['domain'],r['metric']):r for r in metrics}
    ff={r['comparison']:r for r in failures}
    xx={(r['comparison'],r['effect']):r for r in states}
    lines=['# 同一实际锚点下的换人数与增加背景：完成结果',
      '',
      '**固定原队A并增加跨类替换人数，与固定替换块再增加共同背景，得到不同的质量响应。** 在覆盖最广的普通Manual结构方向“TURN3常规转折→TURN3较多转折”中，固定A的m5→6和m5→7多数图对有净质量增益；增加共同D则往往提高源类对照队B，同时削弱目标队C的质量优势。平均转折数没有同步明显增加，底面定位误差的变化提供了更直接的解释线索。',
      '',
      '这是本轮新严格ABC设计已保存结果上的路径汇总，没有另选团队、重分类或新增融合。主方向按注册覆盖最广选择，完整其它方向保存在 `PATH_OVERALL_RESULTS.csv`。表内事件是覆盖量，实际支持以图对和建筑报告；不把路径数当作独立房间。',
      '',
      '## 1. 固定A与n：C本身变化、B本身变化和净差同时保留',
      '',
      'A由路径的真实成员定义，已核两个视角的team_key一致。设计为去除A/B镜像而规范化X/Y时，按 `nominal_A_role` 恢复真实A/B身份。Q、D10、转折、短转折、近共线、底面/方向/高度以下采用同一12端点共同支持。',
      '',
      '|同A转移|共同可评/全部尝试|图对/楼|C的Q变化|B的Q变化|净差C变化−B变化|楼等权净差|净差正向图对|',
      '|---|---:|---:|---:|---:|---:|---:|---:|']
    scale=[c for c in ss if c.startswith('fixed_A')]
    for c in scale:
        s=ss[c];m=mm[(c,'joint_Q_structure_position','B8L2')]
        lines.append(f"|{LABELS[c]}|{s['joint_Q_structure_position_transitions']}/{s['attempted_transitions']}|{s['joint_pairs']}/{s['joint_buildings']}|{num(m['pair_equal__C_change'])}|{num(m['pair_equal__B_change'])}|{num(m['pair_equal__net_C_minus_B_change'])}|{num(m['building_equal__net_C_minus_B_change'])}|{m['positive_pairs__net_C_minus_B_change']}/{m['supported_pairs__net_C_minus_B_change']}|")
    lines += ['',
      'm5→6、m5→7和m5→8各自在同一实际A内比较；它们的支持不同，不能再把三个均值相减解释更换第七或第八人的边际作用。m8只在两个图对、一栋楼有支持。固定A最小m→最大m的完整主方向结果为41图对、4楼：C平均+1.115、B−0.196、净+1.311分，楼等权净+1.186；对应表保留全部实际n/m。',
      '',
      '## 2. 固定X/Y/Z：背景加入过程的分段变化',
      '',
      '本节保持实际X/Y/Z不变，按原注册D顺序增加背景。这里n和替换比例一起改变，A/B/C都吸收同一个D；不是固定A的换人数实验。每段使用其自己的共同前后支持。',
      '',
      '|背景段|共同可评/全部尝试|图对/楼|C的Q变化|B的Q变化|净差|跨类额外幅度的变化|',
      '|---|---:|---:|---:|---:|---:|---:|']
    background=['pure_to_half','half_to_first_below_half','first_below_half_to_max','pure_to_max','half_to_max']
    for c in background:
        if c not in ss:continue
        s=ss[c];m=mm[(c,'joint_Q_structure_position','B8L2')]
        lines.append(f"|{LABELS[c]}|{s['joint_Q_structure_position_transitions']}/{s['attempted_transitions']}|{s['joint_pairs']}/{s['joint_buildings']}|{num(m['pair_equal__C_change'])}|{num(m['pair_equal__B_change'])}|{num(m['pair_equal__net_C_minus_B_change'])}|{num(m['pair_equal__extra_amplitude_change'])}|")
    lines += ['',
      '纯块→半队时，C平均回落、B平均提高；半队→首次少于半队时两队都平均回落，净差较小；后续继续加至最大D时，主要表现为B继续改善而C平均变化很小。这些是不同分段的实际结果，不把大跨度变化全部归于某一个D类别或单一投票门槛。分段支持不同，因此不把各段均值直接相加复原纯块→最大D。',
      '',
      '## 3. 数量结构与定位分项走不同方向',
      '',
      '|转移|C转折数变化|B转折数变化|C底面误差变化（°）|B底面误差变化（°）|',
      '|---|---:|---:|---:|---:|']
    for c in scale+background:
        if c not in ss:continue
        t=mm[(c,'joint_Q_structure_position','fusion_turn_n')]
        p=mm[(c,'joint_Q_structure_position','S_bottom_deg')]
        lines.append(f"|{LABELS[c]}|{num(t['pair_equal__C_change'])}|{num(t['pair_equal__B_change'])}|{num(p['pair_equal__C_change'])}|{num(p['pair_equal__B_change'])}|")
    lines += ['',
      '底面误差降低表示定位更接近冻结参考。固定A扩大m时C的平均转折变化接近零，但底面误差下降；纯块加D时C底面误差上升，而B下降。该分项模式提示定位与位置估计是需要保留的解释，不能仅凭目标类别名称写成“加入更多必要结构”。转折均值接近零也不证明每个成员或每个转移结构完全相同；精确逐视角变化保留在 `ANCHOR_PATH_EFFECTS.csv.gz`。',
      '',
      '## 4. 平均净收益与跨视角逐次响应分别看',
      '',
      '下表以C前后质量变化为对象，采用已有2分实际幅度阈值；在每个图对内先配置等权，再图对等权。两边近零不记作两边同向非零。',
      '',
      '|转移|两边近零|单边响应|两边同向非零|两边反向|',
      '|---|---:|---:|---:|---:|']
    for c in scale+background:
        if (c,'C_change') not in xx:continue
        x=xx[(c,'C_change')]
        lines.append('|'+LABELS[c]+'|'+'|'.join(pct(x['pair_equal__'+k]) for k in ['both_near_zero','one_sided','both_same_nonzero','both_opposite'])+'|')
    lines += ['',
      '固定A扩大m的平均净收益可以在多数图对出现，同时某一次具体调整仅在一个视角明显响应。这里支持的是有范围的配置作用，不是把同一个成员块在两个视角的变化当作完全可复制。零阈值的精确逐转移状态仍保留在全表。',
      '',
      '## 5. 低尾、失败及记录劳动时间',
      '',
      '|转移|C降质>5分|C升质>5分|C新增不可评分|C恢复可评分|',
      '|---|---:|---:|---:|---:|']
    for c in scale+background:
        if c not in ff:continue
        f=ff[c]
        lines.append('|'+LABELS[c]+'|'+'|'.join(pct(f['pair_equal__C_'+k]) for k in ['Q_loss_gt5_fraction','Q_gain_gt5_fraction','new_score_failure_fraction','recovered_score_fraction'])+'|')
    lines += ['',
      '升降超过5分使用共同12端点可评支持；新增失败和恢复使用全部尝试，先在两个视角取比例再按同样层级汇总。它们不使用同一个分母，也不把缺失评分补零。原表同时保留完整/不完整变化。',
      '',
      '同语义共同Q/T支持明显窄于质量支持：m5→6为292条转移、4图对、2楼，C平均Q+1.040、记录总劳动−31.72秒；m5→7为97条、2图对、2楼，C平均Q+1.619、劳动−21.40秒。m5→8没有共同Q/T支持。两组支持不同，不据此构造换人数的劳动趋势。增加完全相同D时，A/B/C各自增加相同的记录劳动量，劳动净差数学上为零；表中约1e−13的残差只来自浮点计算，不是成本收益。记录劳动不是并行交付时间。',
      '',
      '## 6. 表、精确键与复算',
      '',
      '- `ANCHOR_PATH_TRANSITIONS.csv.gz`：35,603条去重物理转移，固定A12,720条、固定XYZ22,883条；同一转移可回答多个阶段问题，比较标签不再相加当独立样本。',
      '- `ANCHOR_PATH_EFFECTS.csv.gz`：两阶段、两视角、ABC的精确键及原值、分项、状态；28,320个原ABC事件，完整端点引用无缺失，Q共同支持30,144条、Q/T共同支持11,887条。',
      '- `PATH_PAIR_CONFIG_SUMMARY.csv.gz`、`PATH_PAIR_SUMMARY.csv.gz`、`PATH_BUILDING_SUMMARY.csv`、`PATH_OVERALL_RESULTS.csv`：全部角色方向及实际n/m的结果。',
      '- `KEY_PATH_SEGMENT_SUPPORT.csv`、`KEY_PATH_JOINT_METRICS.csv`、`KEY_PATH_FAILURE_LOWTAIL.csv`、`KEY_PATH_CROSSVIEW_STATES.csv`：上文可读结果与分母。',
      '- `KEY_PATH_TRANSITION_INDEX.csv.gz`：可读段落回连全部实际转移；再经event_small/event_large连接严格ABC设计、team_key及geometry/full_state。',
      '',
      '从专题根目录运行：',
      '',
      '```bash',
      'python analysis/analyze_anchor_paths.py --design-dir design --native native_endpoints/ENDPOINT_SCALARS.csv.gz --out anchor_paths',
      'python analysis/report_anchor_paths.py --root .',
      '```',
      '',
      '前一脚本使用全量已保存端点；后一脚本仅重聚合已保存路径结果。都不重新融合或重分类。固定设计、标签和参考身份沿用本轮manifest；这不是丢失旧包的原件恢复。',
      '',
      '**采用判断：** 把“增加目标类替换规模”和“给固定替换块加背景”分别作为论文主文中的两条结果；前者在主方向多数图对取得有限净增益，后者常缩小目标类优势。把定位分项、低尾及单边响应一并保留，避免用历史结构类别名称代替当次几何机制。']
    (out/'README_ZH.md').write_text('\n'.join(lines)+'\n')

def main(root):
    root=Path(root);out=root/'anchor_paths'
    names=set(META+FAILURE)
    for m in STRUCTURE_METRICS+['recorded_time_total_seconds']:
        names.update([m+'_common12']+[m+'_'+e for e in EFFECTS])
    for e in ['C_change','B_change','net_C_minus_B_change']:
        names.add('eps2_'+e+'_crossview_state')
    d=pd.read_csv(out/'ANCHOR_PATH_EFFECTS.csv.gz',usecols=lambda c:c in names,low_memory=False)
    d=d[(d.method=='V3_BEHAVIOR')&(d.condition=='manual')&boolean(d.ordinary_comparable)&
        (d.source_role_key=='TURN3:常规转折')&(d.target_role_key=='TURN3:较多转折')].copy()
    if d.path_transition_id.duplicated().any():raise ValueError('duplicate physical transition')
    comparisons=[]
    for large in [6,7,8]:
        dd=d[(d.study_type=='fixed_A_scale')&(d.m_small==5)&(d.m_large==large)]
        if len(dd):comparisons.append((f'fixed_A_m5_to_m{large}',dd))
    for tag in ['pure_to_half','half_to_first_below_half','first_below_half_to_max','pure_to_max','half_to_max']:
        dd=d[(d.study_type=='fixed_XYZ_background')&d.comparison_tags.str.split('|').map(lambda a:tag in a)]
        if len(dd):comparisons.append((tag,dd))
    supports=[];metrics=[];failures=[];states=[];members=[]
    for comparison,dd in comparisons:
        common=np.ones(len(dd),bool)
        for metric in STRUCTURE_METRICS:common &= boolean(dd[metric+'_common12']).to_numpy()
        joint=dd[common];qt=dd[boolean(dd.QT_common12)]
        support=dict(comparison=comparison,method='V3_BEHAVIOR',condition='manual',
          source_role_key='TURN3:常规转折',target_role_key='TURN3:较多转折',
          attempted_transitions=len(dd),pairs=dd.pair_key.nunique(),buildings=dd.building.nunique(),
          Q_common12_transitions=int(boolean(dd.Q_common12).sum()),
          joint_Q_structure_position_transitions=len(joint),joint_pairs=joint.pair_key.nunique(),
          joint_buildings=joint.building.nunique(),QT_common12_transitions=len(qt),
          QT_pairs=qt.pair_key.nunique(),QT_buildings=qt.building.nunique(),
          exact_n_m_transitions='|'.join(f'{int(n1)}/{int(m1)}→{int(n2)}/{int(m2)}' for n1,m1,n2,m2 in sorted(set(zip(dd.n_small,dd.m_small,dd.n_large,dd.m_large)))),
          selection='all saved physical transitions of the named design segment; no outcome filtering')
        supports.append(support)
        members.extend(dict(comparison=comparison,path_transition_id=x) for x in dd.path_transition_id)
        for domain,dz,ms in [('joint_Q_structure_position',joint,STRUCTURE_METRICS),
                             ('joint_Q_recorded_time',qt,['B8L2','recorded_time_total_seconds'])]:
            for metric in ms:
                cs=[metric+'_'+e for e in EFFECTS]
                row,cfg,pair=aggregates(dz,cs)
                row={k.replace(metric+'_',''):v for k,v in row.items()}
                row.update(comparison=comparison,domain=domain,metric=metric,
                    transitions=len(dz),configurations=len(cfg),pairs=len(pair),
                    buildings=pair.reset_index().building.nunique())
                metrics.append(row)
        row,cfg,pair=aggregates(dd,FAILURE)
        row.update(comparison=comparison,attempted_transitions=len(dd),pairs=len(pair),buildings=dd.building.nunique())
        failures.append(row)
        for effect in ['C_change','B_change','net_C_minus_B_change']:
            q=dd[boolean(dd.Q_common12)].copy();c='eps2_'+effect+'_crossview_state'
            cstates=['both_near_zero','one_sided','both_same_nonzero','both_opposite']
            for state in cstates:q[state]=q[c].eq(state).astype(float)
            row,cfg,pair=aggregates(q,cstates)
            row.update(comparison=comparison,effect=effect,threshold=2,
                transitions=len(q),pairs=len(pair),buildings=q.building.nunique())
            states.append(row)
    for filename,records in [('KEY_PATH_SEGMENT_SUPPORT.csv',supports),('KEY_PATH_JOINT_METRICS.csv',metrics),
        ('KEY_PATH_FAILURE_LOWTAIL.csv',failures),('KEY_PATH_CROSSVIEW_STATES.csv',states),
        ('KEY_PATH_TRANSITION_INDEX.csv.gz',members)]:
        pd.DataFrame(records).to_csv(out/filename,index=False,compression='gzip' if filename.endswith('.gz') else None)
    receipt=dict(version='SRLB_PATH_READING_20261023_v1',new_fusion_calls=0,new_designs=0,
      source='ANCHOR_PATH_EFFECTS.csv.gz',main_direction='TURN3:常规转折 -> TURN3:较多转折',
      selection_basis='widest ordinary Manual direction by registered design coverage',segments=len(supports),
      joint_quality_geometry_metrics=STRUCTURE_METRICS,
      scale_support='m5 to m6/m7/m8 are existing physical transitions; their supports differ and are not subtracted from each other',
      background_support='fixed actual XYZ and nested D; each segment uses its own paired before/after support',
      time_rule='Q and recorded time both common across all 12 endpoint references; not a wall-clock completion estimate',
      zero_time_net='Adding identical D adds identical recorded labor to A/B/C; tiny net floating differences are not a cost benefit.',
      failures='all attempted transitions, while Q loss/gain fractions retain saved common-Q support',
      weighting='member transitions within exact pair/direction/n_small/n_large/m_small/m_large -> physical pair -> optional building')
    (out/'KEY_PATH_READING_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    write_report(out,supports,metrics,failures,states)
    print(json.dumps({'segments':len(supports),'metric_rows':len(metrics),'failure_rows':len(failures),'crossview_rows':len(states)},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default=Path(__file__).resolve().parents[1]);main(p.parse_args().root)
