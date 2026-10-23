#!/usr/bin/env python3
"""New, outcome-blind, strict large-block ABC design; NOT recovered old design.

The frozen source data identify direct same-room pairs and out-of-building
classes. No target annotation score, geometry, or time is used in selection.
All feasible integer n/m configurations are covered. Small exact spaces are
enumerated; larger spaces use balanced circular member anchors and two
background orders. ABC mirror events are deduplicated and path links preserve
the nominal original-team orientation for fixed-A scale comparisons.
"""
import argparse
import collections
import csv
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path

VERSION = "same_room_strict_abc_rebuilt_20261023_v1"
COMMIT = "e92abe8631d7f01dc192ee796b46f295ece37a6d"
SEED = "HOHONET-new-strict-ABC-20261023-v1"
RELATION_VERSION = "same_room_user_working_classification_20261016_v2"


def digest(x, n=20):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()[:n]


def team_key(pool, members):
    return pool + "__" + digest(sorted(members))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_csv(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields=None):
    rows = list(rows)
    if fields is None:
        fields = list(rows[0]) if rows else []
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def parse_members(s):
    return tuple(sorted(x for x in s.split("|") if x))


def pipe(x):
    return "|".join(sorted(x))


def num(x):
    try:
        f = float(x)
        return f if math.isfinite(f) else None
    except (ValueError, TypeError):
        return None


def boolean(x):
    return x is True or str(x).lower() == "true"


def horder(values, *key):
    return sorted(values, key=lambda x: digest([SEED, *key, x], 64))


def rotate(values, offset):
    offset %= len(values)
    return values[offset:] + values[:offset]


