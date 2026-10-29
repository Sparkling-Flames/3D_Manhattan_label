"""从当前仓库原池快照核对07A的目标身份、结构量和历史权重；不评分或融合。"""
import argparse
import ast
import gzip
import io
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd
from shapely.geometry import Point, Polygon


def audit(repo, downloads):
    # 只加载既有纯几何函数，避免导入报告模块时读取其它实验或设置绘图环境。
    namespace = dict(np=np, Point=Point, Polygon=Polygon, EPS=1e-8)
    modules = {
        "gt_order_visibility_20261009.py": {"classify_ring_x", "cross", "visibility_from_floor"},
        "scope_difficulty_review_20261011.py": {"floor_features"},
        "difficulty_mechanisms_v2_20261020.py": {"reference_traits"},
    }
    for filename, names in modules.items():
        path = repo / "tools/thesis_main/analysis" / filename
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        assert {n.name for n in nodes} == names
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    traits = namespace["reference_traits"]
    square = traits([[-1, -1], [1, -1], [1, 1], [-1, 1]])
    assert (square["ref_turn5"], square["ref_H"], square["ref_short_edges"]) == (4, 0, 0)

    paths = list(downloads.glob("HOHONET_v21_*07A*.zip"))
    assert len(paths) == 1, paths
    with zipfile.ZipFile(paths[0]) as archive:
        pools = pd.read_csv(io.BytesIO(archive.read("targets/POOL_TARGET_CONDITIONS.csv")))
        records = pd.read_csv(io.BytesIO(gzip.decompress(archive.read(
            "targets/RECORD_TARGET_LINKS_AND_ALL_SUPPORT_WEIGHTS.csv.gz"))))
    assert pools.pool_id.is_unique and records.record_id.is_unique
    snapshots = []
    for path in ["pools/INPUT_SNAPSHOT.json", "admitted_space_extension/pools/INPUT_SNAPSHOT.json"]:
        snapshots.extend(json.loads((repo / "research/data/releases/v2.1" / path)
                                    .read_text(encoding="utf-8-sig"))["images"])
    assert len(snapshots) == len(pools) == 294
    assert {x["pool_id"] for x in snapshots} == set(pools.pool_id)
    indexed_pools = pools.set_index("pool_id")
    indexed_records = records.set_index("record_id")
    seen_records = set()
    numeric_max = {key: 0.0 for key in traits([[-1, -1], [1, -1], [1, 1], [-1, 1]])
                   if key != "ref_geometry_status"}
    score_max = {"B8L2": 0.0, "D10": 0.0}
    for snapshot in snapshots:
        row = indexed_pools.loc[snapshot["pool_id"]]
        meta, reference = snapshot["meta"], snapshot["reference"]
        for key in ["image", "image_id", "condition", "building", "reference_id", "reference_version"]:
            assert row[key] == meta[key], (snapshot["pool_id"], key)
        assert row.reference_id == reference["target_id"]
        assert row.pool_n == len(snapshot["records"])
        computed = traits(reference["floor_xz_h"])
        assert computed["ref_geometry_status"] == row.ref_geometry_status
        for key in numeric_max:
            actual, expected = computed[key], row[key]
            if pd.isna(actual) or pd.isna(expected):
                assert pd.isna(actual) and pd.isna(expected), (row.pool_id, key)
            else:
                numeric_max[key] = max(numeric_max[key], abs(float(actual) - expected))
                assert np.isclose(actual, expected, atol=1e-10, rtol=0), (row.pool_id, key)
        challenge = computed["ref_turn5"] > 6 or computed["ref_H"] > 0 or computed["ref_short_edges"] > 0
        assert challenge == row.geometric_challenge
        for original in snapshot["records"]:
            object_id = original["object_id"]
            assert object_id not in seen_records
            seen_records.add(object_id)
            saved = indexed_records.loc[object_id]
            assert saved.pool_id == snapshot["pool_id"] and saved.worker == original["worker"]
            for key in ["reference_id", "reference_version", "condition", "image_id", "building"]:
                assert saved[key] == meta[key], (object_id, key)
            for key in ["B8L2", "D10", "source_time_seconds", "target_time_seconds"]:
                actual, expected = original.get(key), saved[key]
                if actual is None or pd.isna(expected):
                    assert actual is None and pd.isna(expected), (object_id, key)
                else:
                    assert np.isclose(actual, expected, atol=1e-10, rtol=0), (object_id, key)
                    if key in score_max:
                        score_max[key] = max(score_max[key], abs(actual - expected))
    assert seen_records == set(records.record_id) and len(seen_records) == 8385
    history = ["worker", "condition"]
    target = history + ["image_id", "reference_id"]
    image = history + ["image_id"]
    building = history + ["building"]
    expected_weights = (1 / records.groupby(target).record_id.transform("size")
                        / records.groupby(image).reference_id.transform("nunique")
                        / records.groupby(building).image_id.transform("nunique")
                        / records.groupby(history).building.transform("nunique"))
    weight_error = float((expected_weights - records.history_weight_on_this_support).abs().max())
    assert weight_error < 1e-12
    assert np.allclose(records.groupby(history).history_weight_on_this_support.sum(), 1)
    other = pools[pools.scope.eq("other_admitted")]
    assert len(other) == 31 and other.official_difficulty.isna().all()
    assert not other.official_difficulty_inherited_from_other_space.any()
    unique_targets = other.drop_duplicates(["image_id", "reference_id"])
    return dict(
        zip=paths[0].name, pools=len(pools), records=len(records), images=pools.image_id.nunique(),
        targets=len(pools.drop_duplicates(["image_id", "reference_id"])), buildings=pools.building.nunique(),
        scope_counts=records.groupby("scope").size().to_dict(),
        geometry_fields_recomputed_from_local_snapshots=numeric_max,
        saved_quality_comparison_max_abs_difference=score_max,
        history_weight_max_abs_difference=weight_error,
        other_pools=len(other), other_targets=len(unique_targets),
        other_formal_grade_known=int(other.official_difficulty.notna().sum()),
        other_geometry_challenge_pools=int(other.geometric_challenge.sum()),
        other_grade_evidence=unique_targets.difficulty_evidence_status.value_counts().to_dict(),
        source_time_known=int(records.source_time_seconds.notna().sum()),
        target_time_known=int(records.target_time_seconds.notna().sum()),
        boundary="核对现有分数，不重新评分；复算底面结构量，不重跑融合；不作文件哈希。",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--downloads", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.repo, args.downloads)
    text = json.dumps(result, ensure_ascii=False, indent=2, default=int) + "\n"
    args.output.write_text(text, encoding="utf-8")
    print(text)
