import pandas as pd
import pytest

from tools.thesis_main.analysis.compare_admitted_space_classifications_20261029 import align_labels, compare, normalize


def rows(labels, known=None):
    known = known or [True] * len(labels)
    return pd.DataFrame([dict(worker_id=f'W{i}', condition='manual', method='RFUSE_GEOM_K2',
                              heldout_building='ALL', known=k, class_id=label, all_images=10+i)
                         for i, (label, k) in enumerate(zip(labels, known))])


def test_relabeling_does_not_become_person_change():
    old = normalize(rows(['C1', 'C1', 'C2', 'C2']), 'fusion')
    new = normalize(rows(['C2', 'C2', 'C1', 'C1']), 'fusion')
    summary, people = compare(old, new)
    row = summary.iloc[0]
    assert row.changed_raw_id == 4
    assert row.changed_after_alignment == 0
    assert row.ari == pytest.approx(1)
    assert not people.partition_changed_after_alignment.any()


def test_real_change_and_known_support_are_distinct():
    old = normalize(rows(['C1', 'C1', 'C2', None], [True, True, True, False]), 'fusion')
    new = normalize(rows(['C1', 'C2', 'C2', 'C1']), 'fusion')
    summary, people = compare(old, new)
    row = summary.iloc[0]
    assert (row.common_known, row.gained_known, row.lost_known) == (3, 1, 0)
    assert row.changed_after_alignment == 1
    assert people.loc[people.worker_id.eq('W3'), 'support_state'].iloc[0] == 'gained_known'
    assert pd.isna(people.loc[people.worker_id.eq('W3'), 'partition_changed_after_alignment'].iloc[0])


def test_ambiguous_mapping_is_disclosed():
    mapping, ambiguous = align_labels(['a', 'a', 'b', 'b'], ['x', 'y', 'x', 'y'])
    assert len(mapping) == 2
    assert ambiguous


def test_new_person_is_counted_without_forcing_a_label_change():
    old = normalize(rows(['C1', 'C2']), 'fusion')
    new = normalize(rows(['C1', 'C2', 'C1']), 'fusion')
    summary, people = compare(old, new)
    assert (summary.iloc[0].roster_old, summary.iloc[0].roster_extended) == (2, 3)
    assert summary.iloc[0].gained_known == 1
    assert people.loc[people.worker_id.eq('W2'), 'support_state'].iloc[0] == 'gained_known'


def test_unknown_and_duplicate_identifiers_rejected():
    with pytest.raises(ValueError, match='known label missing'):
        normalize(rows([None]), 'fusion')
    d = rows(['C1'])
    with pytest.raises(ValueError, match='duplicate'):
        normalize(pd.concat([d, d]), 'fusion')
