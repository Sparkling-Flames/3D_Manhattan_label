"""Materialize one expert-side Manhattan feedback ledger JSONL entry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


def materialize_entry(
    core_output: Mapping[str, Any], expert_review: Mapping[str, Any]
) -> dict[str, Any]:
    if core_output.get("schema_version") != "manhattan_constrained_hypothesis_ranking_core_v1":
        raise ValueError("unsupported core output schema_version")
    if not isinstance(core_output.get("state_before"), Mapping):
        raise ValueError("core output has no state_before")
    candidates = {
        str(row["candidate_id"]): row for row in core_output.get("candidate_set", [])
    }
    if not candidates:
        raise ValueError("core output has no candidate_set")
    shown_rank = [str(value) for value in expert_review.get("shown_rank", [])]
    selected = expert_review.get("expert_selected_candidate")
    selected = str(selected) if selected is not None else None
    rejected = [str(value) for value in expert_review.get("expert_rejected_candidates", [])]
    unknown = set(shown_rank + rejected + ([selected] if selected else [])) - set(candidates)
    if unknown:
        raise ValueError(f"expert review references unknown candidates: {sorted(unknown)}")
    accepted_directly = bool(expert_review.get("accepted_directly", False))
    accepted_after_edit = bool(expert_review.get("accepted_after_minor_edit", False))
    if accepted_directly and accepted_after_edit:
        raise ValueError("accepted_directly and accepted_after_minor_edit are mutually exclusive")
    if (accepted_directly or accepted_after_edit) and selected is None:
        raise ValueError("accepted candidate status requires expert_selected_candidate")
    manual_edit = expert_review.get("manual_edit_after_candidate")
    delta = expert_review.get("delta_candidate_to_final")
    final_layout = expert_review.get("final_layout")
    final_layout_available = bool(
        expert_review.get("final_layout_available", final_layout is not None)
    )
    candidate_verdicts = expert_review.get("candidate_verdicts", {})
    if not isinstance(candidate_verdicts, Mapping):
        raise ValueError("candidate_verdicts must be an object")
    unknown_verdicts = set(candidate_verdicts) - set(candidates)
    if unknown_verdicts:
        raise ValueError(
            f"candidate_verdicts references unknown candidates: {sorted(unknown_verdicts)}"
        )
    if not final_layout_available and final_layout is not None:
        raise ValueError("final_layout must be null when final_layout_available is false")
    if accepted_after_edit and (manual_edit is None or delta is None):
        raise ValueError("accepted_after_minor_edit requires edit and delta records")
    if accepted_directly and (manual_edit not in (None, {}, []) or delta not in (None, {}, [])):
        raise ValueError("accepted_directly cannot include a non-empty manual edit or delta")
    evaluations = core_output.get("constrained_evaluations", {})
    evaluator_versions = {
        row.get("evaluator_version") for row in evaluations.values() if row.get("evaluator_version")
    }
    return {
        "state_before": core_output["state_before"],
        "case_contract": core_output["case_contract"],
        "candidate_set": list(core_output["candidate_set"]),
        "candidate_metrics": dict(evaluations),
        "shown_rank": shown_rank,
        "expert_selected_candidate": selected,
        "expert_selected_candidate_role": expert_review.get(
            "expert_selected_candidate_role"
        ),
        "expert_rejected_candidates": rejected,
        "candidate_verdicts": dict(candidate_verdicts),
        "manual_edit_after_candidate": manual_edit,
        "final_layout": final_layout,
        "final_layout_available": final_layout_available,
        "delta_candidate_to_final": delta,
        "accepted_directly": accepted_directly,
        "accepted_after_minor_edit": accepted_after_edit,
        "rejected_reason_optional": expert_review.get("rejected_reason_optional"),
        "case_tags": list(expert_review.get("case_tags", [])),
        "action_family": candidates[selected].get("action_family") if selected else None,
        "parameter_snapshot": expert_review.get(
            "parameter_snapshot", core_output.get("state_before", {}).get("projection_config", {})
        ),
        "ranker_version": core_output["schema_version"],
        "evaluator_version": next(iter(evaluator_versions)) if len(evaluator_versions) == 1 else sorted(evaluator_versions),
    }


def run(core_path: Path, review_path: Path, output_path: Path) -> Path:
    core = json.loads(core_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    entry = materialize_entry(core, review)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-output", type=Path, required=True)
    parser.add_argument("--expert-review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(run(args.core_output, args.expert_review, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
