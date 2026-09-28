"""只打包分析结果，不计算研究指标、分类、分簇或几何拟合。"""
from __future__ import annotations
import argparse
import copy
import json
import math
from pathlib import Path
import re
import shutil
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STUDIO = ROOT / "tools/label_studio/panorama_studio"
MODULES = ("overview", "annotation", "stability", "people", "rooms", "features")
DIMS = ("version", "condition", "method", "classification", "building", "room", "image")
STATES = {"ready", "pending", "not_computed", "insufficient", "not_met", "unresolved", "not_applicable"}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def fields(obj, required, optional=()):
    require(isinstance(obj, dict), "expected object")
    require(set(required) <= obj.keys(), f"missing fields: {set(required) - obj.keys()}")
    require(obj.keys() <= set(required) | set(optional), f"unknown fields: {obj.keys() - set(required) - set(optional)}")


def ids(items):
    require(isinstance(items, list), "expected list")
    values = [item["id"] for item in items]
    require(all(isinstance(v, str) and v for v in values), "empty identity")
    require(len(values) == len(set(values)), "duplicate identity")
    return set(values)


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def portable(value):
    if isinstance(value, str):
        require(not re.search(r"(?:https?://|file:|[A-Za-z]:[\\/]|\\\\)", value), "remote or absolute path in results")
    elif isinstance(value, dict):
        for item in value.values():
            portable(item)
    elif isinstance(value, list):
        for item in value:
            portable(item)
    elif isinstance(value, float):
        require(math.isfinite(value), "nonfinite number")


