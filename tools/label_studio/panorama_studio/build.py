"""Build an offline, read-only studio bundle from explicit layouts or local demo assets."""
from __future__ import annotations
import argparse
import base64
import csv
import io
import json
import shutil
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote, urlparse

from PIL import Image

from .geometry import analyze, read_layout

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent


@lru_cache(maxsize=16)
def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def annotation_layout(task, annotation_id):
    matches=[a for a in task["annotations"] if str(a["id"])==str(annotation_id)]
    if len(matches)!=1: raise ValueError("annotation identity is missing or ambiguous")
    points=[p for p in matches[0]["result"] if p.get("type")=="keypointlabels"]
    if len(points)<6 or len(points)%2: raise ValueError("raw export has an odd/insufficient endpoint count")
    sizes={(p["original_width"],p["original_height"]) for p in points}
    if len(sizes)!=1: raise ValueError("mixed coordinate dimensions")
    w,h=next(iter(sizes))
    if any(p.get("image_rotation",0)!=0 for p in points): raise ValueError("rotated annotation requires explicit conversion")
    return {"width":w,"height":h,"coordinate_mode":"ls_percent",
            "ordered_pairs":[{"source_pair_id":f"ann{annotation_id}:{points[i]['id']}:{points[i+1]['id']}",
                "top":{k:points[i]["value"][k] for k in ["x","y"]},
                "bottom":{k:points[i+1]["value"][k] for k in ["x","y"]}}
                for i in range(0,len(points),2)]}


def load_variant(spec):
    path=Path(spec["path"])
    if "annotation_id" in spec:
        tasks=[t for t in read_json(str(path)) if str(t["id"])==str(spec["task_id"])]
        if len(tasks)!=1: raise ValueError("task identity is missing or ambiguous")
        payload=annotation_layout(tasks[0],spec["annotation_id"])
    else:
        payload=read_layout(path,spec.get("width",1024),spec.get("height",512))
    return {"name":spec["name"],"source":dict(spec),"geometry":analyze(payload)}


def image_stem(task):
    data=task.get("data",{})
    return Path(unquote(urlparse(data.get("image",data.get("title",""))).path)).stem


def demo_manifest():
    """Existing audit selects identities only; coordinates re-read from raw exports."""
    locator=ROOT/"analysis_results/paper_a_manhattan/manhattan_worker_gt_calibration_panel_20260816/worker_gt_metrics.csv"
    rows=list(csv.DictReader(locator.open(encoding="utf-8-sig")))
    chosen=["501","625","477","492","493","505","568","572","573"]
    specs=[]
    gt_path=ROOT/"export_label/人工精标/project-20-at-2026-03-27-14-57-e66c6481.json"
    gt_tasks=read_json(str(gt_path))
    for task_id in chosen:
        group=[r for r in rows if r["task_id"]==task_id]
        base=group[0]["base_task_id"]
        variants=[]
        candidates=[t for t in gt_tasks if image_stem(t)==base]
        for task in candidates:
            for ann in task.get("annotations",[]):
                if ann.get("was_cancelled"): continue
                variants.append({"name":f"历史精标导出 · ann{ann['id']} · 原始顺序","path":str(gt_path),
                                 "task_id":task["id"],"annotation_id":ann["id"],"role":"reference"})
        # Keep both the old residual-minimizer and boundary-best counterexample.
        selected=[min(group,key=lambda r:float(r["floor_heading_residual_sum_deg"] or "inf")),
                  max(group,key=lambda r:float(r["q_boundary"] or "-inf"))]
        if task_id=="625": selected += [r for r in group if r["annotation_id"] in {"3285","4744"}]
        seen=set()
        for row in selected:
            identity=(row["source_export"],row["runtime_task_id"],row["annotation_id"])
            if identity in seen: continue
            seen.add(identity)
            variants.append({"name":f"人工标注 · ann{row['annotation_id']}","path":str(ROOT/row["source_export"]),
                "task_id":row["runtime_task_id"],"annotation_id":row["annotation_id"],"role":"human",
                "historical_a_line":{"heading_sum_deg":row["floor_heading_residual_sum_deg"],
                    "q_boundary":row["q_boundary"],"q_wallwall":row["q_wallwall"],"locator":str(locator)}})
        specs.append({"image_id":base,"title":f"A line · {task_id}","category":"既有工人—参考对照",
                      "variants":variants})
    labels=ROOT/"data/mp3d_layout/test/label_cor"
    remaining=[p for p in sorted(labels.glob("*.txt")) if p.stem not in {s["image_id"] for s in specs}]
    dense=max(remaining,key=lambda p:len(p.read_text().splitlines()))
    extra=[("7y3sRwLe3Va_ad77d6eeca5b492b8fe3317177f4f03f","原始点序诊断"),
           (dense.stem,"密集角点"),
           (next(p.stem for p in remaining if len(p.read_text().splitlines())==8),"四角房间")]
    for base,category in extra:
        if base not in {s["image_id"] for s in specs}:
            specs.append({"image_id":base,"title":category,"category":category,"variants":[]})
    bi_root=Path("D:/Work/Manhattan_3D/Bi_layout/exports/mp3d_dual_predictions")
    for spec in specs:
        base=spec["image_id"]
        spec["image"]=str(ROOT/f"data/mp3d_layout/test/img/{base}.png")
        candidates=[("公开数据集布局",labels/f"{base}.txt","dataset_reference"),
                    ("HoHoNet · ep300 离线结果",ROOT/f"analysis_results/model_initialization_test_ep300_replay_20260823_v1/prediction_txt/{base}.layout.txt","offline_model"),
                    ("Bi · enclosed",bi_root/f"test/enclosed/corners_1024x512/{base}.txt","offline_model"),
                    ("Bi · extended",bi_root/f"test/extended/corners_1024x512/{base}.txt","offline_model")]
        spec["missing_sources"]=[]
        for name,path,role in candidates:
            if path.exists(): spec["variants"].append({"name":name,"path":str(path),"role":role})
            else: spec["missing_sources"].append({"name":name,"path":str(path),"reason":"file_missing"})
    return {"schema_version":"panorama_studio_input_v1","cases":specs,
            "selection":"12 purposeful engineering cases; not a representative research sample"}


