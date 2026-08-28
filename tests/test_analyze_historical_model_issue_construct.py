from tools.thesis_main.analysis.analyze_historical_model_issue_construct import aggregate_p1


def _fact(proposal: str, image: str, truth: str) -> dict[str, str]:
    return {
        "stage": "P1",
        "proposal_id": proposal,
        "image_id": image,
        "building_id": "b",
        "initial_geometry_hash": f"hash-{proposal}",
        "initial_points_json": "[]",
        "initialization_source_kind": "control_natural",
        "reference_sha256_set_json": "[]",
        "reference_type_set_json": "[]",
        "planned_trap_family_set_json": f'["{truth}"]',
        "trap_family_set_json": f'["{truth}"]',
    }


def _responses(proposal: str, choices: list[str]) -> list[dict[str, str]]:
    return [
        {
            "stage": "P1",
            "proposal_id": proposal,
            "worker_id": str(index),
            "model_issue_choice_set_json": choice,
        }
        for index, choice in enumerate(choices)
    ]


def test_aggregate_keeps_multilabel_and_truth_selection_separate() -> None:
    choices = ['["corner_duplicate"]'] * 14 + ['["corner_duplicate","over_parsing"]'] * 4 + ['["acceptable"]'] * 8
    images, families = aggregate_p1([_fact("p", "image", "corner_duplicate")], _responses("p", choices))
    row = images[0]
    assert row["truth_selected_count"] == 18
    assert row["exact_truth_set_count"] == 14
    assert row["multi_issue_count"] == 4
    assert row["acceptable_count"] == 8
    assert families[0]["truth_selected_rate"] == 18 / 26
