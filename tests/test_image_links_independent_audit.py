import pandas as pd

from tools.thesis_main.analysis.image_portrait.image_links_independent_audit import select_family


def test_model_selection_uses_inner_scores_not_outer_results():
    data = pd.DataFrame([
        dict(condition='manual', target='t', building='b', feature='da3__a', inner_loss=.2, inner_n=10, loss=.9),
        dict(condition='manual', target='t', building='b', feature='da3__b', inner_loss=.3, inner_n=10, loss=.1),
    ])
    selected = select_family(data, 'da3')
    assert selected.feature.tolist() == ['da3__a']
    data['loss'] = [100, 0]
    assert select_family(data, 'da3').feature.tolist() == ['da3__a']
