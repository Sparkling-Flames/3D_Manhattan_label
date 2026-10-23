"""Freeze the actual finished R04B analysis-data file list; do not copy inputs."""
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
WORKSPACE = BASE.parents[1]
OUT = WORKSPACE / "deliverables/HOHONET_rebuilt_20261023"
PREFIX = "research/same_room/same_room_large_block_rebuilt_20261023/"


def main():
    files = []
    for folder in ("results", "geometry_summary", "anchor_paths", "direction_tables"):
        files.extend(sorted((BASE / folder).glob("*.csv.gz")))
    for relative in (
        "geometry/EVENT_GEOMETRY_RESULTS.csv.gz",
        "geometry/UNIQUE_GEOMETRY_COMPARISONS.csv.gz",
        "geometry/COMPLETION.json",
        "history_q/HISTORY_Q_MATCHED_STRATA.csv.gz",
        "sensitivity/MEMBER_MATCHED_STRATA.csv.gz",
        "results/EVENT_JOIN_RECEIPT.json",
        "results/SUMMARY_RECEIPT.json",
        "geometry_summary/GEOMETRY_SUMMARY_RECEIPT.json",
        "history_q/HISTORY_Q_ANALYSIS_RECEIPT.json",
        "sensitivity/MEMBER_ANALYSIS_RECEIPT.json",
        "anchor_paths/PATH_RECEIPT.json",
        "anchor_paths/KEY_PATH_READING_RECEIPT.json",
        "direction_tables/DIRECTION_DISPLAY_RECEIPT.json",
    ):
        files.append(BASE / relative)
    if len(files) != len(set(files)):
        raise ValueError("Duplicate source path in R04B")
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing)
    direction = json.loads((BASE / "direction_tables/DIRECTION_DISPLAY_RECEIPT.json").read_text())
    paths = json.loads((BASE / "anchor_paths/PATH_RECEIPT.json").read_text())
    if direction["design_only"] or paths["design_only"] or paths["partial_input"]:
        raise ValueError("R04B requires completed direction and path data")
    expected = {
        "results/EVENT_Q_STRUCTURE_EFFECTS.csv.gz": 62676,
        "results/EVENT_ENDPOINT_STATUS.csv.gz": 62676,
        "geometry/EVENT_GEOMETRY_RESULTS.csv.gz": 376056,
        "geometry/UNIQUE_GEOMETRY_COMPARISONS.csv.gz": 365622,
        "geometry_summary/EVENT_GEOMETRY_COMMON_SUPPORT.csv.gz": 62676,
        "anchor_paths/ANCHOR_PATH_EFFECTS.csv.gz": paths["transitions"],
        "anchor_paths/ANCHOR_PATH_TRANSITIONS.csv.gz": paths["transitions"],
        "direction_tables/DIRECTION_BACKGROUND_MEMBER_INDEX.csv.gz": direction["background_context_rows"],
    }
    config = dict(
        output=str(OUT / "HOHONET_R04B_新逐事件与匹配路径数据.zip"),
        receipt=str(OUT / "HOHONET_R04B_包内通读回执.json"),
        entries=[dict(source=str(path), archive_path=PREFIX + str(path.relative_to(BASE)))
                 for path in sorted(files)],
        expected_rows={PREFIX + name: rows for name, rows in expected.items()},
        identity="actual new exact-ABC analyses, not recovered missing original results",
        omitted="historical inputs, single-pool caches, anchor_paths/validation partial checks",
    )
    target = HERE / "R04B_PACK_MANIFEST.json"
    target.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(dict(manifest=str(target), files=len(files),
                          source_bytes=sum(path.stat().st_size for path in files),
                          output=config["output"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
