import json
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.rebuild_v21_20261028 import ROOT,OUT,read


def test_current_statistics_keep_inventory_masks_and_reference_identity():
    folder=OUT/'descriptive_statistics'
    fields=['object_id','image_id','condition','chosen_target_id','quality_usable','B8L2','D10','data_release','source_active_time_seconds','semi_initial_B8L2','semi_project_gain_B8L2','diagnostic_B8L2','semi_current_gain_available']
    d=pd.read_csv(folder/'shared_records.csv',usecols=fields,low_memory=False)
    q=pd.DataFrame(read(OUT/'quality_inventory.json')).set_index('object_id').loc[d.object_id]
    assert len(d)==10439 and d.object_id.is_unique and d.quality_usable.sum()==8154
    assert d.data_release.eq('v2.1').all()
    assert d.B8L2.notna().equals(d.quality_usable) and d.D10.notna().equals(d.quality_usable)
    assert d.chosen_target_id.fillna('').tolist()==q.chosen_target_id.fillna('').tolist()
    for metric in ['B8L2','D10','source_active_time_seconds']:
        assert np.allclose(pd.to_numeric(d[metric]),pd.to_numeric(q[metric]),atol=1e-9,equal_nan=True)
    semi=d[d.semi_current_gain_available]
    assert len(semi)>0 and np.allclose(semi.semi_project_gain_B8L2,semi.diagnostic_B8L2-semi.semi_initial_B8L2,atol=1e-9)
    contract=read(folder/'FIELD_CONTRACT.json')
    for name,item in contract['tables'].items():
        assert item['data_release']=='v2.1'
        if item['keys']:
            table=pd.read_csv(folder/item['path'],usecols=item['keys'])
            assert not table.duplicated(item['keys']).any(),name


def test_raw_disagreement_reused_without_changing_the_pair_population():
    cols=['image_id','condition','possible_pairs','measurable_pairs','unmeasurable_pairs','R_mean']
    old=pd.read_csv(ROOT/'research/statistics/v2_integrated_analysis_20261019/raw_disagreement_summary.csv',usecols=cols)
    new=pd.read_csv(OUT/'descriptive_statistics/raw_disagreement_summary.csv',usecols=cols)
    pd.testing.assert_frame_equal(new,old)
    interface=read(OUT/'descriptive_statistics/CONSUMER_INTERFACE.json')
    assert interface['data_release']=='v2.1' and interface['no_new_raw_annotation_or_fusion']


def test_added_quality_support_is_not_an_old_version_zero_score():
    d=pd.read_csv(OUT/'QUALITY_COMMON_SUPPORT_COMPARISON.csv')
    assert d.loc[d.support.eq('common'),'records'].sum()==7302
    added=d[d.support.eq('added')]
    assert added.records.sum()==852 and added.B8L2_v2_record_mean.isna().all() and added.B8L2_image_equal_delta.isna().all()
