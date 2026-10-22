"""Fill every feasible class-count configuration missing from the main subspace.

One outcome-free unordered ABC per missing configuration, both source-team
orientations. This is a separate coverage layer, not extra independent repeats.
"""
from register_semi_closure import *


def main():
    E = pd.read_csv(HERE / "EVENTS_REGISTERED.csv.gz", keep_default_na=False)
    T = pd.read_csv(HERE / "ALL_TEAMS.csv.gz", keep_default_na=False)
    D = pd.read_csv(HERE / "DOMAIN_INVENTORY.csv").set_index("pool_id")
    L = pd.read_csv(HERE / "INHERITED_LABELS_LOBO.csv.gz")
    tables = {b: g.set_index("worker_id") for b, g in L.groupby("heldout_building")}
    existing = set(T.team_key)
    historical = OLD / "ALL_USED_ENDPOINT_SCALARS.csv.gz"
    if historical.exists():
        existing.update(pd.read_csv(historical, usecols=["team_key"]).team_key)
    new_events, new_controls, configurations, teams = [], [], [], {}

    def add_team(meta, workers):
        key = team_key(meta["pool_id"], workers)
        teams[key] = {k: meta[k] for k in ["pool_id", "image", "building", "condition", "difficulty", "layer"]}
        teams[key].update(team_key=key, n=len(workers), k=len(workers), member_workers=join(workers))
        return key

    for cell, group in E.groupby("cell_id", sort=True):
        first = group.iloc[0].to_dict()
        pool, n, m = first["pool_id"], int(first["n"]), int(first["m_AB"])
        src, dst = first["source_class"], first["target_class"]
        fold = tables[first["building"]]
        lm = fold.coarse_label.to_dict()
        ws = D.loc[pool, "workers"].split("|")
        cap = json.loads(D.loc[pool, "class_capacity"])
        remaining_cap = dict(cap)
        remaining_cap[src] -= 2*m
        remaining_cap[dst] -= m
        utility = ((fold.q_history-fold.q_history.mean())/fold.q_history.std(ddof=0)
                   -(fold.t_history-fold.t_history.mean())/fold.t_history.std(ddof=0))
        registered = set(zip(group.A_counts, group.C_counts))
        for v in count_vectors(remaining_cap, n-m):
            ac, cc = dict(v), dict(v)
            ac[src] += m
            cc[dst] += m
            av = "|".join(f"{k}:{value}" for k,value in sorted(ac.items()) if value)
            cv = "|".join(f"{k}:{value}" for k,value in sorted(cc.items()) if value)
            config_id = h("class_configuration", cell, av, cv)[:24]
            old = (av,cv) in registered
            configurations.append(dict(cell_id=cell, config_id=config_id, pool_id=pool, image=first["image"],
                                       building=first["building"], source_class=src,target_class=dst,n=n,m=m,
                                       A_counts=av,C_counts=cv,previously_registered=old,
                                       coverage_layer="main_source_partition" if old else "configuration_completion"))
            if old:
                continue
            background = []
            for lab, number in v.items():
                candidates = sorted([w for w in ws if lm[w]==lab], key=lambda w:h(config_id,"D",lab,w))
                background.extend(candidates[:number])
            background = tuple(sorted(background))
            source = sorted([w for w in ws if lm[w]==src and w not in background], key=lambda w:h(config_id,"source",w))[:2*m]
            Z = tuple(sorted(sorted([w for w in ws if lm[w]==dst and w not in background],key=lambda w:h(config_id,"target",w))[:m]))
            S = tuple(sorted(source))
            X, Y = tuple(sorted(source[:m])),tuple(sorted(source[m:]))
            rid = h("configuration_completion_reservoir",cell,S,Z)[:24]
            bid = h("background",pool,background)[:24]
            candidate = sorted(set(ws)-set(background)-set(S))
            Q = tuple(sorted(sorted(candidate,key=lambda w:(-float(utility.loc[w]),h("qt_tie",w)))[:m]))
            qt_key = add_team(first,(*background,*Q))
            C = tuple(sorted((*background,*Z)))
            c_key = add_team(first,C)
            control_id = h("configuration_completion_qt",config_id,S,Z,background)[:24]
            new_controls.append(dict(control_id=control_id,cell_id=cell,pool_id=pool,image=first["image"],
                                     building=first["building"],condition="semi",source_class=src,target_class=dst,n=n,m=m,
                                     common_background=join(background),source_union=join(S),class_target_block=join(Z),
                                     candidate_workers=join(candidate),candidate_size=len(candidate),
                                     feasible_candidate_blocks=math.comb(len(candidate),m),qt_workers=join(Q),
                                     team_C=c_key,team_QT=qt_key,C_QT_actual_m=m-len(set(Z)&set(Q)),qt_same_as_class=tuple(Z)==Q,
                                     qt_score="z_fold_q_history_minus_z_fold_t_history",uses_target_outcomes=False,
                                     coverage_layer="configuration_completion"))
            for X0,Y0 in [(X,Y),(Y,X)]:
                A,B = tuple(sorted((*background,*X0))),tuple(sorted((*background,*Y0)))
                keys = [add_team(first,w) for w in (A,B,C)]
                event = dict(first)
                event.update(stage="semi_closure_configuration_completion",event_id=h("completion_event",keys)[:24],
                             physical_triple_id=digest(sorted(keys))[:24],oriented_triple_id=digest(keys)[:24],
                             team_A=keys[0],team_B=keys[1],team_C=keys[2],A_member_workers=join(A),B_member_workers=join(B),C_member_workers=join(C),
                             common_background=join(background),outgoing_block_X=join(X0),same_count_block_Y=join(Y0),changed_count_block_Z=join(Z),
                             A_counts=vector(A,lm),B_counts=vector(B,lm),C_counts=vector(C,lm),
                             reservoir_id=rid,background_id=bid,background_path="one_frozen_background_per_missing_configuration",
                             cell_complete_enumeration=False,qt_control_id=control_id,team_QT=qt_key,
                             config_id=config_id,design_scope="all_configuration_coverage_supplement_one_physical_ABC_per_missing_configuration")
                assert event["A_counts"]==av and event["C_counts"]==cv
                assert len(set(A)&set(B))==len(set(A)&set(C))==len(set(B)&set(C))==n-m
                new_events.append(event)
    NE = pd.DataFrame(new_events).drop_duplicates("oriented_triple_id")
    NT = pd.DataFrame(teams.values()).sort_values("team_key")
    NT["cached_or_already_requested"] = NT.team_key.isin(existing)
    NC = pd.DataFrame(new_controls)
    CFG = pd.DataFrame(configurations)
    combined = pd.concat([E,NE],ignore_index=True)
    assert combined.oriented_triple_id.nunique()==len(combined)
    for name,frame in [("CONFIGURATION_COMPLETION_EVENTS.csv.gz",NE),
                       ("CONFIGURATION_COMPLETION_ALL_TEAMS.csv.gz",NT),
                       ("CONFIGURATION_COMPLETION_TEAM_REQUEST.csv.gz",NT[~NT.cached_or_already_requested]),
                       ("CONFIGURATION_COMPLETION_QT_CONTROLS.csv.gz",NC),
                       ("ALL_CLASS_CONFIGURATIONS.csv",CFG),
                       ("EVENTS_REGISTERED_ALL.csv.gz",combined)]:
        write(HERE/name,frame)
    info=dict(stage="configuration_completion_before_target_results",base_freeze_sha256=sha(HERE/"DESIGN_FREEZE.json"),
              seed=SEED,feasible_class_configurations=len(CFG),previously_covered=int(CFG.previously_registered.sum()),
              newly_covered=int((~CFG.previously_registered).sum()),configuration_coverage_complete=True,
              supplemental_oriented_ABC=len(NE),supplemental_physical_ABC=NE.physical_triple_id.nunique(),
              supplemental_unique_teams=len(NT),cached_or_already_requested=int(NT.cached_or_already_requested.sum()),
              new_endpoint_requests=int((~NT.cached_or_already_requested).sum()),
              target_outcomes_used=False,selection_criterion="missing class-count configuration only",
              claim="All 631 feasible class-count configurations are covered; concrete members/backgrounds are not globally exhaustive.",
              analysis_scope="separate configuration-completion layer; primary robustness layer remains full source partitions",
              event_sha256=sha(HERE/"CONFIGURATION_COMPLETION_EVENTS.csv.gz"),
              request_sha256=sha(HERE/"CONFIGURATION_COMPLETION_TEAM_REQUEST.csv.gz"))
    save(HERE/"CONFIGURATION_COMPLETION_FREEZE.json",info)
    print(json.dumps(info,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
