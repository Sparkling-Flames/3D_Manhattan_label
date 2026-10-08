"""固定137图扩展：当前输入、共同身份与定位三路线，不读取GT。"""
import json
from collections import Counter
import numpy as np

from .research_artifact_io import ROOT, write_json, write_csv, read_csv
from .ring_correspondence_20261007 import build, CODES, GAP
from .fixed_identity_location_20261007 import compare_locations
from .research_round_20260929 import reconstruct

OUT = ROOT / 'analysis_results/ring_correspondence_20261007/expanded'


def partition(result):
    return {frozenset((m['id'], m['pair_index']) for m in g['members'])
            for g in result['identity_groups']}


def location_layout(result, locations, route):
    byid = {g['feature_id']: g for g in locations}
    order = result['ring_diagnostics']['feature_ids']
    unresolved = [g['feature_id'] for g in locations if g['estimates'][route]['center'] is None]
    points = None
    if order and not unresolved:
        points = [p for fid in order for p in byid[fid]['estimates'][route]['center']]
    geo = reconstruct(dict(points=points), coordinate_convention='continuous') if points else None
    return dict(route=route, feature_ids=order, unresolved_nodes=unresolved, points=points,
                geometry_status=geo['status'] if geo else 'not_evaluable',
                reason=geo['reason'] if geo else ('unresolved_location' if unresolved else 'no_complete_source_ring'))


def run():
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle
    OUT.mkdir(parents=True, exist_ok=True)
    old = ROOT / 'analysis_results/adaptive_point_20261007/expanded'
    codes = json.loads((old / 'PLAN.json').read_text(encoding='utf-8'))['images']
    conditions = {r['image']: r for r in read_csv(old / 'image_conditions.csv')}
    baseline = {s['image']: s['result']['candidate'] for s in
                json.loads((old / 'candidates.json').read_text(encoding='utf-8'))['states'] if s['route'] == 'paired'}
    old_inputs = {im['image']: im['records'] for im in json.loads((old / 'inputs.json').read_text(encoding='utf-8'))['images']}
    bundle = load_current_bundle(); data, aliases = project_bundle(bundle)
    images = {im['code']: im for im in data['images']}
    objects = {aliases['records'][o['object_id']]: o for o in bundle['data']['objects']}
    write_json(OUT / 'PLAN.json', dict(images=codes, development_images=CODES,
        input='current bundle, independent Manual main_candidate full pools; frozen old 137 image roster',
        matching=['free', 'cyclic'], gap_deg=GAP, location_threshold_deg=9,
        locations=['all_median', 'joint_mode', 'split_mode', 'adaptive'],
        policy='no GT; original full-N MV50; source order unchanged; unavailable pools retained',
        interpretation='coverage/diagnostics, not semantic accuracy; no manual edits in this run'))
    write_json(OUT / 'field_contract.json', dict(schema='correspondence_expansion_v2',
        per_image='current records with source mapping; two identity partitions with order-independent node_consensus; fixed-cyclic-identity localization and complete layouts',
        summary='one row per attempted image including pool_error; N never reduced on failure',
        location='one row per retained cyclic identity at fixed 9deg; choice does not change existence votes',
        conditions='existing image labels used only for reporting, not matching or source selection',
        baseline='old paired 9deg result reused after exact record/point comparison',
        counts='geometry availability is not correspondence correctness; ordinary scene does not mean easy difficulty'))
    summary = []; positions = []
    for i, code in enumerate(codes):
        records = sorted([dict(r) for r in images[code]['annotations'] if r['independent'] and
            r['consensus_eligible'] and r['condition'] == 'manual' and
            r['main_consensus_gate']['status'] == 'main_candidate'], key=lambda r: r['id'])
        assert {r['id']: r['points'] for r in records} == {r['id']: r['points'] for r in old_inputs[code]}, code
        for r in records:
            o = objects[r['id']]; r.update(object_id=o['object_id'], source_pair_indices=o['ordered_source_pair_indices'])
        row = dict(image=code, n=len(records), scene=conditions[code]['scene'], difficulty=conditions[code]['difficulty'],
                   development=code in CODES, baseline_pairs=len(baseline[code].get('points') or []) // 2,
                   baseline_status=baseline[code]['status'], pool_error='')
        artifact = dict(image=code, records=records, image_id=objects[records[0]['id']]['image_id'])
        try:
            results = {mode: build(records, mode) for mode in ('free', 'cyclic')}
        except ValueError as e:
            row['pool_error'] = str(e); artifact['pool_error'] = str(e)
        else:
            artifact['correspondence'] = results
            row['partitions_equal'] = partition(results['free']) == partition(results['cyclic'])
            for mode, result in results.items():
                row[mode + '_selected'] = sum(g['selected'] for g in result['identity_groups'])
                row[mode + '_status'] = result['candidate']['status']
            result = results['cyclic']; selected = [g for g in result['identity_groups'] if g['selected']]
            locations = [compare_locations(g, len(records), 9) for g in selected]
            artifact['locations'] = locations
            layouts = [location_layout(result, locations, route) for route in ('all_median', 'joint_mode', 'split_mode', 'adaptive')]
            artifact['layouts'] = layouts
            row['source_ring_available'] = bool(result['ring_diagnostics']['feature_ids'])
            for layout in layouts:
                row[layout['route'] + '_geometry'] = layout['geometry_status']
                row[layout['route'] + '_unresolved'] = len(layout['unresolved_nodes'])
            for g, loc in zip(selected, locations):
                a = loc['estimates']['adaptive']; all_center = loc['estimates']['all_median']['center']
                np.testing.assert_allclose(all_center, g['center'])
                delta = None
                if a['center'] is not None and all_center is not None:
                    d = np.array(a['center']) - np.array(all_center); d[:, 0] = (d[:, 0] + 512) % 1024 - 512
                    delta = float(np.max(abs(d)))
                positions.append(dict(image=code, node=g['feature_id'], n=len(records), existence=g['support'],
                    choice=a['choice'], top=a['top_support'], bottom=a['bottom_support'], joint=a['joint_support'],
                    joint_ties=len(loc['position_candidates']['joint']), top_ties=len(loc['position_candidates']['top']),
                    bottom_ties=len(loc['position_candidates']['bottom']), adaptive_max_coordinate_shift_px=delta))
        write_json(OUT / (code + '.json'), artifact); summary.append(row)
        print(i + 1, code, row.get('cyclic_selected'), row.get('adaptive_geometry'), row['pool_error'], flush=True)
    write_csv(OUT / 'summary.csv', summary); write_csv(OUT / 'locations.csv', positions)
    panels = []
    for name, rows in [('all', summary), ('additional', [r for r in summary if not r['development']])] + [
        (scene, [r for r in summary if r['scene'] == scene]) for scene in sorted({r['scene'] for r in summary})]:
        good = [r for r in rows if not r['pool_error']]
        panels.append(dict(panel=name, images=len(rows), pool_errors=len(rows)-len(good),
            partitions_equal=sum(r['partitions_equal'] for r in good),
            source_ring_available=sum(r['source_ring_available'] for r in good),
            geometry_ok={route:sum(r[route+'_geometry']=='ok' for r in good) for route in ('all_median','joint_mode','split_mode','adaptive')}))
    write_json(OUT / 'summary.json', dict(panels=panels, choices=dict(Counter(p['choice'] for p in positions)),
        selected_identities=len(positions), people_records=sum(r['n'] for r in summary)))


