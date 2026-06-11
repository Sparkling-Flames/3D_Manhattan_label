"""Smoke CLI for M15.10 height reproject applicability review rows.

This CLI is offline and diagnostic only. It does not implement height
reprojection, generate y-coordinate candidates, modify candidate pairs or
annotations, connect to UI/Label Studio, or feed routing/formal artifacts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.manhattan_assist_review_harness import (  # noqa: E402
    HEIGHT_REPROJECT_APPLICABILITY_OPERATION,
    build_pair_assist_review_rows,
    summarize_height_reproject_applicability_review,
)


def _load_records(input_path: Path) -> list[dict[str, Any]]:
    with input_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict) and isinstance(payload.get("records"), list):
        records = payload["records"]
    else:
        raise ValueError("input JSON must be a list of records or an object with records=[]")
    if not all(isinstance(record, dict) for record in records):
        raise ValueError("all input records must be JSON objects")
    return records


def build_smoke_payload(input_path: Path) -> dict[str, Any]:
    records = _load_records(input_path)
    rows = build_pair_assist_review_rows(
        records,
        operation=HEIGHT_REPROJECT_APPLICABILITY_OPERATION,
    )
    summary = summarize_height_reproject_applicability_review(rows)
    return {
        "rows": rows,
        "summary": summary,
    }


def run_smoke(input_path: Path, output_path: Path | None = None, pretty: bool = False) -> dict[str, Any]:
    payload = build_smoke_payload(input_path)
    indent = 2 if pretty else None
    text = json.dumps(payload, indent=indent, sort_keys=pretty)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build offline height reproject applicability smoke rows and summary.",
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Fixture or records JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path. Defaults to stdout.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    run_smoke(args.input, output_path=args.output, pretty=args.pretty)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
