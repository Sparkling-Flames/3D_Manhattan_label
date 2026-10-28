"""Measure saved scope/revised-GT axis residuals without changing geometry or Q."""
import csv
import gzip
import json
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'research/data/scope_quality_rescore_20261016/vertical_cut_audit_20261028'


def axis_residual(points):
    p = np.asarray(points, float)
    assert Polygon(p).is_valid and Polygon(p).area > 0
    v = np.roll(p, -1, axis=0)-p
    lengths = np.linalg.norm(v, axis=1)
    assert (lengths > 0).all()
    a = np.arctan2(v[:, 1], v[:, 0])
    axis = np.angle(np.sum(lengths*np.exp(4j*a)))/4
    residual = np.abs((a-axis+np.pi/4) % (np.pi/2)-np.pi/4)*180/np.pi
    return float(axis*180/np.pi), float(residual.max()), float(np.average(residual, weights=lengths))


def main():
    assert axis_residual([[0,0],[2,0],[2,1],[0,1]])[1] < 1e-10
    assert axis_residual([[0,0],[2,0],[2.1,1],[0,1]])[1] > 1
    read = lambda p: json.loads((ROOT/p).read_text(encoding='utf-8'))
    views = read('research/data/scope_redundant_vertices_20261016/scope_views.json')
    catalog = read('research/quality/quality_workers_v2_20261019/reference_catalog.json')
    with gzip.open(ROOT/'research/data/releases/v2/analysis_input/data.json.gz', 'rt', encoding='utf-8') as f:
        data = json.load(f)
    manual = [o for o in data['objects'] if o['object_kind']=='gt_manual_revision']
    inventory = []
    for o in manual:
        entries = [r for r in catalog if r['image_id']==o['image_id']]
        own = [r for r in entries if r['target_id']==o['object_id']]
        inventory.append(dict(image=o['image_code'],object_id=o['object_id'],
            saved_reference_role='|'.join(r['role'] for r in own) or 'absent_from_reference_catalog',
            current_target_ids='|'.join(r['target_id'] for r in entries if r['current_target']),
            note='目录角色不是正式质量资格；排除状态与逐作答绑定另行核对'))
    assert len(manual)==30 and len({o['image_id'] for o in manual})==30
    with (OUT/'MANUAL_GT30_REFERENCE_INVENTORY.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(inventory[0]));writer.writeheader();writer.writerows(inventory)
    receipt = json.loads((OUT/'LATEST_E9Z_SCOPE_RECEIPT.json').read_text(encoding='utf-8'))
    inputs = [(v['image_code'],v['target_id'],'confirmed_scope',v['precision_floor_view']['floor']) for v in views]
    inputs += [(c['image_code'],c['target_id'],'explicit_revised_gt',c['floor_xz_h']) for c in catalog if c['target_id'].startswith('gt_user_revision_20261015:')]
    assert len(inputs) == 45 and len({t[1] for t in inputs}) == 45
    results=[]
    for image, target, kind, points in inputs:
        if image == 'e9zR4mvMWw7-09' and kind == 'confirmed_scope':
            points = receipt['record']['cropped_floor_xz_h']
        axis, maximum, mean = axis_residual(points)
        results.append(dict(image=image,target_id=target,kind=kind,vertices=len(points),axis_deg=axis,max_residual_deg=maximum,length_weighted_mean_residual_deg=mean,floor_revision=receipt['exported_at'] if image=='e9zR4mvMWw7-09' else 'saved_confirmed_view'))
    with (OUT/'ORTHOGONALITY_SCAN_20261028.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(results[0]));writer.writeheader();writer.writerows(results)
    print(json.dumps(dict(scopes=43,revised_gt=2,scope_max_deg=max(r['max_residual_deg'] for r in results if r['kind']=='confirmed_scope'),revised_gt_max_deg={r['image']:r['max_residual_deg'] for r in results if r['kind']=='explicit_revised_gt'},new_scores=0,geometry_changes=0),ensure_ascii=False))


if __name__=='__main__':
    main()
