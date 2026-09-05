import numpy as np
import pytest
from PIL import Image

from tools.thesis_main.data_prep.build_annotation_research_review50_20260905 import (
    select_images, projected_segments, validate_advisory, normalize_image,
)


def test_selection_is_order_invariant_exact_and_preserves_exclusions():
    rows = [dict(image_id=f"{b}_{i}", building_id=b, max_mask_difference=i / 10)
            for b in ("A", "B") for i in range(8)]
    first = select_images(rows, {"A": 5, "B": 4}, {"A_7"}, seed=17)
    second = select_images(list(reversed(rows)), {"B": 4, "A": 5}, {"A_7"}, seed=17)
    assert first == second
    assert len({r["image_id"] for r in first}) == 9
    assert "A_7" not in {r["image_id"] for r in first}
    assert sum(r["selection_role"] == "seeded_coverage" for r in first) == 5
    with pytest.raises(ValueError, match="capacity"):
        select_images(rows, {"A": 9}, set())


def test_panorama_edges_are_curved_and_do_not_draw_across_the_seam():
    pieces = projected_segments([128, 100], [384, 100], ceiling=True)
    xy = np.concatenate(pieces)
    assert xy[:, 1].min() < 90  # a 3D horizontal line projects to a curve
    seam = projected_segments([950, 100], [60, 100], ceiling=True)
    assert len(seam) == 2
    assert all(np.max(np.abs(np.diff(p[:, 0]))) <= 1 for p in seam)


def test_machine_advice_cannot_claim_a_human_decision():
    ids = {"R50-001"}
    validate_advisory({"items": [{"review_id": "R50-001", "advisory_only": True}]}, ids)
    with pytest.raises(ValueError):
        validate_advisory({"items": [{"review_id": "R50-001", "advisory_only": False}]}, ids)
    with pytest.raises(ValueError):
        validate_advisory({"items": [{"review_id": "R50-001", "advisory_only": True, "human_review": {"scope": "in_scope"}}]}, ids)


def test_source_resolution_is_explicitly_rescaled_to_model_coordinates():
    assert normalize_image(Image.new('RGB', (2048, 1024))).size == (1024, 512)
    with pytest.raises(ValueError, match='dimensions'):
        normalize_image(Image.new('RGB', (1024, 768)))
