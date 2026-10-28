import importlib.util
import pandas as pd
from tools.thesis_main.analysis.refit_v21_condition_classes_20261028 import CORE, TARGET
from tools.thesis_main.analysis.rebuild_v21_20261028 import OUT, read


def test_scores_and_target_building_exclusion():
    raw=pd.read_csv(TARGET/'RAW_CONDITION_RESPONSE_RECORDS.csv.gz',low_memory=False)
    quality=pd.DataFrame(read(OUT/'quality_inventory.json')).set_index('object_id')
    assert raw.object_id.is_unique and len(raw)==8154
    assert (raw.B8L2-raw.object_id.map(quality.B8L2)).abs().max()<1e-10
    spec=importlib.util.spec_from_file_location('condition_test_native',CORE)
    core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    labels=pd.read_csv(TARGET/'LABELS_ALL_LOBO.csv.gz')
    roster=labels[['worker_id','origin']].drop_duplicates().sort_values('worker_id')
    fold=sorted(raw.building.unique())[0]
    got=core.history(raw,roster,fold).set_index('worker_id').sort_index()
    # Changing every held-out outcome must leave its training history unchanged.
    perturbed=raw.copy()
    for field in core.BASE_METRICS:
        perturbed.loc[perturbed.building.eq(fold),field+'_peer']=1e6
    again=core.history(perturbed,roster,fold).set_index('worker_id').sort_index()
    pd.testing.assert_frame_equal(got,again)
    saved=pd.read_csv(TARGET/'HISTORY_FEATURES_ALL_LOBO.csv.gz')
    saved=saved[saved.heldout_building.eq(fold)].set_index('worker_id').sort_index()
    pd.testing.assert_frame_equal(got,saved[got.columns],check_dtype=False,atol=1e-10)
