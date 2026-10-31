"""The release must point to real, unambiguous adopted experiments."""

import csv
import gzip
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_adoption_resolves_conditions_and_lobo_labels_without_relabeling_baselines():
    release = json.loads((ROOT / 'research/data/releases/v2.1/RELEASE.json').read_text(encoding='utf-8'))
    adopted = release['personnel_reselection']
    for field in ('source_root', 'import_receipt', 'independent_review', 'conditions',
                  'image_results', 'labels', 'frozen_baseline', 'dependency_report',
                  'dependency_table', 'adopted_results', 'workbench', 'same_room_fixed_panels'):
        assert (ROOT / adopted[field]).exists(), field
    with (ROOT / adopted['conditions']).open(encoding='utf-8-sig', newline='') as stream:
        conditions = list(csv.DictReader(stream))
    with gzip.open(ROOT / adopted['labels'], 'rt', encoding='utf-8-sig', newline='') as stream:
        labels = list(csv.DictReader(stream))
    for selected in adopted['main_exchange_conditions']:
        matches = [row for row in conditions if row['method'] == selected['method']
                   and int(row['n']) == selected['n'] and int(row['m']) == selected['m']
                   and row['scope'] == selected['scope']]
        assert len(matches) == 1, selected
        row = matches[0]
        for field in ('axis', 'rank_direction'):
            if field in selected:
                assert row[field] == selected[field]
        assert 0 < int(row['B8L2_CB_valid_images']) <= int(row['images'])
        assert 0 < int(row['ABC_scored_events']) <= int(row['events'])
        assert any(item['method'] == selected['method'] for item in labels)
    assert adopted['full_downstream_reclassified'] is False
    dependencies = adopted['class_dependent_downstream']
    assert dependencies['large_pool_class_priority_policy32'].startswith('not_rebuilt')
    assert dependencies['same_room_new_family'].startswith('not_rebuilt')
    assert release['full_mainline_including_other_targets_complete'] is False


def test_current_working_results_do_not_relabel_frozen_experiments():
    release = json.loads((ROOT / 'research/data/releases/v2.1/RELEASE.json').read_text(encoding='utf-8'))
    working = release['personnel_reselection']
    assert working['classification_finalized'] is True
    assert working['status'] == 'dstruct_classification_rfuse_explanation_joint_profile_adopted'
    assert working['labels'] != working['current_working_labels']
    for field in ('current_working_labels', 'current_working_label_results',
                  'q_only_review', 'structure_Q_diagnostic'):
        assert (ROOT / working[field]).is_file(), field
    assert release['other_admitted_spaces']['pending'] == []
    assert release['full_mainline_including_other_targets_complete'] is False
    current = json.loads((ROOT / 'research/data/releases/CURRENT.json').read_text(encoding='utf-8'))
    assert current['data_release'] == 'v2'


def test_doorway_delivery_keeps_scope_and_reproduction_boundaries():
    release = json.loads((ROOT / 'research/data/releases/v2.1/RELEASE.json').read_text(encoding='utf-8'))
    doorway = release['doorway_space_dual_version_20261031']
    for field in ('handoff', 'results', 'workbench', 'current_release', 'effective_screening_ledger', 'gt_visual_shortlist'):
        assert (ROOT / doorway[field]).is_file(), field
    rows = json.loads((ROOT / doorway['frozen553_sources']['ledger']).read_text(encoding='utf-8'))
    base = [r for r in rows if r['base_candidate']]
    assert doorway['scope_field'] == 'final_scope'
    excluded = sum(r['final_scope'] == '都不符合（看不懂）' for r in base)
    assert len(base) == doorway['base_records'] == 584
    assert excluded == 31
    assert doorway['excluded_records'] == 145
    assert len(base) - excluded == 553
    assert doorway['screened_records'] == 439
    assert doorway['exclude13_sensitivity_team_sizes'] == [6, 10]
    for field in ('global_eligibility_rewritten', 'gt_revision_performed',
                  'full_curve_sensitivity_complete', 'self_contained_archive', 'browser_acceptance'):
        assert doorway[field] is False
