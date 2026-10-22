#!/usr/bin/env python3
"""Copy a small, exact subset of completed closure cases. No fusion/replay."""
from pathlib import Path
import csv
import gzip
import hashlib
import io
import json
import os

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[4]
SOURCE = REPO/"research/workers/personnel_exchange_closure_20261022/mechanisms"
COMMIT = "ef148c82df18582228b2d23837faa2659e79eba7"
CASES = ["manual_structure", "manual_threshold20", "manual_threshold21", "manual_failure"]


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name+".tmp")
    with open(tmp, "wb") as f:
        assert f.write(data)==len(data)
        f.flush()
        os.fsync(f.fileno())
    assert tmp.read_bytes()==data
    os.replace(tmp,path)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def table_payload(fieldnames, rows):
    stream=io.StringIO(newline="")
    writer=csv.DictWriter(stream,fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


def main():
    manifest=[]
    files=[f"cases/{c}.json.gz" for c in CASES]
    files += ["FIXED_BLOCK_THRESHOLD_MECHANISM.csv", "FAILURE_CONNECTION_MECHANISM.json",
              "figures/STRUCTURE_LOCAL_VOTES.png", "figures/THRESHOLD_REVERSAL.png",
              "figures/FAILURE_LOCAL_CONNECTION.png",
              "figures/manual_structure/member_overlays.png",
              "figures/manual_structure/raw_three_views.png"]
    for name in files:
        src=SOURCE/name
        data=src.read_bytes()
        save(OUT/name,data)
        if name.endswith(".json.gz"):
            json.loads(gzip.decompress(data))
        manifest.append(dict(source_path=str(src.relative_to(REPO)), output_path=str((OUT/name).relative_to(REPO)),
            source_sha256=digest(data),output_sha256=digest(data),source_bytes=len(data),output_bytes=len(data),
            transformation="byte-identical copy",rows="",cases="|".join(CASES),source_commit=COMMIT,
            stage="inherited_closure_20261022",data_version="real_v2"))
    tables=["EXACT_EVENTS.csv.gz", "EXACT_MEMBERS.csv.gz", "ENDPOINT_METRICS.csv.gz",
            "GROUP_VOTES.csv.gz", "OBSERVATION_ASSIGNMENTS.csv.gz", "EDGE_VOTES.csv.gz",
            "LOCAL_STRUCTURE_VOTES.csv"]
    for name in tables:
        src=SOURCE/name
        data=src.read_bytes()
        payload=gzip.decompress(data) if name.endswith(".gz") else data
        reader=csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
        fields=reader.fieldnames
        selected=[row for row in reader if row["case_id"] in CASES]
        new=table_payload(fields,selected)
        output=gzip.compress(new,compresslevel=5,mtime=0) if name.endswith(".gz") else new
        save(OUT/name,output)
        verified=gzip.decompress(output) if name.endswith(".gz") else output
        assert len(list(csv.DictReader(io.StringIO(verified.decode("utf-8-sig")))))==len(selected)
        manifest.append(dict(source_path=str(src.relative_to(REPO)),output_path=str((OUT/name).relative_to(REPO)),
            source_sha256=digest(data),output_sha256=digest(output),source_bytes=len(data),output_bytes=len(output),
            transformation="row selection only; original field strings preserved; case_id in selected cases",
            rows=len(selected),cases="|".join(CASES),source_commit=COMMIT,
            stage="inherited_closure_20261022",data_version="real_v2"))
    save(OUT/"SOURCE_MANIFEST.csv",table_payload(list(manifest[0]),manifest))
    receipt=dict(source_commit=COMMIT,case_ids=CASES,case_events=4,unique_images=2,
        uses="necessary structure completion; fixed-block threshold loss; invalid-floor connection",
        copied_or_filtered_files=len(manifest),bytes=sum(r["output_bytes"] for r in manifest),
        new_fusion_calls=0,new_scoring_calls=0,state_replays_this_round=0,
        selection="previous post-result explanatory selection; copied as historical evidence",
        source_report=str((SOURCE/"机制解释_原答到融合.md").relative_to(REPO)))
    save(OUT/"COPY_RECEIPT.json",json.dumps(receipt,ensure_ascii=False,indent=2).encode())
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
