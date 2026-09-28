"""从解压目录运行：python -B verify_bundle.py。只验证公开副本，不回写原件。"""
import importlib.metadata
import json
import re
from pathlib import Path

from tools.thesis_main.analysis.union_branch_consensus_20260926 import fit_union_branches

ROOT = Path(__file__).resolve().parent


def main():
    manifest = json.loads((ROOT / 'MANIFEST.json').read_text(encoding='utf-8'))
    for row in manifest['files']:
        path = ROOT / row['path']
        assert path.is_file() and path.stat().st_size == row['bytes'], row['path']
    text = (ROOT / 'inputs/eight_image_panel.json').read_text(encoding='utf-8')
    assert not re.search(r'W\d{3}|canonical_annotation_id|raw_export_path|runtime_task_id', text)
    panel = json.loads(text)
    assert panel['counts'] == dict(images=8, annotations=160, independent_computable=153, workers=24)
    annotation_ids = []
    checks = []
    for image in panel['images']:
        rows = image['annotations']
        assert len({a['worker_id'] for a in rows}) == len(rows)
        annotation_ids.extend(a['annotation_id'] for a in rows)
        records = [a['core_record'] for a in rows if a['core_record'] is not None]
        for record in records:
            assert record['independent_raw_vote'] is True
            assert len(record['floor']) == len(record['pairs']) == len(record['heights'])
        result = fit_union_branches(records, point_tol_deg=5.)
        assert sum(b['support'] for b in result['branches']) == len(records)
        checks.append(dict(code=image['code'], input=len(rows), computable=len(records),
                           branches_at_5deg=len(result['branches']),
                           max_support=max(b['support'] for b in result['branches'])))
    assert len(set(annotation_ids)) == len(annotation_ids) == 160
    assert sum(r['computable'] for r in checks) == 153
    assert len(panel['references_for_evaluation_only']) == 8
    for entry in panel['references_for_evaluation_only']:
        for ref in entry['references']:
            assert ref['used_for_fitting'] is False
    output = dict(status='passed', meaning='portable_inputs_and_existing_core_only_not_new_search_validation',
                  counts=panel['counts'], image_checks=checks,
                  versions={p: importlib.metadata.version(p) for p in ['numpy','scipy','shapely','pytest','matplotlib']})
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
