"""Publication-style figures from the stop reconstruction and native branch."""
import sys as _delivery_sys
from pathlib import Path as _DeliveryPath
_delivery_root = next((p for p in _DeliveryPath(__file__).resolve().parents if (p / 'direct_io.py').is_file()))
_delivery_sys.path.insert(0, str(_delivery_root))
from direct_io import read_csv as _read_csv, open_data as _open_data, write_csv as _write_csv, write_bytes as _write_bytes, data_exists as _data_exists
from pathlib import Path
import argparse, gzip, json, hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
LABEL = {'fixed_5_geometry': '固定5人＋补收', 'fixed_7_geometry': '固定7人＋补收', 'fixed_9_geometry': '固定9人＋补收', 'full_common_pool': '全共同人员池', 'source_within2_min3_geometry': '源曲线距峰≤2分', 'source_within1_min3_geometry': '源曲线距峰≤1分', 'source_q_minus_k_min3_geometry': '源Q－人数', 'online_same_nodecount_3_geometry': '仅点数连续稳定', 'online_three_transitions_2deg': '点数＋环距连续稳定'}

def main(repo, out, font, photo=None):
    font_manager.fontManager.addfont(str(font))
    plt.rcParams['font.family'] = font_manager.FontProperties(fname=str(font)).get_name()
    plt.rcParams.update({'axes.spines.top': False, 'axes.spines.right': False, 'font.size': 10, 'savefig.dpi': 180, 'axes.unicode_minus': False})
    blue = '#1565a8'
    orange = '#d26b31'
    green = '#2a8c77'
    gray = '#7e8792'
    summary = _read_csv(out / 'stopping_summary.csv')
    main = summary[(summary.panel == 'whole_group') & (summary.support == 'all_attempts') & (summary.history_budget == 'maximum_history') & (summary.time_support == 'all_groups')].set_index('policy')
    policies = ['fixed_5_geometry', 'fixed_7_geometry', 'source_q_minus_k_min3_geometry', 'source_within2_min3_geometry', 'source_within1_min3_geometry', 'full_common_pool']
    colors = [gray, gray, orange, blue, blue, green]
    y = np.arange(len(policies))
    z = main.loc[policies]
    fig, axs = plt.subplots(1, 3, figsize=(15.6, 5.3), gridspec_kw={'width_ratios': [1, 1.35, 1]})
    axs[0].barh(y, z.mean_k, color=colors)
    axs[0].set_yticks(y, [LABEL[p] for p in policies])
    axs[0].invert_yaxis()
    axs[0].set_xlabel('目标实际收答人数')
    for i, v in enumerate(z.mean_k):
        axs[0].text(v + 0.15, i, f'{v:.2f}', va='center')
    axs[0].set_xlim(0, 18)
    for i, (q, t) in enumerate(zip(z.q_mean, z.q10)):
        axs[1].plot([t, q], [i, i], color=colors[i], lw=3, alpha=0.7)
        axs[1].scatter([q], [i], color=colors[i], s=55)
        axs[1].scatter([t], [i], color=colors[i], s=50, marker='|')
        axs[1].text(q + 0.35, i, f'{q:.2f}', va='center', fontsize=9)
    axs[1].set_yticks(y, [])
    axs[1].invert_yaxis()
    axs[1].set_xlabel('B8L2：圆点为均值，短竖线为平均目标内P10')
    axs[1].set_xlim(75, 92)
    axs[2].barh(y, 100 * z.loss_gt5_to_full_rate_paired, color=colors)
    axs[2].set_yticks(y, [])
    axs[2].invert_yaxis()
    axs[2].set_xlabel('相对全共同池损失>5分的比例（%）')
    for i, v in enumerate(100 * z.loss_gt5_to_full_rate_paired):
        axs[2].text(v + 0.3, i, f'{v:.1f}%', va='center', fontsize=9)
    axs[2].set_xlim(0, 34)
    fig.suptitle('同房源曲线有实用人数信息，但平均收益与坏尾需要同时评价', x=0.04, ha='left', fontsize=17, weight='bold')
    fig.text(0.04, 0.015, '普通Manual；6个全组共同池／24图／6栋建筑；最大历史 N−1；全部尝试；目标→组→建筑等权。\n表中各规则完整率均100%；P10为各目标路径分布第10百分位的层级平均，不是全体样本的合并分位数。', fontsize=9, color='#48515c')
    fig.tight_layout(rect=[0, 0.095, 1, 0.91])
    fig.savefig(out / 'stopping_quality_tail.png')
    plt.close(fig)
    t = summary[(summary.panel == 'whole_group') & (summary.support == 'all_attempts') & (summary.history_budget == 'maximum_history') & (summary.time_support == 'all_new_complete_time')].set_index('policy')
    proj = _read_csv(out / 'source_acquisition_summary.csv')
    proj = proj[(proj.panel == 'whole_group') & (proj.history_budget == 'maximum_history')].set_index('policy')
    ps = ['fixed_7_geometry', 'source_q_minus_k_min3_geometry', 'source_within2_min3_geometry', 'full_common_pool']
    fig, axs = plt.subplots(1, 3, figsize=(15.5, 5.4))
    x = np.arange(4)
    axs[0].bar(x, t.loc[ps, 'ratio_mean_activity_to_fixed7_geometry'], color=[gray, orange, blue, green])
    axs[0].axhline(1, color='#222', lw=0.8)
    axs[0].set_xticks(x, [LABEL[p] for p in ps], rotation=20, ha='right')
    axs[0].set_ylabel('目标劳动／固定7人＋补收')
    axs[0].set_title('源历史已存在：目标边际劳动')
    for i, v in enumerate(t.loc[ps, 'ratio_mean_activity_to_fixed7_geometry']):
        axs[0].text(i, v + 0.04, f'{v:.3f}', ha='center')
    vals = [1, proj.loc[ps[1], 'project_ratio_to_fixed7_geometry'], proj.loc[ps[2], 'project_ratio_to_fixed7_geometry']]
    axs[1].bar(np.arange(3), vals, color=[gray, orange, blue])
    axs[1].axhline(1, color='#222', lw=0.8)
    axs[1].set_xticks(np.arange(3), [LABEL[p] for p in ps[:3]], rotation=20, ha='right')
    axs[1].set_ylabel('整组劳动／所有视角固定7人＋补收')
    axs[1].set_title('从零建立源全曲线：源＋目标')
    for i, v in enumerate(vals):
        axs[1].text(i, v + 0.04, f'{v:.3f}', ha='center')
    tail = 100 * t.loc[ps, 'loss_gt5_to_full_rate_paired']
    axs[2].bar(x, tail, color=[gray, orange, blue, green])
    axs[2].set_xticks(x, [LABEL[p] for p in ps], rotation=20, ha='right')
    axs[2].set_ylabel('各规则相对全共同池损失>5分（%）')
    axs[2].set_title('同支持上的质量坏尾')
    for i, v in enumerate(tail):
        axs[2].text(i, v + 0.5, f'{v:.2f}%', ha='center')
    fig.suptitle('省下目标劳动，不等于为了这一次决策建立历史也划算', x=0.04, ha='left', fontsize=17, weight='bold')
    fig.text(0.04, 0.015, '4个全新人员共同池／14图／4栋建筑；所有完整源历史与目标均有同语义活动耗时；最大历史 N−1。\n左图先求目标内平均劳动之比，再按图／组／建筑等权；中图逐历史划分比较整组源＋目标劳动。参考建立、评分劳动未记录，未补成零。', fontsize=9, color='#48515c')
    fig.tight_layout(rect=[0, 0.11, 1, 0.9])
    fig.savefig(out / 'stopping_cost_source_acquisition.png')
    plt.close(fig)
    src = repo / 'research/same_room/same_room_multiview_20261020'
    nodes = _read_csv(src / 'replay_nodes.csv.gz', low_memory=False)
    gid = 'MV0001'
    image = 'S9hNv5qa7GM-21'
    replay = 136
    n = nodes[(nodes.group_id == gid) & (nodes.image == image) & (nodes.replay == replay)].sort_values('k')
    with _open_data(out / 'online_geometry_prefixes.json.gz', 'rt') as f:
        states = json.load(f)
    st = {r['k']: r for r in states if r['group_id'] == gid and r['image_code'] == image and (r['replay'] == replay)}
    tr = _read_csv(out / 'online_geometry_transitions.csv')
    tr = tr[(tr.group_id == gid) & (tr.image_id == n.image_id.iloc[0]) & (tr.replay == replay)].sort_values('k')
    with _open_data(src / 'REPLAY_POOLS.json.gz', 'rt') as f:
        pool = next((p for p in json.load(f) if p['meta']['image'] == image))
    reference = np.asarray(pool['reference']['floor_xz_h'])
    fig = plt.figure(figsize=(15.5, 9))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.65, 1], height_ratios=[1.1, 1], hspace=0.33, wspace=0.23)
    ax = fig.add_subplot(gs[0, 0])
    ax.plot(n.k, n.B8L2, 'o-', ms=3, color=blue, label='B8L2（仅用于事后评价）')
    ax.plot(n.k, n.D10, '--', lw=1.2, color=gray, label='D10（同一精确团队）')
    for k, label, col in [(6, '无GT几何停止\nk=6, Q=70.07', orange), (19, '源曲线停止\nk=19, Q=92.02', green), (30, '全共同池\nk=30, Q=96.02', blue)]:
        q = float(n.loc[n.k == k, 'B8L2'].iloc[0])
        ax.scatter([k], [q], s=65, color=col, zorder=5)
        ax.annotate(label, (k, q), xytext=(0, -38 if k == 6 else -32), textcoords='offset points', ha='center', fontsize=9, color=col)
    ax.axvline(6, color=orange, ls=':')
    ax.set_ylim(56, 101)
    ax.set_xlim(0.5, 31)
    ax.set_xlabel('实际收答人数 k')
    ax.set_ylabel('参考质量分')
    ax.legend(loc='lower right', fontsize=8)
    ax.set_title('同一人员顺序：短期稳定后，质量仍继续改变', loc='left')
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.plot(tr.k, tr.transition_bound_cyclic_deg, 'o-', ms=3, color=orange, label='与上一前缀的绑定环对应角距')
    ax2.axhline(2, color='#333', ls='--', lw=1, label='固定2°阈值')
    ax2.axvspan(3.7, 6.3, color=orange, alpha=0.12)
    ax2.axvline(6, color=orange, ls=':')
    ax2.set_xlabel('当前人数 k')
    ax2.set_ylabel('相邻融合角距（度）')
    ax2.set_xlim(0.5, 31)
    ax2.set_ylim(0, 6)
    ax2.text(0.03, 0.91, 'k=3–6均为完整六角；三次转换为1.559°、1.558°、1.415°', transform=ax2.transAxes, fontsize=9)
    ax2.legend(loc='upper right', bbox_to_anchor=(1, -0.19), fontsize=8, ncol=1)
    ax2.set_title('停止判定只读取已到达的目标几何', loc='left')
    ax3 = fig.add_subplot(gs[:, 1])
    for points, style, col, label in [(reference, '--', '#20242b', '固定参考'), (np.asarray(st[6]['footprint']), '-', orange, 'k=6：六角、Q70.07'), (np.asarray(st[30]['footprint']), '-', blue, 'k=30：六角、Q96.02')]:
        pts = np.vstack([points, points[0]])
        ax3.plot(pts[:, 0], pts[:, 1], style, color=col, label=label, lw=1.7)
        ax3.scatter(points[:, 0], points[:, 1], s=18, color=col)
    ax3.set_aspect('equal')
    ax3.set_xlabel('x / 相机高')
    ax3.set_ylabel('z / 相机高')
    ax3.legend(loc='lower left', fontsize=9)
    ax3.set_title('同图BEV：关键差异是墙向／位置', loc='left')
    ax3.annotate('早期端点形成斜墙\n方向残差4.93°→0.95°', xy=(-1.38, 0.33), xytext=(-1.7, 1.65), arrowprops={'arrowstyle': '->', 'color': orange}, color=orange, fontsize=10)
    fig.suptitle('G046-21：节点齐全且连续小变化，仍会稳定在较差的几何上', x=0.04, y=0.98, ha='left', fontsize=18, weight='bold')
    fig.text(0.04, 0.04, '实际前六人：W105、W134、W131、W111、W102、W123；使用固定多数投票／中位数／连接。\n在线规则：k≥5，最近四次输出完整同角点数、三次相邻环距均≤2°；本案例在k=6首次满足。参考只用于曲线评价和右侧解释。', fontsize=10, color='#48515c')
    fig.subplots_adjust(top=0.9, bottom=0.17)
    fig.savefig(out / 'online_geometry_stable_wrong_G046_21.png')
    plt.close(fig)
    _write_csv(n[n.k.isin([3, 4, 5, 6, 9, 19, 30])][['request_id', 'team_id', 'reference_id', 'group_id', 'image_id', 'image', 'replay', 'k', 'ordered_workers', 'member_object_ids', 'B8L2', 'D10', 'nodes', 'dir', 'S_bottom_deg', 'direction_loss', 'boundary_loss', 'height_loss']], out / 'online_G046_21_case_evidence.csv', index=False)
    if photo is not None:
        image_array = plt.imread(photo)
        pts_ref = np.asarray(pool['reference']['points_1024x512'])
        pts6 = np.asarray(st[6]['points'])
        pts30 = np.asarray(st[30]['points'])
        members = st[6]['ordered_workers'].split('|')
        byworker = {r['worker_id']: r for r in pool['records']}
        workercolors = plt.cm.tab10(np.linspace(0, 0.6, len(members)))
        fig = plt.figure(figsize=(15.5, 11))
        gs = fig.add_gridspec(2, 3, height_ratios=[1, 1], hspace=0.23, wspace=0.2)
        ax = fig.add_subplot(gs[0, :])
        ax.imshow(image_array, extent=(0, 1024, 512, 0))
        ax.set_xlim(0, 1024)
        ax.set_ylim(512, 0)
        for p, c, label in [(pts_ref, 'white', '固定参考'), (pts6, orange, 'k6停止'), (pts30, '#00dbff', 'k30全共同池')]:
            ax.scatter(p[:, 0], p[:, 1], s=22, color=c, edgecolor='#222', linewidth=0.5, label=label)
            for a, b in zip(p[::2], p[1::2]):
                ax.plot([a[0], b[0]], [a[1], b[1]], color=c, alpha=0.75, lw=0.8)
        from matplotlib.patches import Rectangle
        for x0, x1, y0, y1, label in [(105, 160, 175, 380, '定位局部1'), (275, 325, 175, 380, '定位局部2')]:
            ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, edgecolor='#ffe066', linewidth=1.4))
            ax.text(x0, y0 - 8, label, color='#ffe066', fontsize=10)
        ax.legend(loc='upper right', ncol=3, fontsize=9)
        ax.axis('off')
        ax.set_title('Release原图按原比例显示；冻结1024×512坐标；下方局部横向放大以分辨点位，坐标值不变', loc='left', fontsize=11)
        for column, (x0, x1, title) in enumerate([(105, 160, '局部1：底点位置偏移'), (275, 325, '局部2：窄转折附近位置')]):
            ax = fig.add_subplot(gs[1, column])
            ax.imshow(image_array, extent=(0, 1024, 512, 0))
            ax.set_xlim(x0, x1)
            ax.set_ylim(380, 175)
            for w, c in zip(members, workercolors):
                p = np.asarray(byworker[w]['points'])
                for a, b in zip(p[::2], p[1::2]):
                    ax.plot([a[0], b[0]], [a[1], b[1]], color=c, lw=0.9, alpha=0.65)
                ax.scatter(p[1::2, 0], p[1::2, 1], s=32, facecolors='none', edgecolors=[c], linewidth=1.2, label=w)
            for p, c, marker, label in [(pts_ref, 'white', 's', '参考'), (pts6, orange, 'X', 'k6'), (pts30, '#00dbff', '+', 'k30')]:
                ax.scatter(p[:, 0], p[:, 1], s=65, color=c, edgecolor='#151515' if marker != '+' else c, linewidth=0.7, marker=marker, zorder=8, label=label)
            ax.set_aspect('auto')
            ax.set_xlabel('ERP x（1024坐标）')
            ax.set_ylabel('ERP y')
            ax.set_title(title, loc='left', fontsize=11)
            if column == 0:
                ax.legend(loc='lower left', fontsize=8, ncol=3, framealpha=0.9)
        ax = fig.add_subplot(gs[1, 2])
        ax.axis('off')
        bottom = np.column_stack([pts_ref[1::2, 1], pts6[1::2, 1], pts30[1::2, 1]])
        ax.text(0, 1, '前六人的原答与融合', va='top', fontsize=14, weight='bold')
        explanation = '实际成员：\n' + '、'.join(members[:3]) + '\n' + '、'.join(members[3:]) + f'\n\n圆圈：各人的原始底点；细竖线：\n原答顶点—底点对。不同原答可能\n有不同角点数，未强行配齐。\n\n局部1参考/k6/k30底点y：\n{bottom[2, 0]:.2f} / {bottom[2, 1]:.2f} / {bottom[2, 2]:.2f}\n局部2参考/k6/k30底点y：\n{bottom[3, 0]:.2f} / {bottom[3, 1]:.2f} / {bottom[3, 2]:.2f}\n\n两端不同方向的底点偏差使BEV\n长墙倾斜。k6六节点已齐全；\n继续收答主要校正位置与墙向。\n\nB8L2：70.07 → 96.02\nD10：76.26 → 96.33\n方向残差：4.93° → 0.95°'
        ax.text(0, 0.89, explanation, va='top', fontsize=10, linespacing=1.45)
        fig.suptitle('G046-21：原答位置分散与早期稳定几何的偏差', x=0.04, y=0.98, ha='left', fontsize=18, weight='bold')
        fig.text(0.04, 0.018, '本图不新增同房/局部对应裁定。G046已确认的转折关系、GT和固定评分均保持不变；局部圈定用于解释同一视角的位置差异。', fontsize=9, color='#48515c')
        fig.subplots_adjust(top=0.93, bottom=0.07)
        fig.savefig(out / 'online_G046_21_original_annotations.png')
        plt.close(fig)
        manifest = dict(case_id='G04621_stable_geometry_orientation', group_id=gid, image_id=n.image_id.iloc[0], image_code=image, replay=replay, reference_id=n.reference_id.iloc[0], release_tag='quality-original-images-20261015', original_local_file=str(photo), original_sha256=hashlib.sha256(photo.read_bytes()).hexdigest(), native_geometry_file='online_geometry_prefixes.json.gz', native_geometry_keys=[dict(group_id=gid, image_code=image, replay=replay, k=k) for k in [3, 4, 5, 6, 19, 30]], exact_members_at_k6=members, object_ids_at_k6=st[6]['member_object_ids'].split('|'), feature_keys=[dict(feature_id='G04621_bottom_position_ref_index2', coordinate_frame='ERP1024x512', bbox=[105, 175, 160, 380], reference_corner_index=2), dict(feature_id='G04621_bottom_position_ref_index3', coordinate_frame='ERP1024x512', bbox=[275, 175, 325, 380], reference_corner_index=3)], evidence_identity='new native geometry reconstruction and original-image viewing; archived fixed B8L2/D10; no GT re-adjudication')
        (out / 'online_G046_21_visual_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--output', type=Path, default=Path(__file__).resolve().parent)
    p.add_argument('--font', type=Path, required=True)
    p.add_argument('--photo', type=Path)
    a = p.parse_args()
    main(a.repo, a.output, a.font, a.photo)
