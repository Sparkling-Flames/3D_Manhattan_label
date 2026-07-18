from __future__ import annotations

import json

import pytest

from tools.thesis_main.registry.init_failure_disposition_rule_manifest import build_manifest


def test_manifest_freezes_all_three_attribution_paths() -> None:
    manifest = build_manifest(locked_round="C2", contract_version="v1")

    assert manifest["meta"]["locked_round"] == "C2"
    assert manifest["worker_caused_structural_failure"]["t1_quality"] == "zero_in_assigned_condition"
    assert manifest["policy_caused_failure"]["v1_itt"] == "included_with_zero_when_not_delivered"
    assert manifest["external_system_failure"]["max_reruns"] == 1
    assert manifest["external_system_failure"]["t1_pair_rule"] == "rerun_or_administratively_censor_whole_pair"


def test_manifest_rejects_non_c2_freeze() -> None:
    with pytest.raises(ValueError, match="C2"):
        build_manifest(locked_round="C1", contract_version="v1")


def test_manifest_is_json_serializable() -> None:
    assert json.loads(json.dumps(build_manifest(locked_round="C2", contract_version="v1")))["meta"]["contract_version"] == "v1"
