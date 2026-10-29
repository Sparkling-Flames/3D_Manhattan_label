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
