"""Scientific overlays of frozen observed points and Release photographs.

View panels retain their own camera frames; no physical camera registration is
invented. Case selection is explanatory after observing results.
"""
import sys as _delivery_sys
from pathlib import Path as _DeliveryPath
_delivery_root = next((p for p in _DeliveryPath(__file__).resolve().parents if (p / 'direct_io.py').is_file()))
_delivery_sys.path.insert(0, str(_delivery_root))
from direct_io import read_csv as _read_csv, open_data as _open_data, write_csv as _write_csv, write_bytes as _write_bytes, data_exists as _data_exists
from pathlib import Path
import os, sys, json, gzip, importlib.util
os.environ.setdefault('MPLCONFIGDIR', '/tmp/hohonet_same_room_plots')
import numpy as np
import pandas as pd
from PIL import Image
ROOT = Path(os.environ.get('HOHONET_REPO', Path(__file__).resolve().parents[2] / 'hohonet'))
OUT = Path(__file__).resolve().parent
sys.path[:0] = ['/tmp/hohonet_deps', str(ROOT)]
spec = importlib.util.spec_from_file_location('case_visuals_frozen', ROOT / 'research/workers/personnel_interchangeability_20261020/analysis/composition/case_visuals.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
font = Path(os.environ.get('HOHONET_FONT', OUT / 'NotoSansCJKsc-Regular.otf'))
if not _data_exists(font):
    parts = sorted((ROOT / 'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/presentation/fonts').glob('NotoSansCJKsc-Regular.otf.gz.part*'))
    if not parts:
        raise FileNotFoundError('Set HOHONET_FONT to a CJK font, or restore the two fixed repository font parts')
    font.parent.mkdir(parents=True, exist_ok=True)
    _write_bytes(font, gzip.decompress(b''.join((p.read_bytes() for p in parts))))
v._configure_font(font)
plt = v.plt
FIG = OUT / 'figures'
FIG.mkdir(exist_ok=True)
EVID = OUT / 'case_evidence'
EVID.mkdir(exist_ok=True)
COLORS = ['#00c9e8', '#ff5da2', '#85e572', '#ab7aff']

def read(p):
    p = Path(p)
    with _open_data(p, 'rt') if p.suffix == '.gz' else p.open() as f:
        return json.load(f)

def save(p, x):
    b = json.dumps(x, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    _write_bytes(Path(p), gzip.compress(b, mtime=0) if str(p).endswith('.gz') else b)

def person_cases():
    obs = read(ROOT / 'research/statistics/v2_evidence_audit_20261019/records.json.gz')['records']
    labels = _read_csv(ROOT / 'research/workers/personnel_taxonomy_20261021/labels/lobo_labels.csv').set_index(['condition', 'heldout_building', 'worker_id'])
    cases = [('G130_identity_changes', ['pa4otMbVnkk-42', 'pa4otMbVnkk-44'], ['W103', 'W132', 'W102'], '同房均值接近，两个同类人的质量却反向变化', '两图均为4角参考；相机坐标分别绘制。黄色为固定参考，三种颜色为同一批具体人员。'), ('G202_pool_masks_view', ['wc2JMjhGNzB-26', 'wc2JMjhGNzB-53'], ['W123', 'W122', 'W028'], '固定同一人后，视角困难与几何偏差显现', '-26沿用整空间确定性参考；-53沿用原GT。均为8角；不把8角齐全直接解释为高质量。'), ('G236_structure_opportunity', ['yqstnuAEVhm-01', 'yqstnuAEVhm-06'], ['W122', 'W115', 'W127'], '结构表达随视角机会而变；相同标签保留类内差异', '两个视角各自参考表达8角与4角；不宣称物理墙角消失，不凭本轮重新判定同房。')]
    manifests = []
    for cid, codes, workers, title, note in cases:
        fig = plt.figure(figsize=(17, 9.4))
        gs = fig.add_gridspec(2, 3, width_ratios=[2.25, 1, 1], hspace=0.3, wspace=0.14)
        evidence = []
        for row, code in enumerate(codes):
            rs = [r for r in obs if r['image_code'] == code and r['condition'] == 'manual' and (r['quality_use'] == 'ordinary_primary') and r['quality_usable'] and (r['worker_id'] in workers)]
            rs = sorted(rs, key=lambda r: workers.index(r['worker_id']))
            if len(rs) != len(workers):
                raise ValueError((code, len(rs)))
            first = rs[0]
            ref = first['reference_evidence']
            photo = np.asarray(Image.open(OUT / 'photos' / (first['image_id'] + '.png')).convert('RGB'))
            ax = fig.add_subplot(gs[row, 0])
            v._erp_background(ax, photo)
            for r in rs:
                v._erp_edges(ax, r['points_1024x512'], COLORS[workers.index(r['worker_id'])], linewidth=1.25, markers=True)
            v._erp_edges(ax, ref['points_1024x512'], v.REF_ERP_COLOR, reference=True, linewidth=1.15)
            labels_text = []
            geos = [v.viewer_geometry(r['points_1024x512']) for r in rs]
            refg = v.viewer_geometry(ref['points_1024x512'])
            bounds = v._bounds(geos + [refg])
            heights = v._heights(geos + [refg])
            for r in rs:
                lb = labels.loc['manual', r['building_id'], r['worker_id']]
                labels_text.append(f"{r['worker_id']} {lb.primary_fine_class}: Q {r['B8L2']:.1f}, {r['point_count'] // 2}角")
                evidence.append({k: r.get(k) for k in ['object_id', 'worker_id', 'image_id', 'image_code', 'building_id', 'condition', 'origin', 'B8L2', 'D10', 'reference_id', 'reference_version', 'quality_use', 'quality_usable', 'points_1024x512', 'raw_original_available', 'source_evidence', 'coordinate_evidence', 'measurements', 'scope_evidence']})
                evidence[-1].update(primary_coarse_class=lb.primary_coarse_class, primary_fine_class=lb.primary_fine_class, label_version=lb.label_version, label_heldout_building=r['building_id'], reference_points=ref['points_1024x512'])
            ax.set_title(code + '\n' + '   |   '.join(labels_text), fontsize=10.2, loc='left')
            bx = fig.add_subplot(gs[row, 1])
            tx = fig.add_subplot(gs[row, 2], projection='3d')
            for r, g in zip(rs, geos):
                color = COLORS[workers.index(r['worker_id'])]
                v._bev_ring(bx, g['floor'], color, linewidth=1.5)
                v._wire3d(tx, g, color)
            v._bev_ring(bx, refg['floor'], '#202b3b', reference=True)
            v._style_bev(bx, bounds)
            bx.set_title('BEV：点数与位置分别看', fontsize=10)
            v._wire3d(tx, refg, '#202b3b', reference=True)
            v._style3d(tx, bounds, heights, {'elev': 26, 'azim': -53})
            tx.set_title('3D推导：高度与墙向', fontsize=10)
        fig.suptitle(cid.split('_')[0] + ' · ' + title, fontsize=17, y=0.98)
        handles = [v.Line2D([0], [0], color=COLORS[i], lw=2, label=w) for i, w in enumerate(workers)] + [v.Line2D([0], [0], color='#505050', ls='--', label='固定参考（照片上为黄线）')]
        fig.legend(handles=handles, loc='lower center', bbox_to_anchor=(0.5, 0.048), ncol=4, frameon=False, fontsize=11)
        fig.text(0.5, 0.025, note, ha='center', fontsize=10, color='#495769')
        fig.text(0.5, 0.006, 'Release原图；保存的处理后作答，保持点序与环序。BEV/3D单位为相机高度 h，不是米；不同视角没有空间配准。', ha='center', fontsize=9, color='#495769')
        fig.subplots_adjust(top=0.89, bottom=0.12)
        path = FIG / (cid + '.png')
        fig.savefig(path, dpi=145)
        plt.close(fig)
        save(EVID / (cid + '.json.gz'), evidence)
        manifests.append(dict(case_id=cid, figure=str(path.relative_to(OUT)), evidence='case_evidence/' + cid + '.json.gz', selection='结果后解释性选择；非新验证集', objects=[r['object_id'] for r in evidence]))
    save(EVID / 'PERSON_CASE_MANIFEST.json', manifests)
    print('Person case figures', len(manifests), flush=True)

def fusion_cases():
    native = OUT / 'native_teams'
    teams = read(native / 'TEAMS.json.gz')
    states = read(native / 'CASE_STATES.json.gz')
    defs = read(native / 'CASE_DEFINITIONS.json')
    pools = {p['pool_id']: p for p in read(ROOT / 'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz')['images']}
    rows = []
    figdefs = []
    for cid in ['G117_repeat', 'G015_reversal']:
        ds = [d for d in defs if d['case_id'] == cid]
        codes = list(dict.fromkeys((d['image'] for d in ds)))
        fig = plt.figure(figsize=(15, 12.2))
        gs = fig.add_gridspec(4, 2, height_ratios=[1.55, 1.25, 1.55, 1.25], hspace=0.43, wspace=0.13)
        ev = []
        for ri, code in enumerate(codes):
            selections = [d for d in ds if d['image'] == code]
            p = pools[selections[0]['pool_id']]
            ref = p['reference']
            photo = np.asarray(Image.open(OUT / 'photos' / (p['meta']['image_id'] + '.png')))
            bounds = v._bounds([v.viewer_geometry(teams[d['team_key']]['geometry']['points']) for d in selections] + [v.viewer_geometry(ref['points_1024x512'])])
            for ci, d in enumerate(selections):
                team = teams[d['team_key']]
                state = states[d['team_key']]
                color = ['#00b8cf', '#df518c'][ci]
                ax = fig.add_subplot(gs[2 * ri, ci])
                v._erp_background(ax, photo)
                for r in p['records']:
                    if r['worker_id'] in d['workers']:
                        v._erp_edges(ax, r['points'], '#ffffff', linewidth=0.65, alpha=0.32)
                v._erp_edges(ax, team['geometry']['points'], color, linewidth=2, markers=True)
                v._erp_edges(ax, ref['points_1024x512'], v.REF_ERP_COLOR, linewidth=1.15, reference=True)
                ax.set_title(f"{code} · {d['arm']} · Q={team['B8L2']:.2f} / D10={team['D10']:.2f}\n" + ', '.join(d['workers']), fontsize=9.5, loc='left')
                bx = fig.add_subplot(gs[2 * ri + 1, ci])
                v._bev_ring(bx, team['geometry']['footprint'], color, linewidth=2)
                v._bev_ring(bx, ref['floor_xz_h'], '#222222', reference=True)
                v._style_bev(bx, bounds)
                bx.set_title(f"{team['nodes']}角；门槛{state['minimum_support']}票；节点票数 {team['node_supports']}", fontsize=10)
                ev.append(dict(case_id=cid, image=code, arm=d['arm'], meta=p['meta'], team=team, state=state, reference=ref, records=[r for r in p['records'] if r['worker_id'] in d['workers']]))
                for j, g in enumerate(state['identity_groups']):
                    rows.append(dict(case_id=cid, image=code, arm=d['arm'], team_key=d['team_key'], group_index=j, group_id=g.get('feature_id'), support=g['support'], threshold=state['minimum_support'], selected=g['selected'], members=json.dumps(g.get('members'), ensure_ascii=False)))
        title = '完全相同的两人替换，两视角都补回局部结构' if cid == 'G117_repeat' else '同一人的加入：一图改定位，一图补结构；固定GT下出现反向收益'
        fig.suptitle(cid.split('_')[0] + ' · ' + title, fontsize=16, y=0.985)
        fig.text(0.5, 0.026, '淡白为参与者原答；蓝/红为融合；黄线/黑虚线为固定参考。每个视角按其原相机坐标显示。', ha='center', fontsize=10)
        fig.text(0.5, 0.009, 'G015采用既有人工解释：-11壁炉细节被当前GT简化；此处未更改GT、投票或评分。' if cid == 'G015_reversal' else 'B→C的核心完全相同；成员信息先形成身份组，再按全池MV50门槛选点，中位数定位。', ha='center', fontsize=10)
        fig.subplots_adjust(top=0.925, bottom=0.06)
        path = FIG / (cid + '.png')
        fig.savefig(path, dpi=145)
        plt.close(fig)
        save(EVID / (cid + '.json.gz'), ev)
        figdefs.append(dict(case_id=cid, figure=str(path.relative_to(OUT)), evidence='case_evidence/' + cid + '.json.gz'))
    _write_csv(pd.DataFrame(rows), EVID / 'FUSION_VOTE_LEDGER.csv', index=False)
    save(EVID / 'FUSION_CASE_MANIFEST.json', figdefs)
    print('Fusion case figures', len(figdefs), flush=True)

def local_and_position():
    ev = read(EVID / 'G117_repeat.json.gz')
    lookup = {(x['image'], x['arm']): x for x in ev}
    windows = [('jtcxE69GiFV-26', '近处墙体转折', [650, 716, 360, 430], ['node_002'], ['node_001']), ('jtcxE69GiFV-26', '另一端转折', [890, 958, 285, 352], ['node_005'], ['node_004']), ('jtcxE69GiFV-28', '两处局部转折', [40, 115, 300, 367], ['node_004', 'node_005'], ['node_004', 'node_005'])]
    fig, axes = plt.subplots(3, 2, figsize=(13, 12))
    rows = []
    for i, (code, title, zoom, bids, cids) in enumerate(windows):
        for j, arm in enumerate(['B', 'C']):
            e = lookup[code, arm]
            ax = axes[i, j]
            photo = np.asarray(Image.open(OUT / 'photos' / (e['meta']['image_id'] + '.png')))
            v._erp_background(ax, photo, zoom)
            color = ['#00b8cf', '#df518c'][j]
            for r in e['records']:
                v._erp_edges(ax, r['points'], '#ffffff', linewidth=0.8, alpha=0.5)
            v._erp_edges(ax, e['reference']['points_1024x512'], v.REF_ERP_COLOR, reference=True, linewidth=1.5)
            v._erp_edges(ax, e['team']['geometry']['points'], color, linewidth=2.2, markers=True)
            ids = bids if arm == 'B' else cids
            texts = []
            for g in e['state']['identity_groups']:
                if g['feature_id'] not in ids:
                    continue
                x, y = g['center'][1]
                ax.scatter([x], [y], s=90, facecolors=color if g['selected'] else 'none', edgecolors=color, linewidths=2, zorder=8)
                ax.annotate(f"{g['support']}/6票", (x, y), xytext=(5, 14 if g['support'] < 3 else -20), textcoords='offset points', color='white', fontsize=12, bbox=dict(facecolor='#142635', alpha=0.8, pad=2, edgecolor='none'), zorder=9)
                members = [m['worker'] for m in g['members']]
                texts.append('+'.join(members))
                rows.append(dict(case_id='G117_repeat', image=code, local_feature_key=code + ':' + title, arm=arm, team_key=e['team']['team_key'], feature_id=g['feature_id'], center=g['center'], members=members, support=g['support'], minimum_support=3, selected=g['selected']))
            ax.set_title(f'{code} · {title} · {arm}组\n' + '；'.join(texts), fontsize=9.5, loc='left')
    fig.suptitle('G117局部票账：表达来自具体成员，达票取决于固定核心与新增两人', fontsize=16, y=0.99)
    fig.text(0.5, 0.015, '两列都是6人、门槛3票。白线是实际原答；黄线固定参考；彩线融合。空心圆是未达票身份组，实心圆已达票。局部键逐图定义，未新增跨视角物理角点对应。', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(FIG / 'G117_local_votes.png', dpi=145)
    plt.close(fig)
    save(EVID / 'G117_local_votes.json', rows)
    defs = read(OUT / 'native_teams/CASE_DEFINITIONS.json')
    teams = read(OUT / 'native_teams/TEAMS.json.gz')
    states = read(OUT / 'native_teams/CASE_STATES.json.gz')
    pools = {p['pool_id']: p for p in read(ROOT / 'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz')['images']}
    ds = [d for d in defs if d['case_id'] == 'G205_position']
    fig = plt.figure(figsize=(14, 12))
    gs = fig.add_gridspec(3, 2, width_ratios=[2, 1], hspace=0.22, wspace=0.17)
    evidence = []
    for i, d in enumerate(ds):
        p = pools[d['pool_id']]
        t = teams[d['team_key']]
        s = states[d['team_key']]
        photo = np.asarray(Image.open(OUT / 'photos_extra' / (p['meta']['image_id'] + '.png')))
        ax = fig.add_subplot(gs[i, 0])
        v._erp_background(ax, photo)
        for r in p['records']:
            if r['worker_id'] in d['workers']:
                v._erp_edges(ax, r['points'], '#ffffff', linewidth=0.6, alpha=0.35)
        v._erp_edges(ax, p['reference']['points_1024x512'], v.REF_ERP_COLOR, reference=True, linewidth=1.4)
        v._erp_edges(ax, t['geometry']['points'], '#00c9e8', linewidth=2, markers=True)
        ax.set_title(f"{d['image']} · Q={t['B8L2']:.2f} · {t['nodes']}角 · 支持票数 {t['node_supports']}", loc='left', fontsize=11)
        bx = fig.add_subplot(gs[i, 1])
        a = v.viewer_geometry(t['geometry']['points'])
        r = v.viewer_geometry(p['reference']['points_1024x512'])
        v._bev_ring(bx, a['floor'], '#00b8cf', linewidth=2)
        v._bev_ring(bx, r['floor'], '#222222', reference=True)
        v._style_bev(bx, v._bounds([a, r]))
        bx.set_title('BEV仍有位置差；全票不校准位置', fontsize=10)
        evidence.append(dict(case_id=d['case_id'], meta=p['meta'], team=t, state=s, reference=p['reference'], records=[r for r in p['records'] if r['worker_id'] in d['workers']]))
    fig.suptitle('G205 · 同一7人、全票结构，仍出现约18分的视角质量差', fontsize=16, y=0.99)
    fig.text(0.5, 0.022, '成员：W012、W017、W031、W032、W130、W133、W134。原图与原答都保留；固定参考中的近共线分段不自动解释为必要角点遗漏。', ha='center', fontsize=9)
    fig.subplots_adjust(top=0.95, bottom=0.055)
    fig.savefig(FIG / 'G205_position.png', dpi=145)
    plt.close(fig)
    save(EVID / 'G205_position.json.gz', evidence)
    print('Local and position figures saved', flush=True)
if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('stage', choices=['person', 'fusion', 'local'])
    a = p.parse_args()
    {'person': person_cases, 'fusion': fusion_cases, 'local': local_and_position}[a.stage]()
