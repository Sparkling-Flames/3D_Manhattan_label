"""Choice parsing and Label Studio result extraction for analyze_quality."""

from collections import defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_LABEL_STUDIO_CONFIG_PATH = (
    _PROJECT_ROOT
    / "tools"
    / "label_studio"
    / "config_history"
    / "uncertainty_meta_v1_prechange_20260824"
    / "zh"
    / "xml"
    / "label_studio_view_config.xml"
)


def _load_label_studio_choice_alias_map(xml_path: Path) -> dict[str, dict[str, str]]:
    """Load Choice value->alias mappings per field name from Label Studio view config.

    We use aliases as stable IDs to:
    - Keep CSV fields concise and reproducible.
    - Align with perturbation operators (operator_id == alias).

    Returns:
      {"scope": {"In-scope：...": "normal", ...}, "model_issue": {...}, ...}
    """
    try:
        if not xml_path.exists():
            return {}
        root = ET.parse(str(xml_path)).getroot()
        out: dict[str, dict[str, str]] = {}
        for choices_node in root.iter():
            if choices_node.tag != "Choices":
                continue
            field_name = choices_node.attrib.get("name")
            if not field_name:
                continue
            mapping: dict[str, str] = out.setdefault(field_name, {})
            for choice_node in list(choices_node):
                if choice_node.tag != "Choice":
                    continue
                value_text = (choice_node.attrib.get("value") or "").strip()
                alias = (choice_node.attrib.get("alias") or "").strip()
                if value_text and alias:
                    mapping[value_text] = alias
        return out
    except Exception:
        return {}


_CHOICE_VALUE_TO_ALIAS_BY_FIELD: dict[str, dict[str, str]] = _load_label_studio_choice_alias_map(_LABEL_STUDIO_CONFIG_PATH)


def _map_choice_value_to_alias(field_name: str, value: str) -> str:
    """Map a Label Studio exported choice value to the configured alias when possible."""
    if not isinstance(value, str):
        return value
    v = value.strip()
    if not v:
        return ""
    mapping = _CHOICE_VALUE_TO_ALIAS_BY_FIELD.get(str(field_name), {})
    # If already an alias (common in hand-edited CSVs), keep it.
    if v in set(mapping.values()):
        return v
    return mapping.get(v, v)


def _normalize_choice_values(field_name: str, values) -> list[str]:
    """Split + map values to aliases with deterministic ordering and de-dup."""
    out: list[str] = []
    for v in _split_choice_values(values):
        v2 = _map_choice_value_to_alias(field_name, v)
        if v2 and v2 not in out:
            out.append(v2)
    return out


def _split_choice_values(values) -> list:
    """Split multi-choice strings like 'a;b;c' into a clean list.

    Label Studio v2 exports are lists already (from extract_data). We keep this
    helper to safely handle legacy/hand-edited CSV-like strings.
    """
    if values is None:
        return []
    if isinstance(values, (list, tuple)):
        out = []
        for v in values:
            if isinstance(v, str) and v.strip():
                out.append(v.strip())
        return out
    if isinstance(values, str):
        s = values.strip()
        if not s:
            return []
        return [x.strip() for x in s.split(";") if x.strip()]
    return []


_MODEL_ISSUE_TAG_REMAP = {
    # Legacy UI option kept in historical CSVs; replaced by the new ontology.
    "corner_mismatch": "topology_failure",
}


_MODEL_ISSUE_PRIMARY_PRIORITY = [
    # Higher = more severe / more diagnostic; deterministic if multiple selected.
    "fail",
    "topology_failure",
    "corner_duplicate",
    "corner_drift",
    "over_parsing",
    "overextend_adjacent",
    "underextend",
]


def _normalize_model_issue_values(values) -> list[str]:
    """Normalize model_issue tags to the current ontology.

    - Keeps ordering.
    - Removes empties.
    - Remaps legacy tags (e.g., corner_mismatch -> topology_failure).
    """
    out: list[str] = []
    for v in _split_choice_values(values):
        v2 = _MODEL_ISSUE_TAG_REMAP.get(v, v)
        if v2 and v2 not in out:
            out.append(v2)
    return out


def _pick_primary_model_issue(issue_types: list[str]) -> str:
    if not issue_types:
        return ""
    issue_set = set([str(x).strip() for x in issue_types if str(x).strip()])
    for t in _MODEL_ISSUE_PRIMARY_PRIORITY:
        if t in issue_set:
            return t
    return sorted(issue_set)[0] if issue_set else ""


def _scope_is_oos(scope_values: list) -> bool:
    """Decide OOS purely from structured scope field when present."""
    for s in _split_choice_values(scope_values):
        sl = s.lower()
        if sl.startswith("oos") or ("out-of-scope" in sl) or ("out of scope" in sl) or ("oos：" in s) or ("oos:" in sl):
            return True
        if "边界不可判定" in s or "几何假设不成立" in s or "错层" in s or "多平面" in s or "证据不足" in s:
            return True
    return False


def _has_token_in_choices(choice_values: list, tokens: list) -> bool:
    q = ";".join(_split_choice_values(choice_values)).lower()
    return any((t.lower() in q) for t in tokens)


def _has_prediction_fail(choice_values: list) -> bool:
    """Strictly detect prediction-failure tags from model_issue.

    NOTE:
    - Do NOT use generic substring 'fail' matching, otherwise tags like
      'Topological failure' would be misclassified as prediction failure.
    - Keep backward compatibility for legacy compact value 'fail'.
    """
    for s in _split_choice_values(choice_values):
        sl = s.strip().lower()
        if sl == "fail":
            return True
        if "prediction failure" in sl:
            return True
        if "预标注失效" in s or "模型预标注失效" in s:
            return True
    return False


