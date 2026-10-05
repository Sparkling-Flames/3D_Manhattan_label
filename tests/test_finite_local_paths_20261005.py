"""Regression checks for the local research fork; no semantic deletion rule."""
import json
from pathlib import Path

from tools.thesis_main.analysis import finite_local_paths_20261005 as paths

ARCHIVE = Path(__file__).resolve().parents[1]/'research/local_path_research_20261005/pro_original'


def test_budget_exclusions_cover_every_admissible_candidate():
    candidates = json.loads((ARCHIVE/'results/final/finite/all_candidates.json').read_text(encoding='utf-8'))
    domain = json.loads((ARCHIVE/'inputs/domain.json').read_text(encoding='utf-8'))
    original = json.loads((ARCHIVE/'results/final/finite/policy_outputs_before_truth.json').read_text(encoding='utf-8'))
    for old in original:
        if old['policy']['kind'] != 'budget_compact':
            continue
        new = paths.policy_select(candidates, domain, old['policy'])
        assert new['candidate_ids'] == old['candidate_ids']
        selected, excluded = set(new['candidate_ids']), set(new['excluded'])
        assert not selected & excluded
        assert selected | excluded == {c['id'] for c in candidates if c['admissible']}
        added = set(new['excluded']) - set(old['excluded'])
        assert len(added) == (9 if old['policy']['budget_h'] == .05 else 21)
        assert {new['excluded'][c] for c in added} == {'eligible_but_more_knots'}


def test_json_output_is_order_independent_and_uses_lf(tmp_path):
    a, b = tmp_path/'a.json', tmp_path/'b.json'
    paths.dump(a, {'z': {'b': 2, 'a': 1}, 'a': 0})
    paths.dump(b, {'a': 0, 'z': {'a': 1, 'b': 2}})
    assert a.read_bytes() == b.read_bytes()
    assert b'\r' not in a.read_bytes()
