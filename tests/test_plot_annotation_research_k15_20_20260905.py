import pytest

from tools.thesis_main.analysis.plot_annotation_research_k15_20_20260905 import fixed_series


def test_plot_keeps_fixed_image_support_and_building_weighting():
    rows = [dict(stage='S', condition='manual', base_task_id=image, building_id=building,
                 k=k, evaluable=True, rate=value)
            for image, building, value in [('a', 'B1', 0), ('b', 'B1', 0), ('c', 'B2', 1)]
            for k in range(15, 21)]
    rows.append(dict(stage='S', condition='manual', base_task_id='d', building_id='B3',
                     k=15, evaluable=True, rate=1))
    result = fixed_series(rows, 'rate')[0]
    assert result['image_count'] == 3
    assert result['values'][0]['image_equal'] == 1 / 3
    assert result['values'][0]['building_equal'] == .5
    with pytest.raises(ValueError, match='support'):
        fixed_series(rows[1:], 'rate')