def validate(data):
    fields(data, ["schema_version", "release", "versions", "methods", "classifications", "sources",
                  "participants", "images", "cases", "views"])
    require(data["schema_version"] == "research_dashboard_v1", "unsupported schema_version")
    require(isinstance(data["release"], str) and data["release"], "missing release")
    portable(data)
    catalogs = {}
    for key in ["versions", "methods", "classifications", "sources"]:
        catalogs[key] = ids(data[key])
        for item in data[key]:
            fields(item, ["id", "label", "description"])
            require(all(isinstance(x, str) and x for x in item.values()), f"invalid {key}")
    people = ids(data["participants"])
    for person in data["participants"]:
        fields(person, ["id", "label"])
    images = ids(data["images"])
    image_map = {i["id"]: i for i in data["images"]}

    def refs(obj):
        require(isinstance(obj["source_ids"], list) and bool(obj["source_ids"]), "source_ids required")
        require(set(obj["source_ids"]) <= catalogs["sources"], "source mismatch")
        if "member_ids" in obj:
            require(isinstance(obj["member_ids"], list), "member_ids must be list")
            require(set(obj["member_ids"]) <= people, "member mismatch")
            require(len(obj["member_ids"]) == len(set(obj["member_ids"])), "duplicate member")
        if obj.get("image_id"):
            require(obj["image_id"] in images, "image mismatch")

    def number(obj):
        require(obj["status"] in STATES, "unknown status")
        if obj["status"] == "ready":
            require(finite(obj["value"]), "ready requires finite value")
        else:
            require(obj["value"] is None, f"{obj['status']} value must be null")
        den = obj["denominator"]
        require(den is None or finite(den) and den > 0, "denominator must be positive or null")
        if "numerator" in obj:
            num = obj["numerator"]
            require(num is None or finite(num) and num >= 0, "invalid numerator")
            require(num is None or den is not None and num <= den, "numerator exceeds denominator")
        refs(obj)

    for im in data["images"]:
        fields(im, ["id", "building", "room", "scene", "source_ids"])
        refs(im)
    ids(data["views"])
    scopes = set()
    for view in data["views"]:
        fields(view, ["id", *DIMS, "image_ids", "modules"])
        require(all(isinstance(view[k], str) for k in DIMS), "dimensions must be strings")
        for key, catalog in [("version", "versions"), ("method", "methods"), ("classification", "classifications")]:
            require(view[key] in catalogs[catalog], f"{key} mismatch")
        require(bool(view["condition"]), "condition required")
        scope = tuple(view[k] for k in DIMS)
        require(scope not in scopes, "duplicate scope")
        scopes.add(scope)
        require(isinstance(view["image_ids"], list) and set(view["image_ids"]) <= images, "view image mismatch")
        require(len(view["image_ids"]) == len(set(view["image_ids"])), "duplicate view image")
        if view["image"]:
            require(view["image_ids"] == [view["image"]], "image slice mismatch")
        for image_id in view["image_ids"]:
            im = image_map[image_id]
            require(all(not view[k] or view[k] == im[k] for k in ["building", "room"]), "building/room mismatch")
        fields(view["modules"], MODULES)
        for mod in view["modules"].values():
            fields(mod, ["status", "note", "metrics", "charts", "tables"])
            require(mod["status"] in STATES, "unknown module status")
            for metric in mod["metrics"]:
                fields(metric, ["label", "value", "unit", "status", "definition", "denominator", "source_ids", "member_ids"])
                number(metric)
            ids(mod["charts"])
            for chart in mod["charts"]:
                fields(chart, ["id", "title", "kind", "x_label", "x_unit", "y_label", "unit", "definition", "rows"], ["group_by_image"])
                require("group_by_image" not in chart or isinstance(chart["group_by_image"], bool), "group_by_image must be boolean")
                require(chart["kind"] in ["line", "scatter", "bar"], "unsupported chart kind")
                seen = set()
                for row in chart["rows"]:
                    fields(row, ["x", "value", "status", "series", "image_id", "numerator", "denominator", "member_ids", "source_ids"])
                    require(isinstance(row["x"], str) or finite(row["x"]), "invalid x")
                    require(isinstance(row["series"], str), "invalid series")
                    require(row["image_id"] == "" or row["image_id"] in view["image_ids"], "chart image outside view")
                    key = (row["series"], row["image_id"], row["x"])
                    require(key not in seen, "duplicate chart point")
                    seen.add(key)
                    number(row)
            ids(mod["tables"])
            for table in mod["tables"]:
                fields(table, ["id", "title", "columns", "rows"], ["replay"])
                require("replay" not in table or isinstance(table["replay"], bool), "replay must be boolean")
                keys = []
                for col in table["columns"]:
                    fields(col, ["key", "label", "unit"])
                    keys.append(col["key"])
                require(len(set(keys)) == len(keys), "duplicate table column")
                require({"source_ids", "member_ids", "image_id"} <= set(keys), "table needs source/member/image columns")
                for row in table["rows"]:
                    fields(row, keys)
                    refs(row)
                    require(not row["image_id"] or row["image_id"] in view["image_ids"], "table image outside view")
            if mod["status"] != "ready":
                require(not (mod["charts"] or mod["metrics"] or mod["tables"]), "unavailable module cannot contain results")
    ids(data["cases"])
    for case in data["cases"]:
        fields(case, ["id", "image_id", "version", "condition", "method", "classification", "pointset_version",
                      "source_ids", "width", "height", "variants"])
        refs(case)
        require(any(all(case[k] == v[k] for k in DIMS[:4]) and case["image_id"] in v["image_ids"]
                    for v in data["views"]), "case context mismatch")
        require(finite(case["width"]) and case["width"] > 0 and finite(case["height"]) and case["height"] > 0, "image dimensions invalid")
        require(isinstance(case["pointset_version"], str) and case["pointset_version"], "pointset_version required")
        ids(case["variants"])
        for variant in case["variants"]:
            fields(variant, ["id", "name", "kind", "pointset_version", "member_ids", "source_ids", "cluster_ids",
                             "pairs", "connections"], ["geometry", "geometry_pointset_version"])
            refs(variant)
            require(variant["pointset_version"] == case["pointset_version"], "pointset version mismatch")
            require(variant["kind"] in ["original", "fit", "perturbation"], "unknown geometry kind")
            pairs = variant["pairs"]
            pair_ids = []
            for n, pair in enumerate(pairs, 1):
                fields(pair, ["source_pair_id", "display_index", "top", "bottom"])
                require(pair["display_index"] == n, "point numbering mismatch")
                pair_ids.append(pair["source_pair_id"])
                for ep in ["top", "bottom"]:
                    p = pair[ep]
                    require(isinstance(p, list) and len(p) == 2 and all(finite(x) for x in p), "invalid coordinates")
                    require(0 <= p[0] <= case["width"] and 0 <= p[1] <= case["height"], "coordinates out of bounds")
            require(len(set(pair_ids)) == len(pair_ids), "duplicate pair identity")
            for edge in variant["connections"]:
                require(len(edge) == 2 and set(edge) <= set(pair_ids), "connection mismatch")
            if "geometry" in variant:
                g = variant["geometry"]
                require(variant.get("geometry_pointset_version") == case["pointset_version"], "geometry pointset version mismatch")
                require(g["pairs"] == pairs and g["width"] == case["width"] and g["height"] == case["height"], "geometry point identity mismatch")
                ring = [[pair_ids[i], pair_ids[(i + 1) % len(pair_ids)]] for i in range(len(pair_ids))]
                require(variant["connections"] == ring, "Studio requires explicit ordered ring connections")
                require(g.get("schema_version") == "panorama_studio_v1", "geometry schema mismatch")
                require("raw" in g and "fit" in g, "geometry missing raw/fit")
                require(len(pairs) >= 3, "geometry requires at least three pairs")
                require(g["fit"].get("status") in ["ok", "blocked"], "geometry fit status invalid")
                for surface in [g["raw"]] + ([g["fit"]] if g["fit"]["status"] == "ok" else []):
                    for endpoint in ["floor", "ceiling"]:
                        require(len(surface.get(endpoint, [])) == len(pairs), "geometry vertex count mismatch")
                        for vertex in surface[endpoint]:
                            require(vertex is None or len(vertex) == 3 and all(finite(x) for x in vertex), "geometry invalid vertex")
                        for tri in surface.get(endpoint + "_triangles", []):
                            require(len(tri) == 3 and all(type(i) is int and 0 <= i < len(pairs) for i in tri), "geometry invalid triangle")
                require(isinstance(g["raw"].get("issues"), list), "geometry issues required")
                if g["fit"]["status"] == "ok":
                    fit = g["fit"]
                    require(len(fit.get("per_pair_residual_deg", [])) == len(pairs), "geometry residual count mismatch")
                    require(len(fit.get("reprojected_pairs", [])) == len(pairs), "geometry fitted pair count mismatch")
                    require([p["source_pair_id"] for p in fit["reprojected_pairs"]] == pair_ids, "geometry fitted identity mismatch")
    return data


