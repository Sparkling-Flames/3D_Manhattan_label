"""复核全量历史库存与本轮采用子集；人数分档不定义收敛或采集资格。"""
import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'analysis_results/stage1_person_image_packages_20260913_v2'


def main():
    with gzip.open(ROOT / 'analysis_results/confirmed_point_calculation_view_20260909_v1/reviewed/calculation_view.jsonl.gz', 'rt', encoding='utf-8') as f:
        records = [json.loads(line) for line in f]
    assert len({r['canonical_annotation_id'] for r in records}) == len(records)
    raw = {}
    for path in sorted({r['raw_export_path'] for r in records}):
        tasks = json.loads((ROOT / path).read_text(encoding='utf-8'))
        raw[path] = {(str(t['id']), str(a['id'])): (Path(unquote(urlparse(t['data']['image']).path)).stem, int(a['completed_by']['id'] if isinstance(a['completed_by'], dict) else a['completed_by'])) for t in tasks for a in t.get('annotations', [])}
    for r in records:
        _, _, task, worker, annotation = r['raw_annotation_version_id'].split('|')
        assert raw[r['raw_export_path']][task, annotation] == (r['image_id'], int(worker))
    p = json.loads((BASE / '分配建议与核验.json').read_text(encoding='utf-8'))
    adopted = {r['image_id'] for r in p['images']}
    before, submitted, semi = (defaultdict(set) for _ in range(3))
    for r in records:
        w, iid = int(r['worker_id']), r['image_id']
        if w in {19, 26}:
            continue
        if r['assistance_exposure'] == 'none':
            submitted[iid].add(w)
        if r['unassisted_manual_included']:
            before[iid].add(w)
        if r['assistance_exposure'] == 'model_preannotation':
            semi[iid].add(w)
    after = {iid: set(ws) for iid, ws in before.items()}
    for r in p['assignments']:
        assert r['worker_id'] not in after.get(r['image_id'], set())
        after.setdefault(r['image_id'], set()).add(r['worker_id'])
    rows = [dict(image_id=iid, in_current_adopted_pool=iid in adopted, historical_unassisted_submitters=len(submitted[iid]), historical_geometry_workers=len(before[iid]), historical_semi_workers=len(semi[iid]), after_required_workers=len(after.get(iid, set()))) for iid in sorted({r['image_id'] for r in records} | set(after))]
    def count(view):
        values = [len(ws) for ws in view.values() if ws]
        return dict(images=len(values), person_images=sum(values), histogram=dict(sorted(Counter(values).items())), at_least_8=sum(n >= 8 for n in values), at_least_16=sum(n >= 16 for n in values))
    summary = dict(scope='全部2501条canonical历史计算视图及其原始导出，不限制当前采用池；不是线上实时导出', raw_canonical_records=len(records), raw_images=len({r['image_id'] for r in records}), raw_workers=len({r['worker_id'] for r in records}), raw_exports_verified=len(raw), excluded_workers=[19, 26], before=count(before), after_required=count(after), adopted_high16=sum(iid in adopted and len(ws)>=16 for iid, ws in before.items()), outside_adopted_high16=sum(iid not in adopted and len(ws)>=16 for iid, ws in before.items()), eligibility_note='无辅助含经核实无辅助的历史oos；几何可计算不等于非OOS或已获新采集采用；Semi不混入无辅助人数')
    assert summary['before']['images'] == 196 and summary['before']['person_images'] == 1843
    assert summary['before']['at_least_16'] == 55
    assert summary['after_required']['person_images'] - summary['before']['person_images'] == 480
    with (BASE / '全量历史与本轮覆盖核对.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    (BASE / '全量历史与本轮覆盖核对.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
