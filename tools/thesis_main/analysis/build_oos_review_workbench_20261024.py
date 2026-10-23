"""Build the offline OOS review payload from the registered checklist and v2 evidence."""
import csv
import gzip
import json
import os
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CHECKLIST = ROOT / "research/difficulty/difficulty_mechanisms_v2_20261020/scope_closeout_20261022/OOS_REVIEW_20261024.md"
OUTPUT = ROOT / "research/statistics/research_explorer_v1_r2_20261017/oos-review-data.js"

def build_payload():
    records = json.load(gzip.open(ROOT / "research/statistics/v2_evidence_audit_20261019/records.json.gz", "rt", encoding="utf-8"))["records"]
    by_image = defaultdict(list)
    for r in records:
        if r["is_oos"]:
            by_image[r["image_code"]].append(r)
    summary_path = CHECKLIST.parent / "oos_statistics_20261024/image_condition_source.csv"
    with summary_path.open(encoding="utf-8-sig", newline="") as handle:
        diagnostics = {r["image_code"]: {
            k: float(r[k]) if r[k] else None for k in
            ["inventory_n", "pool_n", "R_pair_union_mean", "source_seconds_median", "scope_out_n", "scope_normalized_n"]
        } for r in csv.DictReader(handle) if r["condition"] == "manual" and r["origin"] == "new"}
    images = []
    for line in CHECKLIST.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|["):
            continue
        cells = line.strip("|").split("|")
        match = re.fullmatch(r"\[([^]]+)\]\(([^)]+)\)", cells[0])
        if not match:
            continue
        code, relative = match.groups()
        source = (CHECKLIST.parent / relative).resolve()
        assert source.is_file(), source
        rows = by_image.pop(code)
        assert len(rows) == int(cells[1]), code
        answers = []
        for r in rows:
            points = r["points_1024x512"]
            confirmed = r["ring_confirmed"] is True
            answers.append({"id": r["object_id"], "worker": r["worker_id"], "condition": r["condition"],
                            "disposition": r["cleaning_disposition"], "order_status": r["order_status"],
                            "points": points if confirmed else None, "raw_points": points,
                            "source_time": r["source_active_time_seconds"], "reference_id": r["reference_id"]})
        images.append({"id": rows[0]["image_id"], "code": code, "photo": Path(os.path.relpath(source, OUTPUT.parent)).as_posix(),
                       "room": cells[2], "candidate": cells[3], "question": cells[4], "basis": cells[5],
                       "diagnostic": diagnostics[code], "answers": answers})
    assert not by_image, sorted(by_image)
    assert len(images) == 28 and sum(len(i["answers"]) for i in images) == 1222
    return {"schema": "oos_review_v1", "release": "v2", "images": images}

if __name__ == "__main__":
    payload = build_payload()
    OUTPUT.write_text("window.OOS_REVIEW_DATA=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"OOS: {len(payload['images'])} images, 1222 answers -> {OUTPUT.relative_to(ROOT)}")
