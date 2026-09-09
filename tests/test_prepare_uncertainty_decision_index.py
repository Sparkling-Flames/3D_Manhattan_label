import pandas as pd
import pytest

from tools.thesis_main.data_prep.prepare_uncertainty_decision_index import join_index


def test_join_preserves_missing_time_and_requires_complete_semi_trace():
    a = pd.DataFrame({'canonical_annotation_id': ['a', 'b'], 'raw_condition': ['manual', 'semi']})
    links = a[['canonical_annotation_id']].assign(partition_ids_json='[]', model_layout_ids_json='[]', reference_ids_json='[]', actual_proposal_ids_json='[]')
    times = a[['canonical_annotation_id']].assign(active_time_seconds='', active_time_formal_available='false', timing_status='unknown', active_time_source='')
    trace = pd.DataFrame([dict(canonical_annotation_id='b', legacy_initialization_source_kind='missing_required_initialization', initial_import_match_status='all_matching', initial_model_checkpoint_status='not_bound', initialization_reconstructed_source='import_payload', initial_trace_interpretation='not_a_view_event')])
    got = join_index(a, links, times, trace)
    assert list(got.canonical_annotation_id) == ['a', 'b']
    assert list(got.active_time_seconds) == ['', '']
    assert got.iloc[1].legacy_initialization_source_kind == 'missing_required_initialization'
    assert got.iloc[1].initialization_reconstructed_source == 'import_payload'
    with pytest.raises(ValueError, match='trace coverage'):
        join_index(a, links, times, trace.iloc[:0])