def js(path, name, payload):
    path.write_text("window." + name + "=" + json.dumps(payload, ensure_ascii=False, allow_nan=False).replace("</", "<\\/") + ";\n", encoding="utf-8")


def local(base, name):
    require(isinstance(name, str) and not re.search(r"[:\\]", name), "asset needs relative POSIX path")
    path = (base / name).resolve()
    require(path.is_relative_to(base.resolve()) and path.is_file(), "asset outside manifest directory or missing")
    return path


def build(manifest, base, out):
    fields(manifest, ["schema_version", "release", "results", "selected_cases"])
    require(manifest["schema_version"] == "research_dashboard_manifest_v1", "unsupported manifest")
    base, out = Path(base).resolve(), Path(out).resolve()
    protected = [ROOT / name for name in ["export_label", "import_json", "active_logs", "data", "tools", "docs", "tests", ".git", ".agents", ".codex"]]
    require(out != ROOT and not any(out.is_relative_to(p) for p in protected), "output must be an independent artifact directory")
    require(not out.exists() and not out.with_suffix(".zip").exists(), "output already exists; choose a new release directory")
    if manifest["results"] is None:
        data = {"schema_version": "research_dashboard_v1", "release": manifest["release"],
                **{key: [] for key in ["versions", "methods", "classifications", "sources", "participants", "images", "cases", "views"]}}
    else:
        data = json.loads(local(base, manifest["results"]).read_text(encoding="utf-8-sig"))
    validate(data)
    require(data["release"] == manifest["release"], "release mismatch")
    require(isinstance(manifest["selected_cases"], list), "selected_cases must be list")
    selected = {}
    for spec in manifest["selected_cases"]:
        fields(spec, ["case_id", "image"])
        require(spec["case_id"] not in selected, "duplicate selected case")
        selected[spec["case_id"]] = local(base, spec["image"])
    require(set(selected) <= {c["id"] for c in data["cases"]}, "selected case missing")
    payload = copy.deepcopy(data)
    payload["cases"] = [c for c in payload["cases"] if c["id"] in selected]
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dashboard-", dir=out.parent) as tmp:
        stage = Path(tmp) / "bundle"
        assets = stage / "assets"
        assets.mkdir(parents=True)
        for name in ["index.html", "dashboard.css", "dashboard.js", "preview.js"]:
            shutil.copy2(HERE / name, stage / name if name == "index.html" else assets / name)
        from plotly.offline import get_plotlyjs
        (assets / "plotly.min.js").write_text(get_plotlyjs(), encoding="utf-8")
        if selected:
            from PIL import Image
            from tools.label_studio.panorama_studio.build import data_image
            shared = assets / "studio"
            shared.mkdir()
            for name in ["studio.css", "studio.js"]:
                shutil.copy2(STUDIO / name, shared / name)
            for name in ["three.min.js", "OrbitControls.js"]:
                shutil.copy2(STUDIO.parent / name, shared / name)
            with (shared / "studio.css").open("a", encoding="utf-8") as f:
                f.write("\n.order-editor{display:none!important}\n")
            for n, case in enumerate(payload["cases"]):
                path = selected[case["id"]]
                require(path.suffix.lower() in [".png", ".jpg", ".jpeg"], "image format must be PNG/JPEG")
                with Image.open(path) as im:
                    require(im.width * case["height"] == im.height * case["width"], "image dimensions mismatch")
                    case["source_image_size"] = list(im.size)
                image_payload = {"original": data_image(path), "texture": data_image(path, True)}
                case["image_script"] = f"assets/case-{n}.js"
                js(stage / case["image_script"], "DASHBOARD_IMAGE", image_payload)
                for j, variant in enumerate(case["variants"]):
                    if "geometry" not in variant:
                        continue
                    dest = stage / "cases" / f"{n}-{j}"
                    dest.mkdir(parents=True)
                    html = (STUDIO / "index.html").read_text(encoding="utf-8")
                    for name in ["studio.css", "studio.js", "three.min.js", "OrbitControls.js"]:
                        html = html.replace('"' + name + '"', '"../../assets/studio/' + name + '"')
                    html = html.replace('<script defer src="../../assets/studio/three.min.js">',
                        f'<script defer src="../../assets/preview.js"></script><script defer src="../../{case["image_script"]}"></script><script defer src="../../assets/studio/three.min.js">')
                    (dest / "index.html").write_text(html, encoding="utf-8")
                    studio_case = {"image_id": case["image_id"], "title": variant["name"], "image_script": "image.js",
                        "variants": [{"name": variant["name"], "source": {"pointset_version": case["pointset_version"],
                            "source_ids": variant["source_ids"], "kind": variant["kind"]}, "geometry": variant.pop("geometry")}]}
                    js(dest / "data.js", "STUDIO_DATA", {"cases": [studio_case], "counts": {"cases": 1, "variants": 1}})
                    with (dest / "data.js").open("a", encoding="utf-8") as f:
                        f.write("window.STUDIO_IMAGES={};")
                    (dest / "image.js").write_text("window.STUDIO_IMAGES[0]=window.DASHBOARD_IMAGE;", encoding="utf-8")
                    variant["preview"] = f"cases/{n}-{j}/index.html"
        js(assets / "data.js", "RESEARCH_DATA", payload)
        shutil.copy2(HERE / "README.md", stage / "使用与换数说明.md")
        shutil.copy2(ROOT / "docs/thesis_main/OFFLINE_RESEARCH_DASHBOARD.md", stage / "数据接口.md")
        (stage / "version.json").write_text(json.dumps({"release": data["release"], "schema_version": data["schema_version"],
            "selected_cases": list(selected), "image_count": len(data["images"]), "view_count": len(data["views"])},
            ensure_ascii=False, indent=2), encoding="utf-8")
        shutil.make_archive(str(Path(tmp) / "bundle"), "zip", stage)
        stage.rename(out)
        (Path(tmp) / "bundle.zip").rename(out.with_suffix(".zip"))
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    build(json.loads(args.manifest.read_text(encoding="utf-8-sig")), args.manifest.parent, args.out)
    print(args.out.resolve())
