"""Recreate selected explanatory cases; these cases were chosen after inspecting outcomes."""
import sys as _delivery_sys
from pathlib import Path as _DeliveryPath
_delivery_root = next((p for p in _DeliveryPath(__file__).resolve().parents if (p / 'direct_io.py').is_file()))
_delivery_sys.path.insert(0, str(_delivery_root))
from direct_io import read_csv as _read_csv, open_data as _open_data, write_csv as _write_csv, write_bytes as _write_bytes, data_exists as _data_exists
import argparse, json, gzip
from pathlib import Path
import pandas as pd
from analyze import history_stats

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--out', type=Path, default=Path(__file__).parent)
    a = ap.parse_args()
    p = a.out
    r = a.repo
    d = _read_csv(p / 'formal_record_index.csv.gz')
    lab = _read_csv(r / 'research/workers/personnel_taxonomy_20261021/labels/lobo_labels.csv')
    with _open_data(r / 'research/statistics/v2_evidence_audit_20261019/records.json.gz', 'rt') as f:
        raw = {x['object_id']: x for x in json.load(f)['records']}
    selected = {'G130': ['W102', 'W103', 'W132', 'W115', 'W126'], 'G202': ['W123', 'W122', 'W028']}
    pp = _read_csv(p / 'direct_pair_workers.csv.gz')
    cases = []
    geom = []
    for gid, ws in selected.items():
        for row in pp[(pp.user_groups == gid) & (pp.condition == 'manual') & pp.worker_id.isin(ws)].itertuples():
            h = history_stats(d, {row.building}).loc[row.worker_id]
            ll = lab[(lab.condition == 'manual') & (lab.heldout_building == row.building) & (lab.worker_id == row.worker_id)].iloc[0]
            for side in ['a', 'b']:
                rid = getattr(row, 'object_' + side)
                z = raw[rid]
                dd = d[d.object_id == rid].iloc[0]
                mm = z['measurements'].get('same_reference_measurements') or {}
                cases.append(dict(group=gid, worker_id=row.worker_id, object_id=rid, image_id=z['image_id'], image_code=z['image_code'], Q=z['B8L2'], D10=z['D10'], relative_Q=dd.relative_B8L2, outside_Q=h.ext_abs, outside_relative_Q=h.theta, outside_n=h.ext_n, outside_buildings=h.ext_buildings, primary_fine_class=ll.primary_fine_class, primary_coarse_class=ll.primary_coarse_class, label_version=ll.label_version, label_heldout_building=ll.heldout_building, declared_pairs=z['declared_pair_count'], reference_pairs=dd.reference_pairs, reference_id=z['reference_id'], reference_version=z['reference_version'], source_path=z['source_evidence'].get('path'), iou_2d=mm.get('iou_2d'), S_bottom_deg=mm.get('S_bottom_deg'), direction_loss=mm.get('dir'), Hmean=mm.get('Hmean'), Hcenter=mm.get('Hcenter')))
                geom.append({'object_id': rid, 'image_id': z['image_id'], 'worker_id': z['worker_id'], 'original_points': z['original_points'], 'points_1024x512': z['points_1024x512'], 'reference_id': z['reference_id'], 'reference_version': z['reference_version'], 'reference_points_1024x512': z['reference_evidence']['points_1024x512'], 'coordinate_evidence': z['coordinate_evidence']})
    _write_csv(pd.DataFrame(cases), p / 'selected_person_cases.csv', index=False)
    (p / 'selected_person_geometry.json').write_text(json.dumps(geom, ensure_ascii=False), encoding='utf-8')
    x = pp[(pp.condition == 'manual') & (pp.layer == 'ordinary') & pp.scope_comparable & ~pp.substantive_conflict].copy()
    x['same_sign'] = (x.relative_a >= 0) == (x.relative_b >= 0)
    x['rel_gap'] = abs(x.relative_a - x.relative_b)
    x['abs_gap'] = abs(x.Q_a - x.Q_b)
    summ = []
    brows = []
    for worker in ['W115', 'W126', 'W123', 'W132']:
        z = x[x.worker_id == worker]
        bg = z.groupby('building').agg(pair_n=('pair_id', 'size'), same_sign=('same_sign', 'mean'), relative_gap=('rel_gap', 'mean'), Q_gap=('abs_gap', 'mean'))
        bg['worker_id'] = worker
        brows.append(bg.reset_index())
        imgs = set(z.image_a) | set(z.image_b)
        v = d[(d.condition == 'manual') & (d.layer == 'ordinary') & (d.worker_id == worker)]
        s = v[v.image_id.isin(imgs)]
        ss = bg.same_sign
        hold = [ss.drop(b).mean() for b in ss.index]
        summ.append(dict(worker_id=worker, pairs=len(z), images=len(imgs), buildings=z.building.nunique(), same_sign=ss.mean(), leave_one_building_out_same_sign_min=min(hold), leave_one_building_out_same_sign_max=max(hold), room_low=int((s.B8L2 < 50).sum()), room_answers=len(s), all_formal_low=int((v.B8L2 < 50).sum()), all_formal_answers=len(v), low_buildings=v[v.B8L2 < 50].building.nunique(), same_room_low_object_ids='|'.join(s[s.B8L2 < 50].object_id), same_room_low_image_codes='|'.join(s[s.B8L2 < 50].image_code)))
    _write_csv(pd.DataFrame(summ), p / 'selected_worker_stability.csv', index=False)
    _write_csv(pd.concat(brows), p / 'selected_worker_buildings.csv', index=False)
if __name__ == '__main__':
    main()
