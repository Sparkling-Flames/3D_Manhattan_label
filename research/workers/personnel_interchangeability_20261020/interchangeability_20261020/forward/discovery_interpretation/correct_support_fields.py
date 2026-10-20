#!/usr/bin/env python3
"""Correct pool/image support names without changing any computed outcome.

Within every existing method/domain row a pool maps one-to-one to a physical
image. Across Manual/Semi methods it does not. Verify this from exact requests,
keep the existing numerical tables, and correct the overall receipt explicitly.
"""
from pathlib import Path
from datetime import datetime, timezone
import collections
import json
import pandas as pd
from analyze_discovery import ROOT, stream_events, write_csv, write_json, sha

HERE = Path(__file__).resolve().parent

def main():
    metadata = []
    for e in stream_events(ROOT / "interchangeability_20261020/discovery/forward_requests.json.gz"):
        metadata.append({k: e[k] for k in ("event_id", "method_id", "domain", "pool_id", "image", "building", "n", "m")})
    df = pd.DataFrame(metadata)
    group_map = df[["method_id", "domain", "pool_id", "image"]].drop_duplicates()
    assert group_map.groupby(["method_id", "domain", "pool_id"]).image.nunique().max() == 1
    # All result rows are subsets of these method/domain groups. Thus their
    # existing pool counts equal true image counts, while pooled headline does not.
    assert group_map.groupby(["method_id", "domain", "image"]).pool_id.nunique().max() == 1
    before, updated = {}, []
    for path in sorted(HERE.rglob("*.csv.gz")):
        if "aggregate" not in path.name and path.name != "n_qualification.csv.gz":
            continue
        t = pd.read_csv(path)
        cols = [c for c in t if c == "images" or c.endswith("_known_images")]
        if not cols:
            continue
        before[str(path.relative_to(HERE))] = sha(path)
        for c in cols:
            dest = "pools" if c == "images" else c.replace("_known_images", "_known_pools")
            if dest in t:
                assert t[dest].equals(t[c])
            else:
                t.insert(t.columns.get_loc(c), dest, t[c])
        write_csv(path, t)
        updated.append(str(path.relative_to(HERE)))
    p = df.loc[(df.n >= 3) & (df.m >= 2)]
    receipt_path = HERE / "DISCOVERY_INTERPRETATION_RECEIPT.json"
    receipt = json.loads(receipt_path.read_text())
    original_image_count = receipt["primary_images"]
    receipt.update(input_images=int(df.image.nunique()), primary_pools=int(p.pool_id.nunique()), primary_images=int(p.image.nunique()),
                   support_correction="Original primary_images counted pool_id (62). Actual distinct image IDs are 55, because Manual/Semi can share an image. All within-method/domain support rows were independently verified one-pool-per-image, so their existing images values and every scientific metric are unchanged; explicit pools and metric_known_pools columns are added.",
                   support_corrected_script_sha256=sha(HERE / "analyze_discovery.py"))
    write_json(receipt_path, receipt)
    audit = dict(schema="true_image_pool_support_correction_v1", corrected_utc=datetime.now(timezone.utc).isoformat(),
                 input_events=len(df), input_pools=int(df.pool_id.nunique()), input_images=int(df.image.nunique()),
                 primary_events=len(p), original_primary_images_field=original_image_count,
                 primary_pools=int(p.pool_id.nunique()), true_primary_images=int(p.image.nunique()), primary_buildings=int(p.building.nunique()),
                 per_method_domain_one_pool_per_image_verified=True, scientific_outcome_metrics_changed=False,
                 tables_updated=updated, previous_table_sha256=before, corrected_receipt_sha256=sha(receipt_path))
    write_json(HERE / "IMAGE_POOL_SUPPORT_AUDIT.json", audit)
    print(json.dumps({k: audit[k] for k in ("input_events", "input_pools", "input_images", "primary_events", "primary_pools", "true_primary_images")}))

if __name__ == "__main__":
    main()
