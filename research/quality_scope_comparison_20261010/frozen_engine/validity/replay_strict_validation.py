#!/usr/bin/env python3
"""Reproducible strict-validation regression audit; does not alter source data."""
import argparse
from copy import deepcopy
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

from strict_geometry import validate_layout, validate_record, validate_footprint, _orient_sign, VALIDATOR_VERSION


def dump_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def dump_csv(path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def make_layout(xz, top_y=1.):
    xz = np.asarray(xz, float)
    y = np.broadcast_to(np.asarray(top_y, float), (len(xz),))
    return {"top3d": np.column_stack([xz[:, 0], y, xz[:, 1]]).tolist(),
            "bottom3d": np.column_stack([xz[:, 0], -np.ones(len(xz)), xz[:, 1]]).tolist()}


def input_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=True).encode()).hexdigest()


def cases():
    rectangle = make_layout([(-3,-2),(3,-2),(3,2),(-3,2)])
    out = []
    def add(name, record, available, valid2d, valid3d, code=None, role="annotation", note=""):
        out.append(dict(case=name, record=record, expected_available=available, expected_valid_2d=valid2d,
                        expected_valid_3d=valid3d, expected_code=code, role=role, note=note))
    add("valid_rectangle", rectangle, True, True, True)
    add("valid_triangle", make_layout([(-3,-2),(3,-2),(0,2)]), True, True, True)
    add("valid_nonorthogonal_quadrilateral", make_layout([(-3,-2),(3,-1),(2,2),(-2,3)]), True, True, True)
    add("valid_top_below_camera", make_layout([(-3,-2),(3,-2),(3,2),(-3,2)], -.5), True, True, True,
        note="全体 top 在相机下方但高于地面；可形成有效墙环。")
    add("valid_mixed_top_signs_positive_heights", make_layout([(-3,-2),(3,-2),(3,2),(-3,2)],[-.99,1.99,-.99,1.99]), True, True, True)
    add("valid_nonflat_target_error", make_layout([(-3,-2),(3,-2),(3,2),(-3,2)],[.01,1.99,.01,1.99]), True, True, True)
    add("valid_camera_outside", make_layout([(7,-2),(13,-2),(13,2),(7,2)]), True, True, True)
    add("valid_non_star_shaped", make_layout([(-3,-2),(3,-2),(3,2),(1,2),(1,.5),(-1,.5),(-1,2),(-3,2)]), True, True, True)
    add("valid_very_thin", make_layout([(-3,-1e-8),(3,-1e-8),(3,1e-8),(-3,1e-8)]), True, True, True,
        note="长宽比约 3e8，不以形状细长为几何无效。")
    add("valid_large_coordinate", make_layout([(1e6-3,-2),(1e6+3,-2),(1e6+3,2),(1e6-3,2)]), True, True, True,
        note="先平移相对坐标算面积；不因原点很远产生面积抵消。")
    add("finite_but_numeric_area_overflow", make_layout([(-1e200,-1e200),(1e200,-1e200),(1e200,1e200),(-1e200,1e200)]),
        False, False, False,"unresolved_numeric_dynamic_range",note="输入有限但面积超出 float64；返回数值不可计算而不崩溃。")
    add("finite_but_numeric_extent_overflow", make_layout([(-1e308,-1e308),(1e308,-1e308),(1e308,1e308),(-1e308,1e308)]),
        False, False, False,"unresolved_numeric_dynamic_range")
    add("valid_exact_forward_collinear", make_layout([(-3,-2),(-1,-2),(1,-2),(3,-2),(3,2),(-3,2)]), True, True, True)
    add("valid_forward_collinear_at_closure", make_layout([(-3,-2),(3,-2),(3,2),(-3,2),(-3,0)]), True, True, True)
    add("valid_near_touch_positive_clearance", make_layout([(-3,-2),(3,-2),(3,2),(0,-2+1e-12),(-3,2)]), True, True, True)
    add("valid_near_touch_one_ulp_clearance", make_layout([(-3,-2),(3,-2),(3,2),(0,float(np.nextafter(-2.,0.))),(-3,2)]), True, True, True,
        note="精确谓词保留存储 float 的正间隙；不 epsilon 吸附成触边。")
    add("invalid_exact_touch", make_layout([(-3,-2),(3,-2),(3,2),(0,-2),(-3,2)]), False, False, False,"nonadjacent_vertex_touches_edge")
    add("invalid_one_ulp_crossing", make_layout([(-3,-2),(3,-2),(3,2),(0,float(np.nextafter(-2.,-math.inf))),(-3,2)]), False, False, False,"self_intersection")
    a=make_layout([(-3,-2),(3,-2),(3,2),(0,float(np.nextafter(-2.,0.))),(-3,2)])
    a['top3d'][3][2]=float(np.nextafter(-2.,-math.inf))
    add('roundoff_paired_top_crossing',a,False,True,False,'paired_topology_inconsistent_within_roundoff')
    a=deepcopy(a);a['top3d'][3][2]=-2.
    add('roundoff_paired_top_touch',a,False,True,False,'paired_topology_inconsistent_within_roundoff')
    a=deepcopy(a);a['top3d'][3][2]=float(np.nextafter(np.nextafter(-2.,0.),0.))
    add('roundoff_paired_both_rings_simple',a,True,True,True)
    add("invalid_adjacent_backtrack", make_layout([(-3,-2),(3,-2),(1,-2),(3,2),(-3,2)]), False, False, False,"overlapping_backtrack_edges")
    add("invalid_nonadjacent_collinear_overlap", make_layout([(-3,-2),(3,-2),(3,2),(-1,2),(-1,-2),(1,-2),(1,1),(-3,1)]), False, False, False,"overlapping_nonadjacent_edges")
    add("invalid_bowtie", make_layout([(-3,-2),(3,2),(-3,2),(3,-2)]), False, False, False,"self_intersection")
    add("invalid_crossing_nonzero_signed_area", make_layout([(-3,-2),(3,2),(-2,2),(3,-2)]), False, False, False,"self_intersection")
    add("invalid_all_collinear_zero_area", make_layout([(-3,0),(0,0),(3,0)]), False, False, False,"zero_signed_area")
    add("invalid_adjacent_repeat", make_layout([(-3,-2),(3,-2),(3,-2),(3,2),(-3,2)]), False, False, False,"zero_length_edge")
    add("invalid_explicit_duplicate_closure", make_layout([(-3,-2),(3,-2),(3,2),(-3,2),(-3,-2)]), False, False, False,"repeated_closure_vertex")
    add("invalid_nonadjacent_repeat", make_layout([(-3,-2),(3,-2),(3,2),(0,0),(-3,2),(0,0)]), False, False, False,"repeated_nonadjacent_vertex")
    a=deepcopy(rectangle); a["top3d"][0][0] += 1e-3
    add("invalid_unpaired_xz", a, False, True, False,"unpaired_vertical_xz")
    a=deepcopy(rectangle); a["top3d"]=a["top3d"][:-1]
    add("invalid_unequal_counts", a, False, True, False,"unequal_paired_ring_shapes")
    a=deepcopy(rectangle); a["top3d"][0][1]=-1
    add("invalid_top_at_floor", a, False, True, False,"top_at_or_below_floor")
    a=deepcopy(rectangle); a["top3d"][0][1]=-1.01
    add("invalid_top_below_floor", a, False, True, False,"top_at_or_below_floor")
    a=deepcopy(rectangle); a["bottom3d"][0][1]=-1.01
    add("model_nonplanar_floor", a, False, True, False,"unsupported_floor_model_or_units")
    a=deepcopy(rectangle); a["bottom3d"]=[[x,-2,z] for x,y,z in a["bottom3d"]]
    add("model_wrong_floor_units", a, False, True, False,"unsupported_floor_model_or_units")
    a=deepcopy(rectangle); del a["top3d"]
    add("missing_top_retains_bottom_area", a, False, True, False,"missing_top3d")
    a=deepcopy(rectangle); del a["bottom3d"]
    add("missing_bottom", a, False, False, False,"missing_bottom3d")
    a=deepcopy(rectangle); a["top3d"][0][1]=math.nan
    add("nonfinite_top_retains_bottom_area", a, False, True, False,"nonfinite_top3d_coordinate")
    a=deepcopy(rectangle); a["bottom3d"][0][1]=math.nan
    add("nonfinite_bottom_y_retains_xz_area", a, False, True, False,"nonfinite_bottom3d_coordinate")
    a=deepcopy(rectangle); a["bottom3d"][0][0]=math.inf
    add("nonfinite_bottom_xz", a, False, False, False,"nonfinite_footprint_coordinate")
    a=deepcopy(rectangle); a["top3d"]=[[1,2]]
    add("malformed_top_shape_retains_bottom", a, False, True, False,"malformed_top3d_shape")
    a=deepcopy(rectangle); a["top3d"]=[[1,2,3],[1]]
    add("malformed_top_ragged_retains_bottom", a, False, True, False,"malformed_top3d")
    a=deepcopy(rectangle); a["top3d"]=[[str(v) for v in p] for p in a["top3d"]]
    add("string_top_not_implicitly_converted",a,False,True,False,"nonnumeric_or_nonreal_top3d_coordinate")
    a=deepcopy(rectangle); a["top3d"][0][0]=None
    add("explicit_missing_coordinate",a,False,True,False,"missing_coordinate_in_top3d")
    add("invalid_reference_is_separate_role", make_layout([(-3,-2),(3,-2),(1,-2),(3,2),(-3,2)]), False, False, False,"overlapping_backtrack_edges",role="reference")
    add("geometry_valid_spherical_origin_vertex", make_layout([(0,0),(2,0),(2,2),(0,2)],[0,1,1,1]), False, True, True,"spherical_vertex_at_camera_origin")
    add("geometry_valid_spherical_origin_crossing", make_layout([(-1,0),(1,0),(1,2),(-1,2)],[0,0,1,1]), False, True, True,"edge_passes_camera_origin")
    add("geometry_valid_spherical_radial_zero_arc", make_layout([(1,0),(2,0),(2,2),(1,2)],[0,0,1,1]), False, True, True,"zero_angular_length_edge")
    add("geometry_valid_but_current_spherical_numeric_limit", make_layout([(-3,-1e-12),(3,-1e-12),(3,1e-12),(-3,1e-12)]), False, True, True,"numerically_unresolved_spherical_arc")
    return out


