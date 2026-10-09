"""固定178池全来源范围诊断；只作复核线索，不用人员结果定义难度。"""
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon, Point
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = Path(__file__).parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(ROOT))
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def polygon(points):
    p = np.asarray(points, dtype=float)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) < 6 or len(p) % 2 or not np.isfinite(p).all():
        return None, 'invalid_pairs'
    if np.any(p[:, 0] < 0) or np.any(p[:, 0] > 1024) or np.any(p[:, 1] < 0) or np.any(p[:, 1] > 512):
        return None, 'outside_canvas'
    floor = p[1::2]; v = (floor[:, 1]/512-.5)*np.pi
    if np.any(v <= 0) or np.any(v >= np.pi/2):
        return None, 'floor_not_below_horizon'
    u = (floor[:, 0]/1024-.5)*2*np.pi
    r = 1/np.tan(v)
    xy = np.stack([r*np.sin(u), -r*np.cos(u)], axis=1)
    poly = Polygon(xy)
    if not poly.is_valid or poly.area <= 0:
        return None, 'invalid_polygon'
    if not poly.contains(Point(0, 0)):
        return None, 'camera_not_inside'
    return poly, 'valid'


def disagreement(a, b):
    return dict(symmetric_difference=a.symmetric_difference(b).area/b.area,
                excess=a.difference(b).area/b.area, missing=b.difference(a).area/b.area)


