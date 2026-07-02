from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[2]
SOURCE_TASK_IMPORT = ROOT / "import_json/calibration_c1_v2_draft/review_only_anchor12_task_import_v1.json"
SOURCE_CONTACT_SHEET_IMPORT = ROOT / "import_json/calibration_c1_v2_draft/review_only_anchor12_contact_sheet_import_v1.json"
TARGET_IMAGE_BASE = "https://label-images-1389474327.cos.ap-guangzhou.myqcloud.com/data/mp3d_layout/test/img/"
TARGET_VIS_BASE = "http://175.178.71.217:8000"
LAYOUT_JSON_DIR = ROOT / "output/layout_json"


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


def _rewrite_image_url(url: str) -> str:
    filename = url.rsplit("/", 1)[-1]
    return f"{TARGET_IMAGE_BASE}{filename}"


def _rewrite_contact_sheet_html(html: str) -> str:
    for prefix in (
        "http://106.53.106.49:8000/data/mp3d_layout/test/img/",
        "http://175.178.71.271:8000/data/mp3d_layout/test/img/",
        "https://label-images-1389474327.cos.ap-guangzhou.myqcloud.com/data/mp3d_layout/test/img/",
    ):
        html = html.replace(prefix, TARGET_IMAGE_BASE)
    return html


def _rewrite_json_file(path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rewritten = 0

    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            data = item.get("data")
            if not isinstance(data, dict):
                continue

            image = data.get("image")
            if isinstance(image, str):
                new_image = _rewrite_image_url(image)
                if new_image != image:
                    data["image"] = new_image
                    rewritten += 1

            base_task_id = data.get("base_task_id")
            if isinstance(base_task_id, str) and not isinstance(data.get("vis_3d"), str):
                data["vis_3d"] = _build_vis_3d_url(_load_runtime_pairs(base_task_id))
                rewritten += 1

            contact_sheet_html = data.get("contact_sheet_html")
            if isinstance(contact_sheet_html, str):
                new_html = _rewrite_contact_sheet_html(contact_sheet_html)
                if new_html != contact_sheet_html:
                    data["contact_sheet_html"] = new_html
                    rewritten += 1
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return rewritten

    raise TypeError(f"Unsupported JSON shape in {path}")


def main() -> None:
    task_count = _rewrite_json_file(SOURCE_TASK_IMPORT)
    contact_count = _rewrite_json_file(SOURCE_CONTACT_SHEET_IMPORT)
    print(f"rewrote {task_count} task image URLs in {SOURCE_TASK_IMPORT}")
    print(f"rewrote {contact_count} contact sheet image URLs in {SOURCE_CONTACT_SHEET_IMPORT}")


if __name__ == "__main__":
    main()