def review_panel():
    """一处新定位失败的全部六份来源，供目标判断；不改对应或输出。"""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'DejaVu Sans']
    code = 'uNb9QFRL6hY-36'
    artifact = json.loads((OUT / (code + '.json')).read_text(encoding='utf-8'))
    image_path = next(ROOT.glob('data/mp3d_layout/*/img/' + artifact['image_id'] + '.png'))
    photo = Image.open(image_path)
    g = next(g for g in artifact['correspondence']['cyclic']['identity_groups'] if g['feature_id'] == 'node_003')
    loc = next(g for g in artifact['locations'] if g['feature_id'] == 'node_003')
    chosen = set(map(tuple, loc['estimates']['adaptive']['top_members']))
    fig, axes = plt.subplots(2, 4, figsize=(15, 9))
    for ax in axes.flat:
        ax.imshow(photo, extent=(0, 1024, 512, 0)); ax.axis('off')
    axes.flat[0].set_title('原图；框内为本次比较位置')
    from matplotlib.patches import Rectangle
    axes.flat[0].add_patch(Rectangle((190,190),160,210,fill=False,edgecolor='red',lw=2))
    members = []
    for i, (ax, m) in enumerate(zip(list(axes.flat)[1:7], g['members']), 1):
        p = np.array(m['points']); selected = (m['id'],m['pair_index']) in chosen
        ax.plot(p[:,0],p[:,1],'-o',c='#009fdd' if selected else '#d27b16',lw=2)
        ax.axhline(256,c='white',ls='--',lw=1); ax.set_xlim(190,350); ax.set_ylim(400,190)
        ax.set_title(f"{i}: {m['worker']} / {m['id']}\n上y={p[0,1]:.2f}；{'被局部选择' if selected else '未被局部选择'}",fontsize=10)
        members.append(dict(display=i, **m, selected_in_adaptive=selected))
    ax=axes.flat[7]; ax.set_xlim(190,350);ax.set_ylim(400,190);ax.axhline(256,c='white',ls='--')
    for route,color,label in [('all_median','#00bb66','全部六人中位数'),('adaptive','#ee2050','自适应')]:
        p=np.array(loc['estimates'][route]['center']);ax.plot(p[:,0],p[:,1],'-o',c=color,lw=2,label=label)
    ax.legend(fontsize=8);ax.set_title('融合位置对照；白虚线y=256')
    fig.suptitle('uNb-36：六人同组，位置来源选择后上端越过地平线\n只需判断上端目标；不按GT选择，不审核角点顺序')
    fig.tight_layout();fig.savefig(OUT/(code+'_review.png'),dpi=150);plt.close(fig)
    write_json(OUT/'review_request.json',dict(image=code,feature_id='node_003',members=members,
        source_image=code+'_review.png',status='pending_user_target_review',
        question='1—3与4—6是在标同一墙角的位置偏差，还是前后不同墙角／不同上端目标？无需检查精确坐标或顺序。'))


if __name__ == '__main__':
    run()
    review_panel()
