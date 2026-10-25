"""Replay delivered complete cases with the existing frozen local engine."""
from pathlib import Path
import gzip
import importlib.util
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ENGINE = REPO / 'research/same_room/same_room_large_block_rebuilt_20261023/engine/native_team_runner.py'


def main():
    spec = importlib.util.spec_from_file_location('audit_frozen_native', ENGINE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    paths = list((ROOT/'unpacked/02C/cases').glob('*/CASE_GEOMETRY.json.gz'))
    paths += list((ROOT/'unpacked/06B/cases_reverse').glob('*/CASE_GEOMETRY.json.gz'))
    assert len(paths) == 5
    checks = []
    fields = ['B8L2', 'D10', 'IoU3D100', 'iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter', 'nodes']
    with module.FrozenNativeEngine(full_state=True) as engine:
        for path in paths:
            with gzip.open(path, 'rt', encoding='utf-8') as f:
                case = json.load(f)
            engine.reset_pool()
            for arm in ['A','B','C']:
                workers = case['event'][arm+'_members'].split('|')
                result = engine.evaluate(case['pool'],workers)
                saved = case['saved_endpoint_rows'][arm]
                errors = {field: abs(float(result[field])-float(saved[field])) for field in fields}
                assert max(errors.values()) < 1e-7, (path, arm, errors)
                assert result['team_key'] == saved['team_key']
                for field in ['points','footprint']:
                    assert np.allclose(result['geometry'][field], saved['geometry'][field], atol=1e-8,rtol=0), (path,arm,field)
                assert result['node_supports'] == saved['node_supports']
                checks.append({'case_id':path.parent.name,'arm':arm,'team_key':result['team_key'],
                               'max_scalar_error':max(errors.values()),'geometry_and_support_match':True})
                print(checks[-1],flush=True)
    (ROOT/'NATIVE_CASE_REPLAY.json').write_text(json.dumps({'cases':5,'endpoints':len(checks),'checks':checks},ensure_ascii=False,indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
