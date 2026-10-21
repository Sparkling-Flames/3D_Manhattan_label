"""Publication-readable summaries; numeric tables remain the primary evidence."""
import sys as _delivery_sys
from pathlib import Path as _DeliveryPath
_delivery_root = next((p for p in _DeliveryPath(__file__).resolve().parents if (p / 'direct_io.py').is_file()))
_delivery_sys.path.insert(0, str(_delivery_root))
from direct_io import read_csv as _read_csv, open_data as _open_data, write_csv as _write_csv, write_bytes as _write_bytes, data_exists as _data_exists
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties, fontManager

def save(fig, out, name):
    fig.savefig(out / 'figures' / (name + '.png'), dpi=180, bbox_inches='tight', facecolor='white')
    fig.savefig(out / 'figures' / (name + '.svg'), bbox_inches='tight', facecolor='white')
    plt.close(fig)

def figures(out):
    t = out / 'tables'
    (out / 'figures').mkdir(parents=True, exist_ok=True)
    groups = _read_csv(t / 'declared_group_similarity.csv')
    views = _read_csv(t / 'declared_group_views.csv')
    gs = groups[(groups.declaration_source == 'original') & (groups.condition == 'manual') & (groups.layer == 'ordinary') & groups.all_pair_scope_comparable].sort_values('declaration_id')
    fig, axes = plt.subplots(1, 2, figsize=(14, 10), sharey=True, gridspec_kw={'wspace': 0.1})
    colors = {'简单': '#247ba0', '中等': '#d18b19', '困难': '#b33e54', '单列': '#675e8c'}
    for j, g in enumerate(gs.itertuples()):
        v = views[(views.declaration_id == g.declaration_id) & (views.declaration_source == 'original') & (views.condition == 'manual')].sort_values('image_code')
        for ax, col in zip(axes, ['mean', 'whole_group_common_mean']):
            if col.startswith('whole') and g.whole_group_common_n < 3:
                ax.text(53, j, '全组共同人员不足 3 人', va='center', color='#888888', fontsize=9)
                continue
            x = v[col].values
            ax.plot([np.min(x), np.max(x)], [j, j], color='#9aa7b0', lw=2, zorder=1)
            offsets = np.linspace(-0.14, 0.14, len(v))
            for offset, r in zip(offsets, v.itertuples()):
                val = getattr(r, col)
                ax.scatter(val, j + offset, s=33, color=colors.get(r.current_class, '#675e8c'), edgecolor='white', lw=0.4, zorder=3)
            for idx, align, off in [(int(np.argmin(x)), 'right', -0.9), (int(np.argmax(x)), 'left', 0.9)]:
                r = v.iloc[idx]
                ax.text(x[idx] + off, j + (0.18 if idx == int(np.argmax(x)) else -0.18), str(r.image_code).rsplit('-', 1)[-1], ha=align, va='center', fontsize=7, color='#4d5861')
        if j % 2 == 0:
            for ax in axes:
                ax.axhspan(j - 0.45, j + 0.45, color='#f3f6f8', zorder=0)
    axes[0].set_yticks(np.arange(len(gs)), [f'{g.declaration_id}  ·  {g.n_quality_images} 图' for g in gs.itertuples()])
    for ax in axes:
        ax.set_xlim(20, 99)
        ax.set_ylim(len(gs) - 0.4, -0.6)
        ax.set_xlabel('各视角 B8L2 均值（分）')
        ax.grid(axis='x', alpha=0.18)
        ax.spines[['top', 'right', 'left']].set_visible(False)
        ax.tick_params(axis='y', length=0)
    axes[0].set_title('实际人员池：全部 64 图', fontsize=13, pad=12)
    axes[1].set_title('固定全组共同人员：有支持的 44 图', fontsize=13, pad=12)
    for k, c in colors.items():
        axes[1].scatter([], [], c=c, s=32, label=k)
    handles, labels = axes[1].get_legend_handles_labels()
    fig.legend(handles, labels, title='现用难度', frameon=False, loc='lower center', ncol=4, bbox_to_anchor=(0.55, 0.07))
    fig.suptitle('同房均值往往相近，但视角差异和人员构成均不可忽略', fontsize=18, y=0.985)
    fig.text(0.5, 0.025, '19 个原声明组全部展示，含 10 个只有两张可评分视角的组。点代表图片；横线代表组内范围；小数字为图片编号。\n右图每一组固定同一批人员；不同组的共同人员数量不同。声明组可能重叠，不计作独立房间样本。', ha='center', fontsize=10, color='#4d5861')
    fig.subplots_adjust(top=0.93, bottom=0.18, left=0.13, right=0.98)
    save(fig, out, '01_declared_group_means')
    bridge = _read_csv(t / 'matched_control_support_bridge.csv')
    bridge = bridge[bridge.metric == 'B8L2']
    main = bridge[bridge.panel == 'actual'].set_index('control')
    labels = ['同一支持：未知背景未匹配', '同一支持：匹配难度', '同一支持：难度＋转折＋遮挡', '再固定三图共同人员']
    selected = [main.loc[k] for k in ['same_support_unmatched', 'same_support_class', 'same_support_strict']] + [bridge[(bridge.panel == 'triple') & (bridge.control == 'same_support_strict')].iloc[0]]
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.4), gridspec_kw={'width_ratios': [1.25, 1]})
    y = np.arange(4)
    axes[0].barh(y - 0.16, [r.same_gap for r in selected], height=0.3, color='#247ba0', label='同房')
    axes[0].barh(y + 0.16, [r.unknown_gap for r in selected], height=0.3, color='#c8ced3', label='同建筑关系未知')
    for j, r in enumerate(selected):
        axes[0].text(r.same_gap + 0.12, j - 0.16, f'{r.same_gap:.2f}', va='center', fontsize=11)
        axes[0].text(r.unknown_gap + 0.12, j + 0.16, f'{r.unknown_gap:.2f}', va='center', fontsize=11)
    axes[0].set_yticks(y, labels)
    axes[0].invert_yaxis()
    axes[0].set_xlim(0, 13.2)
    axes[0].legend(frameon=False, ncol=2, loc='upper right')
    axes[0].set_xlabel('平均质量绝对差（建筑等权，分）')
    b = _read_csv(t / 'matched_unknown_buildings.csv')
    b = b[(b.subset == 'strict_class_turns_hidden') & (b.panel == 'triple') & (b.metric == 'B8L2')].sort_values('gain')
    for j, r in enumerate(b.itertuples()):
        axes[1].plot([r.same_gap, r.unknown_gap], [j, j], color='#bac3c9', lw=2)
        axes[1].scatter(r.same_gap, j, c='#247ba0', s=50, zorder=3)
        axes[1].scatter(r.unknown_gap, j, c='#929ba3', s=50, zorder=3)
        axes[1].text(max(r.same_gap, r.unknown_gap) + 0.22, j, f'Δ {r.gain:+.2f}', va='center', fontsize=9)
    axes[1].set_yticks(range(len(b)), b.building_id)
    axes[1].set_xlim(0, 12.7)
    axes[1].set_xlabel('三图共同人员的均值差（分）')
    axes[1].set_title('严格匹配后，9 栋中 8 栋同房更接近', fontsize=12)
    for ax in axes:
        ax.spines[['top', 'right', 'left']].set_visible(False)
        ax.grid(axis='x', alpha=0.15)
        ax.tick_params(axis='y', length=0)
    fig.suptitle('难度解释了较大部分相似性；同房仍提供约 2.24 分的额外接近', fontsize=17, y=1.0)
    fig.text(0.5, 0.015, '左图前三行固定 209 个方向／9 栋建筑；最后一行为 205 方向／108 对、同一三图共同人员不少于 4 人。\n未知背景按全部满足条件者平均，未依据 Q 挑选。末行同房优势 2.24 分，建筑 bootstrap 区间 [1.15, 3.46]。', ha='center', fontsize=10, color='#4d5861')
    fig.subplots_adjust(top=0.88, bottom=0.18, left=0.2, right=0.98, wspace=0.48)
    save(fig, out, '02_matched_unknown_background')
    s = _read_csv(t / 'mean_holdout_summary.csv')
    s = s[(s.metric == 'B8L2') & (s.panel == 'actual_pool')]
    fig = plt.figure(figsize=(14, 10))
    grid = fig.add_gridspec(2, 3, height_ratios=[1.1, 1], hspace=0.48, wspace=0.32)
    ax = fig.add_subplot(grid[0, :])
    methods = ['external_image_mean', 'calibrated_peer_roster_only', 'source_mean', 'calibrated_peer_source', 'known_difficulty_adjusted_source']
    labels = ['楼外图片均值', '楼外人员相对 Q＋校准', '同房源均值', '同房＋人员相对 Q＋校准', '同房＋全局难度差校正']
    colors_stage = ['#b2bec7', '#247ba0', '#b33e54']
    for j, stage in enumerate(['single_source', 'minimum_majority', 'maximum_history']):
        z = s[s.stage == stage].set_index('method').loc[methods]
        ax.bar(np.arange(len(methods)) + (j - 1) * 0.24, z.mae, width=0.22, color=colors_stage[j], label=['单源', '最低严格多数', 'N−1 张历史'][j])
        for k, r in enumerate(z.itertuples()):
            ax.text(k + (j - 1) * 0.24, r.mae + 0.11, f'{r.mae:.2f}', ha='center', fontsize=9)
    ax.set_xticks(range(len(methods)), labels)
    ax.set_ylim(0, 12.5)
    ax.set_ylabel('留出图片均值 MAE（分）')
    ax.legend(frameon=False, ncol=3)
    ax.grid(axis='y', alpha=0.15)
    ax.spines[['top', 'right']].set_visible(False)
    g = _read_csv(t / 'mean_holdout_groups.csv')
    g = g[(g.metric == 'B8L2') & (g.panel == 'actual_pool')]
    for i, (gid, title) in enumerate([('MV0002', 'G047 · 5 图'), ('MV0006', 'G172 · 11 图'), ('MV0007', 'G178 · 7 图')]):
        ax = fig.add_subplot(grid[1, i])
        z = g[(g.group_id == gid) & (g.method == 'source_mean')].sort_values('m')
        ax.plot(z.m, z.mae, 'o-', color='#247ba0', lw=2)
        for r in z.itertuples():
            ax.annotate(f'{r.mae:.2f}', (r.m, r.mae), xytext=(0, 8), textcoords='offset points', ha='center', fontsize=10)
        ax.set_xticks(z.m)
        ax.set_xlabel('实际历史图片数 m')
        ax.set_ylabel('均值 MAE（分）')
        ax.set_title(title)
        ax.set_ylim(0, max(z.mae) * 1.2)
        ax.grid(alpha=0.15)
        ax.spines[['top', 'right']].set_visible(False)
    fig.suptitle('均值迁移最有用的是同房公共水平；人员画像的额外增益很小', fontsize=18, y=0.98)
    fig.text(0.5, 0.015, '主面板：44 图／9 个声明组／7 栋建筑，同一目标支持，楼外拟合。多数历史枚举所有 m>N/2 的来源组合。\n最低多数的简单源均值 MAE=4.110，最强连续校正=4.076（改善 0.033）；其误差超过 10 分的概率由 2.92% 升至 3.90%。\n下图保留真正有多个严格多数历史量的三组；其余六组的最低／最高多数历史相同。', ha='center', fontsize=10, color='#4d5861')
    fig.subplots_adjust(top=0.92, bottom=0.17, left=0.07, right=0.98)
    save(fig, out, '03_mean_holdout_and_history_budget')
    lines = ['# 逐声明组质量图谱', '', '这是本轮新增的可读索引，使用原房间声明和冻结评分。原声明组和候选子集分别标明；组可能重叠，不将行数视为独立房间数。实际池均值与固定全组共同人员均值分别保留。', '']
    for condition, layer, comparable, title in [('manual', 'ordinary', True, '普通 Manual：范围可比'), ('manual', 'ordinary', False, '普通 Manual：范围不同／不可比'), ('manual', 'doorway', False, 'Manual：含门洞视角'), ('semi', 'ordinary', False, 'Semi：现有成对支持')]:
        z = groups[(groups.declaration_source == 'original') & (groups.condition == condition) & (groups.layer == layer) & (groups.all_pair_scope_comparable == comparable)].sort_values('declaration_id')
        lines += ['## ' + title, '', '|原组|各视角：实际人员池均值（人数）|共同人数|固定全组共同人员：各视角均值|逐对共同池平均绝对差|', '|---|---|---:|---|---:|']
        for r in z.itertuples():
            v = views[(views.declaration_id == r.declaration_id) & (views.declaration_source == 'original') & (views.condition == condition)].sort_values('image_code')
            a = '；'.join((f"{x.image_code.rsplit('-', 1)[-1]}: {x.mean:.2f} ({x.n})" for x in v.itertuples()))
            c = '；'.join((f"{x.image_code.rsplit('-', 1)[-1]}: {x.whole_group_common_mean:.2f}" for x in v.itertuples())) if r.whole_group_common_n else '无全组共同人员'
            lines.append(f'|{r.declaration_id} · {r.building_id}|{a}|{r.whole_group_common_n}|{c}|{r.pair_common_abs_gap:.2f}|')
        lines += ['']
    lines += ['## 连接说明', '', '完整图片 ID、目标／参考、物理关系、范围状态、难度、各图分位数及每对成员见 `tables/declared_group_views.csv` 和 `tables/direct_pair_similarity.csv`。G236 的候选子集与原声明在当前可评分图上重合，因此可读表不重复一行，CSV保留其来源。含门洞组中的普通–普通图对，仍在逐对表按其实际层次记录。', '']
    (out / 'GROUP_ATLAS_ZH.md').write_text('\n'.join(lines), encoding='utf8')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--font', type=Path, required=True)
    a = ap.parse_args()
    fontManager.addfont(str(a.font))
    plt.rcParams.update({'font.family': FontProperties(fname=a.font).get_name(), 'font.size': 10, 'axes.unicode_minus': False, 'svg.fonttype': 'path'})
    figures(a.out)
if __name__ == '__main__':
    main()
