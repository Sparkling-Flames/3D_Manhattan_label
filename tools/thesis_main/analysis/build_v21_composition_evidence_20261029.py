"""Index and independently check delivered finite-composition evidence only."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
PACKAGES = ROOT / "research/workers/personnel_v21_reselection_20261029/additional_delivery/packages"
OUT = ROOT / "research/data/releases/v2.1/simulated_population_evidence/composition"
METRICS = ["B8L2", "fusion_turn_n", "recorded_time_total_seconds"]
DATASETS = {
    "primary_manual45": ("03B_core", "primary_panel_inputs", "primary_compact_links", "manual", [f"03B_{i:02}" for i in range(1, 6)]),
    "primary_semi4": ("03C", "primary_semi_inputs", "primary_semi_compact_links", "semi", ["03C"]),
    "other_targets_manual45": ("03A", "other_targets_design", "", "manual", ["03A"]),
    "other_targets_semi4": ("03A", "other_targets_design", "", "semi", ["03A"]),
}


def read(path, **kwargs):
    return pd.read_csv(path, low_memory=False, **kwargs)


def write(path, frame):
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig",
                 compression={"method": "gzip", "mtime": 0} if path.suffix == ".gz" else None)


def relative(path):
    return Path(path).relative_to(ROOT).as_posix()


def truth(series):
    mapped = series.map({True: True, False: False, "True": True, "False": False})
    assert mapped.notna().all(), "Unexpected boolean/missing state"
    return mapped.astype(bool)


def vector(value):
    return {part.rsplit(":", 1)[0]: int(part.rsplit(":", 1)[1]) for part in value.split("|")}


def numeric_check(actual, expected, keys, columns):
    assert not actual.duplicated(keys).any() and not expected.duplicated(keys).any()
    joined = actual.merge(expected, on=keys, how="outer", suffixes=("_calc", "_saved"), indicator=True)
    assert joined._merge.eq("both").all(), joined.loc[joined._merge.ne("both"), keys + ["_merge"]].head().to_dict("records")
    error = 0.
    for column in columns:
        a = pd.to_numeric(joined[column + "_calc"], errors="raise").to_numpy(float)
        b = pd.to_numeric(joined[column + "_saved"], errors="raise").to_numpy(float)
        assert np.allclose(a, b, rtol=1e-8, atol=1e-8, equal_nan=True), (column, np.nanmax(abs(a - b)))
        if np.isfinite(a - b).any():
            error = max(error, float(np.nanmax(abs(a - b))))
    return len(joined), error


def moments_and_distributions(values, labels):
    """Independent finite-population moments and linear quantiles (ddof=0)."""
    good = np.isfinite(values)
    x, groups = values[good], labels[good]
    total = within = between = np.nan
    if len(x):
        unique, inv = np.unique(groups, return_inverse=True)
        counts = np.bincount(inv)
        means = np.bincount(inv, weights=x) / counts
        total = float(np.mean((x - x.mean()) ** 2))
        within = float(np.mean((x - means[inv]) ** 2))
        between = float(np.sum(counts * (means - x.mean()) ** 2) / len(x))
    result = dict(valid_teams=len(x), total_variance=total, within_variance=within, between_variance=between)
    distributions = []
    for label in np.unique(labels):
        y = values[labels == label]
        finite = y[np.isfinite(y)]
        row = dict(class_counts=label, teams=len(y), valid_teams=len(finite), missing_teams=len(y)-len(finite))
        qs = np.quantile(finite, [0, .05, .25, .5, .75, .95, 1]) if len(finite) else np.full(7, np.nan)
        row.update(zip(["minimum", "p05", "p25", "median", "p75", "p95", "maximum"], qs))
        row.update(mean=float(finite.mean()) if len(finite) else np.nan,
                   sd=float(finite.std()) if len(finite)>1 else np.nan,
                   iqr=qs[4]-qs[2] if len(finite)>1 else np.nan,
                   range=qs[6]-qs[0] if len(finite)>1 else np.nan)
        distributions.append(row)
    return result, distributions


def macro(panel_rows):
    keys = ["method", "condition", "support", "metric", "time_source"]
    fields = ["total_variance", "within_variance", "between_variance"]
    rows = panel_rows.dropna(subset=["total_variance"])
    if rows.empty:
        return pd.DataFrame(columns=keys+fields+["between_share"])
    target = rows.groupby(keys+["building", "image", "pool_id"], dropna=False)[fields].mean()
    image = target.reset_index().groupby(keys+["building", "image"], dropna=False)[fields].mean()
    building = image.reset_index().groupby(keys+["building"], dropna=False)[fields].mean()
    result = building.reset_index().groupby(keys, dropna=False)[fields].mean().reset_index()
    result["between_share"] = (result.between_variance/result.total_variance).where(result.total_variance.gt(1e-12))
    return result


def prepare(dataset):
    package, inputs_name, compact_name, condition, method_packages = DATASETS[dataset]
    inputs = PACKAGES/package/"composition"/inputs_name
    panels = read(inputs/"PANELS_USED.csv")
    panels = panels[panels.condition.eq(condition)].copy()
    links = read(inputs/"PANEL_TEAMS.csv.gz")
    links = links[links.panel_id.isin(panels.panel_id)].reset_index(drop=True)
    member_path = inputs/("TEAM_MEMBERS.csv.gz" if compact_name else "TEAM_REQUESTS.csv.gz")
    members = read(member_path).set_index("team_key")
    endpoint_path = inputs/"ENDPOINT_SCALARS.csv.gz" if compact_name else PACKAGES/package/"composition/other_targets_endpoints/ENDPOINT_SCALARS.csv.gz"
    endpoints = read(endpoint_path)
    assert not endpoints.team_key.duplicated().any() and members.index.is_unique
    endpoints = endpoints.set_index("team_key")
    wanted = links.team_key
    assert wanted.isin(endpoints.index).all() and wanted.isin(members.index).all()
    assert endpoints.loc[wanted, "condition"].eq(condition).all()
    time = pd.to_numeric(endpoints.recorded_time_total_seconds, errors="raise")
    endpoints["recorded_time_total_seconds"] = time.where(truth(endpoints.recorded_time_eligible)&time.gt(0))
    if "failure" not in endpoints:
        endpoints["failure"] = 1-truth(endpoints.complete_evaluable).astype(float)
    methods = {}
    for pk in method_packages:
        base = PACKAGES/pk/"composition"/dataset/"by_method"
        for directory in sorted(base.iterdir()):
            if directory.is_dir():
                assert directory.name not in methods
                methods[directory.name] = directory
    assert len(methods) == (45 if condition == "manual" else 4)
    labels_path = PACKAGES/("03B_core" if condition == "manual" else "03C")/"classification"/("MAIN45_LABELS_ALL_LOBO.csv.gz" if condition == "manual" else "SEMI_BASE_LABELS_ALL_LOBO.csv.gz")
    labels = read(labels_path)
    labels = labels[labels.heldout_building.ne("ALL") & labels.method.isin(methods)].copy()
    assert not labels.duplicated(["method", "heldout_building", "worker_id"]).any()
    labels = labels[truth(labels.known)&labels.class_id.notna()]
    label_maps = {m:{(r.heldout_building,r.worker_id):str(r.class_id) for r in group.itertuples()} for m,group in labels.groupby("method")}
    compact = PACKAGES/package/"composition"/compact_name if compact_name else None
    if compact:
        index = read(compact/"TEAM_LINK_INDEX.csv.gz")
        codes = read(compact/"METHOD_VECTOR_CODES.csv.gz")
        book = read(compact/"VECTOR_CODEBOOK.csv", keep_default_na=False)
        assert index.team_link_id.equals(codes.team_link_id)
        assert index[["panel_id", "team_key"]].equals(links[["panel_id", "team_key"]])
        assert truth(index.shared_known).equals(codes[list(methods)].gt(0).all(axis=1))
        vectors = {}
        for method in methods:
            codebook = book[book.method.eq(method)].set_index("vector_code").class_counts.to_dict()
            vectors[method] = pd.DataFrame(dict(panel_id=index.panel_id, team_key=index.team_key,
                class_counts=codes[method].map(codebook).fillna(""), known=codes[method].gt(0), shared_known=truth(index.shared_known)))
    else:
        vectors = {m:read(d/"TEAM_CLASS_VECTORS.csv.gz").fillna({"class_counts":""}) for m,d in methods.items()}
        for m,v in vectors.items():
            assert v[["panel_id","team_key"]].equals(links[["panel_id","team_key"]])
        common = np.logical_and.reduce([truth(v.known).to_numpy() for v in vectors.values()])
        assert all(np.array_equal(common, truth(v.shared_known)) for v in vectors.values())
    prepared = []
    for panel in panels.to_dict("records"):
        positions = links.index[links.panel_id.eq(panel["panel_id"])].to_numpy()
        keys = links.loc[positions,"team_key"].tolist()
        teams = [str(s).split("|") for s in members.loc[keys,"member_workers"]]
        workers = sorted(set(w for team in teams for w in team))
        worker_index = {w:i for i,w in enumerate(workers)}
        matrix = np.zeros((len(teams),len(workers)), dtype=np.int16)
        for i,team in enumerate(teams):
            assert len(team)==len(set(team))==int(panel["n"])
            matrix[i,[worker_index[w] for w in team]]=1
        background = set(str(panel.get("background_workers","")).split("|")) if pd.notna(panel.get("background_workers")) else set()
        background.discard("")
        for team, selected in zip(teams, links.loc[positions,"selected_variable_workers"]):
            assert set(team)==background|set(str(selected).split("|"))
        assert endpoints.loc[keys,"pool_id"].eq(panel["pool_id"]).all()
        assert endpoints.loc[keys,"k"].eq(panel["n"]).all()
        prepared.append((panel,positions,keys,workers,matrix))
    return dict(panels=panels,links=links,members_path=member_path,endpoints=endpoints,
                endpoint_path=endpoint_path,methods=methods,vectors=vectors,labels_path=labels_path,
                label_maps=label_maps,compact=compact,prepared=prepared,inputs=inputs)


def verify_method(data, method):
    vectors = data["vectors"][method]
    lm = data["label_maps"][method]
    rows, distributions = [], []
    for panel,positions,keys,workers,matrix in data["prepared"]:
        known = np.array([(panel["building"],w) in lm for w in workers])
        team_known = matrix[:,~known].sum(axis=1)==0
        vv = vectors.iloc[positions]
        assert np.array_equal(team_known,truth(vv.known))
        classes = sorted({v for (b,w),v in lm.items() if b==panel["building"]})
        class_matrix=np.array([[int(lm.get((panel["building"],w))==c) for c in classes] for w in workers],dtype=np.int16)
        calculated=matrix@class_matrix
        decoded_rows=[vector(s) for s in vv.loc[team_known,"class_counts"]]
        decoded=np.array([[d.get(c,0) for c in classes] for d in decoded_rows],dtype=np.int16).reshape((int(team_known.sum()),len(classes)))
        assert np.array_equal(calculated[team_known],decoded)
        assert (calculated[team_known].sum(axis=1)==panel["n"]).all()
        e=data["endpoints"].loc[keys]
        for support,mask in [("method_known",team_known),("shared_known",truth(vv.shared_known).to_numpy())]:
            labels=vv.loc[mask,"class_counts"].to_numpy()
            selected=e.iloc[np.flatnonzero(mask)]
            base={k:panel[k] for k in ["panel_id","pool_id","image","building","condition"]}
            base.update(method=method,support=support)
            for metric in METRICS:
                source_masks=[("not_time",np.ones(len(selected),dtype=bool))]
                if metric=="recorded_time_total_seconds":
                    kinds=selected.time_source_kinds.fillna("unknown").astype(str)
                    source_masks=[(s,kinds.eq(s).to_numpy()) for s in sorted(kinds.unique()) if s and "|" not in s]
                for source,source_mask in source_masks:
                    values=pd.to_numeric(selected[metric],errors="raise").to_numpy(float)[source_mask]
                    values[~np.isfinite(values)]=np.nan
                    result,dist=moments_and_distributions(values,labels[source_mask])
                    meta=dict(base,metric=metric,time_source=source)
                    rows.append(meta|result)
                    distributions.extend(meta|d for d in dist)
    dist_columns=["panel_id","pool_id","image","building","condition","method","support","metric","time_source",
                  "class_counts","teams","valid_teams","missing_teams","mean","minimum","p05","p25","median","p75","p95","maximum","sd","iqr","range"]
    return pd.DataFrame(rows),pd.DataFrame(distributions,columns=dist_columns)


def publish_source_index(out=OUT):
    """Publish available source tables early; validation is separately reported."""
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    indices=[];summaries=[]
    for dataset,(package,inputs_name,compact_name,condition,method_packages) in DATASETS.items():
        inputs=PACKAGES/package/"composition"/inputs_name
        compact=PACKAGES/package/"composition"/compact_name if compact_name else None
        for pk in method_packages:
            for directory in sorted((PACKAGES/pk/"composition"/dataset/"by_method").iterdir()):
                if not directory.is_dir():continue
                receipt=json.loads((directory/"COMPLETE.json").read_text(encoding="utf-8-sig"))
                summary=read(directory/"SUMMARY.csv")
                summaries.append(summary[summary.summary_axis.eq("all")].assign(dataset=dataset,source_file=relative(directory/"SUMMARY.csv")))
                indices.append(dict(dataset=dataset,method=directory.name,configuration_rows=receipt["configuration_rows"],distribution_rows=receipt["distribution_rows"],
                    counts_path=relative(directory/"CONFIGURATION_COUNTS.csv.gz"),distributions_path=relative(directory/"CONFIGURATION_DISTRIBUTIONS.csv.gz"),
                    panel_variance_path=relative(directory/"PANEL_VARIANCE.csv.gz"),summary_path=relative(directory/"SUMMARY.csv"),
                    panel_path=relative(inputs/"PANELS_USED.csv"),panel_teams_path=relative(inputs/"PANEL_TEAMS.csv.gz"),
                    members_path=relative(inputs/("TEAM_MEMBERS.csv.gz" if compact else "TEAM_REQUESTS.csv.gz")),
                    endpoints_path=relative(inputs/"ENDPOINT_SCALARS.csv.gz" if compact else PACKAGES/package/"composition/other_targets_endpoints/ENDPOINT_SCALARS.csv.gz"),
                    labels_path=relative(PACKAGES/("03B_core" if condition=="manual" else "03C")/"classification"/("MAIN45_LABELS_ALL_LOBO.csv.gz" if condition=="manual" else "SEMI_BASE_LABELS_ALL_LOBO.csv.gz")),
                    team_vectors_path=relative(directory/"TEAM_CLASS_VECTORS.csv.gz") if not compact else "",
                    compact_index_path=relative(compact/"TEAM_LINK_INDEX.csv.gz") if compact else "",
                    compact_codes_path=relative(compact/"METHOD_VECTOR_CODES.csv.gz") if compact else "",
                    compact_book_path=relative(compact/"VECTOR_CODEBOOK.csv") if compact else ""))
    for name,data in [("SOURCE_INDEX.csv",pd.DataFrame(indices)),("ALL_METHOD_SUMMARY.csv",pd.concat(summaries,ignore_index=True))]:
        temp=out/(name+".tmp")
        write(temp,data);temp.replace(out/name)


def run(out=OUT):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    publish_source_index(out)
    summaries=[];indices=[];counts=[];key_distributions=[];checks=[];recomputed=[];coverage=[]
    for dataset in DATASETS:
        data=prepare(dataset)
        p=data["panels"]
        coverage.append(dict(dataset=dataset,panels=len(p),pools=p.pool_id.nunique(),images=p.image.nunique(),
                             buildings=p.building.nunique(),team_links=len(data["links"]),unique_endpoints=data["links"].team_key.nunique(),methods=len(data["methods"])))
        for method,directory in data["methods"].items():
            print(dataset,method,flush=True)
            receipt=json.loads((directory/"COMPLETE.json").read_text(encoding="utf-8-sig"))
            count=read(directory/"CONFIGURATION_COUNTS.csv.gz")
            distribution=read(directory/"CONFIGURATION_DISTRIBUTIONS.csv.gz")
            saved_panel=read(directory/"PANEL_VARIANCE.csv.gz")
            summary=read(directory/"SUMMARY.csv")
            assert len(count)==receipt["configuration_rows"] and len(distribution)==receipt["distribution_rows"]
            assert count.teams.eq(count.possible_member_sets_on_label_support).all()
            assert truth(count.member_census_complete).all()
            for row in count.itertuples():
                full,bg,selected,capacity=map(vector,[row.class_counts,row.background_class_counts,row.selected_variable_counts,row.variable_class_capacity])
                assert sum(full.values())==row.n
                assert all(full[c]==bg[c]+selected[c] for c in full)
                possible=1
                for c in full:possible*=comb(capacity[c],selected[c])
                assert possible==row.teams
            calc,dist=verify_method(data,method)
            panel_keys=["panel_id","method","support","metric","time_source"]
            selected_panel=saved_panel[saved_panel.metric.isin(METRICS)]
            pn,pe=numeric_check(calc,selected_panel,panel_keys,["valid_teams","total_variance","within_variance","between_variance"])
            selected_dist=distribution[distribution.metric.isin(METRICS)].copy()
            dn,de=numeric_check(dist,selected_dist,panel_keys+["class_counts"],
                ["teams","valid_teams","missing_teams","mean","minimum","p05","p25","median","p75","p95","maximum","sd","iqr","range"])
            overall=summary[summary.summary_axis.eq("all")].copy()
            mn,me=numeric_check(macro(calc),overall[overall.metric.isin(METRICS)],
                ["method","condition","support","metric","time_source"],
                ["total_variance","within_variance","between_variance","between_share"])
            summaries.append(overall.assign(dataset=dataset,source_file=relative(directory/"SUMMARY.csv")))
            counts.append(count.assign(dataset=dataset,source_file=relative(directory/"CONFIGURATION_COUNTS.csv.gz")))
            key_distributions.append(selected_dist.assign(dataset=dataset,source_file=relative(directory/"CONFIGURATION_DISTRIBUTIONS.csv.gz")))
            recomputed.append(calc.assign(dataset=dataset))
            indices.append(dict(dataset=dataset,method=method,configuration_rows=len(count),distribution_rows=len(distribution),
                counts_path=relative(directory/"CONFIGURATION_COUNTS.csv.gz"),distributions_path=relative(directory/"CONFIGURATION_DISTRIBUTIONS.csv.gz"),
                panel_variance_path=relative(directory/"PANEL_VARIANCE.csv.gz"),summary_path=relative(directory/"SUMMARY.csv"),
                panel_path=relative(data["inputs"]/"PANELS_USED.csv"),panel_teams_path=relative(data["inputs"]/"PANEL_TEAMS.csv.gz"),
                members_path=relative(data["members_path"]),endpoints_path=relative(data["endpoint_path"]),labels_path=relative(data["labels_path"]),
                team_vectors_path=relative(directory/"TEAM_CLASS_VECTORS.csv.gz") if not data["compact"] else "",
                compact_index_path=relative(data["compact"]/"TEAM_LINK_INDEX.csv.gz") if data["compact"] else "",
                compact_codes_path=relative(data["compact"]/"METHOD_VECTOR_CODES.csv.gz") if data["compact"] else "",
                compact_book_path=relative(data["compact"]/"VECTOR_CODEBOOK.csv") if data["compact"] else ""))
            checks.append(dict(dataset=dataset,method=method,panel_metric_rows=pn,distribution_rows=dn,summary_rows=mn,
                max_panel_abs_error=pe,max_distribution_abs_error=de,max_summary_abs_error=me,
                full_team_lobo_vectors_verified=True,all_configuration_censuses_verified=True))
        write(out/"RECOMPUTE_CHECKS.csv",pd.DataFrame(checks))
    for filename,frames in [("ALL_METHOD_SUMMARY.csv",summaries),("CONFIGURATION_INDEX.csv.gz",counts),
                            ("KEY_DISTRIBUTIONS.csv.gz",key_distributions),("RECOMPUTED_PANEL_KEY_METRICS.csv.gz",recomputed)]:
        write(out/filename,pd.concat(frames,ignore_index=True))
    write(out/"SOURCE_INDEX.csv",pd.DataFrame(indices));write(out/"DATASET_COVERAGE.csv",pd.DataFrame(coverage))
    result=dict(complete=True,new_fusion=0,new_scoring=0,new_classification_fit=0,new_team_design=0,
                datasets=coverage,checked_methods=len(checks),independently_checked_metrics=METRICS,
                all_metrics_retained_in_summary=True,full_source_distributions_indexed=True,
                manual_shared_support="intersection of 45 methods",semi_shared_support="intersection of 4 own-Semi methods",
                total_configuration_rows=sum(len(x) for x in counts),total_source_distribution_rows=sum(r["distribution_rows"] for r in indices),
                exported_key_distribution_rows=sum(len(x) for x in key_distributions),
                max_distribution_abs_error=max(r["max_distribution_abs_error"] for r in checks))
    (out/"CHECKS.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--out",type=Path,default=OUT)
    run(parser.parse_args().out)
