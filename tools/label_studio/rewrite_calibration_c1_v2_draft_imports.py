from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[2]
MANUAL_CORE_IMPORT = ROOT / "import_json/calibration_c1_v2_draft/stage2_calibration_manual_core_import_c1_v2_draft.json"
SEMI_IMPORT = ROOT / "import_json/calibration_c1_v2_draft/stage2_calibration_semi_import_c1_v2_draft.json"
LAYOUT_JSON_DIR = ROOT / "output/layout_json"

TARGET_IMAGE_BASE = "https://label-images-1389474327.cos.ap-guangzhou.myqcloud.com/data/mp3d_layout/test/img/"
TARGET_VIS_BASE = "http://175.178.71.217:8000"


def _build_vis_3d_url(runtime_pairs: list[dict[str, object]]) -> str:
    payload = quote(json.dumps(runtime_pairs, ensure_ascii=False))
    return f"{TARGET_VIS_BASE}/tools/vis_3d.html?w=1024&h=512&data={payload}"


def _load_runtime_pairs(base_task_id: str) -> list[dict[str, object]]:
    layout_path = LAYOUT_JSON_DIR / f"{base_task_id}.json"
    payload = json.loads(layout_path.read_text(encoding="utf-8"))
    corners = payload["layout"]["corners"]
    return [
        {
            "x": float(corner["x"]),
            "y_ceiling": float(corner["y_ceiling"]),
            "y_floor": float(corner["y_floor"]),
        }
        for corner in corners
    ]


def _rewrite_payload(path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rewritten = 0

    if not isinstance(payload, list):
        raise TypeError(f"Unsupported JSON shape in {path}")

    for item in payload:
        if not isinstance(item, dict):
            continue
        data = item.get("data")
        if not isinstance(data, dict):
            continue

        image = data.get("image")
        if isinstance(image, str):
            filename = image.rsplit("/", 1)[-1]
            new_image = f"{TARGET_IMAGE_BASE}{filename}"
            if new_image != image:
                data["image"] = new_image
                rewritten += 1

        base_task_id = data.get("base_task_id")
        if isinstance(base_task_id, str):
            vis_3d = data.get("vis_3d")
            new_vis_3d = _build_vis_3d_url(_load_runtime_pairs(base_task_id))
            if vis_3d != new_vis_3d:
                data["vis_3d"] = new_vis_3d
                rewritten += 1

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rewritten


def main() -> None:
    manual_count = _rewrite_payload(MANUAL_CORE_IMPORT)
    semi_count = _rewrite_payload(SEMI_IMPORT)
    print(f"rewrote {manual_count} fields in {MANUAL_CORE_IMPORT}")
    print(f"rewrote {semi_count} fields in {SEMI_IMPORT}")


if __name__ == "__main__":
    main()