def summarize_case(case_id, record, result, **metadata):
    return {"case_id": case_id, **metadata, "status": result["status"],
            "valid_2d": result["valid_2d"], "valid_3d": result["valid_3d"],
            "spherical_boundary_available": result["spherical_boundary_available"],
            "area_h2": result["footprint_2d"].get("area_h2"),
            "reason_codes": "|".join(result["reason_codes"]),
            "failure_classes": "|".join(result["failure_classes"]),
            "warning_codes": "|".join(w["code"] for w in result["warnings"]),
            "input_sha256": input_hash(record)}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--package",type=Path,required=True)
    ap.add_argument("--audit",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args(); package=args.package.resolve(); audit=args.audit.resolve(); output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    source=package/"source/oct8-pro-quality-handoff"
    files=sorted(p for p in source.rglob("*") if p.is_file())
    before={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    checks=[]; details=[]; synthetic=[]
    def check(case_id, assertion, expected, observed):
        checks.append(dict(case_id=case_id,assertion=assertion,expected=expected,observed=observed,passed=expected==observed))
    for c in cases():
        h=input_hash(c["record"]); res=validate_record(c["record"],role=c["role"],source={"case":c["case"]})
        for key in ("available","valid_2d","valid_3d"):
            check(c["case"],key,c["expected_"+key],res[key])
        if c["expected_code"]:
            check(c["case"],"specific_reason",True,c["expected_code"] in res["reason_codes"])
        check(c["case"],"input_preserved",h,input_hash(c["record"]))
        if c["role"]=="reference":
            check(c["case"],"reference_category",True,"reference_not_applicable" in res["failure_classes"])
        if c["case"].startswith("missing_top") or c["case"].startswith("nonfinite_top"):
            check(c["case"],"bottom_area_preserved",24.,res["footprint_2d"].get("area_h2"))
        details.append(dict(case_id=c["case"],note=c["note"],result=res))
        synthetic.append(summarize_case(c["case"],c["record"],res,source="analytically_constructed"))

    # Classification is unaffected by scene labels; labels are provenance only.
    a=make_layout([(-3,-2),(3,-2),(3,2),(-3,2)])
    for metadata in ({"OOS":True},{"scene":"doorway_junction"},{"scene":"nonManhattan"}):
        res=validate_record(a,source=metadata)
        check("scene_label_"+str(metadata),"available_independent_of_label",True,res["available"])
    complex_top=np.asarray(a['top3d'],complex)+1j
    complex_bottom=np.asarray(a['bottom3d'],complex)+1j
    complex_before=(complex_top.tobytes(),complex_bottom.tobytes())
    res=validate_layout(complex_top,complex_bottom)
    check('complex_input','rejected_without_dropping_imaginary_part',False,res['available'])
    check('complex_input','specific_type_reason',True,'nonnumeric_or_nonreal_top3d_coordinate' in res['reason_codes'])
    check('complex_input','raw_input_bytes_preserved',complex_before,(complex_top.tobytes(),complex_bottom.tobytes()))

    # Exact forward subdivision, reversal and cyclic start do not change the
    # geometry. Test real stored coordinates, not a validator-internal fixture.
    geom=json.loads((source/"inputs/frozen_geometry.json").read_text())
    originals=[]; original_results=[]
    for im in geom["images"]:
        for role,key in (("annotation","annotations"),("reference","groundtruths")):
            for a in im[key]:
                res=validate_record(a,role=role,source={"image_code":im["code"],"id":a["id"],"version":a.get("version")})
                originals.append(summarize_case(a["id"],a,res,image_code=im["code"],review_id=a.get("reviewId"),role=role,version=a.get("version")))
                original_results.append(dict(image_code=im["code"],record_id=a["id"],review_id=a.get("reviewId"),role=role,result=res))
                for name, transform in (("reverse",lambda p:p[::-1]),("cyclic_start",lambda p:np.roll(p,1,axis=0)),
                                        ("subdivide3",lambda p:np.array([x+(y-x)*(j/3) for x,y in zip(p,np.roll(p,-1,axis=0)) for j in range(3)]))):
                    alt={key:transform(np.asarray(a[key],float)).tolist() for key in ("top3d","bottom3d")}
                    r=validate_record(alt,role=role)
                    check(a["id"]+"_"+name,"same_availability",res["available"],r["available"])
                    check(a["id"]+"_"+name,"same_2d_validity",res["valid_2d"],r["valid_2d"])
    check("original_36_annotations","n_available",36,sum(r["status"]=="available" and r["role"]=="annotation" for r in originals))
    check("original_8_references","n_available",8,sum(r["status"]=="available" and r["role"]=="reference" for r in originals))

    # Coordinate scale and orientation of exact analytic patterns. These are
    # geometry-domain checks, not invariance of scene interpretation or score.
    base_valid=np.array([(-3,-2),(-1,-2),(3,-2),(3,2),(-3,2)],float)
    base_invalid=np.array([(-3,-2),(3,-2),(1,-2),(3,2),(-3,2)],float)
    transform_count=0
    for scale in (1e-6,1.,1e6):
        for shift in ((0.,0.),(1e6,-1e6)):
            for reflect in (False,True):
                for reverse in (False,True):
                    for name,p,expected in (("forward",base_valid,True),("backtrack",base_invalid,False)):
                        q=p.copy()*scale
                        if reflect:q[:,0]*=-1
                        q+=shift
                        if reverse:q=q[::-1]
                        r=validate_footprint(q)
                        check(f"scale_{scale}_shift_{shift}_reflect_{reflect}_reverse_{reverse}_{name}","2d_topology",expected,r["available"])
                        transform_count+=1

    controls=[]; control_details=[]
    groups=[("original_251",package/"results/geometry/control_geometries.json"),
            ("uniform_height_9",package/"results/height_guard/large_room_uniform_height9_geometries.json"),
            ("new_audit_8",audit/"numeric/independent_counterexample_geometries.json")]
    for label,path in groups:
        for c in json.loads(path.read_text()):
            name=c.get("case_id",c.get("case"))
            for role in ("annotation","reference"):
                a=c[role]; res=validate_record(a,role=role,source={"group":label,"case":name,"path":str(path)})
                controls.append(summarize_case(name,a,res,group=label,role=role))
                if not res["available"] or label=="new_audit_8":
                    control_details.append(dict(case_id=name,group=label,role=role,result=res))
                if label=="new_audit_8":
                    expected=not(role=="annotation" and name in {"overlapping_backtrack_edges","nonadjacent_vertex_touches_edge"})
                    check(name+"_"+role,"audit_counterexample_availability",expected,res["available"])
    after={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    check("source_hashes","all_unchanged",before,after)
    failures=[c for c in checks if not c["passed"]]
    summary={"validator_version":VALIDATOR_VERSION,"python":sys.version,"numpy":np.__version__,
             "original_annotation_count":36,"original_reference_count":8,
             "original_annotations_available":sum(r["status"]=="available" and r["role"]=="annotation" for r in originals),
             "original_references_available":sum(r["status"]=="available" and r["role"]=="reference" for r in originals),
             "original_warning_records":sum(bool(r["warning_codes"]) for r in originals),
             "hand_constructed_case_count":len(synthetic),"coordinate_topology_transform_count":transform_count,
             "original_transform_count":len(originals)*3,"control_pair_count":len(controls)//2,
             "control_record_count":len(controls),"control_unavailable_records":sum(r["status"]!="available" for r in controls),
             "check_count":len(checks),"failed_check_count":len(failures),"failed_checks":failures,
             "source_file_count":len(files),"source_hashes_unchanged":before==after,
             "unavailable_control_records":[r for r in controls if r["status"]!="available"],
             "claim_limit":"严格输入域与计算回归检查；不是新增建筑验证，也不是质量标定。"}
    dump_csv(output/"strict_validation_checks.csv",checks)
    dump_csv(output/"strict_validation_constructed_cases.csv",synthetic)
    dump_csv(output/"strict_validation_original44.csv",originals)
    dump_csv(output/"strict_validation_controls536.csv",controls)
    dump_json(output/"strict_validation_constructed_details.json",details)
    dump_json(output/"strict_validation_original44_details.json",original_results)
    dump_json(output/"strict_validation_control_failures_and_audit_details.json",control_details)
    dump_json(output/"strict_validation_source_hashes.json",before)
    dump_json(output/"strict_validation_summary.json",summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    if failures:raise SystemExit(1)


if __name__=="__main__":main()
