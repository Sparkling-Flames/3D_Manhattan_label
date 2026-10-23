"""Read a saved native exact-team row and full geometry/vote state.

This is a reader, not a fusion or scoring approximation.  It accepts the scalar
table's geometry_state_pointer or resolves an exact team_key in the final CSV.
"""
from pathlib import Path
import argparse
import csv
import gzip
import json


def scalar_row(native_root, team_key):
    path = Path(native_root) / "ENDPOINT_SCALARS.csv.gz"
    found = None
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["team_key"] == team_key:
                if found is not None:
                    raise ValueError("Duplicate exact team key in scalar table")
                found = row
    if found is None:
        raise KeyError("Exact team key is not in this native result table")
    return found


def geometry_row(native_root, pointer, expected_team_key=None):
    relative, marker, line_number = pointer.rpartition("#L")
    if not marker or not line_number.isdigit() or int(line_number) < 1:
        raise ValueError("Expected relative geometry shard path followed by #L<1-based row>")
    root = Path(native_root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Geometry pointer escapes the supplied native result directory")
    found = None
    # Read the whole gzip member to EOF, so a truncated footer is not hidden by
    # an early return even when the requested row is at the start of the shard.
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for n, line in enumerate(stream, 1):
            row = json.loads(line)
            if n == int(line_number):
                found = row
    if found is None:
        raise IndexError("Geometry pointer row does not exist")
    if expected_team_key is not None and found["team_key"] != expected_team_key:
        raise ValueError("Scalar team key and pointed geometry team key differ")
    if found.get("geometry_state_pointer") != pointer:
        raise ValueError("Pointed geometry's own saved pointer differs")
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--team-key")
    mode.add_argument("--pointer")
    parser.add_argument("--output", required=True, help="JSON or JSON.gz output path")
    args = parser.parse_args()
    scalar = scalar_row(args.native_root, args.team_key) if args.team_key else None
    pointer = scalar["geometry_state_pointer"] if scalar else args.pointer
    record = geometry_row(args.native_root, pointer, args.team_key)
    value = dict(scalar=scalar, geometry_state=record,
                 provenance="Exact saved native result; no fusion/scoring recomputation")
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    path.write_bytes(gzip.compress(raw, mtime=0) if path.name.endswith(".gz") else raw)
    print(json.dumps(dict(output=str(path), team_key=record["team_key"],
                          has_geometry=record.get("geometry") is not None,
                          has_full_state=record.get("full_state") is not None,
                          exact_shard_read_to_eof=True), ensure_ascii=False))


if __name__ == "__main__":
    main()
