#!/usr/bin/env python3
"""Supported forward subtypes for direct, equal-turnover fusion experiments.

Candidate definitions and capacity selection use historical features and pool
membership metadata only. No screening score, replacement outcome, or held-out
quality is read. T remains a distinct efficiency axis; it is not optimized into
a quality score. Missing opportunities never become zero performance.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import cut_tree, linkage
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist
from sklearn.decomposition import PCA

from audit_and_features import clean, js, sha

BASE = Path(__file__).resolve().parents[2]
SEED = 2026102003


def robust_matrix(f, groups):
    blocks, transforms = [], {}
    for group, cols in groups.items():
        a = f[cols].to_numpy(float)
        assert np.isfinite(a).all(), (group, cols)
        center = np.median(a, axis=0)
        scale = np.quantile(a, .75, axis=0) - np.quantile(a, .25, axis=0)
        scale = np.where(scale > 1e-10, scale, 1.4826*np.median(np.abs(a-center), axis=0))
        scale = np.where(scale > 1e-10, scale, a.std(axis=0))
        scale = np.where(scale > 1e-10, scale, 1)
        z = np.clip((a-center)/scale, -3, 3) / np.sqrt(len(cols))
        blocks.append(z)
        transforms[group] = dict(fields=cols, center=center, scale=scale,
                                 clipping=[-3,3], group_weight=1/len(groups))
    return np.column_stack(blocks)/np.sqrt(len(groups)), transforms


def balanced_medoids(x, k, seed):
    """Capacity-constrained k-medoids; capacities differ by at most one.

    Hungarian assignment minimizes exact distances to representative workers;
    every accepted iterate is kept, so no assumption of monotonic reassignment
    is needed. The best of 8 deterministic initializations is selected using
    historical feature distances only.
    """
    d = cdist(x, x)
    n = len(x)
    capacities = np.full(k, n//k, int)
    capacities[:n % k] += 1
    slotclass = np.repeat(np.arange(k), capacities)
    best = None
    rng = np.random.default_rng(seed)
    for restart in range(8):
        medoids = rng.choice(n, k, replace=False)
        seen = set()
        for iteration in range(40):
            key = tuple(medoids.tolist())
            if key in seen:
                break
            seen.add(key)
            rows, slots = linear_sum_assignment(d[:, medoids[slotclass]])
            labels = np.zeros(n, int)
            labels[rows] = slotclass[slots]
            objective = float(d[np.arange(n), medoids[labels]].sum())
            if best is None or objective < best[0] - 1e-12:
                best = (objective, labels.copy(), medoids.copy(), restart, iteration)
            nxt = []
            for c in range(k):
                ids = np.flatnonzero(labels == c)
                nxt.append(ids[np.argmin(d[np.ix_(ids, ids)].sum(axis=1))])
            medoids = np.array(nxt)
    return best[1], dict(capacities=capacities.tolist(), restarts=8,
                        objective=best[0], medoid_indices=best[2].tolist(),
                        selected_restart=best[3], selected_iteration=best[4])


def relabel(lab, f, ordering):
    lab = np.asarray(lab)
    ids = sorted(set(lab.tolist()))
    # This only names groups. It does not optimize any label or outcome.
    ordering = [c for c in ordering if c in f]
    keys = {c: tuple(float(f.loc[lab == c, v].mean()) for v in ordering)
            + (str(min(f.loc[lab == c, "worker_id"])),) for c in ids}
    mp = {c: f"C{i+1:02d}" for i, c in enumerate(sorted(ids, key=lambda c: keys[c]))}
    return np.array([mp[c] for c in lab]), mp


class Catalog:
    def __init__(self, f):
        self.f = f.reset_index(drop=True)
        self.rows, self.methods, self.profiles = [], {}, []
        self.priority = []

    def add(self, method_id, lab, eligible, known, *, groups, description,
            domain="all", pool_filter="ordinary_manual", eligible_definition,
            parameters=None, family="rule", objective="interchangeability_and_quality",
            order=None, status=None, shortlist_priority=None, ablation=None):
        assert method_id not in self.methods, method_id
        good = np.asarray(known, bool)
        elig = np.asarray(eligible, bool)
        assert np.all(~good | elig), method_id
        g = self.f.loc[good].reset_index(drop=True)
        fields = list(dict.fromkeys(itertools.chain.from_iterable(groups.values())))
        if len(g) and lab is not None and len(set(lab)) >= 2:
            labels, naming_map = relabel(lab, g, order or fields)
            classes = sorted(set(labels))
            worker_map = dict(zip(g.worker_id, labels))
            sizes = Counter(labels)
            status = status or ("supported" if min(sizes.values()) >= 4 else "small_class_limited_block_capacity")
        else:
            labels, classes, worker_map, sizes, naming_map = [], [], {}, {}, {}
            status = status or "failed_insufficient_opportunity_or_no_feature_variation"
        manifest = dict(method_id=method_id, domain=domain, pool_filter=pool_filter,
            family=family, description_zh=description, objective=objective,
            eligible_definition=eligible_definition, eligible_workers=self.f.loc[elig,"worker_id"].tolist(),
            history_feature_supported_workers=g.worker_id.tolist(), known_workers=sorted(worker_map),
            unknown_policy="Outside population or missing required opportunity is unknown; may form a fixed outside_group background but is never treated as a subtype member.",
            known_workers_n=len(worker_map), classes_n=len(classes), class_sizes=dict(sizes),
            feature_groups=groups, required_fields=fields, parameters=parameters or {},
            ordering_fields=order or fields, status=status, train_key=self.f.train_key.iloc[0],
            ablation=ablation, classes={})
        tcols = [c for c in fields if "time_effect" in c or c=="t_source_origin_effect"]
        if not tcols:
            tcols = ["t_source_origin_effect"]
        for c in classes:
            cc = g.loc[np.asarray(labels)==c]
            means = {col: float(cc[col].mean()) if cc[col].notna().any() else None
                     for col in list(dict.fromkeys(fields + ["q_beta","q_abs_mean","q_abs_p10","q_residual_sd",
                         "pair_count_effect","bottom_y_effect","top_y_effect","height_log_effect",
                         "t_source_origin_effect","t_log_residual_tail","source_time_median",
                         "hard_minus_easy","semi_new_error_nonedit_effect","semi_new_edit_effect",
                         "semi_old_edit_effect","scope_out_effect"]))}
            time = {}
            for origin, co in cc.groupby("person_origin"):
                time[origin] = {col: {"n": int(co[col].notna().sum()),
                     "log_effect_mean": float(co[col].mean()) if co[col].notna().any() else None,
                     "multiplicative_time": float(np.exp(co[col].mean())) if co[col].notna().any() else None}
                     for col in tcols}
            manifest["classes"][c] = dict(workers=sorted(cc.worker_id), people=len(cc),
                origin_counts=cc.person_origin.value_counts().to_dict(), feature_means=means,
                relative_time_by_origin=time,
                time_interpretation="Source-specific task-adjusted multiplier, not cross-source absolute seconds or independently verified raw log time.")
            row = dict(method_id=method_id, domain=domain, class_id=c, people=len(cc),
                       new_people=int(cc.person_origin.eq("new").sum()), v1_people=int(cc.person_origin.eq("v1").sum()),
                       members="|".join(sorted(cc.worker_id)))
            row.update(means)
            self.profiles.append(row)
        canonical = json.dumps(sorted(worker_map.items()), separators=(",", ":"))
        manifest["partition_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
        self.methods[method_id] = manifest
        if shortlist_priority is not None:
            self.priority.append((shortlist_priority, method_id))
        for i, r in self.f.iterrows():
            label = worker_map.get(r.worker_id, "unknown")
            reason = "supported_history" if label != "unknown" else ("outside_eligible_population" if not elig[i]
                else "insufficient_required_feature_opportunity" if not good[i] else "candidate_definition_failed")
            self.rows.append(dict(worker_id=r.worker_id, method_id=method_id, domain=domain,
                class_id=label, known=label != "unknown", origin=r.person_origin,
                eligible_population=bool(elig[i]), reason=reason, train_key=r.train_key))

    def scalar(self, name, population, column, *, k=2, cut=None, description,
               definition, domain="all", pool_filter="ordinary_manual", priority=None,
               feature_group="T", objective="interchangeability_and_quality"):
        good = population & self.f[column].notna()
        values = self.f.loc[good, column].to_numpy(float)
        cuts = np.asarray(cut if cut is not None else np.quantile(values, np.arange(1,k)/k) if len(values) else [],float)
        labels = np.searchsorted(cuts, values, side="left") if len(values) >= 2*k else None
        par = {"requested_k":k, "cuts":cuts.tolist(), "cut_rule":"fixed" if cut is not None else "history population quantiles; ties stay together",
               "comparison":"lower bin includes cut equality"}
        self.add(name, labels, population, good, groups={feature_group:[column]}, description=description,
                 eligible_definition=definition, domain=domain, pool_filter=pool_filter, parameters=par,
                 shortlist_priority=priority, objective=objective)

    def cross(self, name, population, columns, *, description, definition,
              cuts=None, domain="all", pool_filter="ordinary_manual", priority=None):
        good = population & self.f[columns].notna().all(axis=1)
        g = self.f.loc[good]
        cuts = list(cuts) if cuts is not None else [float(g[c].median()) for c in columns]
        lab = sum((g[col].to_numpy(float)>cut).astype(int)*2**(len(columns)-i-1)
                  for i,(col,cut) in enumerate(zip(columns,cuts)))
        self.add(name, lab if len(g)>=8 else None, population, good,
            groups={f"axis{i+1}":[col] for i,col in enumerate(columns)},
            description=description, eligible_definition=definition, domain=domain,
            pool_filter=pool_filter, parameters={"axis_cuts":dict(zip(columns,cuts)),"comparison":"> cut; ties stay together"},
            family="interpretable_cross", order=columns, shortlist_priority=priority)

    def cluster(self, name, population, groups, *, k, description, definition,
                algorithm="balanced_medoids", domain="all", pool_filter="ordinary_manual",
                priority=None, shared_mask=None, ablation=None):
        fields = list(dict.fromkeys(itertools.chain.from_iterable(groups.values())))
        good = population & self.f[fields].notna().all(axis=1)
        if shared_mask is not None:
            good &= shared_mask
        g = self.f.loc[good].reset_index(drop=True)
        par = {"requested_k":k,"seed":SEED,"groups_equal_weight":True,"missing_handling":"complete required opportunities; no imputation"}
        if len(g) < 4*k:
            lab = None
            par["failure"] = f"only {len(g)} supported workers; require >=4*k for multivariate partition"
        else:
            x, transform = robust_matrix(g, groups)
            par["transforms"] = transform
            if algorithm=="pca_ward":
                pc = PCA(n_components=min(3,x.shape[1],len(g)-1), svd_solver="full")
                z = pc.fit_transform(x)
                lab = cut_tree(linkage(z, method="ward"), n_clusters=k).ravel()
                par.update(pca_components=pc.components_, pca_variance_ratio=pc.explained_variance_ratio_,
                           retained_dimensions=z.shape[1], linkage="ward")
            else:
                lab, extra = balanced_medoids(x,k,SEED+31*k)
                par.update(extra)
                par["medoid_workers"] = g.iloc[extra["medoid_indices"]].worker_id.tolist()
        self.add(name,lab,population,good,groups=groups,description=description,
            eligible_definition=definition,domain=domain,pool_filter=pool_filter,
            parameters=par,family=algorithm,shortlist_priority=priority,ablation=ablation)


def define_candidates(f):
    c = Catalog(f)
    core = f.core_supported.astype(bool)
    high23 = core & f.q_beta.ge(0)
    # Reproduce the original exact high-tertile membership from historical rank.
    cut18 = float(np.quantile(f.loc[core,"q_beta"],2/3))
    high18 = core & f.q_beta.gt(cut18)
    new = core & f.person_origin.eq("new")
    highnew = high23 & f.person_origin.eq("new")
    old = f.person_origin.eq("v1")
    defs = {"all":"core_supported (>=8 ordinary Manual history tasks and >=3 buildings)",
            "high23":"core_supported and history q_beta>=0 (23 workers, new15/v1 8)",
            "high18":f"core_supported and history q_beta>{cut18:.14g} (original Q-tertile high18)",
            "new":"core_supported and origin=new (35 workers)",
            "highnew":"core_supported and q_beta>=0 and origin=new (15 workers)"}
    Q = {"Q":["q_beta","q_residual_p10","q_residual_sd"]}
    T = {"T":["t_source_origin_effect","t_log_residual_tail"]}
    G = {"geometry":["pair_count_effect","bottom_y_effect","height_log_effect"]}
    D = {"difficulty":["hard_minus_easy","medium_minus_easy"]}
    E = {"semi_edit":["semi_new_edit_effect"]}
    R = {"new_report_nonedit":["semi_new_error_nonedit_effect"]}
    S = {"scope_propensity":["scope_out_effect"]}
    # Baselines and single-variable competitors are still real candidates.
    c.scalar("F20_all_Q_zero_K2",core,"q_beta",cut=[0],description="历史相对Q零阈两类；本轮基线",definition=defs["all"],feature_group="Q",priority=1)
    for k in [2,3,4]:
        c.scalar(f"F20_all_T_qK{k}",core,"t_source_origin_effect",k=k,
            description="来源内任务调整时间分位类；速度作为独立效用",definition=defs["all"],priority=3 if k==3 else None,objective="efficiency_and_interchangeability")
    c.cross("F20_all_QxT_K4",core,["q_beta","t_source_origin_effect"],cuts=[0,0],
            description="Q方向与同来源相对时间方向交叉；不相加总分",definition=defs["all"],priority=2)
    for name,pop in [("highQ23",high23),("highQ18",high18)]:
        de = defs["high23" if name=="highQ23" else "high18"]
        scalar_axes = [("T","t_source_origin_effect","时间", "T"),
            ("Ttail","t_log_residual_tail","时间长尾", "T"),
            ("Detail","pair_count_effect","相对点数习惯", "geometry"),
            ("Bottom","bottom_y_effect","历史底部垂直坐标倾向", "geometry"),
            ("Top","top_y_effect","历史顶部垂直坐标倾向", "geometry"),
            ("Height","height_log_effect","高度比倾向", "geometry"),
            ("Qtail","q_residual_p10","同任务相对Q低尾", "Q"),
            ("Volatility","q_residual_sd","同任务相对Q波动", "Q")]
        for short,col,text,grp in scalar_axes:
            for k in [2,3]:
                pr = None
                if name=="highQ23":
                    pr = {("T",2):8,("T",3):9,("Detail",2):10,("Bottom",2):11,("Height",2):12}.get((short,k))
                elif short=="T" and k==2:pr=16
                c.scalar(f"F20_{name}_{short}_qK{k}",pop,col,k=k,
                    description=f"{name}内部{text}分位细类",definition=de,feature_group=grp,priority=pr,
                    objective="efficiency_and_interchangeability" if grp=="T" else "interchangeability_and_quality")
        for shorts,cols in [("TxDetail",["t_source_origin_effect","pair_count_effect"]),
                            ("TxBottom",["t_source_origin_effect","bottom_y_effect"]),
                            ("TxQtail",["t_source_origin_effect","q_residual_p10"]),
                            ("DetailxHeight",["pair_count_effect","height_log_effect"])]:
            c.cross(f"F20_{name}_{shorts}_K4",pop,cols,description=f"{name}内两种可解释倾向的中位数交叉",
                    definition=de,priority=13 if name=="highQ23" and shorts=="TxDetail" else None)
    # Coarse quality group preserved, refine only the high branch. This keeps
    # outside high-Q participants as a named coarse group for composition use.
    for axes,suffix,pr in [(["t_source_origin_effect"],"T",6),
                           (["t_source_origin_effect","pair_count_effect"],"TxDetail",7)]:
        good = core & (~high23 | f[axes].notna().all(axis=1))
        labs = np.zeros(good.sum(),int)
        fg = f.loc[good]
        hi = fg.q_beta.ge(0).to_numpy()
        cuts = {col:float(f.loc[high23,col].median()) for col in axes}
        labs[hi] = 1 + sum((fg.loc[hi,col].to_numpy()>cuts[col]).astype(int)*2**(len(axes)-j-1)
                           for j,col in enumerate(axes))
        c.add(f"F20_coarseQ_refineHigh_{suffix}",labs,core,good,groups={"Q":["q_beta"],"refinement":axes},
              description="保留Q<0粗类，只细分Q>=0群；与高Q子群专用标签分别登记",eligible_definition=defs["all"],
              parameters={"coarse_cut":0,"high_branch_cuts":cuts},family="coarse_then_refine",order=["q_beta",*axes],shortlist_priority=pr)
    for population,pop,de,ks,families in [
        ("all",core,defs["all"],[2,3,4,5,6,8],{"QTG":Q|T|G,"TG":T|G}),
        ("highQ23",high23,defs["high23"],[2,3,4],{"TG":T|G,"TQtail":T|{"Qtail":["q_residual_p10","q_residual_sd"]},"Q-T-G":Q|T|G}),
        ("highQ18",high18,defs["high18"],[2,3,4],{"TG":T|G}),
    ]:
        for family,groups in families.items():
            for algorithm in ["balanced_medoids","pca_ward"]:
                for k in ks:
                    pr = None
                    if algorithm=="balanced_medoids":
                        pr={('all','QTG',3):4,('all','QTG',4):5,('highQ23','TG',3):14,('highQ23','TQtail',3):15}.get((population,family,k))
                    c.cluster(f"F20_{population}_{family}_{algorithm}_K{k}",pop,groups,k=k,
                        algorithm=algorithm,description="少量历史字段域等权的人员细类；不以目标融合Q筛选",definition=de,priority=pr)
    # Existing difficulty protocol is a declared condition, not a newly learned
    # pre-acquisition image detector. All/hard versions expose the same mechanism.
    for domain in ["all","hard"]:
        c.scalar(f"F20_highQ23_HardAdapt_qK2_{domain}",high23,"hard_minus_easy",k=2,
            description="高Q内困难相对容易的历史适应细类",definition=defs["high23"],feature_group="difficulty",domain=domain,
            priority=17 if domain=="hard" else None)
    # Behavior candidates actually enter both Manual and relevant Semi panels.
    for short,col,grp in [("Scope","scope_out_effect","scope_propensity"),
                          ("NewNonedit","semi_new_error_nonedit_effect","new_report_nonedit"),
                          ("NewEdit","semi_new_edit_effect","semi_edit")]:
        for popname,pop,de in [("new",new,defs["new"]),("highQnew",highnew,defs["highnew"])]:
            for k in [2,3]:
                pr = {('new','Scope',2):22,('new','NewNonedit',2):24,('new','NewEdit',2):26}.get((popname,short,k))
                c.scalar(f"F20_{popname}_{short}_qK{k}",pop,col,k=k,
                    description="新来源历史行为倾向细类；未修改不等于盲信、scope不等于裁定正确",definition=de,
                    feature_group=grp,priority=pr)
            for k in [2,3]:
                groups=T|{grp:[col]}
                pr={('new','Scope',3):23,('new','NewNonedit',3):25,('new','NewEdit',3):27,
                    ('highQnew','Scope',2):18,('highQnew','NewNonedit',2):20,('highQnew','NewEdit',2):21}.get((popname,short,k))
                c.cluster(f"F20_{popname}_T_{short}_balanced_K{k}",pop,groups,k=k,
                    description="时间效率与行为倾向分别保留的双域细类",definition=de,priority=pr)
        # Manual-trained behavioral labels evaluated under Semi separately.
        c.scalar(f"F20_semiNew_{short}_qK2",f.person_origin.eq("new"),col,k=2,
            description="历史行为倾向在新Semi条件的直接替换实验；不以普通结果代替",definition="origin=new and required historical behavioral opportunity",
            feature_group=grp,domain="semi_new",pool_filter="semi_new",priority=33 if short=="NewNonedit" else 34 if short=="Scope" else None)
    c.cluster("F20_highQnew_DG_balanced_K2",highnew,D|G,k=2,
        description="同为新批高Q的困难适应与几何细类",definition=defs["highnew"],domain="hard",priority=19)
    c.cluster("F20_hard_TDG_balanced_K3",core,T|D|G,k=3,
        description="已有困难判定下的时间、适应与几何细类",definition=defs["all"],domain="hard",priority=30)
    # Group ablation: every fit uses the identical complete-opportunity people,
    # even when one group is removed. This prevents coverage gains masquerading
    # as information gains. No labels are tuned with direct replacement outputs.
    full = Q|T|D|G|E|R|S
    common = new & f[list(itertools.chain.from_iterable(full.values()))].notna().all(axis=1)
    for k in [2,3]:
        for removed in [None,*full]:
            groups = {g:cols for g,cols in full.items() if g!=removed}
            suffix="Full" if removed is None else "No"+removed
            priority = 28 if k==3 and removed is None else 29 if k==3 and removed=="Q" else None
            c.cluster(f"F20_newCommon_{suffix}_balanced_K{k}",new,groups,k=k,
                description="固定共同机会人员的七域多变量分型或删一域消融",definition=defs["new"]+"; fixed intersection of Q/T/difficulty/geometry/edit/new-nonedit/scope support",
                shared_mask=common,ablation={"family":f"newCommon_K{k}","removed_group":removed,"common_workers":f.loc[common,"worker_id"].tolist()},priority=priority)
    # Own-condition quality, geometry and time, with source-specific behavior.
    for domain,pop,pr in [("semi_new",f.semi_new_supported.astype(bool),31),
                          ("semi_v1",f.semi_v1_supported.astype(bool),35),
                          ("doorway",f.doorway_supported.astype(bool),36)]:
        pre="cond_"+domain+"_"
        q={"condition_Q":[pre+"q_effect",pre+"q_abs_p10"]}
        t={"condition_T":[pre+"time_effect"]}
        g={"condition_geometry":[pre+"pair_effect",pre+"bottom_y_effect",pre+"height_log_effect"]}
        pool_filter={"doorway":"doorway_manual"}.get(domain,domain)
        de=f"own {domain} qualified historical final-Q support (>=4 tasks, >=3 buildings); required own-condition fields known"
        for k in [2,3]:
            for short,col,group in [("Q",pre+"q_effect","condition_Q"),("T",pre+"time_effect","condition_T")]:
                c.scalar(f"F20_{domain}_{short}_qK{k}",pop,col,k=k,description="本条件自己的最终质量或时间细类",definition=de,
                         feature_group=group,domain=domain,pool_filter=pool_filter,
                         objective="efficiency_and_interchangeability" if short=="T" else "interchangeability_and_quality")
        c.cross(f"F20_{domain}_QxT_K4",pop,[pre+"q_effect",pre+"time_effect"],
                description="本条件Q和T中位数交叉",definition=de,domain=domain,pool_filter=pool_filter)
        families={"QT":q|t,"QTG":q|t|g}
        if domain=="semi_new":
            families.update(QTGEditReport=q|t|g|E|R, QTGScope=q|t|g|S)
        elif domain=="semi_v1":
            families.update(QTGEdit=q|t|g|{"old_edit":["semi_old_edit_effect"]})
            c.scalar("F20_semiV1_Edit_qK2",old,"semi_old_edit_effect",description="旧Semi一般修改倾向，不推定修对",definition="origin=v1 and old editing opportunity supported",feature_group="old_edit",domain=domain,pool_filter=pool_filter)
        for family,groups in families.items():
            for k in [2,3,4]:
                p = pr if k==3 and ((domain=="semi_new" and family=="QT") or (domain=="semi_v1" and family=="QTGEdit") or (domain=="doorway" and family=="QTG")) else None
                if domain=="semi_new" and family=="QTGEditReport" and k==3:p=32
                c.cluster(f"F20_{domain}_{family}_balanced_K{k}",pop,groups,k=k,description="本条件的多变量少维细类，保留行为证据等级",definition=de,
                          domain=domain,pool_filter=pool_filter,priority=p)
    # Failures are prospective definitions, not hidden zero-valued evidence.
    for domain,col,pop in [("semi_v1","semi_old_error_nonedit_effect",old),
                           ("semi_new","cond_semi_new_scope_effect",f.person_origin.eq("new")),
                           ("semi_v1","cond_semi_v1_scope_effect",old)]:
        suffix="ConfirmedNonedit" if "nonedit" in col else "OwnScope"
        c.scalar(f"F20_{domain}_{suffix}_qK2",pop,col,k=2,
            description="本条件已登记但历史机会或变异可能不足，失败保留",definition=f"origin matching {domain}; original field opportunity gate",
            feature_group="behavior",domain=domain,pool_filter=domain)
    return c


def capacity(catalog, repo, split):
    inv = pd.read_csv(repo/"research/workers/personnel_composition_handoff_20261019/POOL_INVENTORY.csv")
    mem = pd.read_csv(repo/"research/workers/personnel_composition_handoff_20261019/POOL_MEMBERS.csv.gz")
    pools = {p.pool_id:p for p in inv.itertuples()}
    members = {key:g.drop_duplicates("worker_id") for key,g in mem.groupby("pool_id")}
    phase = {b:p for p in ["history","discovery","validation"] for b in split[p+"_buildings"]}
    rows, summaries = [], []
    # Exact participant-capacity bounds, before background/team sampling. A/B
    # reserve 2m different outgoing-class workers and C reserves m incoming.
    panels=[(5,1),(5,2),(9,2),(9,3),(13,2),(13,4),(17,2),(17,4),(17,6)]
    for method, spec in catalog.methods.items():
        label = {w:cl for cl,info in spec["classes"].items() for w in info["workers"]}
        local=[]
        if len(spec["classes"])<2:
            spec["capacity"]={"status":"no_supported_partition"}
            continue
        for pid,g0 in members.items():
            p=pools[pid]
            if spec["pool_filter"] in ["semi_new","semi_v1"]:
                if p.layer != "ordinary_semi":continue
                origin="new" if spec["pool_filter"]=="semi_new" else "v1"
                g=g0[g0.origin.eq(origin)].copy()
            else:
                if p.layer!=spec["pool_filter"]:continue
                g=g0.copy()
            if spec["domain"] in ["easy","medium","hard"]:
                cn={"easy":"简单","medium":"中等","hard":"困难"}[spec["domain"]]
                if p.difficulty!=cn:continue
            if g.empty:continue
            g["class_id"]=g.worker_id.map(label)
            ct=g.dropna(subset=["class_id"]).groupby(["class_id","origin"]).size().to_dict()
            classes=sorted(g.class_id.dropna().unique())
            for n,m in panels:
                if n+2*m>len(g):continue
                for out,inc in itertools.permutations(classes,2):
                    on,ov=ct.get((out,"new"),0),ct.get((out,"v1"),0)
                    inn,iv=ct.get((inc,"new"),0),ct.get((inc,"v1"),0)
                    if on+ov<2*m or inn+iv<m:continue
                    source_alloc=[r for r in range(m+1) if on>=2*r and ov>=2*(m-r) and inn>=r and iv>=m-r]
                    row=dict(method_id=method,domain=spec["domain"],pool_filter=spec["pool_filter"],
                        phase=phase[p.building],pool_id=pid,image=p.image,building=p.building,
                        k=n,m=m,out_class=out,in_class=inc,pool_workers=len(g),known_workers=int(g.class_id.notna().sum()),
                        out_available=on+ov,in_available=inn+iv,source_matched_feasible=bool(source_alloc),
                        feasible_new_block_counts="|".join(map(str,source_alloc)))
                    local.append(row)
        rows.extend(local)
        lc=pd.DataFrame(local)
        methodsum=[]
        if len(lc):
            for keys,g in lc.groupby(["phase","k","m"]):
                gs=g[g.source_matched_feasible]
                methodsum.append(dict(method_id=method,domain=spec["domain"],phase=keys[0],k=keys[1],m=keys[2],
                    feasible_images=g.image.nunique(),feasible_buildings=g.building.nunique(),
                    directed_pool_class_cells=len(g),source_matched_images=gs.image.nunique(),
                    source_matched_buildings=gs.building.nunique(),source_matched_cells=len(gs)))
        summaries.extend(methodsum)
        hist=[r for r in methodsum if r["phase"]=="history" and r["m"]>=2]
        spec["capacity"]={"history_max_images_mge2":max([r["feasible_images"] for r in hist] or [0]),
            "history_max_buildings_mge2":max([r["feasible_buildings"] for r in hist] or [0]),
            "history_max_source_matched_images_mge2":max([r["source_matched_images"] for r in hist] or [0]),
            "history_max_source_matched_buildings_mge2":max([r["source_matched_buildings"] for r in hist] or [0]),
            "interpretation":"Exact membership capacity bounds with fixed unlabelled/background people allowed; not observed fusion success. Background class mix and individual sampling remain for direct experiment."}
    return pd.DataFrame(rows),pd.DataFrame(summaries)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--features",type=Path,default=Path(__file__).resolve().parent/"features_train.csv.gz")
    ap.add_argument("--repo",type=Path,default=BASE/"repo")
    ap.add_argument("--split",type=Path,default=BASE/"analysis/composition/SPLIT.json")
    ap.add_argument("--out",type=Path,default=Path(__file__).resolve().parent)
    args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    f=pd.read_csv(args.features)
    split=json.loads(args.split.read_text())
    catalog=define_candidates(f)
    capacities,summaries=capacity(catalog,args.repo,split)
    capacities.to_csv(args.out/"capacity_directed_cells.csv.gz",index=False)
    summaries.to_csv(args.out/"capacity_summary.csv",index=False)
    ledger=[]
    seen={}
    for method,m in catalog.methods.items():
        signature=m["partition_sha256"]
        dup=seen.get((m["pool_filter"],m["domain"],signature))
        if m["known_workers_n"]:seen.setdefault((m["pool_filter"],m["domain"],signature),method)
        m["duplicate_partition_same_domain_of"]=dup
        ledger.append(dict(method_id=method,domain=m["domain"],pool_filter=m["pool_filter"],family=m["family"],
            status=m["status"],eligible_people=len(m["eligible_workers"]),known_people=m["known_workers_n"],
            K=m["classes_n"],class_sizes="/".join(map(str,m["class_sizes"].values())),
            min_class_n=min(m["class_sizes"].values()) if m["class_sizes"] else 0,
            feature_groups="|".join(m["feature_groups"]),objective=m["objective"],
            duplicate_partition_of=dup,history_mge2_images=m.get("capacity",{}).get("history_max_images_mge2",0),
            history_mge2_buildings=m.get("capacity",{}).get("history_max_buildings_mge2",0),
            history_source_matched_mge2_images=m.get("capacity",{}).get("history_max_source_matched_images_mge2",0),
            history_source_matched_mge2_buildings=m.get("capacity",{}).get("history_max_source_matched_buildings_mge2",0),
            partition_sha256=signature))
    chosen=[]
    for pr,method in sorted(catalog.priority):
        m=catalog.methods[method]
        eligible=m["known_workers_n"]>=8 and m["classes_n"]>=2 and m.get("capacity",{}).get("history_max_buildings_mge2",0)>=3
        chosen.append(dict(priority=pr,method_id=method,domain=m["domain"],pool_filter=m["pool_filter"],
            capacity_gate_passed=eligible,class_sizes=m["class_sizes"],
            known_people=m["known_workers_n"],capacity=m.get("capacity"),
            objective=m["objective"],selection_basis="pre-outcome feature-domain diversity plus history-only membership capacity; no target fusion score selection"))
    long=pd.DataFrame(catalog.rows)
    long.to_csv(args.out/"worker_labels.csv.gz",index=False)
    pd.DataFrame(ledger).to_csv(args.out/"candidate_ledger.csv",index=False)
    pd.DataFrame(catalog.profiles).to_csv(args.out/"class_profiles.csv.gz",index=False)
    js(args.out/"method_manifest.json",dict(schema="interchangeability_forward_types_20261020_v1",seed=SEED,
        train_key=f.train_key.iloc[0],history_buildings=split["history_buildings"],
        target_outcomes_used=False,method_count=len(catalog.methods),methods=catalog.methods,
        background_policy="Only A/B/C exchanged blocks require these labels; other real pool members may form an identical fixed outside_group background, explicitly untyped.",
        efficiency_policy="Report quality, within-class stability and time separately. Source-specific exp(log-time effect) is descriptive historical relative efficiency; actual team time/known coverage evaluated separately.",
        difficulty_policy="Difficulty includes inherited reference geometry and review; conditional rules require the same known protocol and are not an automatic new-image difficulty detector."))
    js(args.out/"SHORTLIST.json",dict(schema="history_capacity_diverse_forward_shortlist_v1",items=chosen,
        additional_ablation_families=[dict(family=f"newCommon_K{k}",method_ids=[m for m,v in catalog.methods.items() if (v.get("ablation") or {}).get("family")==f"newCommon_K{k}"])
                                      for k in [2,3]],
        no_outcome_screening_performed=True,omission_note="Complete ledger includes unsupported and small classes; shortlist is a capacity-and-domain proposal for the root's direct A/B versus A/C experiment, not an effectiveness claim."))
    js(args.out/"BUILD_RECEIPT.json",dict(utc=datetime.now(timezone.utc).isoformat(),seed=SEED,
        features_sha256=sha(args.features),labels_sha256=sha(args.out/"worker_labels.csv.gz"),
        code_sha256=sha(Path(__file__)),split_sha256=sha(args.split),
        candidate_definitions=len(catalog.methods),labels_rows=len(long),
        supported_methods=int(pd.DataFrame(ledger).K.ge(2).sum()),
        distinct_supported_domain_partitions=int(pd.DataFrame(ledger).query("K>=2").drop_duplicates(["pool_filter","domain","partition_sha256"]).shape[0]),
        requested_shortlist=len(chosen),capacity_passed_shortlist=sum(r["capacity_gate_passed"] for r in chosen),
        directed_capacity_rows=len(capacities),fusion_runs=0,target_outcomes_read=False))
    print(json.dumps(clean({"definitions":len(catalog.methods),"supported":sum(m["classes_n"]>=2 for m in catalog.methods.values()),
        "shortlist":[{k:r[k] for k in ["priority","method_id","known_people","class_sizes","capacity_gate_passed"]} for r in chosen]}),ensure_ascii=False))


if __name__=="__main__":
    main()