def data_image(path, texture=False):
    path=Path(path)
    if not texture:
        mime="image/png" if path.suffix.lower()==".png" else "image/jpeg"
        return f"data:{mime};base64,"+base64.b64encode(path.read_bytes()).decode("ascii")
    with Image.open(path) as im:
        im=im.convert("RGB")
        im.thumbnail((2048,1024))
        buf=io.BytesIO(); im.save(buf,format="JPEG",quality=94,subsampling=0)
    return "data:image/jpeg;base64,"+base64.b64encode(buf.getvalue()).decode("ascii")


def build(manifest,out):
    out=Path(out).resolve()
    if out==ROOT or ROOT in out.parents and out.parts[len(ROOT.parts)] in {"export_label","import_json","data","active_logs","tools","docs"}:
        raise ValueError("output must be an independent artifact directory")
    out.mkdir(parents=True,exist_ok=True)
    cases=[]; counts={"cases":0,"variants":0,"fit_ok":0,"fit_blocked":0,"input_failed":0}
    for i,spec in enumerate(manifest["cases"]):
        case={k:spec[k] for k in ["image_id","title","category"] if k in spec}
        case.setdefault("title",spec["image_id"])
        case["image_source"]=spec["image"]
        case["missing_sources"]=spec.get("missing_sources",[])
        with Image.open(spec["image"]) as im: case["image_size"]=list(im.size)
        case["variants"]=[]
        for variant_spec in spec["variants"]:
            try:
                v=load_variant(variant_spec)
                counts["fit_ok" if v["geometry"]["fit"]["status"]=="ok" else "fit_blocked"]+=1
            except (ValueError,KeyError,OSError) as exc:
                v={"name":variant_spec["name"],"source":variant_spec,"error":str(exc)}
                counts["input_failed"]+=1
            case["variants"].append(v); counts["variants"]+=1
        # Per-case scripts allow file:// viewing without fetch, CORS, or a server.
        image_file=f"image_{i:02}.js"
        image_payload={"original":data_image(spec["image"]),"texture":data_image(spec["image"],True)}
        (out/image_file).write_text("window.STUDIO_IMAGES["+str(i)+"]="+json.dumps(image_payload)+";",encoding="utf-8")
        case["image_script"]=image_file
        cases.append(case)
        print(f"case {i+1}: {len(case['variants'])} variants",flush=True)
    counts["cases"]=len(cases)
    payload={"schema_version":"panorama_studio_bundle_v1","cases":cases,"counts":counts,
             "annotation_writeback":False,"selection":manifest.get("selection","explicit user manifest")}
    encoded=json.dumps(payload,ensure_ascii=False,allow_nan=False).replace("</","<\\/")
    (out/"data.js").write_text("window.STUDIO_IMAGES={};window.STUDIO_DATA="+encoded+";",encoding="utf-8")
    for filename in ["index.html","studio.js","studio.css"]: shutil.copy2(HERE/filename,out/filename)
    for filename in ["three.min.js","OrbitControls.js"]: shutil.copy2(HERE.parent/filename,out/filename)
    (out/"input_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"geometry_audit.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps(counts),flush=True)
    return payload


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo",action="store_true")
    source.add_argument("--manifest",type=Path)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    manifest=demo_manifest() if args.demo else read_json(str(args.manifest))
    build(manifest,args.out)


if __name__=="__main__": main()