def create_roles(centers):
    """Describe fixed classes by historical centers, never by target outcomes.

    TURN: rank-aligned ordinal expression. JOINT: turning expression plus
    near-collinear redundancy. CONTEXT: separate contextual expression role.
    QT: historical adjusted-Q rank and adjusted-log-time sign, with exact
    centers retained. This is a display alignment, not a new fitted taxonomy.
    """
    byfold = collections.defaultdict(list)
    for r in centers:
        if r["tier"] == "coarse":
            byfold[(r["condition"], r["method"], r["heldout_building"])].append(r)
    lookup, output = {}, []
    for fold, rows in sorted(byfold.items()):
        ordered = sorted(rows, key=lambda r: (num(r["turn_history_mean"]) or 0, r["class_id"]))
        qordered = sorted(rows, key=lambda r: (num(r["q_history_mean"]) or 0, r["class_id"]))
        redmid = sorted(num(r["redundancy_history_mean"]) or 0 for r in rows)[len(rows)//2]
        for r in rows:
            k = len(rows)
            trank = ordered.index(r) + 1
            qrank = qordered.index(r) + 1
            family = r["selected_family"]
            turn = "较少转折" if trank == 1 else "较多转折" if trank == k else "常规转折"
            red = "较多近共线分段" if (num(r["redundancy_history_mean"]) or 0) > redmid else "较少近共线分段"
            if r["method"] == "V3_BEHAVIOR":
                if family == "TURN":
                    role = turn
                    aligned = f"TURN{k}:{turn}"
                elif family == "JOINT":
                    role = turn + "、" + red
                    aligned = f"JOINT{k}:{role}"
                else:
                    ct = num(r["complex_turn_history_mean"]) or 0
                    context = "复杂图额外保留" if ct > 0 else "复杂图倾向简化"
                    role = turn + "、" + context + "、" + red
                    aligned = f"CONTEXT{k}:{role}"
            else:
                qrole = "历史Q较高" if qrank == k else "历史Q较低" if qrank == 1 else "历史Q中间"
                t = num(r["t_history_mean"])
                speed = "历史较快" if t is not None and t < 0 else "历史较慢" if t is not None and t > 0 else "历史时间近基准"
                role = qrole + "、" + speed + "、" + turn
                aligned = f"{family}{k}:{role}"
            out = dict(r)
            out.update(role_zh=role, role_alignment_key=aligned,
                       turn_center_order=trank, q_center_order=qrank,
                       role_definition="coarse historical fold center display alignment; no refitting",
                       class_fold_key="|".join((*fold, r["class_id"])))
            lookup[(*fold, r["class_id"])] = out
            output.append(out)
    return lookup, output


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--anchors", type=int, default=12)
    ap.add_argument("--enumerate-max", type=int, default=512)
    a = ap.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    cap = read_csv(a.input_dir / "DIRECT_PAIR_CURRENT_CLASS_CAPACITY.csv")
    member_rows = read_csv(a.input_dir / "DIRECT_PAIR_CLASS_MEMBERS.csv")
    labels = read_csv(a.input_dir / "CURRENT_MANUAL_LABELS_LOBO.csv")
    centers = read_csv(a.input_dir / "CURRENT_MANUAL_FOLD_CENTERS.csv")
    roles, role_rows = create_roles(centers)
    write_csv(a.output / "CLASS_ROLES_AND_MEMBERS.csv", role_rows)
    qt = {(r["condition"], r["heldout_building"], r["worker_id"]): r for r in labels if r["method"] == "V3_JOINT_QT"}
    lab = {(r["condition"], r["method"], r["heldout_building"], r["worker_id"]): r for r in labels}
    with gzip.open(a.snapshot, "rt") as f:
        snap = json.load(f)
    pools = {p["pool_id"]: p for p in snap["images"]}
    object_by_pool = {pid: {r["worker_id"]: r["object_id"] for r in p["records"]} for pid, p in pools.items()}
    members = collections.defaultdict(dict)
    for r in member_rows:
        members[(r["pair_key"], r["method"])][r["class_id"]] = parse_members(r["members"])
    events, requests, config_info, directions = {}, {}, {}, []
    path_links, fixed_a_links, frozen_members = [], [], []
    input_qual_checks = []
    n_path_links_before_dedup = 0

    for ci, c in enumerate(cap):
        pair, method = c["pair_key"], c["method"]
        fold = (c["condition"], method, c["building"])
        cm = members[(pair, method)]
        known_cm = {k: tuple(v) for k, v in cm.items() if k != "unknown"}
        common = set(parse_members(c["common_members"]))
        frozen_common = set(object_by_pool[c["pool_id_a"]]) & set(object_by_pool[c["pool_id_b"]])
        assert common == frozen_common, (pair, method, "formal intersection mismatch")
        assert len(common) == int(c["common_n"])
        worker_class = {w: k for k, mm in cm.items() for w in mm}
        assert set(worker_class) == common
        assert sum(map(len, cm.values())) == len(common)
        unknown = sorted(w for w in common if worker_class[w] == "unknown")
        N = len(common)
        input_qual_checks.append({"pair_key":pair,"method":method,"common_n":N,"known_common_n":N-len(unknown),"unknown_n":len(unknown),"formal_intersection_exact":True})
        for w in sorted(common):
            cl = worker_class[w]
            lr = lab.get((*fold, w), {})
            qr = qt.get((c["condition"], c["building"], w), {})
            role = roles.get((*fold, cl), {})
            frozen_members.append({"design_version": VERSION, "pair_key": pair, "method":method,"condition":c["condition"],"building":c["building"],"worker_id":w,"class_id":cl,"role_zh":role.get("role_zh","未知类别"),"role_alignment_key":role.get("role_alignment_key","unknown"),"object_id_a":object_by_pool[c["pool_id_a"]][w],"object_id_b":object_by_pool[c["pool_id_b"]][w],"pool_id_a":c["pool_id_a"],"pool_id_b":c["pool_id_b"],"q_history":qr.get("q_history",""),"t_history":qr.get("t_history",""),"turn_history":lr.get("turn_history",""),"short_history":lr.get("short_history",""),"complex_turn_history":lr.get("complex_turn_history",""),"redundancy_history":lr.get("redundancy_history",""),"allowed_block": "D_only" if cl=="unknown" else "D_X_Y_Z"})

        for source, target in itertools.permutations(sorted(known_cm), 2):
            S, T = len(known_cm[source]), len(known_cm[target])
            M = min(S//2, T)
            sr, tr = roles[(*fold, source)], roles[(*fold, target)]
            dkey = "DIR_" + digest([pair,method,source,target])
            drow = {"direction_id":dkey,"pair_key":pair,"method":method,"condition":c["condition"],"building":c["building"],"groups":c["groups"],"ordinary_comparable":c["ordinary_comparable"],"scope_comparable":c["scope_comparable"],"image_a":c["image_a"],"image_b":c["image_b"],"source_class":source,"target_class":target,"source_role":sr["role_zh"],"target_role":tr["role_zh"],"source_role_key":sr["role_alignment_key"],"target_role_key":tr["role_alignment_key"],"source_n":S,"target_n":T,"common_n":N,"known_common_n":N-len(unknown),"unknown_members":pipe(unknown),"strict_m_max":M,"has_m_gt4":M>=5,"capacity_reason":"feasible" if M>=5 else "requires_source_ge_2m_and_target_ge_m", "source_members":pipe(known_cm[source]),"target_members":pipe(known_cm[target])}
            directions.append(drow)
            if M < 5:
                continue
            for m in range(5, M+1):
                xyspace = math.comb(S,m) * math.comb(S-m,m) // 2
                zspace = math.comb(T,m)
                for n in range(m, N-2*m+1):
                    config_id = "CFG_" + digest([pair,method,source,target,m,n])
                    space = xyspace*zspace*math.comb(N-3*m,n-m)
                    config_info[(dkey,m,n)] = {**drow,"config_id":config_id,"m":m,"n":n,"D_n":n-m,"m_over_n":m/n,"finite_event_space":space,"enumerate_all":space<=a.enumerate_max}

            def add_event(D, X, Y, Z, origin, anchor_id="", bg="", bgpath="", scale_key="", scale_n=""):
                nonlocal n_path_links_before_dedup
                D,X,Y,Z = map(lambda z:tuple(sorted(z)), (D,X,Y,Z))
                nominal_x = X
                if Y < X:
                    X,Y = Y,X
                nominal_role = "A" if nominal_x == X else "B"
                m, n = len(X), len(D)+len(X)
                assert m>4 and len(Y)==len(Z)==m
                blocks = (set(D),set(X),set(Y),set(Z))
                assert all(not blocks[i]&blocks[j] for i in range(4) for j in range(i+1,4))
                assert set(X)|set(Y) <= set(known_cm[source])
                assert set(Z) <= set(known_cm[target])
                assert set().union(*blocks) <= common
                cfg = config_info[(dkey,m,n)]
                eid = "ABC_" + digest([pair,method,source,target,D,X,Y,Z])
                A,B,C = tuple(sorted((*D,*X))),tuple(sorted((*D,*Y))),tuple(sorted((*D,*Z)))
                if eid not in events:
                    out = {"event_id":eid,"design_version":VERSION,"input_commit":COMMIT,"relation_version":RELATION_VERSION,"config_id":cfg["config_id"],"direction_id":dkey}
                    for k in ("pair_key","method","condition","building","image_a","image_b","image_id_a","image_id_b","pool_id_a","pool_id_b","reference_id_a","reference_id_b","groups","ordinary_comparable","scope_comparable","relation_tier","layer_a","layer_b","difficulty_a","difficulty_b","selected_family"):
                        out[k] = c[k]
                    out.update(source_class=source,target_class=target,source_role=sr["role_zh"],target_role=tr["role_zh"],source_role_key=sr["role_alignment_key"],target_role_key=tr["role_alignment_key"],source_class_fold_key=sr["class_fold_key"],target_class_fold_key=tr["class_fold_key"],m=m,n=n,D_n=len(D),m_over_n=m/n,D_members=pipe(D),X_members=pipe(X),Y_members=pipe(Y),Z_members=pipe(Z),A_members=pipe(A),B_members=pipe(B),C_members=pipe(C),source_n=S,target_n=T,common_n=N,known_common_n=N-len(unknown),unknown_members=pipe(unknown),D_unknown_n=sum(worker_class[w]=="unknown" for w in D),D_class_counts=json.dumps(dict(sorted(collections.Counter(worker_class[w] for w in D).items())),ensure_ascii=False,sort_keys=True,separators=(",",":")),anchor_id=anchor_id,background_order=bg,path_id=bgpath,first_origin=origin,finite_event_space=cfg["finite_event_space"],event_weight_within_config=1,canonical_xy_order="lexicographic_unordered_AB",complete_enumeration_config=cfg["enumerate_all"])
                    for blockname, block in (("D",D),("X",X),("Y",Y),("Z",Z)):
                        for metric in ("q","t"):
                            vals = [num(qt.get((c["condition"],c["building"],w),{}).get(metric+"_history")) for w in block]
                            valid = [v for v in vals if v is not None]
                            out[f"{metric}_{blockname}"] = sum(valid)/len(valid) if valid else ""
                            out[f"{metric}_{blockname}_known_n"] = len(valid)
                            out[f"{metric}_{blockname}_full_known"] = len(valid)==len(block)
                    out["three_blocks_q_full_known"] = all(out[f"q_{b}_full_known"] for b in "XYZ")
                    out["three_blocks_t_full_known"] = all(out[f"t_{b}_full_known"] for b in "XYZ")
                    out["block_history_semantics"] = "q=adjusted_relative_quality;t=adjusted_logtime;heldout_building_excluded"
                    for view in ("a","b"):
                        pid = c["pool_id_"+view]
                        for name, team in zip("ABC",(A,B,C)):
                            key = team_key(pid,team)
                            out[f"team_{name}_{view}"] = key
                            out[f"team_key_{name}_{view}"] = key
                            if key not in requests:
                                requests[key] = {"pool_id":pid,"team_key":key,"n":n,"member_workers":pipe(team),"member_object_ids":"|".join(object_by_pool[pid][w] for w in team),"design_version":VERSION,"input_commit":COMMIT}
                    events[eid] = out
                if bgpath:
                    path_links.append({"event_id":eid,"config_id":cfg["config_id"],"direction_id":dkey,"pair_key":pair,"method":method,"anchor_id":anchor_id,"background_order":bg,"background_path_id":bgpath,"m":m,"n":n,"D_n":len(D),"nominal_A_role":nominal_role,"origin":origin})
                    n_path_links_before_dedup += 1
                if scale_key:
                    fixed_a_links.append({"fixed_A_path_id":scale_key,"event_id":eid,"pair_key":pair,"method":method,"direction_id":dkey,"anchor_id":anchor_id,"n":scale_n,"m":m,"nominal_A_role":nominal_role,"fixed_A_members":pipe(A if nominal_role=="A" else B),"nominal_X_members":pipe(nominal_x),"background_order":bg})

            # Membership anchors: circular positions spread over the complete
            # class lists; ordering depends only on building, fold, and classes.
            basekey = [c["condition"],c["building"],method,source,target]
            sorder = horder(known_cm[source], *basekey, "source")
            torder = horder(known_cm[target], *basekey, "target")
            for rep in range(a.anchors):
                so = rotate(sorder, rep*S//a.anchors)
                to = rotate(torder, rep*T//a.anchors)
                # Alternate prefix orientation to avoid overselecting either
                # side of the circular source block while preserving nesting.
                if rep % 2:
                    so = list(reversed(so))
                    to = list(reversed(to))
                Xmax,Ymax,Zmax = so[:M],so[M:2*M],to[:M]
                maximum_blocks = set(Xmax+Ymax+Zmax)
                rmax = horder(common-maximum_blocks,*basekey,"background",rep)
                anchor_id = "ANC_"+digest([pair,method,source,target,rep,sorted(Xmax),sorted(Ymax),sorted(Zmax)])
                for m in range(5,M+1):
                    X,Y,Z = Xmax[:m],Ymax[:m],Zmax[:m]
                    rest = common-set(X+Y+Z)
                    fixed_order = Xmax[m:] + rmax + horder(set(Ymax[m:]+Zmax[m:]),*basekey,"end",rep,m)
                    assert set(fixed_order)==rest and len(fixed_order)==len(rest)
                    byclass = {cl:horder([w for w in rest if worker_class[w]==cl],*basekey,"roundrobin",rep,m,cl) for cl in sorted(set(worker_class[w] for w in rest))}
                    cls_order = horder(byclass, *basekey,"classorder",rep)
                    rr = []
                    for j in range(max(map(len,byclass.values()),default=0)):
                        rr.extend(byclass[cl][j] for cl in cls_order if j<len(byclass[cl]))
                    for bg, order in (("fixed_A_nested",fixed_order),("class_round_robin",rr)):
                        bgpath = "BGP_"+digest([pair,method,source,target,anchor_id,m,bg,order])
                        for dn in range(len(order)+1):
                            n=m+dn
                            scale_key=""
                            if bg=="fixed_A_nested" and M<=n<=M+len(rmax):
                                scale_key="FAP_"+digest([pair,method,source,target,anchor_id,n,sorted(Xmax+rmax[:n-M])])
                            add_event(order[:dn],X,Y,Z,"balanced_anchor",anchor_id,bg,bgpath,scale_key,n)

            # Exhaustive finite configurations. The <= threshold is defined by
            # membership capacity alone, before any endpoint is computed.
            for m in range(5,M+1):
                small = [cfg for (di,mm,nn),cfg in config_info.items() if di==dkey and mm==m and cfg["enumerate_all"]]
                if not small:
                    continue
                src=set(known_cm[source])
                for X in itertools.combinations(sorted(src),m):
                    for Y in itertools.combinations(sorted(src-set(X)),m):
                        if X>=Y:
                            continue
                        for Z in itertools.combinations(known_cm[target],m):
                            rem=sorted(common-set(X)-set(Y)-set(Z))
                            for cfg in small:
                                for D in itertools.combinations(rem,cfg["D_n"]):
                                    add_event(D,X,Y,Z,"full_enumeration")

        if (ci+1)%25==0:
            print(json.dumps({"pair_method_rows":ci+1,"events":len(events),"endpoints":len(requests)},ensure_ascii=False),flush=True)

    ev = sorted(events.values(),key=lambda r:(r["method"],r["pair_key"],r["source_class"],r["target_class"],r["m"],r["n"],r["event_id"]))
    req = sorted(requests.values(),key=lambda r:(r["pool_id"],r["n"],r["team_key"]))
    # Remove duplicate path references (physical event table already unique).
    path_links=list({json.dumps(r,sort_keys=True):r for r in path_links}.values())
    fixed_a_links=list({json.dumps(r,sort_keys=True):r for r in fixed_a_links}.values())
    fpaths=collections.defaultdict(list)
    for r in fixed_a_links:
        fpaths[r["fixed_A_path_id"]].append(r)
    valid_fp={key:rr for key,rr in fpaths.items() if len({r["m"] for r in rr})>=2}
    fixed_a_links=[r for rr in valid_fp.values() for r in rr]
    for key,rr in valid_fp.items():
        assert len({r["fixed_A_members"] for r in rr})==1
        assert len({r["n"] for r in rr})==1
    bycfg=collections.defaultdict(list)
    for r in ev:
        bycfg[r["config_id"]].append(r)
    coverage=[]
    member_coverage=[]
    for cfg in config_info.values():
        ee=bycfg[cfg["config_id"]]
        assert ee
        if cfg["enumerate_all"]:
            assert len(ee)==cfg["finite_event_space"],(cfg["config_id"],len(ee),cfg["finite_event_space"])
        cr=dict(cfg)
        cr.update(selected_unique_events=len(ee),fraction_finite_space=len(ee)/cfg["finite_event_space"],coverage_scheme="enumerated_all" if cfg["enumerate_all"] else "12_circular_anchors_2_background_orders",unique_anchor_ids=len({e["anchor_id"] for e in ee if e["anchor_id"]}))
        for block in "DXYZ":
            counter=collections.Counter(w for e in ee for w in parse_members(e[block+"_members"]))
            cr[f"{block}_unique_workers"]=len(counter)
            for w,count in sorted(counter.items()):
                member_coverage.append({"config_id":cfg["config_id"],"pair_key":cfg["pair_key"],"method":cfg["method"],"building":cfg["building"],"source_class":cfg["source_class"],"target_class":cfg["target_class"],"m":cfg["m"],"n":cfg["n"],"block":block,"worker_id":w,"events_containing":count,"events_denominator":len(ee)})
        coverage.append(cr)
    write_csv(a.output/"STRICT_ABC_EVENTS.csv.gz",ev)
    write_csv(a.output/"ENDPOINT_REQUESTS.csv.gz",req)
    write_csv(a.output/"DESIGN_PATH_LINKS.csv.gz",path_links)
    write_csv(a.output/"FIXED_A_SCALE_PATHS.csv.gz",fixed_a_links)
    write_csv(a.output/"CAPACITY_DIRECTIONS.csv",directions)
    write_csv(a.output/"CAPACITY_CONFIGURATIONS.csv",config_info.values())
    write_csv(a.output/"CONFIGURATION_COVERAGE.csv",coverage)
    write_csv(a.output/"MEMBER_COVERAGE.csv.gz",member_coverage)
    write_csv(a.output/"FROZEN_COMMON_CLASS_MEMBERS.csv.gz",frozen_members)
    write_csv(a.output/"INPUT_COMMON_POOL_CHECKS.csv",input_qual_checks)
    receipt={"design_version":VERSION,"events":len(ev),"unique_endpoint_requests":len(req),"all_events_strict_ABC_valid":True,"all_pair_common_pools_exact_snapshot_intersection":True,"all_configurations_covered":True,"small_spaces_enumeration_verified":True,"source_target_outcome_used_for_selection":False,"unknown_class_allowed_in_D_only":True,"canonical_AB_mirror_deduplicated":True,"fixed_A_paths":len(valid_fp),"fixed_A_path_links":len(fixed_a_links),"background_path_links":len(path_links),"background_path_links_before_exact_dedup":n_path_links_before_dedup}
    (a.output/"LEGALITY_RECEIPT.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    inputs=[{"path":str(p),"bytes":p.stat().st_size,"sha256":sha256(p),"input_commit":COMMIT} for p in sorted(a.input_dir.iterdir()) if p.is_file()]
    inputs.append({"path":str(a.snapshot),"bytes":a.snapshot.stat().st_size,"sha256":sha256(a.snapshot),"input_commit":COMMIT})
    write_csv(a.output/"INPUT_INDEX.csv",inputs)
    outputs=[{"file":p.name,"bytes":p.stat().st_size,"sha256":sha256(p)} for p in sorted(a.output.glob("*")) if p.is_file() and p.name not in {"DESIGN_MANIFEST.json"} and not "PRELIM" in p.name]
    manifest={"design_version":VERSION,"status":"new_experiment_not_recovered_original","input_commit":COMMIT,"relation_version":RELATION_VERSION,"seed":SEED,"anchors":a.anchors,"background_orders":["fixed_A_nested","class_round_robin"],"enumeration_max":a.enumerate_max,"strict_capacity":"m <= min(floor(source_n/2),target_n), m <= n <= N-2*m","primary_layer":"manual ordinary_comparable V3_BEHAVIOR","other_layers":"manual other scope/layers and V3_JOINT_QT retained separately; Semi has no m>4 capacity","history_q":"task-adjusted relative Q; missing values retained; complete block flag required for Q-close subdomain","history_t":"task-adjusted log time, not seconds","source_role_semantics":"fold historical center alignment; numeric class_id never pooled across folds without role keys","receipt":receipt,"input_files":inputs,"output_files":outputs,"code_sha256":sha256(Path(__file__))}
    (a.output/"DESIGN_MANIFEST.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(receipt,ensure_ascii=False,indent=2),flush=True)


if __name__=="__main__":
    main()
