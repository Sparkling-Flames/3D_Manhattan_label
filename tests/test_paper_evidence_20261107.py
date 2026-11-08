"""Figure checks focus on support identity and membership, not rendering mechanics."""
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
AUDIT = json.loads((ROOT / 'docs/thesis_main/论文写作工作资料/新增图表来源核对_20261107.json').read_text(encoding='utf-8'))
MIX = ROOT / 'research/workers/mixture_patterns_and_c13_half_20261104/mixtures'


def test_difficult_c3_display_replacement_preserves_structural_role():
    data = json.loads((ROOT / 'research/workers/current_class_interpretation_20261104/examples/EXAMPLE_DATA.json').read_text(encoding='utf-8'))
    selected = next(s for s in data['slots'] if s['object_id'] == 'v2:new:103127'
                    and s['method'] == 'TARGET_DSTRUCT_K3')
    assert selected['image'] == 'jtcxE69GiFV-26' and selected['class_id'] == 'C3'
    assert selected['selection_rank'] == 2
    assert (selected['turn_n'], selected['short_turn_edges']) == (8, 3)
    assert np.isclose(selected['source_active_time_seconds'], 1018.229)
    labels = pd.read_csv(ROOT / 'research/workers/current_class_interpretation_20261104/basis/WORKER_LABELS_ALL_LOBO.csv.gz')
    heldout = labels[(labels.worker_id == selected['worker_id'])
                     & (labels.heldout_building == 'jtcxE69GiFV')
                     & (labels.method == 'TARGET_DSTRUCT_K3')]
    assert len(heldout) == 1 and heldout.iloc[0].class_id == 'C3'


def test_mixture_effects_keep_the_seven_way_common_images():
    raw = pd.read_csv(MIX / 'DSTRUCT_SEVEN_COALITIONS_COMMON_Q.csv')
    q = raw.pivot(index='image', columns='classes', values='B8L2')
    assert len(q) == 154 and q.notna().all().all()
    expected = [(q[a] - q[b]).mean() for a, b in [
        ('C1|C2', 'C1'), ('C1|C2', 'C2'), ('C1|C3', 'C1'),
        ('C1|C3', 'C3'), ('C2|C3', 'C2'), ('C2|C3', 'C3')]]
    assert np.allclose(AUDIT['profile_mixtures']['paired_effect_means'], expected)
    # Per-image subtraction, not differences on separately available image populations.
    assert raw.groupby('image').classes.nunique().eq(7).all()


def test_fixed_size_intervals_preserve_actual_finite_team_counts():
    raw = pd.read_csv(MIX / 'SAME_CONFIGURATION_MEMBER_DISTRIBUTIONS.csv.gz')
    for row in AUDIT['composition_members']['rows']:
        source = raw[(raw.method == row['method']) & (raw.panel_id == row['panel_id'])
                     & (raw.class_counts == row['class_counts'])]
        assert len(source) == 1
        source = source.iloc[0]
        assert row['n'] == 12 and row['c1'] + row['c2'] + row['c3'] == 12
        assert 0 < row['valid_teams'] <= row['teams']
        assert row['p05'] <= row['p95']
        assert np.allclose([row[k] for k in ['mean', 'p05', 'p95', 'valid_teams']],
                           [source[k] for k in ['mean', 'p05', 'p95', 'valid_teams']])


def test_complete_evaluable_curve_keeps_full_attempt_denominator():
    path = ROOT / 'research/workers/image_response_v21_20261101/HOHONET_v21_image_response_20261101/stage07_summary/manual/FIXED_PANEL_CURVES.csv.gz'
    raw = pd.read_csv(path)
    rows = raw[(raw.panel == 'ordinary_manual_main__capacity_ge30')
               & (raw.metric == 'complete_evaluable_rate') & (raw.stratum == 'all')]
    assert sorted(rows.k.tolist()) == list(range(3, 31))
    assert rows.capacity_images.eq(171).all()
    assert rows.valid_path_rows.eq(171 * 256).all()
    assert rows.mean_image_equal.between(0, 1).all()
    rates = rows.set_index('k').mean_image_equal * 100
    assert np.isclose(rates[6] - rates[3], -1.857, atol=.0005)
    assert np.isclose(rates[30] - rates[20], .420, atol=.0005)


def test_cohort_table_distinguishes_primary_and_assisted_subsets():
    rows = pd.read_csv(ROOT / 'research/data/releases/v2.1/quality_records.csv', low_memory=False)
    assert len(rows) == rows.object_id.nunique() == 8154
    assert rows.image_id.nunique() == 225
    for condition, counts in [('manual', (6512, 206, 60, 22)), ('semi', (960, 37, 59, 12))]:
        subset = rows[(rows.condition == condition) & (rows.quality_use == 'ordinary_primary')]
        assert (len(subset), subset.image_id.nunique(), subset.worker_id.nunique(), subset.building_id.nunique()) == counts


def test_labor_table_keeps_quality_and_time_supports_separate():
    base = ROOT / 'research/workers/personnel_full_chain_v21_20261030'
    rows = pd.read_csv(base / 'HOHONET_v21_full_chain_20261030/stage05_selection_stop/stopping/RELATION_LAYER_STOPPING_SUMMARY.csv')
    rows = rows[(rows.relation_layer == 'no_pending_direct_relations')
                & (rows.history_budget == 'maximum_history') & (rows.panel == 'whole_group')
                & (rows.support == 'all_attempts') & (rows.policy == 'source_within2_min3_geometry')]
    full = rows[rows.time_support == 'all_groups'].iloc[0]
    timed = rows[rows.time_support == 'all_new_complete_time'].iloc[0]
    assert (full.groups, full.images) == (5, 21)
    assert (timed.groups, timed.images) == (3, 11)
    assert np.isclose(full.q_mean, 86.054, atol=.0005)
    assert np.isclose(timed.mean_activity_seconds, 1660.3, atol=.05)


def test_same_room_example_keeps_people_references_and_adopted_geometry():
    base = ROOT / 'research/fusion/manual_order_impact_20261104'
    records = {}
    for path in [base / 'same_room/RECOVERED_AUTOMATIC_ENDPOINTS.jsonl.gz',
                 base / 'endpoints/ENDPOINTS.jsonl.gz']:
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            for row in map(json.loads, f):
                records[row['team_key']] = row
    events = pd.read_csv(base / 'same_room/ASSISTED_CURRENT_EVENTS.csv.gz', low_memory=False)
    selected = AUDIT['same_room_transfer']['selected_event']
    ev = events[(events.event_id == selected) & (events.method_updated == 'TARGET_DSTRUCT_K3')]
    assert len(ev) == 1
    ev = ev.iloc[0]
    assert ev.n == 10 and ev.m == 5 and ev.B8L2_common6
    for side in ['a', 'b']:
        b, c = [records[ev[f'team_key_{arm}_{side}']] for arm in ['B', 'C']]
        assert set(b['member_workers']) == set(ev.B_members.split('|'))
        assert set(c['member_workers']) == set(ev.C_members.split('|'))
        assert b['reference_id'] == c['reference_id'] == ev['reference_id_' + side]
        assert np.isclose(c['B8L2'] - b['B8L2'], ev['B8L2_CB_' + side])
        assert b['geometry']['footprint'] and c['geometry']['footprint']
