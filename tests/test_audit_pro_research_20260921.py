import pandas as pd

from tools.thesis_main.analysis.audit_pro_research_20260921 import roster_features


def test_outer_heldout_roster_applies_to_training_and_test_images():
    views = {
        'train': {'building': 'A', 'workers': ['W1', 'W2']},
        'test': {'building': 'B', 'workers': ['W1', 'W3']},
    }
    roster = pd.DataFrame([
        {'heldout_building': b, 'config': 'Q_2', 'worker': w, 'subtype': t}
        for b, w, t in [('A', 'W1', 1), ('A', 'W2', 1),
                        ('B', 'W1', 2), ('B', 'W2', 1)]
    ])
    features = roster_features(views, roster, 'B')
    assert features.loc['train'].tolist() == [0.5, 0.0]
    assert features.loc['test'].tolist() == [0.0, 0.5]
