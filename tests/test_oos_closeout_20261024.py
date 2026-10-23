"""Focused OOS denominator, provenance and reference-free geometry checks."""
import gzip
import json

import pandas as pd
import pytest
from shapely.geometry import Polygon

from tools.thesis_main.analysis import oos_closeout_20261024 as m


def test_pair_denominators_do_not_turn_missing_into_agreement():
    pairs = pd.DataFrame(dict(floor_pair_measurable=[True, False, False],
                              R_union_normalized=[.3, None, None], same_pair_count=[True, False, None]))
    result = m.pair_summary(pairs)
    assert result["pair_n"] == 3 and result["measurable_pair_n"] == 1
    assert result["comparable_node_pair_n"] == 2
    assert result["R_pair_union_mean"] == .3 and result["different_node_count_rate"] == .5


def test_adopted_overlap_and_holds():
    labels = pd.read_csv(m.OUT / "adopted_factors.csv")
    data = pd.read_csv(m.OUT / "record_diagnostics.csv.gz")
    assert len(labels) == 28 and len(labels.factors.str.split("|").explode()) == 29
    assert labels.set_index("image_code").loc["uNb9QFRL6hY-69", "factors"] == "多标高地面／楼梯挑空|多标高天花板"
    assert data.analysis_pool.sum() == 1051 and data.quality_usable.sum() == 0
    held = data[data.image_code.isin(["b8cTxDM8gDG-04", "pRbA3pwrgk9-16", "uNb9QFRL6hY-51", "x8F5xyUWy9e-01"])]
    assert len(held) == 140 and not held.analysis_pool.any()
    assert held.feature_status.eq("outside_existing_pool").all()


def test_scope_source_and_image_weighting():
    data = pd.read_csv(m.OUT / "record_diagnostics.csv.gz")
    images = pd.read_csv(m.OUT / "image_condition_source.csv")
    factors = pd.read_csv(m.OUT / "factor_condition_source.csv")
    old = data[data.origin.eq("v1")]
    assert old.historical_raw_scope.notna().sum() == 418
    assert old.scope_response.isna().sum() == 207
    assert images.loc[images.origin.eq("v1"), "scope_out_rate"].isna().all()
    assert data.query("origin == 'new'").scope_response.eq("out_of_scope").sum() == 327
    source = images[images.origin.eq("new") & images.image_code.str.startswith("S9")]
    result = factors[(factors.origin == "new") & (factors.factor == "斜顶")].iloc[0]
    assert len(source) == 3 and result.R_image_n == 3
    assert result.R_image_mean == pytest.approx(source.R_pair_union_mean.mean())


def test_saved_pair_geometry_independent_spot_checks():
    records = json.load(gzip.open(m.EVIDENCE, "rt", encoding="utf8"))["records"]
    records = {r["object_id"]: r for r in records if r["is_oos"]}
    pairs = json.load(gzip.open(m.TABLES, "rt", encoding="utf8"))["tables"]["statistics__raw_answer_pairs"]
    checked = set()
    for pair in pairs:
        a, b = pair["object_id_a"], pair["object_id_b"]
        if a not in records or b not in records or not pair["floor_pair_measurable"]:
            continue
        code = records[a]["image_code"]
        if code in checked:
            continue
        _, ga = m.geometry_features(records[a]["points_1024x512"])
        _, gb = m.geometry_features(records[b]["points_1024x512"])
        pa, pb = Polygon(ga["floor"]), Polygon(gb["floor"])
        actual = pa.symmetric_difference(pb).area / pa.union(pb).area
        assert actual == pytest.approx(pair["R_union_normalized"], abs=1e-10)
        checked.add(code)
    assert len(checked) == 24


def test_legacy_fusion_keeps_versions_and_unique_full_teams():
    fusion = pd.read_csv(m.OUT / "legacy_fusion_coverage.csv")
    wall = fusion[fusion.source.eq("v1_wall_random")]
    assert len(wall) == 21 and wall.image_code.nunique() == 19
    assert wall.states.sum() == 1212 and wall.complete_geometry_states.sum() == 1064
    assert wall.full_pool_complete.eq(True).sum() == 19
    assert fusion.image_code.nunique() == 22 and not fusion.formal_Q_allowed.any()
