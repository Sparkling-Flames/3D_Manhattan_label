import pandas as pd
from tools.thesis_main.analysis.worker_four_axis_update_20261015 import scope_target, apply_scope_hold


def test_unknown_and_difficult_are_not_automatic_scope_errors():
    assert scope_target('clear') == 'in_scope'
    for scene in ['doorway_difficult','doorway_annotatable','oos','unflagged']:
        assert scope_target(scene) is None


def test_new_scope_hold_preserves_different_difficulty_target_rows():
    rows=pd.DataFrame(dict(record_id=['a','b','c'],WQ=[1,2,3]))
    binding=pd.DataFrame(dict(record_id=['a','b','c'],new_scope_binding_pending=[True,False,False],
        use_panel=['hold_scope_or_reference','floor_only_target_equivalence','image_only_different_target']))
    kept,held=apply_scope_hold(rows,binding)
    assert kept.record_id.tolist()==['b','c'] and held.record_id.tolist()==['a']