def parse_quality_flags_v2(choice_map: dict, quality_all: str = "", mode: str = "v2") -> dict:
    """Parse flags using v2 structured fields.

    This repo is v2-only: we do NOT fall back to legacy free-text keyword parsing.
    If v2 structured fields are missing, we return tri-state unknowns and mark
    scope_missing=True so downstream filtering can make an explicit choice.
    """
    choice_map = choice_map or {}

    mode_norm = str(mode or "v2").strip().lower()
    if mode_norm != "v2":
        raise ValueError(f"quality_mode must be 'v2' (got: {mode!r})")

    scope_vals = _normalize_choice_values("scope", choice_map.get("scope", []))
    diff_vals = _normalize_choice_values("difficulty", choice_map.get("difficulty", []))
    model_vals = _normalize_model_issue_values(_normalize_choice_values("model_issue", choice_map.get("model_issue", [])))
    tool_vals = _normalize_choice_values("tool_issue", choice_map.get("tool_issue", []))

    has_structured = bool(scope_vals or diff_vals or model_vals or tool_vals)
    scope_missing = not bool(_split_choice_values(scope_vals))
    difficulty_missing = not bool(_split_choice_values(diff_vals))
    model_issue_missing = not bool(_split_choice_values(model_vals))

    difficulty_conflict = ("trivial" in set([str(x).strip().lower() for x in diff_vals]) and len(diff_vals) > 1)
    model_issue_conflict = ("acceptable" in set([str(x).strip().lower() for x in model_vals]) and len(model_vals) > 1)

    if has_structured:
        # IMPORTANT: if structured fields exist but scope is empty, treat it as UNKNOWN.
        # Do not silently fold it into in-scope; downstream filtering/plots can decide.
        is_oos = None if scope_missing else _scope_is_oos(scope_vals)
        # Difficulty: only set coarse booleans; keep the raw strings in CSV for detailed analysis.
        is_occlusion = _has_token_in_choices(diff_vals, ["occlusion", "遮挡"])
        is_residual = _has_token_in_choices(diff_vals, ["residual", "尽力调整", "仍不佳", "hard to align", "对齐困难"])
        # Model init failure: from model_issue choices only (strict matching).
        is_fail = _has_prediction_fail(model_vals)

        # In-scope flag is the complement of OOS within scope selections.
        scope_text = ";".join(_split_choice_values(scope_vals)).lower()
        is_normal = None if scope_missing else (
            ("in-scope" in scope_text or "camera room" in scope_text or "normal" in scope_text or "只标相机房间" in scope_text)
            and not bool(is_oos)
        )

        return {
            "scope_missing": bool(scope_missing),
            "difficulty_missing": bool(difficulty_missing),
            "model_issue_missing": bool(model_issue_missing),
            "difficulty_conflict": bool(difficulty_conflict),
            "model_issue_conflict": bool(model_issue_conflict),
            "is_oos": is_oos,
            "is_occlusion": bool(is_occlusion),
            "is_fail": bool(is_fail),
            "is_residual": bool(is_residual),
            "is_normal": is_normal,
        }

    # No structured fields found.
    # IMPORTANT (paper/reproducibility): do NOT infer scope from legacy free-text.
    return {
        "scope_missing": True,
        "difficulty_missing": True,
        "model_issue_missing": True,
        "difficulty_conflict": False,
        "model_issue_conflict": False,
        "is_oos": None,
        "is_occlusion": False,
        "is_fail": False,
        "is_residual": False,
        "is_normal": None,
    }


def extract_data(results, width=1024, height=512):
    """Extract geometry and choice fields from Label Studio results.

    Returns:
      corners_px: np.ndarray (N,2)
      poly_points_px: list[[x,y], ...]
    choice_map: dict[str, list[str]]  (from_name -> selected choice aliases when available)
      quality_all: str  (all selected choice texts joined by ';')

    Notes:
      - Old configs used a single Choices name='quality'.
            - New rigorous configs split into multiple fields: scope/difficulty/model_issue.
            - Label Studio exports the displayed Choice value text (not alias).
                We map it to the XML-configured alias when possible.
    """
    corners = []
    poly_points = []
    choice_map = defaultdict(list)

    for r in results:
        r_type = r.get('type')
        val = r.get('value', {})

        # 1. Extract Corners
        if r_type in ['keypointlabels', 'keypointregion']:
            x = val.get('x')
            y = val.get('y')
            if x is not None and y is not None:
                corners.append([x * width / 100.0, y * height / 100.0])

        # 2. Extract Polygon
        elif r_type in ['polygonlabels', 'polygonregion']:
            points = val.get('points', [])
            for p in points:
                poly_points.append([p[0] * width / 100.0, p[1] * height / 100.0])

        # 3. Extract choice fields
        elif r_type == 'choices':
            choices = val.get('choices', []) or []
            from_name = r.get('from_name') or r.get('name') or 'quality'
            for c in choices:
                if isinstance(c, str) and c:
                    choice_map[str(from_name)].append(_map_choice_value_to_alias(str(from_name), c))

    # Flatten all choices (dedup) for backward-compatible parsing
    all_choices = []
    for items in choice_map.values():
        all_choices.extend(items)
    # Keep deterministic ordering for logs/CSVs
    quality_all = ";".join(sorted(set(all_choices))) if all_choices else "unknown"

    return np.array(corners), poly_points, dict(choice_map), quality_all