def main():
    all_mode = '--all' in sys.argv
    assert abs(disagreement(Polygon([(0,0),(2,0),(2,1),(0,1)]), Polygon([(0,0),(1,0),(1,1),(0,1)]))['symmetric_difference']-1) < 1e-10
    assert polygon([[1,1],[1,200]]*3)[1] == 'floor_not_below_horizon'
    pool_path = ROOT/'analysis_results/direct_fusion_20261007/gap_sweep/population/inputs.json'
    pools = json.loads(pool_path.read_text(encoding='utf-8'))['images']
    legacy = {i['image'] for i in json.loads((ROOT/'analysis_results/adaptive_point_20261007/expanded/inputs.json').read_text(encoding='utf-8'))['images']}
    bundle = load_current_bundle(); _, aliases = project_bundle(bundle)
    objects = {o['object_id']: o for o in bundle['data']['objects']}
    public = {aliases['records'][k]:v for k,v in objects.items()}
    images = {im['image_id']:im for im in bundle['data']['images']}
    base = ROOT/'analysis_results/objective_difficulty_20261009'
    classes = {r['image_id']:r for r in read_csv(base/'structure_classification/images.csv')}
    working = {r['image_id']:r for r in read_csv(base/'review_examples/working_classification_20261010.csv')}
    photos = {r['image_id']:r['hohonet_path'] for r in read_csv(base/'model_comparison/image_source_audit.csv')}
    current_pools = {im['image_id']: im for im in pools}
    card_dir = OUT/('all_cards' if all_mode else 'cards')
    card_dir.mkdir(exist_ok=True)
    results, members = [], []
    assert len(pools) == 178 and len({im['image'] for im in pools}) == 178
    if all_mode:
        pools = [dict(image_id=iid, image=images[iid]['image_code'], records=[
            dict(id=aliases['records'][o['object_id']], worker=o['worker_id'], points=o['points_1024x512'])
            for o in objects.values() if o['image_id']==iid and o['object_kind']=='annotation']) for iid in classes]
    for index, im in enumerate(sorted(pools, key=lambda r:r['image'])):
        iid, code = im['image_id'], im['image']; row = classes[iid]
        gt = objects[row['gt_object_id']]; gp, gs = polygon(gt['points_1024x512'])
        original = objects[images[iid]['references']['gt_original']]
        op, os = polygon(original['points_1024x512'])
        observations = []
        seen = set()
        for rec in im['records']:
            obj = public[rec['id']]
            assert obj['image_id'] == iid
            if not all_mode: assert obj['condition'] == 'manual'
            assert np.array_equal(obj['points_1024x512'], rec['points']), rec['id']
            if not all_mode: assert obj['worker_id'] not in seen
            seen.add(obj['worker_id'])
            poly, status = polygon(obj['points_1024x512'])
            metrics = disagreement(poly, gp) if poly is not None and gp is not None else None
            ometrics = disagreement(poly, op) if poly is not None and op is not None else None
            entry = dict(image=code, image_id=iid, record_id=rec['id'], object_id=obj['object_id'],
                worker=rec['worker'], worker_id=obj['worker_id'], geometry_status=status,
                condition=obj['condition'], gate=obj['main_consensus_gate']['status'],
                in_current_manual_pool=rec['id'] in {r['id'] for r in current_pools.get(iid, {}).get('records', [])},
                selected_gt_metrics=metrics, original_gt_metrics=ometrics,
                points=obj['points_1024x512'], source=obj['source'],
                footprint=list(poly.exterior.coords) if poly is not None else None)
            observations.append(entry)
            members.append({k:v for k,v in entry.items() if k not in ('points','footprint','source')})
        n = len(observations); valid = [r for r in observations if r['selected_gt_metrics'] is not None]
        counts = {str(t):sum(r['selected_gt_metrics']['symmetric_difference'] >= t for r in valid) for t in (.2,.3,.4)}
        uncertain = n-len(valid)
        result = dict(image=code, image_id=iid, legacy137=code in legacy, in_current178=iid in current_pools, n=n,
            valid_geometry=len(valid), invalid_geometry=uncertain,
            flagged_counts=counts, flag_fraction_lower=counts['0.3']/n,
            flag_fraction_upper=(counts['0.3']+uncertain)/n,
            majority_geometry_signal=n>=3 and 2*counts['0.3']>=n,
            insufficient_people=n<3, gt_object_id=gt['object_id'], gt_status=gs,
            N=int(row['selected_gt_pair_count']), H=int(row['hidden_pair_count']),
            structure_class=row['coarse_class'], working_class=working[iid]['working_difficulty_class'],
            scene=row['scene_stratum'], photo_path=photos[iid],
            reference_flags={k:row[k] for k in ('scope_explicit_tag','scope_existing_ledger','scope_comment_candidate','gt_substantive_error_mark','gt_detail_omission_mark')},
            original_gt_object_id=original['object_id'], selected_gt_points=gt['points_1024x512'],
            observations=observations)
        result['condition_gate_groups'] = []
        for condition, gate in sorted({(r['condition'],r['gate']) for r in observations}):
            group = [r for r in observations if (r['condition'],r['gate'])==(condition,gate)]
            vg = [r for r in group if r['selected_gt_metrics'] is not None]
            kg = {str(t):sum(r['selected_gt_metrics']['symmetric_difference']>=t for r in vg) for t in (.2,.3,.4)}
            result['condition_gate_groups'].append(dict(condition=condition,gate=gate,n=len(group),workers=len({r['worker_id'] for r in group}),invalid=len(group)-len(vg),flagged_counts=kg,geometry_signal=len(group)>=3 and kg['0.3']*2>=len(group)))
        if all_mode:
            result['majority_geometry_signal'] = any(g['geometry_signal'] for g in result['condition_gate_groups'])
            result['mixed_fraction_is_not_a_vote'] = True
        results.append(result)
        fig, axes = plt.subplots(1,2,figsize=(15,5),gridspec_kw={'width_ratios':[2,1]})
        axes[0].imshow(plt.imread(photos[iid]), extent=(0,1024,512,0))
        for j in range(0,len(gt['points_1024x512']),2):
            a,b = gt['points_1024x512'][j:j+2]
            axes[0].plot([a[0],b[0]],[a[1],b[1]],color='#ff355b',lw=1.5)
            axes[0].text(a[0],a[1]-6,str(j//2+1),color='white',fontsize=8,bbox=dict(facecolor='black',alpha=.6,pad=1))
        axes[0].axis('off')
        for entry in observations:
            if entry['footprint']:
                xy=np.asarray(entry['footprint']);axes[1].plot(xy[:,0],xy[:,1],c={'manual':'#2571a6','semi':'#8b47bb','oos':'#269b67'}[entry['condition']],alpha=.45,lw=.8)
        if op is not None:
            x,y=op.exterior.xy;axes[1].plot(x,y,c='#d89c00',ls='--',lw=2,label='Original GT')
        if gp is not None:
            x,y=gp.exterior.xy;axes[1].plot(x,y,c='#ff355b',lw=2,label='Selected GT')
        axes[1].scatter([0],[0],c='black',s=12);axes[1].set_aspect('equal');axes[1].legend(fontsize=7)
        axes[1].set_title(f"{n} records; valid {len(valid)}; missing {uncertain}\nManual blue / Semi purple / OOS green",fontsize=10)
        fig.suptitle(f'{index+1:03d} {code} | N={result["N"]}, H={result["H"]} | {row["scene_stratum"]}',fontsize=13)
        fig.tight_layout();fig.savefig(card_dir/f'{code}.jpg',dpi=110);plt.close(fig)
        if (index+1)%30==0: print(f'{index+1}/{len(pools)} cards',flush=True)
    assert len(results)==(259 if all_mode else 178) and sum(r['legacy137'] for r in results)==137
    if all_mode: assert len(members)==3152 and sum(r['in_current178'] for r in results)==178
    prefix = 'all_' if all_mode else ''
    (OUT/f'{prefix}scope_evidence.json').write_text(json.dumps(results,ensure_ascii=False),encoding='utf-8')
    (OUT/f'{prefix}scope_metrics.json').write_text(json.dumps(members,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(dict(images=len(results),records=len(members),majority_signals=sum(r['majority_geometry_signal'] for r in results),invalid=sum(r['invalid_geometry'] for r in results)),ensure_ascii=False))


if __name__ == '__main__':
    main()
