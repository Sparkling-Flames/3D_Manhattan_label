from copy import deepcopy

import pytest

from tools.thesis_main.analysis.layout_metric_response_20261001 import synthetic_experiments, measure, SCHEMA, PLAN
from tools.thesis_main.analysis.verify_layout_metric_snapshot_20261001 import verify_embedded, _compare


def test_embedded_recheck_detects_metric_and_schema_drift():
    case = synthetic_experiments()[0]
    result = dict(schema=SCHEMA, plan=PLAN, synthetic=[dict(case,metrics=measure(case['a'],case['b'],synthetic=True))],
                  real=[], boundary_dense_check=None)
    summary = verify_embedded(result)
    assert summary['synthetic_pairs'] == 1 and summary['real_comparisons'] == 0
    corrupted = deepcopy(result)
    corrupted['synthetic'][0]['metrics']['column']['1024x512']['iou'] = .9
    with pytest.raises(ValueError, match='1024x512.iou'):
        verify_embedded(corrupted)
    for actual in ({'value':0}, {'value':None,'extra':1}, {'value':float('nan')}):
        with pytest.raises(ValueError):
            _compare({'value':None},actual,'missing')
    with pytest.raises(ValueError, match='numeric'):
        _compare(1.,True,'numeric')
