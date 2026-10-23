"""展示合同：失败保留缺失状态，原答和真实满员集合可直接查看。"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "research/workers/personnel_population_curves_v2_20261023/cases/doorway_full_pool_20261024"


def test_failure_types_and_full_annotation_members():
    data = json.loads((CASE / "CASE_DATA.json").read_text(encoding="utf8"))
    endpoints = {row["k"]: row for row in data["endpoints"]}
    full = endpoints[32]
    assert full["nodes"] == 3 and full["score_status"] == "below_four"
    assert all(full["metrics"][key] is None for key in ("B8L2", "D10", "IoU3D100"))
    assert len(full["geometry"]["points"]) == 6
    assert endpoints[10]["nodes"] == 5 and endpoints[10]["score_status"] == "no_connection"
    assert endpoints[10]["geometry"]["points"] is None
    assert {r["worker_id"] for r in data["annotations"]} == set(full["members"])
    assert len(data["annotations"]) == len(set(full["members"])) == 32
    assert all(len(r["points"]) >= 8 and len(r["points"]) % 2 == 0 for r in data["annotations"])
    assert (ROOT / data["image_path"]).is_file()


def test_full_pool_denominator_and_repeated_paths():
    with (CASE / "DOORWAY_FULL_POOL_STATUS.csv").open(encoding="utf-8-sig", newline="") as f:
        pools = list(csv.DictReader(f))
    assert len(pools) == len({r["pool_id"] for r in pools}) == 17
    assert sum(r["complete_evaluable"] == "False" for r in pools) == 6
    with (CASE / "CASE_PREFIXES.csv").open(encoding="utf-8-sig", newline="") as f:
        prefixes = list(csv.DictReader(f))
    assert len(prefixes) == 768
    final = [r for r in prefixes if r["k"] == r["pool_n"]]
    assert len(final) == 24 and len({r["team_key"] for r in final}) == 1
