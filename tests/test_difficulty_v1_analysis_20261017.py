import pandas as pd
import json
from pathlib import Path

from tools.thesis_main.analysis.difficulty_v1_analysis_20261017 import group_summary, worker_pairs


def test_group_summary_keeps_computation_separate_from_quality_and_missing_time():
    rows = pd.DataFrame([
        dict(object_id='a', image_id='i1', worker_id='w1', building_id='b1', calculation_status='full_computed',
             quality_usable=True, quality_use='ordinary_primary', B8L2=80., D10=82., source_active_time_seconds=40.,
             target_matched_time_seconds=None, pool_min3_pass=True),
        dict(object_id='b', image_id='i1', worker_id='w2', building_id='b1', calculation_status='full_computed',
             quality_usable=False, quality_use='not_qualified', B8L2=None, D10=None, source_active_time_seconds=None,
             target_matched_time_seconds=None, pool_min3_pass=True),
        dict(object_id='c', image_id='i2', worker_id='w1', building_id='b2', calculation_status='input_uncomputable',
             quality_usable=False, quality_use='not_qualified', B8L2=None, D10=None, source_active_time_seconds=70.,
             target_matched_time_seconds=None, pool_min3_pass=False),
    ])
    result = group_summary(rows, quality_use='ordinary_primary')
    assert result['inventory_n'] == 3 and result['quality_n'] == 1
    assert result['full_computed_n'] == 2 and result['computed_but_not_quality_n'] == 1
    assert result['input_uncomputable_n'] == 1 and result['pool_under3_n'] == 1
    assert result['quality_source_time_n'] == 1 and result['quality_target_time_n'] == 0
    assert result['B8L2_mean'] == 80 and result['D10_mean'] == 82


def test_worker_pairs_use_only_workers_present_in_both_groups():
    rows = pd.DataFrame([
        dict(worker_id='w1', condition='manual', stratum='简单', quality_n=5, quality_images=2, B8L2_mean=80., D10_mean=82., B8L2_p10=70., D10_p10=72.,
             source_time_n=5, source_time_mean=30.,input_uncomputable_rate=0.),
        dict(worker_id='w1', condition='manual', stratum='困难', quality_n=4, quality_images=2, B8L2_mean=60., D10_mean=63., B8L2_p10=None, D10_p10=None,
             source_time_n=0, source_time_mean=None,input_uncomputable_rate=.25),
        dict(worker_id='w2', condition='manual', stratum='简单', quality_n=7, quality_images=3, B8L2_mean=70., D10_mean=71., B8L2_p10=65., D10_p10=66.,
             source_time_n=7, source_time_mean=20.,input_uncomputable_rate=.10),
    ])
    paired = worker_pairs(rows, '简单', '困难', 'manual')
    assert len(paired) == 1 and paired.iloc[0].worker_id == 'w1'
    assert paired.iloc[0].B8L2_delta == -20 and paired.iloc[0].D10_delta == -19
    assert paired.iloc[0].uncomputable_rate_delta == .25
    assert pd.isna(paired.iloc[0].source_time_delta)


def test_fusion_fixed_panel_has_complete_pools_and_unchanged_k_denominator():
    root=Path(__file__).resolve().parents[1]
    own=root/'research/difficulty/difficulty_v1_analysis_20261017'
    fusion=root/'research/fusion/wall_consensus_v1_process_20261017'
    panel=json.loads((own/'fusion_panel.json').read_text(encoding='utf-8'))['pool_ids']
    selected=pd.read_csv(own/'fusion_fixed_pool_k.csv')
    completed=pd.read_csv(fusion/'completion.csv')
    assert set(panel) <= set(completed.loc[completed.status.eq('completed'),'pool_id'])
    assert len(panel)==selected.pool_id.nunique()==selected.image.nunique()
    assert set(selected.k)=={3,4,6}
    assert selected.groupby('pool_id').k.apply(lambda k:set(k)=={3,4,6}).all()
    assert selected.path_states.eq(4).all()
    assert selected.groupby('k').path_states.sum().eq(4*len(panel)).all()
