import pandas as pd

from tools.thesis_main.analysis.build_cluster_screen_20260921 import references, select_cases


def test_selection_respects_closed_images_count_gate_and_deterministic_order():
    rows = [dict(image_id=str(i), code=f'b{i}-01', building=f'b{i}', a_id=f'a{i}', b_id=f'z{i}',
                 same_count=i != 1, N=8, fixed_max=20., free_max=20.,
                 complete_same=False, representative_same=True) for i in range(32)]
    df = pd.DataFrame(rows)
    a = select_cases(df, {'0'})
    b = select_cases(df.sample(frac=1, random_state=3), {'0'})
    assert [(x['image_id'], x['a_id']) for x in a] == [(x['image_id'], x['a_id']) for x in b]
    assert not {'0', '1'} & {x['image_id'] for x in a}
    assert len(a) == len({x['image_id'] for x in a})
    assert references({'cases': [{'key': 'closed_image|manual'}, {'code': 'known-21'}]}) == {'closed_image', 'known-21'}
