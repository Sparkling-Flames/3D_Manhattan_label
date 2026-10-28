"""从已保存的同一ABC检查Q与几何变化；不运行融合、评分或重新分类。"""
import gzip
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[3]
RELEASE = ROOT / 'research/data/releases/v2.1'
OUT = RELEASE / 'rfuse_exception_diagnosis_20261029'


def main():
    OUT.mkdir(exist_ok=True)
    summary = pd.read_csv(RELEASE / 'current_exchange_results/confirm/combined/summary/POOL_DIRECTION_SUMMARY.csv.gz')
    chosen = summary[(summary.method == 'DSTRUCT_K3') & (summary.n == 18) & (summary.m == 7)
                     & (summary.phase == 'selection_heldout_building')
                     & summary.source_largest_class.eq(True) & summary.target_highest_turn.eq(True)]
    assert len(chosen) == 33 and chosen.image.is_unique
    columns = ['image', 'pool_id', 'difficulty', 'B8L2_within', 'B8L2_cross', 'B8L2_gap', 'D10_gap',
               'geometry_bev_distance_gap', 'geometry_pair_angle_gap', 'geometry_unmatched_pairs_gap',
               'floor_turn5_n_gap', 'floor_turn5_n_within', 'floor_turn5_n_cross',
               'geometry_unmatched_pairs_within', 'geometry_unmatched_pairs_cross',
               'B8L2_CA', 'B8L2_CB', 'dir_within', 'dir_cross']
    chosen[columns].to_csv(OUT / 'SAME_CONDITION_33_IMAGE_METRICS.csv', index=False, encoding='utf-8-sig')
    s = chosen[chosen.image.eq('jh4fc5c5qoQ-04')].iloc[0]
    events = pd.read_csv(RELEASE / 'current_exchange_results/confirm/EVENT_METRICS.csv.gz', low_memory=False)
    keys = ['pool_id', 'method', 'n', 'm', 'phase', 'source_class', 'target_class']
    all_selected = events.merge(chosen[keys], on=keys, validate='many_to_one')
    valid = all_selected.dropna(subset=['A_B8L2', 'B_B8L2', 'C_B8L2']).copy()
    assert len(all_selected) == 286 and len(valid) == 273
    lower = valid[['A_B8L2', 'B_B8L2']].min(axis=1)
    upper = valid[['A_B8L2', 'B_B8L2']].max(axis=1)
    outside = np.maximum(np.maximum(lower-valid.C_B8L2, valid.C_B8L2-upper), 0)
    assert np.allclose(valid.B8L2_gap, outside-(upper-lower)/2)
    valid['C_inside_AB_interval'] = (valid.C_B8L2 >= lower) & (valid.C_B8L2 <= upper)
    positions = valid.groupby('image').agg(valid_events=('event_id', 'size'),
        C_inside_AB_events=('C_inside_AB_interval', 'sum'),
        negative_event_gap=('B8L2_gap', lambda s: int(s.lt(0).sum())))
    positions = positions.join(chosen.set_index('image')[['B8L2_gap']])
    positions.to_csv(OUT / 'Q_INTERVAL_POSITION_BY_IMAGE.csv', encoding='utf-8-sig')
    teams = pd.concat([
        valid[['image', arm+'_team_key', arm+'_B8L2', arm+'_iou_2d']].set_axis(
            ['image', 'team_key', 'Q', 'iou'], axis=1) for arm in 'ABC'
    ], ignore_index=True)
    assert teams.groupby(['image', 'team_key']).Q.nunique().max() == 1
    teams = teams.drop_duplicates(['image', 'team_key'])
    score_spread = teams.groupby('image').agg(
        valid_unique_teams=('team_key', 'size'), Q_mean=('Q', 'mean'),
        Q_min=('Q', 'min'), Q_max=('Q', 'max'), Q_sd=('Q', 'std'), iou_mean=('iou', 'mean'))
    score_spread = score_spread.join(chosen.set_index('image')[
        ['difficulty', 'B8L2_within', 'B8L2_cross', 'B8L2_gap',
         'geometry_bev_distance_within', 'geometry_bev_distance_cross']])
    assert len(score_spread) == 33
    assert (score_spread.Q_min <= score_spread.Q_mean).all()
    assert (score_spread.Q_mean <= score_spread.Q_max).all()
    score_spread.to_csv(OUT / 'TEAM_SCORE_LEVEL_AND_SPREAD.csv', encoding='utf-8-sig')
    selected = events[(events.pool_id == s.pool_id) & (events.method == s.method)
                      & (events.n == 18) & (events.m == 7) & (events.phase == s.phase)
                      & (events.source_class == s.source_class) & (events.target_class == s.target_class)]
    # 与已交付查看器一致，取原登记顺序第一条；不按最大的分差选例。
    event = selected.iloc[0]
    assert event.event_id == '84320bad6f9ea2b352a805f2'
    wanted = {event[a + '_team_key'] for a in 'ABC'}
    found = {}
    paths = list((RELEASE / 'current_exchange_endpoints' / s.pool_id).glob('*.jsonl.gz'))
    paths.append(RELEASE / 'current_exchange_endpoints/REUSED_ENDPOINTS.jsonl.gz')
    for path in paths:
        with gzip.open(path, 'rt', encoding='utf8') as f:
            for line in f:
                record = json.loads(line)
                if record.get('team_key') in wanted:
                    found[record['team_key']] = record
        if len(found) == 3:
            break
    assert len(found) == 3
    pools = json.loads((RELEASE / 'pools/INPUT_SNAPSHOT.json').read_text(encoding='utf8'))['images']
    pool = next(p for p in pools if p['pool_id'] == s.pool_id)
    reference = np.asarray(pool['reference']['floor_xz_h'])
    reference_polygon = Polygon(reference)
    assert reference_polygon.is_valid
    fields = ['B8L2', 'D10', 'iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter', 'nodes',
              'floor_turn5_n', 'boundary_loss', 'direction_loss', 'height_loss']
    rows = []
    plt.rcParams.update({'font.family': 'Microsoft YaHei', 'axes.unicode_minus': False})
    fig, axes = plt.subplots(1, 3, figsize=(13, 5.5), sharex=True, sharey=True)
    colors = ['#3973ac', '#bf6924', '#198078']
    for ax, arm, color in zip(axes, 'ABC', colors):
        record = found[event[arm + '_team_key']]
        assert sorted(record['member_workers']) == sorted(event[arm + '_members'].split('|'))
        floor = np.asarray(record['geometry']['footprint'])
        polygon = Polygon(floor)
        assert polygon.is_valid
        iou = polygon.intersection(reference_polygon).area / polygon.union(reference_polygon).area
        assert np.isclose(iou, event[arm + '_iou_2d'], atol=1e-10)
        row = dict(arm=arm, event_id=event.event_id, team_key=record['team_key'],
                   **{name: event[arm + '_' + name] for name in fields},
                   minimum_support=record['minimum_support'],
                   selected_support_min=min(record['node_supports']))
        rows.append(row)
        ref = np.vstack([reference, reference[0]])
        ff = np.vstack([floor, floor[0]])
        ax.plot(ref[:, 0], ref[:, 1], '--', color='#555555', lw=1.5, label='当前参考')
        ax.plot(ff[:, 0], ff[:, 1], '-o', color=color, ms=4, lw=2, label=f'{arm}队完整融合底面')
        ax.scatter([0], [0], marker='+', c='black', s=45, label='拍摄点位')
        ax.set_aspect('equal'); ax.grid(alpha=.18)
        ax.set_title(f'{arm}队  Q={row["B8L2"]:.2f}  IoU={iou:.3f}\n方向误差={row["dir"]:.2f}°；有效转折={int(row["floor_turn5_n"])}', fontsize=11)
        ax.set_xlabel('X / 相机高度'); ax.legend(fontsize=8, loc='lower left')
    axes[0].set_ylabel('Z / 相机高度')
    fig.suptitle('jh4-04：同一18人换7人事件中，Q排序与底面接近程度不同', fontsize=14)
    fig.text(.04, .04, 'A、B：同类成员替换；C：跨类替换。三队共用11人背景。虚线参考与实线均来自保存坐标。\nB的方向误差较小；C的底面IoU、底点偏差和高度分项更好。此图解释一条事件，图级结果另按全部事件汇总。', fontsize=10)
    fig.tight_layout(rect=(0, .12, 1, .93))
    fig.savefig(OUT / 'JH4_04_SAME_EVENT_GEOMETRY.png', dpi=220)
    fig.savefig(OUT / 'JH4_04_SAME_EVENT_GEOMETRY.svg')
    plt.close(fig)
    pd.DataFrame(rows).to_csv(OUT / 'JH4_04_FIRST_EVENT_COMPONENTS.csv', index=False, encoding='utf-8-sig')
    a, b, c = [float(event[x + '_B8L2']) for x in 'ABC']
    within = abs(b-a); cross = (abs(c-a)+abs(c-b))/2
    assert min(a,b) < c < max(a,b) and np.isclose(cross, within/2)
    assert np.isclose(within, event.B8L2_within) and np.isclose(cross, event.B8L2_cross)
    result = dict(event_id=event.event_id, image=s.image, Q_within=within, Q_cross=cross,
                  Q_gap=cross-within, bev_within=event.geometry_bev_distance_within,
                  bev_cross=event.geometry_bev_distance_cross, bev_gap=event.geometry_bev_distance_gap,
                  original_33_images=len(chosen), negative_Q_images=int(chosen.B8L2_gap.lt(0).sum()),
                  new_fusion=0, new_scoring=0, new_classification=0)
    (OUT / 'ROOT_DIAGNOSTIC_CHECKS.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
