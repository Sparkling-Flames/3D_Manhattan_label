#!/usr/bin/env python3
"""Wide discovery-only composition screen on actual frozen fusion outputs.

Member-team cross-fitting measures transfer to different concrete teams on the
same discovery images, not an independent-image external validation. Categories
are never re-estimated. Failed scores remain missing and failure is separate.
"""
from __future__ import annotations
import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
import argparse
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import numpy as np
import pandas as pd

SEED = 2026101961
RIDGE = 10.
METRICS = ["B8L2", "D10", "iou_2d", "IoU3D100", "ref_node_recall_9", "ref_edge_recall_9", "omission", "extension"]
MODELS = ["linear", "quadratic", "condition_linear", "image_linear"]


def js(path, obj):
    def clean(x):
        if isinstance(x, dict): return {str(k): clean(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)): return [clean(v) for v in x]
        if isinstance(x, np.integer): return int(x)
        if isinstance(x, np.bool_): return bool(x)
        if isinstance(x, (float, np.floating)): return float(x) if np.isfinite(x) else None
        return x
    path.write_text(json.dumps(clean(obj), ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def rays(footprint, directions=24):
    try:
        p = np.asarray(footprint, float)
        if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3 or not np.isfinite(p).all():
            return np.full(directions, np.nan)
        theta = (np.arange(directions) + .5) * 2 * np.pi / directions
        d = np.column_stack([np.cos(theta), np.sin(theta)])
        a, e = p, np.roll(p, -1, axis=0) - p
        den = d[:, None, 0] * e[None, :, 1] - d[:, None, 1] * e[None, :, 0]
        with np.errstate(divide="ignore", invalid="ignore"):
            r = (a[:, 0] * e[:, 1] - a[:, 1] * e[:, 0])[None, :] / den
            t = (a[None, :, 0] * d[:, None, 1] - a[None, :, 1] * d[:, None, 0]) / den
        good = (r > 0) & (t >= -1e-8) & (t <= 1 + 1e-8) & (np.abs(den) > 1e-12)
        nearest = np.where(good, r, np.inf).min(axis=1)
        return np.where(np.isfinite(nearest), np.log1p(nearest), np.nan)
    except (ValueError, TypeError):
        return np.full(directions, np.nan)


def make_baselines(f, forward, out):
    core = f[f.core_supported].sort_values("worker_id")
    rows = []
    for _, r in core.iterrows():
        rows.append({"method_id": "B_origin", "domain": "all", "worker_id": r.worker_id, "class_id": r.person_origin, "known": True, "route": "baseline"})
    for k in [2, 3, 4]:
        reference = forward[(forward.method_id == f"F_rule_Q_quantile_K{k}") & forward.known].sort_values("worker_id")
        assert set(reference.worker_id) == set(core.worker_id)
        for seed in [2026101971, 2026101972, 2026101973]:
            labels = reference.class_id.to_numpy().copy()
            np.random.default_rng(seed).shuffle(labels)
            for w, lab in zip(reference.worker_id, labels):
                rows.append({"method_id": f"B_random_Qquantile_sizes_K{k}_s{seed}", "domain": "all", "worker_id": w, "class_id": lab, "known": True, "route": "baseline"})
    baseline = pd.DataFrame(rows)
    baseline.to_csv(out / "screen_baseline_labels.csv.gz", index=False)
    return baseline


def load_panel(root, request_path, split):
    request = json.load(gzip.open(request_path, "rt"))
    requests = request["requests"]
    assert all(r["phase"] == "discovery" for r in requests)
    expected = {r["team_key"]: r for r in requests}
    assert len(expected) == len(requests), "screen requests must be unique teams"
    pools = sorted({r["pool_id"] for r in requests})
    teams = []
    for pool in pools:
        # Only these explicitly listed discovery paths are ever opened.
        path = root / "pools" / (pool + ".json.gz")
        data = json.load(gzip.open(path, "rt"))
        for team in data["teams"]:
            if team["team_key"] in expected:
                assert team["building"] in split["discovery_buildings"]
                assert sorted(team["member_workers"]) == sorted(expected[team["team_key"]]["worker_ids"])
                teams.append(team)
    assert len(teams) == len(requests), (len(teams), len(requests))
    teams.sort(key=lambda t: t["team_key"])
    return teams, request


def ridge_predict(xtr, ytr, xte, weights):
    scale = np.sqrt(np.average(xtr * xtr, axis=0, weights=weights))
    keep = scale > 1e-10
    if not keep.any():
        return np.zeros((len(xte), ytr.shape[1]))
    xtr = xtr[:, keep] / scale[keep]
    xte = xte[:, keep] / scale[keep]
    weighted = xtr * weights[:, None]
    coef = np.linalg.solve(xtr.T @ weighted + RIDGE * np.eye(xtr.shape[1]), weighted.T @ ytr)
    return xte @ coef


def regress(x, controls, y, data, image_specific=False, controlled=False):
    """Returns paired errors with intercepts learned exclusively on train teams."""
    predictions = np.full_like(y, np.nan)
    baseline = np.full_like(y, np.nan)
    controlpred = np.full_like(y, np.nan)
    ids = data.index.to_numpy()
    cellcode, cells = pd.factorize(data.cell, sort=True)
    poolcode, pools = pd.factorize(data.pool_id, sort=True)
    folds = data.fold.to_numpy(int)
    for fold in [0, 1]:
        train = folds != fold
        test = folds == fold
        ncell = len(cells)
        counts = np.bincount(cellcode[train], minlength=ncell)
        testcounts = np.bincount(cellcode[test], minlength=ncell)
        usable = (counts >= 3) & (testcounts >= 2)
        train &= usable[cellcode]
        test &= usable[cellcode]
        if train.sum() < 10 or test.sum() < 2:
            continue
        counts = np.bincount(cellcode[train], minlength=ncell)
        denom = np.maximum(counts, 1)
        xmean = np.column_stack([np.bincount(cellcode[train], weights=x[train, j], minlength=ncell) / denom for j in range(x.shape[1])])
        cmean = np.column_stack([np.bincount(cellcode[train], weights=controls[train, j], minlength=ncell) / denom for j in range(controls.shape[1])])
        ymean = np.column_stack([np.bincount(cellcode[train], weights=y[train, j], minlength=ncell) / denom for j in range(y.shape[1])])
        xc, cc, yc = x - xmean[cellcode], controls - cmean[cellcode], y - ymean[cellcode]
        # Equal cell weights within each pool. Building balance is applied to
        # reported errors; no test outcome supplies an intercept or weight.
        weights = 1. / np.maximum(counts[cellcode], 1)
        weights *= train.sum() / weights[train].sum()
        base = ymean[cellcode[test]]
        baseline[test] = base
        if controlled:
            cfit = ridge_predict(cc[train], yc[train], cc[test], weights[train])
            controlpred[test] = base + cfit
        if image_specific:
            for pool in range(len(pools)):
                tr = train & (poolcode == pool)
                te = test & (poolcode == pool)
                if tr.sum() < 10 or not te.any():
                    continue
                design = np.column_stack([cc, xc]) if controlled else xc
                delta = ridge_predict(design[tr], yc[tr], design[te], weights[tr])
                predictions[te] = ymean[cellcode[te]] + delta
                if controlled:
                    controlpred[te] = ymean[cellcode[te]] + ridge_predict(cc[tr], yc[tr], cc[te], weights[tr])
        else:
            design = np.column_stack([cc, xc]) if controlled else xc
            predictions[test] = base + ridge_predict(design[train], yc[train], design[test], weights[train])
    # Binary/recall probabilities and all scores are intentionally not clipped:
    # extrapolation penalties are part of honest squared-error model screening.
    return predictions, baseline, controlpred


def aggregate_errors(y, predictions, base, control, frame, names, info):
    rows, byimages = [], []
    for j, name in enumerate(names):
        take = np.isfinite(predictions[:, j]) & np.isfinite(base[:, j])
        if not take.any():
            rows.append(info | {"outcome": name, "status": "no_member_holdout_support", "tested_teams": 0})
            continue
        a = frame.loc[take, ["pool_id", "building", "k", "difficulty"]].copy()
        a["mse_base"] = (y[take, j] - base[take, j]) ** 2
        a["mse_model"] = (y[take, j] - predictions[take, j]) ** 2
        a["mse_control"] = (y[take, j] - control[take, j]) ** 2
        a["teams"] = 1
        cell = a.groupby(["pool_id", "building", "difficulty", "k"], as_index=False).agg(mse_base=("mse_base", "mean"), mse_model=("mse_model", "mean"), mse_control=("mse_control", "mean"), teams=("teams", "sum"))
        image = cell.groupby(["pool_id", "building", "difficulty"], as_index=False).agg(mse_base=("mse_base", "mean"), mse_model=("mse_model", "mean"), mse_control=("mse_control", "mean"), teams=("teams", "sum"), n_sizes=("k", "nunique"))
        building = image.groupby("building")[["mse_base", "mse_model", "mse_control"]].mean()
        eb, em, ec = [float(building[x].mean()) for x in ["mse_base", "mse_model", "mse_control"]]
        rows.append(info | {"outcome": name, "status": "screened", "tested_teams": int(take.sum()), "images": len(image), "buildings": len(building), "pool_size_cells": len(cell), "baseline_mse": eb, "model_mse": em, "Q_origin_baseline_mse": ec, "mse_reduction_fraction": (eb - em) / eb if eb > 1e-12 else np.nan, "additional_reduction_over_Q_origin": (ec - em) / ec if ec > 1e-12 else np.nan, "improved_images": int((image.mse_model < image.mse_base).sum()), "improved_buildings": int((building.mse_model < building.mse_base).sum())})
        for _, r in image.iterrows():
            byimages.append(info | {"outcome": name, **r.to_dict()})
    return rows, byimages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("analysis/composition"))
    ap.add_argument("--forward", type=Path, default=Path("analysis/forward/results"))
    ap.add_argument("--reverse", type=Path, default=Path("analysis/reverse"))
    ap.add_argument("--out", type=Path, default=Path("analysis/forward/screen"))
    ap.add_argument("--models", nargs="*", default=MODELS)
    ap.add_argument("--controlled-only", action="store_true")
    ap.add_argument("--method", action="append", help="Exact already-frozen method filter for sensitivity; never refits labels")
    ap.add_argument("--domain", action="append", help="Exact domain filter for sensitivity")
    ap.add_argument("--history-q-control", choices=("global", "domain", "global_domain"), default="global")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    split = json.loads((args.root / "SPLIT.json").read_text())
    teams, requests = load_panel(args.root / "runs", args.root / "SCREEN_REQUESTS.json.gz", split)
    f = pd.read_csv(args.forward / "features_train.csv.gz")
    forward = pd.read_csv(args.forward / "worker_labels.csv.gz").assign(route="forward")
    reverse = pd.read_csv(args.reverse / "worker_labels.csv.gz").assign(route="reverse")
    baseline = make_baselines(f, forward, args.out)
    labels = pd.concat([forward, reverse, baseline], ignore_index=True)
    labels["domain"] = labels.domain.replace({"global": "all"})
    workers = sorted(f.worker_id)
    ix = {w: i for i, w in enumerate(workers)}
    incidence = np.zeros((len(teams), len(workers)))
    for i, team in enumerate(teams):
        incidence[i, [ix[w] for w in team["member_workers"]]] = 1
    sizes = incidence.sum(axis=1)
    frame = pd.DataFrame([{k: t.get(k) for k in ["team_key", "pool_id", "building", "difficulty", "scene", "k", "complete_evaluable"]} for t in teams])
    frame["difficulty"] = frame.difficulty.replace({"简单": "easy", "中等": "medium", "困难": "hard"})
    frame["cell"] = frame.pool_id + "|" + frame.k.astype(str)
    frame["fold"] = [int(hashlib.sha256(f"{SEED}|{key}".encode()).hexdigest()[:12], 16) % 2 for key in frame.team_key]
    yquality = np.asarray([[np.nan if t.get(m) is None else t[m] for m in METRICS] for t in teams], float)
    yfailure = (~frame.complete_evaluable.astype(bool)).astype(float).to_numpy()[:, None]
    yshape = np.stack([rays((t.get("geometry") or {}).get("footprint")) if t.get("floor_evaluable") else np.full(24, np.nan) for t in teams])
    ordered = f.set_index("worker_id").loc[workers]
    global_controls = np.column_stack([incidence @ ordered.q_beta.to_numpy() / sizes, incidence @ ordered.person_origin.eq("new").to_numpy(float) / sizes])
    new_only = (incidence @ ordered.person_origin.eq("new").to_numpy(float)) == sizes
    condition = pd.get_dummies(frame[["difficulty", "scene"]], dtype=float).to_numpy()
    allrows, perimage, coveragerows = [], [], []
    candidates = list(labels.groupby(["method_id", "domain", "route"], sort=True))
    if args.method:
        candidates = [item for item in candidates if item[0][0] in args.method]
    if args.domain:
        candidates = [item for item in candidates if item[0][1] in args.domain]
    if args.limit:
        candidates = candidates[:args.limit]
    js(args.out / "SCREEN_DESIGN.json", {"seed": SEED, "ridge_alpha": RIDGE, "models": args.models, "member_split": "SHA256(seed|exact team_key) mod 2; pool×size intercepts fitted only on opposite-fold teams; >=3 train and >=2 heldout teams per cell", "controls": ["history-only mean q_beta globally; theta_domain in requested domain sensitivity", "new-origin member proportion"], "history_Q_control": args.history_q_control, "control_flexibility": "same polynomial degree, difficulty/scene interactions, or image-specific slopes as category model", "reference_diagnostics": "ref_node/edge_recall_9 are frozen geometric matching diagnostics, not necessary-structure correctness", "shape_diagnostic": "MSE across 24 fixed camera-centered log1p nearest-positive polygon-ray distances; supplementary screen of final geometry, not changed fusion/scoring", "aggregation": "teams within pool×size, then equal size cells per pool, then images within building, then equal buildings", "independence": "new concrete member combinations on same discovery images; overlapping teams are not independent samples", "validation_read": False, "common_known_panel": "all-new teams from fixed 35-new-person shared cohort; linear sensitivity only; compare separately from full cohort", "baseline_random_seeds": [2026101971, 2026101972, 2026101973], "failure": "missing B8 never imputed; complete-output failure separate from valid-quality and geometry masks"})
    for number, ((mid, domain, route), labs) in enumerate(candidates, 1):
        goodlabs = labs[labs.known].set_index("worker_id")
        known = np.array([w in goodlabs.index for w in workers], float)
        eligible = (incidence @ known == sizes)
        if domain in ["easy", "medium", "hard"]:
            eligible &= frame.difficulty.eq(domain).to_numpy()
        elif domain != "all":
            eligible &= False  # ordinary-Manual screen cannot validate other conditions
        controls = global_controls
        controls_known = np.ones(len(teams), bool)
        if args.history_q_control != "global" and domain in ("easy", "medium", "hard"):
            qperson = ordered["theta_" + domain].to_numpy(float)
            controls_known = (incidence @ np.isfinite(qperson).astype(float)) == sizes
            qmean = incidence @ np.nan_to_num(qperson, nan=0.) / sizes
            controls = np.column_stack([qmean, global_controls[:, 1]]) if args.history_q_control == "domain" else np.column_stack([global_controls[:, 0], qmean, global_controls[:, 1]])
        classes = sorted(goodlabs.class_id.unique())
        membership = np.array([[float(w in goodlabs.index and goodlabs.loc[w, "class_id"] == cl) for cl in classes] for w in workers]) if classes else np.zeros((len(workers), 0))
        counts = incidence @ membership
        proportions = counts / sizes[:, None] if len(classes) else counts
        signatures = [";".join(str(int(v)) for v in row) for row in counts]
        comp = frame.loc[eligible, ["pool_id", "k"]].copy()
        comp["composition"] = np.asarray(signatures)[eligible]
        cs = comp.groupby(["pool_id", "k", "composition"]).size()
        coverage = {"method_id": mid, "domain": domain, "route": route, "known_workers": int(known.sum()), "classes": len(classes), "eligible_teams": int(eligible.sum()), "eligible_images": frame.loc[eligible, "pool_id"].nunique(), "eligible_buildings": frame.loc[eligible, "building"].nunique(), "total_screen_teams": len(teams), "composition_cells": len(cs), "composition_cells_with_multiple_teams": int((cs >= 2).sum()), "teams_in_repeated_composition_cells": int(cs[cs >= 2].sum()), "quality_finite_teams": int((eligible & np.isfinite(yquality[:, 0])).sum()), "score_failures": int((eligible & yfailure[:, 0].astype(bool)).sum()), "all_new_eligible_teams": int((eligible & new_only).sum()), "history_Q_control": args.history_q_control, "eligible_teams_missing_control_Q": int((eligible & ~controls_known).sum())}
        coveragerows.append(coverage)
        if eligible.sum() < 50 or len(classes) < 2:
            allrows.append({"method_id": mid, "domain": domain, "route": route, "panel": "native_support", "model": "none", "controlled": False, "outcome": "all", "status": "no_ordinary_discovery_opportunity" if domain not in ["all", "easy", "medium", "hard"] else "insufficient_supported_teams", "tested_teams": 0})
            continue
        targets = [("quality", yquality, METRICS), ("failure", yfailure, ["score_failure"]), ("shape", yshape, [f"ray_{j:02d}" for j in range(24)])]
        for panel in ["native_support", "shared_new35"]:
            models = args.models if panel == "native_support" else ["linear"]
            panelmask = eligible & controls_known & (new_only if panel == "shared_new35" else True)
            for model in models:
                x = proportions
                model_controls = controls
                if model == "quadratic":
                    x = np.column_stack([x, *[proportions[:, i] * proportions[:, j] for i in range(len(classes)) for j in range(i, len(classes))]])
                    model_controls = np.column_stack([controls, *[controls[:, i] * controls[:, j] for i in range(controls.shape[1]) for j in range(i, controls.shape[1])]])
                elif model == "condition_linear":
                    x = np.column_stack([x, *[proportions * condition[:, j, None] for j in range(condition.shape[1])]])
                    model_controls = np.column_stack([controls, *[controls * condition[:, j, None] for j in range(condition.shape[1])]])
                for group, yall, names in targets:
                    keep = panelmask & np.isfinite(yall).all(axis=1)
                    if keep.sum() < 50:
                        continue
                    z = frame.loc[keep].reset_index(drop=True)
                    y = yall[keep]
                    for controlled in ([True] if args.controlled_only else [False, True]):
                        pred, base, cpred = regress(x[keep], model_controls[keep], y, z, image_specific=model == "image_linear", controlled=controlled)
                        info = {"method_id": mid, "domain": domain, "route": route, "panel": panel, "model": model, "controlled": controlled, "target_group": group}
                        if group == "shape":
                            # Mean coordinatewise squared error equals the loss
                            # of this explicitly fixed geometric descriptor.
                            valid = np.isfinite(pred).all(1) & np.isfinite(base).all(1)
                            # Represent exact descriptor loss as a scalar target
                            # of zero with residual magnitudes as predictions.
                            yzero = np.zeros((len(z), 1))
                            predloss = np.sqrt(np.mean((yall[keep] - pred) ** 2, axis=1))[:, None]
                            baseloss = np.sqrt(np.mean((yall[keep] - base) ** 2, axis=1))[:, None]
                            closs = np.sqrt(np.mean((yall[keep] - cpred) ** 2, axis=1))[:, None]
                            result, ims = aggregate_errors(yzero, predloss, baseloss, closs, z, ["footprint_24ray_MSE"], info)
                        else:
                            result, ims = aggregate_errors(y, pred, base, cpred, z, names, info)
                        allrows.extend(result)
                        perimage.extend(ims)
        if number % 10 == 0 or number == len(candidates):
            print(json.dumps({"candidate": number, "total": len(candidates), "method_id": mid, "eligible_teams": int(eligible.sum())}), flush=True)
            pd.DataFrame(allrows).to_csv(args.out / "screen_outcomes.partial.csv.gz", index=False)
    summary = pd.DataFrame(allrows)
    summary.to_csv(args.out / "screen_outcomes.csv.gz", index=False)
    pd.DataFrame(perimage).to_csv(args.out / "screen_per_image.csv.gz", index=False)
    pd.DataFrame(coveragerows).to_csv(args.out / "screen_coverage.csv", index=False)
    js(args.out / "SCREEN_RECEIPT.json", {"teams": len(teams), "images": frame.pool_id.nunique(), "buildings": sorted(frame.building.unique()), "distinct_workers": int((incidence.sum(axis=0) > 0).sum()), "candidate_method_domain_pairs": len(candidates), "distinct_candidate_method_ids": labels.method_id.nunique(), "outcome_rows": len(summary), "evaluated_request_sha256": sha(args.root / "SCREEN_REQUESTS.json.gz"), "forward_labels_sha256": sha(args.forward / "worker_labels.csv.gz"), "reverse_labels_sha256": sha(args.reverse / "worker_labels.csv.gz"), "code_sha256": sha(Path(__file__)), "validation_read": False, "all_expected_team_members_reconstructed_exactly": True})
    print(json.dumps({"completed": True, "outcome_rows": len(summary), "per_image_rows": len(perimage)}), flush=True)


if __name__ == "__main__": main()
