import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_XML = _PROJECT_ROOT / "tools" / "label_studio_view_config.xml"


def load_alias_mapping(xml_path: Path) -> dict[str, dict[str, str]]:
    if not xml_path.exists():
        return {}
    root = ET.parse(str(xml_path)).getroot()
    out: dict[str, dict[str, str]] = {}
    for node in root.iter("Choices"):
        field_name = (node.attrib.get("name") or "").strip()
        if not field_name:
            continue
        mapping = out.setdefault(field_name, {})
        for c in node.findall("Choice"):
            value_text = (c.attrib.get("value") or "").strip()
            alias = (c.attrib.get("alias") or "").strip()
            if value_text and alias:
                mapping[value_text] = alias
    return out


def split_values(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, list):
        return [str(v).strip() for v in values if str(v).strip()]
    if isinstance(values, str):
        s = values.strip()
        if not s:
            return []
        if ";" in s:
            return [x.strip() for x in s.split(";") if x.strip()]
        return [s]
    return []


def normalize_values(field_name: str, values: Any, alias_map: dict[str, dict[str, str]]) -> list[str]:
    value_to_alias = alias_map.get(field_name, {})
    alias_set = set(value_to_alias.values())
    out: list[str] = []
    for v in split_values(values):
        vv = value_to_alias.get(v, v)
        if vv in alias_set or vv in value_to_alias.values() or vv:
            if vv not in out:
                out.append(vv)
    return out


def extract_choice_map(annotation_result_list: list[dict]) -> dict[str, list[str]]:
    choice_map: dict[str, list[str]] = {}
    for result in annotation_result_list or []:
        if not isinstance(result, dict):
            continue
        source = result.get("value") if isinstance(result.get("value"), dict) else result
        from_name = result.get("from_name") or source.get("from_name")
        choices = source.get("choices") if isinstance(source, dict) else None
        if not from_name:
            continue
        if isinstance(choices, list):
            choice_map[from_name] = [str(x) for x in choices if str(x).strip()]
    return choice_map


def get_annotations(task: dict) -> list[dict]:
    anns = task.get("annotations")
    if isinstance(anns, list):
        return [a for a in anns if isinstance(a, dict)]
    ann = task.get("annotation")
    if isinstance(ann, dict):
        return [ann]
    return []


def check_meta_rules(condition: str, difficulty: list[str], model_issue: list[str]) -> list[str]:
    reasons: list[str] = []
    difficulty_set = {str(x).strip().lower() for x in difficulty if str(x).strip()}
    model_set = {str(x).strip().lower() for x in model_issue if str(x).strip()}

    if not difficulty_set:
        reasons.append("difficulty_empty")
    if "trivial" in difficulty_set and len(difficulty_set) > 1:
        reasons.append("difficulty_conflict_trivial")

    model_issue_required = "semi" in str(condition or "").strip().lower()
    if model_issue_required and not model_set:
        reasons.append("model_issue_empty_required")
    if "acceptable" in model_set and len(model_set) > 1:
        reasons.append("model_issue_conflict_acceptable")

    return reasons


def validate_export(export_data: list[dict], alias_map: dict[str, dict[str, str]]) -> tuple[list[dict], list[dict]]:
    accepted_rows: list[dict] = []
    rejected_rows: list[dict] = []

    for task in export_data:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        condition = ""
        if isinstance(task.get("data"), dict):
            condition = str(task["data"].get("condition") or "")
        for ann in get_annotations(task):
            ann_id = ann.get("id")
            was_cancelled = bool(ann.get("was_cancelled"))
            if was_cancelled:
                continue
            result_items = ann.get("result") if isinstance(ann.get("result"), list) else []
            choice_map = extract_choice_map(result_items)
            difficulty = normalize_values("difficulty", choice_map.get("difficulty", []), alias_map)
            model_issue = normalize_values("model_issue", choice_map.get("model_issue", []), alias_map)

            reasons = check_meta_rules(condition, difficulty, model_issue)
            row = {
                "task_id": task_id,
                "annotation_id": ann_id,
                "condition": condition,
                "difficulty": ";".join(difficulty),
                "model_issue": ";".join(model_issue),
                "reject_reasons": ";".join(reasons),
            }
            if reasons:
                rejected_rows.append(row)
            else:
                accepted_rows.append(row)

    return accepted_rows, rejected_rows


def write_csv(path: Path, rows: list[dict], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> int:
    parser = argparse.ArgumentParser(description="Meta-label guard: reject invalid difficulty/model_issue records.")
    parser.add_argument("export_json", type=str, help="Label Studio export JSON path")
    parser.add_argument("--xml", type=str, default=str(_DEFAULT_XML), help="Label Studio config XML path")
    parser.add_argument("--out-dir", type=str, default="analysis_results", help="Output directory")
    parser.add_argument("--fail-on-reject", action="store_true", help="Exit code 2 when any reject is found")
    args = parser.parse_args()

    export_path = Path(args.export_json)
    if not export_path.exists():
        raise FileNotFoundError(f"Export JSON not found: {export_path}")

    with export_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Export JSON must be a list of tasks")

    alias_map = load_alias_mapping(Path(args.xml))
    accepted_rows, rejected_rows = validate_export(data, alias_map)

    out_dir = Path(args.out_dir)
    accepted_csv = out_dir / "meta_guard_accepted.csv"
    rejected_csv = out_dir / "meta_guard_rejected.csv"

    headers = ["task_id", "annotation_id", "condition", "difficulty", "model_issue", "reject_reasons"]
    write_csv(accepted_csv, accepted_rows, headers)
    write_csv(rejected_csv, rejected_rows, headers)

    total = len(accepted_rows) + len(rejected_rows)
    print("=== Meta Label Guard Summary ===")
    print(f"Total annotations checked: {total}")
    print(f"Accepted: {len(accepted_rows)}")
    print(f"Rejected: {len(rejected_rows)}")
    if total > 0:
        print(f"Reject rate: {len(rejected_rows) / total:.4f}")
    if rejected_rows:
        reason_counter = Counter()
        for r in rejected_rows:
            for reason in split_values(r.get("reject_reasons", "")):
                reason_counter[reason] += 1
        print("Reject reasons:")
        for k, v in reason_counter.most_common():
            print(f"  - {k}: {v}")

    print(f"Accepted CSV: {accepted_csv}")
    print(f"Rejected CSV: {rejected_csv}")

    if args.fail_on_reject and rejected_rows:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
