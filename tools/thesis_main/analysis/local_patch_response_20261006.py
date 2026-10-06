"""把Pro固定的两处观察片区接回既有人数/构成；不把片区当新GT。"""
import json

import numpy as np
from shapely.geometry import Polygon, shape

from .lee_tile_stage1_20261002 import ROOT, tile_consensus, write_csv, write_json
from .worker_count_composition_20261006 import probabilities, read_csv


SOURCE = ROOT / 'analysis_results/worker_count_composition_20261006'
PRO = ROOT / 'research/pro_parallel_return_20261006/pro_original'
OUT = ROOT / 'analysis_results/consensus_response_20261006/local_patches'


def patch_weights(tiles, patch):
    """按局部相交面积积分；分母固定为整个片区，包括无人覆盖部分。"""
    area = np.array([t.intersection(patch).area for t in tiles])
    return area / patch.area


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    groups = json.loads((SOURCE/'input.json').read_text(encoding='utf-8'))['groups']
    features = json.loads((PRO/'results/diagnostic_patches.geojson').read_text(encoding='utf-8'))['features']
    fusion = read_csv(SOURCE/'per_image.csv')
    assignments = read_csv(SOURCE/'assignments.csv')
    pro_endpoints = {(r['image'], r['object']): float(r['patch_covered_fraction'])
                     for r in read_csv(PRO/'results/local_diagnostics.csv')}
    rows, checks, notices = [], [], []
    for feature in features:
        prop = feature['properties']; image = prop['image']; patch = shape(feature['geometry'])
        group = next(g for g in groups if g['image']==image and g['condition']=='manual' and g['status']=='selected')
        records = group['records']; n = len(records); full_mask = (1 << n)-1
        result = tile_consensus(records); mesh = result['mesh']
        notices.extend(dict(image=image, message=w) for w in result['warnings'])
        patterns = [sum(1 << int(j) for j in np.flatnonzero(col)) for col in mesh['votes'].T]
        weights = patch_weights(mesh['tiles'], patch)
        source = next(r for r in records if r['id']==prop['record'])
        source_fraction = Polygon(source['footprint']).intersection(patch).area / patch.area
        labels = {policy: {r['worker']: r['higher']=='True' for r in assignments
                           if r['image']==image and r['policy']==policy}
                  for policy in ('original', 'revised_where_available')}
        masks = {policy: sum(1 << j for j,r in enumerate(records) if label[r['worker']])
                 for policy,label in labels.items()}
        cache = {}
        selected = [r for r in fusion if r['image']==image and r['condition']=='manual'
                    and (r['scenario']=='uniform' or int(r['k'])==8)]
        for r in selected:
            k = int(r['k']); method = r['method']; policy = r['policy']
            key = (method, k, policy, r['strategy'])
            if key not in cache:
                if r['scenario']=='uniform':
                    q = probabilities(patterns, (full_mask,), (n,), (k,), method)
                else:
                    hm = masks[policy]; nh = hm.bit_count(); h = int(r['higher_n'])
                    q = probabilities(patterns, (hm, full_mask ^ hm), (nh, n-nh), (h, k-h), method)
                cache[key] = float(weights @ q)
            value = cache[key]
            rows.append(dict(image=image, condition='manual', n=n, method=method, k=k,
                scenario=r['scenario'], policy=policy, strategy=r['strategy'], version=r['version'],
                higher_n=r['higher_n'], source_record=source['id'], source_worker=source['worker'],
                source_higher=labels[policy][source['worker']] if policy!='none' else '',
                patch_area_h2=patch.area, source_patch_fraction=source_fraction,
                expected_patch_fraction=value,
                interpretation='observed_protrusion_retention' if source_fraction>.5 else 'observed_indent_filling',
                **{f:float(r[f]) for f in ('omission_ref','extension_ref','ref_symdiff_ref','member_symdiff_union')}))
        one = np.mean([Polygon(r['footprint']).intersection(patch).area/patch.area for r in records])
        for method in ('mv50','mv_strict'):
            k1 = cache[method,1,'none','random']; full = cache[method,n,'none','random']
            actual = result['regions'][method].intersection(patch).area/patch.area
            assert abs(k1-one)<1e-10
            assert abs(full-actual)<1e-10
            assert abs(full-pro_endpoints[image,method])<1e-10
            checks.append(dict(image=image, method=method, single_error=abs(k1-one),
                               all_geometry_error=abs(full-actual), pro_endpoint_error=abs(full-pro_endpoints[image,method])))
        print(image, len(mesh['tiles']), flush=True)
    write_csv(OUT/'per_image.csv', rows)
    write_json(OUT/'field_contract.json', dict(schema='local_patch_response_v1',
        patch_source='Pro diagnostic_patches.geojson; two post-hoc observed path/chord regions, unchanged.',
        input='Existing prepared Manual 24-person pools; original ring order and footprints.',
        expected_patch_fraction='E[area(F intersect patch)] / fixed patch area. Exact finite-pool marginal probabilities; no MC.',
        semantics='rPc: retention of one observed protrusion; yq: filling of one observed indent. Neither is semantic accuracy or point identity support.',
        selection='Uniform k=1..N; existing k=8 compositions and both existing calibration reference policies. No new worker ranking.',
        reference='version indexes evaluation GT; policy indexes calibration GT. Global D/O/E/V reused from existing tables.',
        source_higher='Label of the patch-source worker under the current calibration; blank for uniform rows.',
        checks=checks, warnings=notices))
    plot(rows)
    print(json.dumps(dict(rows=len(rows), max_error=max(max(c[f] for f in ('single_error','all_geometry_error','pro_endpoint_error')) for c in checks))))


def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']; plt.rcParams['axes.unicode_minus']=False
    fig, axes = plt.subplots(2,2,figsize=(12,8))
    for index, image in enumerate(dict.fromkeys(r['image'] for r in rows)):
        for col, field in enumerate(('ref_symdiff_ref','expected_patch_fraction')):
            ax = axes[index,col]
            for method, color in [('mv50','#246a96'),('mv_strict','#c37632')]:
                rs = [r for r in rows if r['image']==image and r['method']==method and r['version']=='original' and r['scenario']=='uniform']
                ax.plot([r['k'] for r in rs],[r[field] for r in rs],color=color,label=method)
                ax.scatter([rs[-1]['k']],[rs[-1][field]],color=color,marker='s')
            for strategy, marker, label in [('higher_rich','^','Q上半8人：MV50'),('lower_rich','v','Q下半8人：MV50')]:
                r=next(r for r in rows if r['image']==image and r['method']=='mv50' and r['version']=='original' and r['policy']=='original' and r['strategy']==strategy)
                ax.scatter([8],[r[field]],color='#71376c',marker=marker,s=65,label=label)
            title='对原GT整体范围差 D（越小越近）' if col==0 else ('观察凸出片区保留率（不是准确率）' if index==0 else '观察内收片区填入率（不是准确率）')
            ax.set_title(image+'\n'+title); ax.set_xlabel('人数 k'); ax.grid(alpha=.2); ax.legend(fontsize=8)
            if col==1: ax.set_ylim(0,1)
    fig.suptitle('同一批24人：人数、Q构成与两处固定观察片区；方点为实际全员终点')
    fig.tight_layout(); fig.savefig(OUT/'local_patch_response.png',dpi=170); plt.close(fig)


if __name__=='__main__': run()
