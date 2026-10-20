#!/usr/bin/env python3
"""Freeze existing history-only partitions on the same 26-person pair panel.

This registration reads labels and panel metadata only. It does not read any
native fusion outcome. The original 16-method ablation registration is intact.
"""
from pathlib import Path
from datetime import datetime, timezone
import collections
import gzip
import hashlib
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent

def read(p):
    return json.loads(p.read_text())

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    out = HERE / "competitors"
    out.mkdir(exist_ok=True)
    assert not (out / "COMPETITOR_REGISTRATION.json").exists(), "Keep existing registration immutable"
    old = ROOT / "current_main_20261020/research/workers/personnel_composition_study_20261019/analysis/forward/results"
    sources = {
        "forward": (HERE.parent / "worker_labels.csv.gz", HERE.parent / "method_manifest.json"),
        "reverse": (ROOT / "interchangeability_20261020/reverse/mixed_fit/worker_labels.csv.gz", ROOT / "interchangeability_20261020/reverse/mixed_fit/METHOD_MANIFEST.json"),
        "history_Q": (old / "worker_labels.csv.gz", old / "method_manifest.json"),
    }
    requested = [
        ("forward", "F20_newCommon_Full_balanced_K2", "all", "共同26人七域等权二类"),
        ("forward", "F20_newCommon_Full_balanced_K3", "all", "共同26人七域等权三类"),
        ("history_Q", "F_rule_Q_quantile_K2", "all", "55人历史相对Q分位二类，投影至共同26人"),
        ("history_Q", "F_rule_Q_quantile_K3", "all", "55人历史相对Q分位三类，投影至共同26人"),
        ("forward", "F20_all_QTG_balanced_medoids_K4", "all", "历史Q／T／几何四类，投影至共同26人"),
        ("reverse", "R_directswap_geometry_partition_b0_K2__ordinary_new__mixed_history_v1", "ordinary_new", "新来源历史无Q融合关系二类"),
        ("reverse", "R_directswap_geometry_partition_b0_K7__ordinary_new__mixed_history_v1", "ordinary_new", "新来源历史无Q融合关系七类"),
        ("reverse", "R_directswap_geometry_partition_b0_K7__ordinary__mixed_history_v1", "ordinary", "普通历史无Q融合关系七类，投影至共同26人"),
    ]
    base_reg = read(HERE / "COMMON_PANEL_REGISTRATION.json")
    population = base_reg["population"]
    assert len(population) == 26
    labels, manifests, input_sha = {}, {}, {}
    for key, (lp, mp) in sources.items():
        labels[key] = pd.read_csv(lp)
        m = read(mp)
        manifests[key] = m.get("methods", m)
        input_sha[key] = {"labels_path": str(lp.relative_to(ROOT)), "labels_sha256": sha(lp),
                          "manifest_path": str(mp.relative_to(ROOT)), "manifest_sha256": sha(mp)}
    rows, methods = [], []
    for source, mid, domain, name in requested:
        raw = labels[source]
        g = raw.loc[(raw.method_id == mid) & (raw.domain == domain) & raw.known.astype(str).str.lower().isin(["true", "1", "1.0"])]
        assert not g.worker_id.duplicated().any()
        mapping = dict(zip(g.worker_id, g.class_id))
        assert set(population) <= mapping.keys(), (mid, set(population) - mapping.keys())
        manifest = manifests[source][mid]
        projection = {w: mapping[w] for w in population}
        methods.append(dict(method_id=mid, domain=domain, name_zh=name, source=source,
                            original_known_people=len(g), original_class_sizes=dict(collections.Counter(mapping.values())),
                            common26_class_sizes=dict(sorted(collections.Counter(projection.values()).items())),
                            common26_members={c: [w for w in population if projection[w] == c] for c in sorted(set(projection.values()))},
                            frozen_definition=manifest.get("parameters", {k: manifest[k] for k in ("representation", "algorithm", "requested_k") if k in manifest})))
        rows.extend(dict(worker_id=w, method_id=mid, domain=domain, class_id=projection[w], known=True, origin="new") for w in population)
    packed = gzip.compress(pd.DataFrame(rows).to_csv(index=False).encode(), mtime=0)
    (out / "competitor_labels.csv.gz").write_bytes(packed)
    assert len(pd.read_csv(out / "competitor_labels.csv.gz")) == 208
    phases = {}
    for phase, panel in (("discovery", HERE), ("assessment", HERE / "assessment")):
        reg = read(panel / "COMMON_PANEL_REGISTRATION.json")
        assert reg["population"] == population
        phases[phase] = dict(panel_path=str(panel.relative_to(ROOT)), registration_sha256=sha(panel / "COMMON_PANEL_REGISTRATION.json"),
                             request_sha256=reg["request_sha256"], anchor_sha256=reg["anchor_sha256"], buildings=reg["buildings"],
                             unique_teams=reg["unique_teams"], n_values=[5, 9, 13, 17], m=2)
    reg = dict(schema="common26_frozen_forward_reverse_Q_competition_v1", frozen_utc=datetime.now(timezone.utc).isoformat(),
               selection="Parent-fixed eight existing history-only methods. No labels refit or target-dependent cut points; existing common-panel outcomes have been seen only for the original16 forward ablations, not for these newly projected competitors. Assessment outcomes have not yet been opened or summarized by this analyst.",
               population=population, population_origin="all new", method_ids=[m["method_id"] for m in methods], methods=methods,
               source_files=input_sha, competitor_labels_sha256=sha(out / "competitor_labels.csv.gz"), phases=phases,
               inherited_metric_contract_sha256=sha(HERE / "REGISTERED_COMPARISON.json"),
               primary="For same core/n/m/base A, compare all disjoint same-composition B versus different-composition C. Native eligible A support is reported; primary method ranking uses intersection of eligible A across all eight competitors. Original16 feature deletions remain separately reported on their original common16 support.",
               secondary="Report pairwise eligibility intersections with each FullK2 and FullK3 benchmark; those pairwise supports may differ and cannot be mixed-ranked. Repeat the same method lists/support rules on assessment. Also A-centered history-Qclose3 neighbor restriction, with no target Q adjustment.",
               direction="Retain actual outgoing/incoming count vectors with supports, quality direction, failure and low tail. No favorable direction is selected from assessment or used to alter separately frozen ratio hypotheses.",
               metrics="Same main/strict/wide, noQ geometry, continuous floor/angle/nodes, signed and absolute B8L2/D10, complete failures, and separate source/target block times as original panel. No new fusion/scoring/reference.",
               aggregation="Equal eligible A within core; cores within pool/n; n within pool for ALL-n summary; pictures within building; equal buildings. Repeated cores/teams are not independent images or people.",
               capacity="Projected classes may be smaller than the full historical class. Missing same-vector disjoint B is a genuine capacity loss, never imputed as a stable or unstable pair.",
               original_16_registration_unchanged_sha256=sha(HERE / "COMMON_PANEL_REGISTRATION.json"),
               script_sha256=sha(Path(__file__)))
    (out / "COMPETITOR_REGISTRATION.json").write_text(json.dumps(reg, ensure_ascii=False, indent=2, sort_keys=True))
    print(json.dumps({"methods": len(methods), "labels": len(rows), "registration_sha256": sha(out / "COMPETITOR_REGISTRATION.json"),
                      "projected_class_sizes": {m["method_id"]: m["common26_class_sizes"] for m in methods}}, ensure_ascii=False))

if __name__ == "__main__":
    main()
