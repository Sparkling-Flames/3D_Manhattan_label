"""Render saved, building-balanced native experiment summaries."""
import sys as _delivery_sys
from pathlib import Path as _DeliveryPath
_delivery_root = next((p for p in _DeliveryPath(__file__).resolve().parents if (p / 'direct_io.py').is_file()))
_delivery_sys.path.insert(0, str(_delivery_root))
from direct_io import read_csv as _read_csv, open_data as _open_data, write_csv as _write_csv, write_bytes as _write_bytes, data_exists as _data_exists
from pathlib import Path
import sys
import numpy as np
import pandas as pd
P = Path(__file__).resolve().parent
sys.path.insert(0, str(P.parent))
import render_cases as v
plt = v.plt
BLUE = '#167b9c'
RED = '#c34d64'
GRAY = '#69798c'
GREEN = '#25866e'

def main_filter(d):
    return d[(d.condition == 'manual') & (d.layer == 'ordinary_manual') & d.scope_comparable]

def main():
    d = main_filter(_read_csv(P / 'SWAP_SUMMARY.csv'))
    d = d[(d.tier == 'primary_coarse_class') & (d.m == 1) & (d.outgoing_class == 'M0') & (d.incoming_class == 'M1')]
    fig, ax = plt.subplots(2, 2, figsize=(14, 9.6))
    a = ax[0, 0]
    for i, n in enumerate([5, 9]):
        for j, (name, color, label) in enumerate([('capacity_random', BLUE, '容量内随机块'), ('outside_Q_gap_le3', RED, '楼外Q差≤3的匹配块')]):
            r = d[(d.n == n) & (d.design == name)].iloc[0]
            x = i + (-0.16 if j == 0 else 0.16)
            a.bar(x, r.net_B8L2, 0.3, color=color, label=label if i == 0 else None)
            a.errorbar(x, r.net_B8L2, yerr=[[r.net_B8L2 - r.net_B8L2_lo], [r.net_B8L2_hi - r.net_B8L2]], color='#263244', capsize=4)
            a.text(x, r.net_B8L2 + (0.45 if r.net_B8L2 >= 0 else -0.7), f'{r.net_B8L2:+.2f}', ha='center', fontsize=11)
    a.axhline(0, color=GRAY, lw=0.8)
    a.set_xticks([0, 1], ['5人换1人', '9人换1人'])
    a.set_ylabel('C−B：融合B8L2变化')
    a.set_title('M0→M1：历史Q匹配后，平均收益不再保持')
    a.legend(frameon=False, fontsize=9, loc='upper right')
    a.set_ylim(-6, 10)
    a = ax[0, 1]
    t = main_filter(_read_csv(P / 'TRANSFER_SUMMARY.csv'))
    t = t[(t.design == 'capacity_random') & (t.tier == 'primary_coarse_class') & (t.m == 1) & (t.n == 5) & (t.outgoing_class == 'M0') & (t.incoming_class == 'M1')].set_index('effect_filter')
    keys = ['all_scored', 'source_abs_ge2', 'both_abs_ge2']
    vals = [t.loc[k, 'sign_agree'] * 100 for k in keys]
    a.bar(range(3), vals, color=[BLUE, BLUE, RED])
    a.set_xticks(range(3), ['所有可评分', '仅源|效应|≥2', '源、目标均≥2'])
    a.set_ylim(0, 100)
    a.set_ylabel('同向率 %')
    a.set_title('双端筛选提高描述性同向率，不能直接部署')
    for i, k in enumerate(keys):
        a.text(i, vals[i] + 2, f"{vals[i]:.1f}%\n{int(t.loc[k, 'events'])}方向／{int(t.loc[k, 'images'])}图", ha='center', fontsize=10)
    a = ax[1, 0]
    q = _read_csv(P / 'HISTORY_Q_ADJUSTMENT_SUMMARY.csv').set_index('model')
    keys = ['history_Q_only', 'history_Q_plus_class', 'history_Q_class_difficulty']
    vals = [q.loc[k, 'AE'] for k in keys]
    a.barh(range(3), vals, color=[BLUE, GRAY, GRAY])
    a.set_yticks(range(3), ['历史Q差', '历史Q差＋类别', '再加类别×难度'])
    a.invert_yaxis()
    a.set_xlim(0, 8)
    a.set_xlabel('留整栋建筑：替换效应MAE')
    a.set_title('类别没有超过历史Q差的连续基线')
    for i, x in enumerate(vals):
        a.text(x + 0.08, i, f'{x:.3f}', va='center')
    a = ax[1, 1]
    n = _read_csv(P / 'NESTED_COUNT_SUMMARY.csv')
    n = n[(n.outgoing_class == 'M0') & (n.incoming_class == 'M1')].sort_values('n')
    a.plot(n.n, n.net_B8L2, 'o-', color=BLUE)
    a.axhline(0, color=GRAY, lw=0.8)
    a.set_xticks(n.n)
    a.set_xlabel('团队人数 n（替换同一人，核心嵌套）')
    a.set_ylabel('融合B8L2变化')
    a.set_title(f'同一嵌套支持：{int(n.iloc[0].images)}图／{int(n.iloc[0].buildings)}栋')
    for r in n.itertuples():
        a.annotate(f'{r.net_B8L2:.2f}', (r.n, r.net_B8L2), xytext=(0, 7), textcoords='offset points', ha='center', fontsize=10)
    fig.suptitle('类别替换：能描述结构，但平均质量增益需要分离历史Q与筛选条件', fontsize=17)
    fig.text(0.5, 0.015, '普通Manual、范围可比；目标图内先平均，再建筑等权。误差线为建筑bootstrap；匹配块是Q重叠区域，不能解释为全体类别的因果效应。', ha='center', fontsize=10)
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    fig.savefig(P.parent / 'figures/class_and_swap_evidence.png', dpi=145)
    plt.close(fig)
    d = main_filter(_read_csv(P / 'POLICY_SUMMARY.csv'))
    z = d[(d.domain == 'new_timed_history') & (d.n == 5)].set_index('policy')
    keys = ['outside_Q', 'outside_Q_outside_T_fast', 'outside_Q_source_T_fast', 'source_Q', 'half_Q_structure', 'random']
    names = ['楼外Q', '楼外Q＋楼外T省时', '楼外Q＋源图T省时', '本人源图Q', '混合Q＋结构构成', '随机']
    fig, ax = plt.subplots(1, 2, figsize=(14, 6.5))
    a = ax[0]
    y = np.arange(len(keys))
    vals = [z.loc[k, 'B8L2'] for k in keys]
    a.barh(y, vals, color=[BLUE, GREEN, GRAY, GRAY, GRAY, '#c6ced7'])
    a.set_yticks(y, names)
    a.invert_yaxis()
    a.set_xlim(75, 100)
    a.set_xlabel('目标融合B8L2')
    a.set_title('同支持：5人、62图、11栋')
    for i, k in enumerate(keys):
        a.text(vals[i] + 0.15, i, f"{vals[i]:.2f}  /  坏尾 {z.loc[k, 'loss_over5'] * 100:.1f}%", va='center', fontsize=10)
    a = ax[1]
    for k, name, col in zip(keys, names, [BLUE, GREEN, RED, GRAY, '#9769a1', '#b5bdc8']):
        r = z.loc[k]
        a.scatter(r.activity_ratio_geometric * 100, r.delta_Q, s=110, color=col)
        a.annotate(name, (r.activity_ratio_geometric * 100, r.delta_Q), xytext=(5, 7 if k != 'outside_Q_source_T_fast' else -16), textcoords='offset points', fontsize=10)
    a.axhline(0, color=GRAY, lw=0.8)
    a.axvline(100, color=GRAY, lw=0.8)
    a.set_xlim(72, 113)
    a.set_ylim(-10, 1.5)
    a.set_xlabel('目标总劳动时间 / 楼外Q团队（几何平均，%）')
    a.set_ylabel('相对楼外Q团队的B8L2变化')
    a.set_title('成本与低尾须同时报告')
    fig.suptitle('人员选择：楼外Q是强基线；连续Q/T能省时，但局部坏尾仍须保留', fontsize=17)
    fig.text(0.5, 0.055, '坏尾＝同目标、同5人预算，相对楼外Q团队损失超过5分；不是不完整率。楼外Q/T省时完整率100%，坏尾8.57%。', ha='center', fontsize=10)
    fig.text(0.5, 0.022, '只计同语义的新数据活动耗时；不是实际交付时间。源图选人额外需要有GT的源图历史；楼外Q/T规则不必新采目标房间历史。', ha='center', fontsize=10)
    fig.tight_layout(rect=(0, 0.12, 1, 0.91))
    fig.savefig(P.parent / 'figures/team_cost_tradeoff.png', dpi=145)
    plt.close(fig)
if __name__ == '__main__':
    main()
