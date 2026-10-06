import subprocess
import sys

import pytest

from tools.thesis_main.analysis import research_artifact_io as artifacts


@pytest.mark.parametrize('module', [
    'difficulty_consensus_20261006',
    'update_difficulty_review_20261006',
    'build_difficulty_review_20261006',
])
def test_difficulty_tools_import_without_geometry_or_count_experiment(module):
    subprocess.run([sys.executable, '-c', f"""
import importlib
import sys
sys.modules['shapely'] = None
sys.modules['matplotlib'] = None
for name in ('lee_tile_stage1_20261002', 'worker_count_composition_20261006',
             'research_round_20260929'):
    sys.modules['tools.thesis_main.analysis.' + name] = None
module = importlib.import_module('tools.thesis_main.analysis.{module}')
from tools.thesis_main.analysis.difficulty_consensus_20261006 import scene_group, summarize
assert scene_group(dict(oos_status='confirmed', doorway_status='difficult')) == 'oos_and_doorway'
meta = {{'a': dict(building='b', scene='clear', difficulty='简单')}}
rows = [dict(image='a', n=8, k=1, method='mv50', distance=.25)]
assert summarize(rows, meta, 8)[0]['mean_distance'] == .25
"""], check=True)


def test_finite_pool_probabilities_do_not_require_geometry():
    subprocess.run([sys.executable, '-c', """
import sys
sys.modules['shapely'] = None
from research.worker_subtype_returns_20261004.pro.src.finite_pool import (
    marginal, coupled, next_member_loss,
)
assert marginal((2,), (1,), (1,), 'mv50') == .5
assert coupled((2,), (1,), (1,), 'mv50', 'add', (1,)) == (.5, .5, 0.)
assert next_member_loss((2,), (1,), (1,), 'mv50', 0) == 1.
"""], check=True)


def test_artifact_io_preserves_existing_entry_points():
    from tools.thesis_main.analysis import lee_tile_stage1_20261002 as lee
    from tools.thesis_main.analysis import worker_count_composition_20261006 as count

    for name in ('ROOT', 'write_csv', 'write_json'):
        assert getattr(lee, name) is getattr(artifacts, name)
        assert getattr(count, name) is getattr(artifacts, name)
    for name in ('INVENTORY', 'read_csv'):
        assert getattr(count, name) is getattr(artifacts, name)


def test_lee_cli_keeps_direct_script_entry_point():
    script = artifacts.ROOT / 'tools/thesis_main/analysis/lee_tile_stage1_20261002.py'
    result = subprocess.run([sys.executable, str(script), '--help'],
                            check=True, capture_output=True, text=True)
    assert '--input' in result.stdout
    assert '--out' in result.stdout


def test_artifact_csv_preserves_bytes_and_column_order(tmp_path):
    path = tmp_path / 'rows.csv'
    rows = [dict(image='图一', distance=.25, missing=None),
            dict(image='a,b', distance=1., missing='')]
    artifacts.write_csv(path, rows)
    assert path.read_bytes() == ('\ufeffimage,distance,missing\n'
                                 '图一,0.25,\n"a,b",1.0,\n').encode('utf-8')
    assert artifacts.read_csv(path) == [
        dict(image='图一', distance='0.25', missing=''),
        dict(image='a,b', distance='1.0', missing=''),
    ]


def test_artifact_json_preserves_format_and_nan_rejection(tmp_path):
    path = tmp_path / 'value.json'
    artifacts.write_json(path, dict(label='简单', distance=.25, missing=None))
    assert path.read_bytes() == ('{\n  "label": "简单",\n  "distance": 0.25,\n'
                                 '  "missing": null\n}\n').encode('utf-8')
    with pytest.raises(ValueError):
        artifacts.write_json(path, dict(distance=float('nan')))
