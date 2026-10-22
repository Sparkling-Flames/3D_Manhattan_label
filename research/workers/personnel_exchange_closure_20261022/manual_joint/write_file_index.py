"""Compact delivery index; do not bundle duplicate checkpoint directories."""
from __future__ import annotations
import hashlib
from pathlib import Path
import pandas as pd
from register_design import HERE, write, save


def digest(path):
    hh = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            hh.update(chunk)
    return hh.hexdigest()


def main():
    rows=[]
    for folder in [HERE, HERE / "phase_b_highq_slower", HERE / "figures", HERE / "mechanism_case", HERE / "mechanism_case/figures"]:
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.name.startswith("FILE_INDEX") or path.suffix not in {".py", ".md", ".csv", ".gz", ".json", ".png", ".pdf"}:
                continue
            relative = str(path.relative_to(HERE))
            identity = "new registered or derived analysis"
            if path.name.startswith(("INPUT_", "TRAINING_", "GLOBAL_DESCRIPTIVE", "ACTUAL_MEMBER", "AVAILABLE_CLASS")):
                identity = "prior frozen labels/history reused or described; not newly fitted"
            if path.suffix in {".py", ".md"}:
                group = "code_and_reports"
            elif path.name == "EVENTS_COMPLETE.csv.gz":
                group = "phase_B_complete_events" if path.parent != HERE else "phase_A_complete_events"
            elif path.name == "POLICIES_COMPLETE.csv.gz":
                group = "complete_policy_records"
            elif path.suffix in {".png", ".pdf"}:
                group = "figures"
            else:
                group = "inputs_registered_design_and_tables"
            rows.append(dict(path=relative, bytes=path.stat().st_size, sha256=digest(path), delivery_group=group, identity=identity,
                exact_endpoint_reference="../native/batches/*/ENDPOINT_SCALARS.csv.gz and ENDPOINT_GEOMETRY.csv.gz" if path.name in {"EVENTS_COMPLETE.csv.gz","TEAM_REQUEST.csv.gz"} else ""))
    write(HERE / "FILE_INDEX.csv", pd.DataFrame(rows))
    save(HERE / "FILE_INDEX_NOTES.json", dict(files=len(rows), bytes=sum(r["bytes"] for r in rows),
        phase_A_registered_events=81221,phase_B_registered_events=21000,policy_rows=79584,
        complete_event_tables_retained=True, duplicate_checkpoint_folders_excluded_from_compact_index=["results", "registration_batches", "phase_b_highq_slower/results"],
        note="Checkpoint folders remain available for incremental restoration. Compact delivery need not duplicate them when the complete table is provided. Root delivery may shard large complete tables with its own checksummed manifest."))
    print(f"Indexed {len(rows)} files, {sum(r['bytes'] for r in rows)/1024**2:.2f} MiB")


if __name__ == "__main__":
    main()
