"""只读复算嵌入证据；不读取完整源表，不生成新研究结果。"""
import csv
import json
from pathlib import Path
import sys

from tools.thesis_main.analysis.verify_layout_metric_snapshot_20261001 import _compare, verify_embedded
from tools.thesis_main.analysis.layout_3d_quality_probe_20261002 import compare, diagnostics, flat, prepare_record

ROOT = Path(__file__).resolve().parent


def read(path):
    return json.loads((ROOT/path).read_text(encoding='utf-8'))


def main():
    manifest = read('MANIFEST.json')
    files = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file()}-{'MANIFEST.json'}
    assert files == {r['path'] for r in manifest['files']}, 'inventory drift'
    for entry in manifest['files']:
        assert (ROOT/entry['path']).stat().st_size == entry['bytes'], entry['path']
    for name, module in list(sys.modules.items()):
        if name.startswith(('tools.', 'lib.')) and getattr(module, '__file__', None):
            assert Path(module.__file__).resolve().is_relative_to(ROOT), 'dependency outside snapshot: '+name
    stage2 = verify_embedded(read('analysis_results/layout_metric_response_20261001/results.json'))
    directory = 'analysis_results/layout_3d_quality_probe_20261002/'
    result = read(directory+'results.json')
    assert result['schema'] == 'layout_3d_quality_probe_v1'
    for o in result['objects']:
        _compare(o['diagnostics'], diagnostics(o['record']), o['record']['id'])
        _compare(o['record'], prepare_record(o['record']), 'order_policy')
    for row in result['real']:
        _compare(row['metrics'], compare(row['a'],row['b']), row['id'])
    for row in result['orders']:
        assert row['status']=='ok'
        assert sorted(map(tuple,row['before']['points'])) == sorted(map(tuple,row['after']['points']))
        _compare(row['change'],compare(row['before'],row['after']), 'order_change')
        for version, metrics in row['references'].items():
            reference = next(r['b'] for r in result['real'] if r['id']==row['id'] and r['reference_version']==version)
            for state in ('before','after'):
                _compare(metrics[state], compare(row[state],reference), 'order_reference')
    contract = read(directory+'field_contract.json')
    with (ROOT/directory/'metrics.csv').open(encoding='utf-8-sig',newline='') as f:
        reader = csv.DictReader(f); rows = list(reader)
        assert reader.fieldnames==contract['metrics_csv'] and len(rows)==len(result['real'])
    for saved, row in zip(rows,result['real']):
        expected = {k:'' if v is None else str(v) for k,v in flat(row).items()}
        assert saved==expected, 'CSV value drift'
    with (ROOT/directory/'order_comparisons.csv').open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f); rows=list(reader)
        assert reader.fieldnames==contract['order_csv'] and len(rows)==len(result['orders'])
    for saved,row in zip(rows,result['orders']):
        expected=dict(image=row['image'],id=row['id'],status=row['status'],reason=row['reason'],
            before_after_bev_iou=row['change']['bev']['bev_range_iou'],before_after_volume_iou=row['change']['model_volume']['iou'])
        assert saved=={k:'' if v is None else str(v) for k,v in expected.items()}, 'order CSV drift'
    print(json.dumps(dict(stage2=stage2, stage3d=result['counts'], files=len(files),
        scope='embedded recomputation only; no source selection or original imagery verification'),ensure_ascii=False))


if __name__=='__main__':
    main()
