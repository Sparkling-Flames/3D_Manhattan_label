"""从冻结结果提取门洞满员失败案例；不运行融合、评分或分类。"""
from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "research/workers/personnel_population_curves_v2_20261023"
OUT = SOURCE / "cases/doorway_full_pool_20261024"
IMAGE = "7y3sRwLe3Va-06"
INPUT = ROOT / "research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz"


def rows(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def write_csv(name, data):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)


def main():
    with gzip.open(INPUT, "rt", encoding="utf8") as handle:
        pool = next(p for p in json.load(handle)["images"] if p["meta"]["image"] == IMAGE and p["meta"]["condition"] == "manual")
    pid = pool["pool_id"]
    prefixes = []
    full = {}
    for row in rows(SOURCE / "stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz"):
        if row["policy"] != "natural_random":
            continue
        if row["layer"] == "doorway_manual" and row["k"] == row["pool_n"]:
            if row["pool_id"] in full:
                assert full[row["pool_id"]]["team_key"] == row["team_key"]
            full[row["pool_id"]] = row
        if row["pool_id"] == pid:
            prefixes.append(row)
    failures = [r for r in full.values() if r["complete_evaluable"] == "False"]
    assert len(full) == 17 and len(failures) == 6
    assert len({r["path_id"] for r in prefixes}) == 24
    assert len(prefixes) == 24 * 32
    # 固定自然路径0，避免按某个前缀的分数挑选故事。
    selected = [r for r in prefixes if r["path_id"] == pid + "__path0" and int(r["k"]) in (3, 10, 20, 32)]
    assert {int(r["k"]) for r in selected} == {3, 10, 20, 32}
    keys = {r["team_key"] for r in selected}
    scalars = {r["team_key"]: r for r in rows(SOURCE / "results/ENDPOINT_SCALARS.csv.gz") if r["team_key"] in keys}
    with gzip.open(SOURCE / "results/ENDPOINT_GEOMETRY.json.gz", "rt", encoding="utf8") as handle:
        geometries = {r["team_key"]: r for r in json.load(handle) if r["team_key"] in keys}
    assert scalars.keys() == geometries.keys() == keys
    final = scalars[full[pid]["team_key"]]
    assert final["nodes"] == "3" and final["minimum_support"] == "16"
    assert final["score_status"] == "below_four" and not final["B8L2"]
    assert int(final["identity_groups_n"]) == 14 and int(final["unselected_groups_n"]) == 11
    assert {r["worker_id"] for r in pool["records"]} == set(final["member_workers"].split("|"))
    assert len(pool["records"]) == 32
    endpoints = []
    metric_names = ("B8L2", "D10", "IoU3D100", "S_bottom_deg", "dir", "Hmean", "Hcenter", "iou_2d")
    for prefix in sorted(selected, key=lambda r: int(r["k"])):
        scalar = scalars[prefix["team_key"]]
        stored = geometries[prefix["team_key"]]
        points = stored["geometry"]["points"]
        if points is None:
            assert scalar["complete_evaluable"] == "False"
        else:
            assert len(points) == 2 * int(scalar["nodes"])
        assert sorted(stored["node_supports"]) == sorted(map(int, scalar["node_supports"].split("|")))
        endpoints.append({
            "team_key": prefix["team_key"], "path_id": prefix["path_id"], "k": int(prefix["k"]),
            "members": scalar["member_workers"].split("|"),
            "minimum_support": int(scalar["minimum_support"]), "nodes": int(scalar["nodes"]),
            "identity_groups_n": int(scalar["identity_groups_n"]),
            "unselected_groups_n": int(scalar["unselected_groups_n"]),
            "complete_evaluable": scalar["complete_evaluable"] == "True", "score_status": scalar["score_status"],
            "metrics": {key: float(scalar[key]) if scalar[key] else None for key in metric_names},
            "geometry": stored["geometry"], "selected_node_supports": stored["node_supports"],
        })
    assert sorted(endpoints[-1]["selected_node_supports"]) == [19, 25, 26]
    assert len(endpoints[-1]["geometry"]["points"]) == 6
    image_path = "data/mp3d_layout/test/img/" + pool["meta"]["image_id"] + ".png"
    assert (ROOT / image_path).is_file()
    data = {
        "schema": "doorway_saved_full_pool_case_v1", "data_release": "v2", "image": IMAGE,
        "image_path": image_path, "coordinate_size": [1024, 512], "pool_meta": pool["meta"],
        "reference": pool["reference"], "annotations": pool["records"], "endpoints": endpoints,
        "context": {"doorway_full_pools": 17, "incomplete_full_pools": 6, "natural_paths": 24,
                    "case_prefix_rows": len(prefixes), "chosen_path": pid + "__path0"},
        "limits": ["节点票数来自已保存结果；未保存的11个未入选组明细不重新推断。",
                   "selected_node_supports没有逐节点ID绑定，不按数组顺序将票数贴到具体角点。",
                   "满员三节点候选不能视为合格完整布局；缺失Q不填0，已有诊断几何仍可展示。",
                   "原答是冻结输入中的完整处理点和环序，未重新排序或补点。"],
        "sources": [str(p.relative_to(ROOT)).replace("\\", "/") for p in
                    [INPUT, SOURCE / "results/ENDPOINT_SCALARS.csv.gz", SOURCE / "results/ENDPOINT_GEOMETRY.json.gz",
                     SOURCE / "stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz"]],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "CASE_DATA.json").write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf8")
    write_csv("CASE_PREFIXES.csv", prefixes)
    write_csv("SELECTED_ENDPOINT_SCALARS.csv", [scalars[r["team_key"]] for r in sorted(selected, key=lambda r: int(r["k"]))])
    fields = ["image", "pool_id", "pool_n", "team_key", "nodes", "complete_evaluable", "B8L2", "geometry_status", "order_status"]
    write_csv("DOORWAY_FULL_POOL_STATUS.csv", [{k: r[k] for k in fields} for r in sorted(full.values(), key=lambda r: r["image"])])
    print(json.dumps({"case": IMAGE, "annotations": 32, "prefixes": len(prefixes), "endpoint_k": [r["k"] for r in endpoints],
                      "full_nodes": endpoints[-1]["nodes"], "all_checks_passed": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
