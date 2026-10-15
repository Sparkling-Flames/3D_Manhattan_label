import pandas as pd
import pytest

from pathlib import Path

from tools.thesis_main.analysis.descriptive_statistics_figures_20261015 import figure_manifest, primary_pairs, select_panels


def test_panel_denominators_keep_overlap_missing_and_time_source():
    records = pd.DataFrame(dict(inventory_record_id=['a','b','c'], WQ=[30.,60.,None],
                                in_worker_931=[True,True,False], in_target_836=[True,False,False],
                                time_status=['usable','lead_time_fallback','usable'],
                                active_time_seconds=[20.,None,40.]))
    assert [len(panel) for panel in select_panels(records).values()] == [3,2,2,1]
    with pytest.raises(AssertionError):
        select_panels(records.assign(active_time_seconds=[20.,90.,40.]))
    with pytest.raises(AssertionError, match='duplicate'):
        select_panels(pd.concat([records,records.iloc[:1]]))


def test_primary_pairs_do_not_upgrade_support_or_sparse_pairs():
    rows = pd.DataFrame(dict(image_a=['a']*4,image_b=['b','c','d','e'],
                             relation=['confirmed_comparable','supported_other','confirmed_comparable','confirmed_comparable'],
                             metric=['WQ','WQ','WQ','B8L2'], n_pairs=[4,8,3,8]))
    assert primary_pairs(rows).image_b.tolist() == ['b']


def test_manifest_keeps_algorithm_versions_and_reuse_boundary_explicit():
    contract = dict(version='schema_v1', protocol='research_v1', sources=['frozen.csv'],
                    score_versions=dict(WQ='wq_version', A10='a_version', B8L2='b_version'),
                    iou_units=dict(IoU3D100='0-100; mean-height prism', same_room_iou_3d='0-1'),
                    time_unit='seconds')
    manifest = figure_manifest(contract, Path('snapshot'))
    assert [manifest['metrics'][m]['version'] for m in ['WQ','A10','B8L2']] == ['wq_version','a_version','b_version']
    assert manifest['metrics']['IoU3D100']['version'] is None
    assert manifest['long_score_interface_consumed'] is False
