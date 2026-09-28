"""Independently probe the returned implementation; never edit its files.

Run: python -B audit_checks.py --package PATH --original-zip PATH
The assertions confirm counterexamples, not correctness of the returned method.
"""
import argparse
import json
import sys
import zipfile
from pathlib import Path

import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--original-zip", type=Path, required=True)
    args = parser.parse_args()
    package = args.package.resolve()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(package / "src"))
    from geometry_core import pairs_from_floor, whole_distance, compare_polygons, geometry_loss
    from consensus_core import safe_records
    from local_window_study import extract_path
    from local_splice_study import splice_window
    from search_core import Scorer
    from model_core import mode_posterior

    def read(name):
        return json.loads((package / name).read_text(encoding="utf-8"))

    def record(points, identity, heights=2.7):
        p = np.asarray(points, dtype=float)
        h = np.broadcast_to(np.asarray(heights, dtype=float), (len(p),))
        return dict(id=identity, worker=identity, floor=p.tolist(), heights=h.tolist(),
                    pairs=pairs_from_floor(p, h).tolist())

    # Byte comparison, not reliance on the returned inventory's claim.
    inventory = read("input_inventory.json")["files"]
    with zipfile.ZipFile(args.original_zip) as archive:
        byte_checks = [dict(path=item["path"], byte_identical=
                            (package / "input_snapshot" / item["path"]).read_bytes()
                            == archive.read(item["original_zip_member"])) for item in inventory]

    square = np.array([[-2., -2.], [2., -2.], [2., 2.], [-2., 2.]])
    base = record(square, "base")
    redundancy = []
    for eps in (0., 1e-9, 1e-7, 1e-5, .001, .01):
        candidate = record(np.insert(square, 1, [0., -2. - eps], axis=0), "extra")
        redundancy.append(dict(epsilon_h=eps, distance=whole_distance(base, candidate),
                               comparison=compare_polygons(base, candidate)))
    assert redundancy[0]["distance"]["distance"] < 1e-6
    assert redundancy[2]["comparison"]["bev_iou"] > .9999999
    assert redundancy[2]["distance"]["distance"] > .12

    # A 20-degree window respects the returned experiment's <=30-degree limit.
    window = dict(entry_deg=125., exit_deg=145., width_deg=20.)
    splice_checks = []
    for eps in (1e-6, .001, .01):
        donor_points = square.copy()
        donor_points[0] += eps
        donor = record(donor_points, "donor")
        candidate = splice_window(base, extract_path(base, window), extract_path(donor, window))
        score = Scorer([base, donor], 2)(candidate)
        comparison = compare_polygons(base, candidate)
        splice_checks.append(dict(epsilon_h=eps, window=window,
                                 original_distance=whole_distance(base, donor),
                                 splice_distance=whole_distance(base, candidate),
                                 comparison=comparison, hard_support=score["hard_support"],
                                 vertex_count=len(candidate["floor"])))
    assert splice_checks[0]["original_distance"]["distance"] < 1e-5
    assert splice_checks[0]["comparison"]["bev_iou"] > .9999999
    assert all(row["hard_support"] == 0 for row in splice_checks)

    images = read("input_snapshot/inputs/eight_image_panel.json")["images"]
    records_by_image = {im["code"]: safe_records(im["annotations"]) for im in images}
    denominators = []
    for im in images:
        geometries = [geometry_loss(r) for r in records_by_image[im["code"]]]
        denominators.append(dict(code=im["code"], n_all=len(im["annotations"]),
                                 n_core=len(geometries), n_valid=sum(g["valid"] for g in geometries),
                                 n_camera_outside=sum(g["valid"] and not g["camera_inside"] for g in geometries)))

    real_splices = []
    for item in read("results/small_window_splice_frozen.json"):
        records = records_by_image[item["code"]]
        lookup = {r["id"]: r for r in records}
        n_all = next(im for im in images if im["code"] == item["code"])
        scorer = Scorer(records, len(n_all["annotations"]))
        for saved in item["candidates"]:
            candidate = saved["record"]
            d = whole_distance(candidate, lookup[candidate["base_id"]])
            score = scorer(candidate)
            assert score["hard_support"] == saved["score"]["hard_support"]
            real_splices.append(dict(id=candidate["id"], code=item["code"],
                                     distance_to_base=d,
                                     structural_penalty=.35*d["unmatched"] + .30*d["adjacency"],
                                     comparison_to_base=compare_polygons(candidate, lookup[candidate["base_id"]]),
                                     hard_support_recomputed=score["hard_support"]))
    assert len(real_splices) == 11
    assert all(r["hard_support_recomputed"] == 0 for r in real_splices)
    assert all(r["structural_penalty"] > .12 for r in real_splices)

    unknown = dict(one_mode=mode_posterior([dict(support=20)]),
                   twenty_singletons=mode_posterior([dict(support=1) for _ in range(20)]))
    assert unknown["twenty_singletons"]["probability"][-1] < unknown["one_mode"]["probability"][-1]
    height_outlier = geometry_loss(record(square, "height_outlier", [2.7, 2.7, 2.7, 8.]))
    assert height_outlier["loss"] < 1e-10 and height_outlier["height_range_relative"] > 1

    result = dict(package=str(package), original_zip=str(args.original_zip.resolve()),
                  input_byte_checks=byte_checks, input_all_identical=all(x["byte_identical"] for x in byte_checks),
                  denominators=denominators, redundancy=redundancy, splice_checks=splice_checks,
                  real_splices=real_splices, unknown_mode_probe=unknown, height_outlier=height_outlier,
                  interpretation="Independent targeted checks; not a rerun of all search and replay experiments.")
    output = Path(__file__).with_name("audit_results.json")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(output=str(output), input_files=len(byte_checks),
                          input_all_identical=result["input_all_identical"],
                          assertions="passed", real_splices=len(real_splices)), ensure_ascii=True))


if __name__ == "__main__":
    main()
