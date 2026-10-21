"""Inspect the observed largest timed-policy loss; no policy tuning.

Replays two already evaluated exact teams solely to retain full identity groups.
The score ablation is diagnostic under the frozen score, not a replacement score.
"""
import sys as _delivery_sys
from pathlib import Path as _DeliveryPath
_delivery_root = next((p for p in _DeliveryPath(__file__).resolve().parents if (p / 'direct_io.py').is_file()))
_delivery_sys.path.insert(0, str(_delivery_root))
from direct_io import read_csv as _read_csv, open_data as _open_data, write_csv as _write_csv, write_bytes as _write_bytes, data_exists as _data_exists
from pathlib import Path
import importlib.util, json, gzip
import numpy as np
import pandas as pd
from PIL import Image
import render_cases as v
OUT = v.OUT

def load_module(name, path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m
s = load_module('native_same_room_study', OUT / 'native_teams/study.py')

def main():
    d = _read_csv(OUT / 'native_teams/SELECTION_RESULTS.csv.gz')
    d = d[(d.target_image == 'uNb9QFRL6hY-43') & (d.source_image == 'uNb9QFRL6hY-40') & (d.domain == 'new_timed_history') & (d.n == 5)]
    selected = d[d.policy.isin(['outside_Q', 'outside_Q_outside_T_fast'])].copy()
    assert len(selected) == 2
    pools = {p['pool_id']: p for p in s.read(s.taxstudy.FUSION / 'INPUT_SNAPSHOT.json.gz')['images']}
    teams = s.read(OUT / 'native_teams/TEAMS.json.gz')
    p = pools[selected.iloc[0].pool_id]
    fe, fr, *_ = s.taxstudy.setup_engine()
    evidence = []
    corners = []
    with fe.cached_matching(), fe.scoring_engine(fe.ENGINE / 'measurement_engine.zip', fe.ENGINE / 'working_models.py') as (engine, models):
        for r in selected.itertuples():
            ws = json.loads(r.workers)
            t = fr.evaluate_one(p, ws, engine, models, {}, full_state=True)
            state = t.pop('full_state')
            assert abs(t['B8L2'] - teams[r.team_key]['B8L2']) < 1e-09
            ab = models.attribution(t['iou_2d'], t['S_bottom_deg'], t['dir'], t['Hmean'], t['Hcenter'], models.B)
            xy = np.asarray(t['geometry']['footprint'])
            edges = np.roll(xy, -1, axis=0) - xy
            for i, (a, b) in enumerate(zip(edges, np.roll(edges, -1, axis=0))):
                angle = np.degrees(np.arccos(np.clip(np.dot(a, b) / np.linalg.norm(a) / np.linalg.norm(b), -1, 1)))
                corners.append(dict(policy=r.policy, edge=i, length_h=np.linalg.norm(a), next_turn_deg=angle, deviation_from_90_deg=abs(angle - 90)))
            evidence.append(dict(case_id='G172_time_bad_tail', meta=p['meta'], source_image=r.source_image, policy=r.policy, team=t, state=state, activity_seconds=r.target_activity_seconds, reference=p['reference'], records=[x for x in p['records'] if x['worker_id'] in ws], score_ablation=ab, selection='observed largest negative n5 timed-policy contrast, explanatory selection after results'))
    s.save(OUT / 'case_evidence/G172_time_bad_tail.json.gz', evidence)
    _write_csv(pd.DataFrame(corners), OUT / 'case_evidence/G172_edge_angles.csv', index=False)
    s.save(OUT / 'case_evidence/G172_REPLAY_RECEIPT.json', dict(additional_native_evaluations=2, additional_unique_teams=0, purpose='full identity-group state for two previously scored teams', unchanged_scores=True))
    render(evidence)
    print(json.dumps([dict(policy=e['policy'], Q=e['team']['B8L2'], D10=e['team']['D10'], nodes=e['team']['nodes'], dir=e['team']['dir'], ablation=e['score_ablation']) for e in evidence], ensure_ascii=False, indent=2))

def render(evidence):
    fig = v.plt.figure(figsize=(15, 10))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.3, 1], hspace=0.3, wspace=0.13)
    photo = np.asarray(Image.open(OUT / 'photos_cost' / (evidence[0]['meta']['image_id'] + '.png')))
    geos = [v.v.viewer_geometry(e['team']['geometry']['points']) for e in evidence] + [v.v.viewer_geometry(evidence[0]['reference']['points_1024x512'])]
    bounds = v.v._bounds(geos)
    for j, e in enumerate(evidence):
        col = ['#00b8cf', '#df518c'][j]
        t = e['team']
        ax = fig.add_subplot(gs[0, j])
        v.v._erp_background(ax, photo)
        for r in e['records']:
            v.v._erp_edges(ax, r['points'], '#ffffff', linewidth=0.7, alpha=0.4)
        v.v._erp_edges(ax, e['reference']['points_1024x512'], v.v.REF_ERP_COLOR, reference=True, linewidth=1.2)
        v.v._erp_edges(ax, t['geometry']['points'], col, linewidth=2, markers=True)
        ax.set_title(('楼外Q选队' if j == 0 else '楼外Q允许2分预算，再优先快人') + f"\nQ={t['B8L2']:.2f}；劳动{e['activity_seconds']:.1f}秒；" + ', '.join(t['member_workers']), loc='left', fontsize=10)
        bx = fig.add_subplot(gs[1, j])
        v.v._bev_ring(bx, geos[j]['floor'], col, linewidth=2)
        v.v._bev_ring(bx, geos[-1]['floor'], '#222222', reference=True)
        v.v._style_bev(bx, bounds)
        bx.set_title(f"均为{t['nodes']}角；内在墙向偏差 {t['dir']:.3f}°；票数 {t['node_supports']}", fontsize=11)
        xy = np.asarray(geos[j]['floor'])
        for i, (x, y) in enumerate(xy):
            bx.annotate(str(i), (x, y), textcoords='offset points', xytext=(4, 4), fontsize=10, color=col)
    fig.suptitle('G172 · uNb-43：省时41.7%，但两处近邻转折的定位使质量下降28.77分', fontsize=16, y=0.98)
    fig.text(0.5, 0.04, '源视角uNb-40仅用于可用人员筛选；该规则按楼外Q/T选人，未用目标Q或时间。原图可见突出窗墙及室内遮挡。', ha='center', fontsize=10)
    fig.text(0.5, 0.018, '白线为成员原答；彩线融合；黄线/黑虚线固定参考。缺角没有增加，主要损失在内在墙向；不能把平均省时解释为逐图保质。', ha='center', fontsize=10)
    fig.subplots_adjust(top=0.91, bottom=0.11)
    fig.savefig(OUT / 'figures/G172_time_bad_tail.png', dpi=145)
    v.plt.close(fig)
if __name__ == '__main__':
    main()
