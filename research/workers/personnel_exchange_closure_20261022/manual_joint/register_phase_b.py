"""One targeted extension selected after phase-A control outcomes were seen.

Condition: n20/m4, target has the highest outside-building class mean Q and is
slower than the source class.  Two previously unused backgrounds, seeds100/101,
are registered before their endpoints.  This is internal background validation,
not a new-building blind test and not part of the pre-specified primary layer.
"""
from __future__ import annotations
import collections
import itertools
import math
import pandas as pd
from register_design import HERE, FEATURES, META, h, digest, team_key, vec, write, save, sha

OUT=HERE/"phase_b_highq_slower"


def main():
    labs=pd.read_csv(HERE/"INPUT_MANUAL_JOINT_LABELS_LOBO.csv.gz")
    centers=pd.read_csv(HERE/"TRAINING_CLASS_CENTERS.csv")
    domains=pd.read_csv(HERE/"INPUT_NEW_ONLY_DOMAINS.csv")
    oldevents=pd.read_csv(HERE/"EVENTS_REGISTERED.csv.gz")
    oldpanels=pd.read_csv(HERE/"BACKGROUND_PANELS.csv.gz")
    oldkeys=set(pd.read_csv(HERE/"TEAM_REQUEST.csv.gz",usecols=["team_key"]).team_key)
    candidates=oldevents[(oldevents.n==20)&(oldevents.m_AB==4)&oldevents.training_QT_direction.eq("q_up__slower")]
    tops=centers.loc[centers.groupby("heldout_building").q_history.idxmax()].set_index("heldout_building").coarse_label.to_dict()
    candidates=candidates[candidates.apply(lambda r:r.target_class==tops[r.building],axis=1)]
    events,panels,teams,capacities=[],[],{},[]
    for (pool,src,dst),group in candidates.groupby(["pool_id","source_class","target_class"]):
        base=group.iloc[0].to_dict();building=base["building"];n,m=20,4
        domain=domains[domains.pool_id==pool].iloc[0]
        fold=labs[(labs.heldout_building==building)&labs.known].set_index("worker_id")
        lm=fold.coarse_label.to_dict();universe=sorted(set(domain.domain_workers.split("|"))&lm.keys());U=len(universe)
        cap=collections.Counter(lm[w] for w in universe)
        old=oldpanels[(oldpanels.pool_id==pool)&(oldpanels.source_class==src)&(oldpanels.target_class==dst)&(oldpanels.n==20)&(oldpanels.m==4)]
        seen_backgrounds=set(old.background_workers)
        suse,tuse,duse=collections.Counter(),collections.Counter(),collections.Counter()
        for r in old.itertuples():
            suse.update(r.source_reservoir.split("|"));tuse.update(r.target_reservoir.split("|"));duse.update(r.background_workers.split("|"))
        tsize=min(cap[dst],m+2,U-n-m)
        for seed in [100,101]:
            for attempt in range(100):
                path=h("phase_b",pool,src,dst,seed,attempt)[:24]
                sb=sorted([w for w in universe if lm[w]==src],key=lambda w:(suse[w],h(path,"source",w)))[:2*m]
                tb=sorted([w for w in universe if lm[w]==dst],key=lambda w:(tuse[w],h(path,"target",w)))[:tsize]
                rest=sorted(set(universe)-set(sb)-set(tb),key=lambda w:(duse[w],h(path,"background",w)))
                D=tuple(sorted(rest[:n-m]));assert len(D)==n-m
                if "|".join(D) not in seen_backgrounds:break
            else:raise RuntimeError("no unused background found")
            seen_backgrounds.add("|".join(D));suse.update(sb);tuse.update(tb);duse.update(D)
            pid=h("phase_b_panel",path)[:24];bg=h("background",pool,D)[:24]
            zsets=list(itertools.combinations(sorted(tb),m));pairs=[]
            for X in itertools.combinations(sorted(sb),m):
                Y=tuple(sorted(set(sb)-set(X)))
                if X>Y:continue
                if h("orientation",pool,src,dst,sorted(sb),X)>h("orientation",pool,src,dst,sorted(sb),Y):X,Y=Y,X
                pairs.append((X,Y))
            panels.append({k:base[k] for k in META}|dict(panel_id=pid,member_path=path,background_id=bg,
                capacity_id=base["capacity_id"],path_seed=seed,source_class=src,target_class=dst,training_QT_direction="q_up__slower",
                n=n,m=m,background_workers="|".join(D),background_counts=vec(D,lm),source_reservoir="|".join(sorted(sb)),
                target_reservoir="|".join(sorted(tb)),source_unordered_partitions=len(pairs),target_subsets=len(zsets),
                registered_ABC=len(pairs)*len(zsets),background_not_in_phase_A=True,condition_selected_after_phase_A_outcomes=True))
            for X,Y in pairs:
                A,B=tuple(sorted(D+X)),tuple(sorted(D+Y))
                ka,kb=team_key(pool,A),team_key(pool,B)
                for Z in zsets:
                    C=tuple(sorted(D+Z));kc=team_key(pool,C)
                    row=dict(base)
                    row.update(event_id=h("event",ka,kb,kc)[:24],physical_triple_id=digest(sorted([ka,kb,kc]))[:24],
                        oriented_triple_id=digest([ka,kb,kc])[:24],stage="phase_b_selected_condition_new_backgrounds",
                        panel_id=pid,member_path=path,background_id=bg,path_seed=seed,
                        source_partition_id=h("partition",pool,D,sorted([X,Y]))[:24],
                        team_A=ka,team_B=kb,team_C=kc,A_member_workers="|".join(A),B_member_workers="|".join(B),C_member_workers="|".join(C),
                        common_background="|".join(D),outgoing_block_X="|".join(X),same_count_block_Y="|".join(Y),changed_count_block_Z="|".join(Z),
                        A_counts=vec(A,lm),B_counts=vec(B,lm),C_counts=vec(C,lm),
                        condition_selected_after_phase_A_outcomes=True,member_selection_uses_target_outcomes=False,
                        target_is_highest_training_Q_class=True,internal_new_background_validation=True)
                    events.append(row)
                    for key,members in [(ka,A),(kb,B),(kc,C)]:
                        teams[key]={k:base[k] for k in META}|dict(team_key=key,n=n,k=n,member_workers="|".join(members),
                            first_use="phase_b_highest_Q_slower",also_registered_phase_A=key in oldkeys)
        theory=math.comb(cap[src],m)*math.comb(cap[src]-m,m)*math.comb(cap[dst],m)*math.comb(U-3*m,n-m)//2
        capacities.append(dict(pool_id=pool,image=base["image"],building=building,n=n,m=m,source_class=src,target_class=dst,
            source_capacity=cap[src],target_capacity=cap[dst],eligible_U=U,theoretical_unordered_source_ABC=str(theory),
            prior_backgrounds=len(old),new_backgrounds=2,new_registered_ABC=2*len(pairs)*len(zsets)))
    E=pd.DataFrame(events).drop_duplicates("event_id");T=pd.DataFrame(teams.values()).sort_values("team_key")
    assert not E.physical_triple_id.duplicated().any()
    assert not set(E.event_id)&set(oldevents.event_id)
    write(OUT/"EVENTS_REGISTERED.csv.gz",E);write(OUT/"TEAM_REQUEST.csv.gz",T)
    write(OUT/"BACKGROUND_PANELS.csv.gz",pd.DataFrame(panels));write(OUT/"CAPACITY.csv",pd.DataFrame(capacities))
    # Empty but schema-valid policy file: continuous QT is already evaluated in
    # the main condition; phase B has the distinct geometry/quality-cost purpose.
    write(OUT/"POLICIES_REGISTERED.csv.gz",pd.read_csv(HERE/"POLICIES_REGISTERED.csv.gz",nrows=0))
    history=pd.read_csv(HERE/"ACTUAL_DIRECTION_HISTORY.csv")
    keys=E[["pool_id","source_class","target_class","n","m_AB"]].drop_duplicates().rename(columns={"m_AB":"m"})
    write(OUT/"ACTUAL_DIRECTION_HISTORY.csv",keys.merge(history,on=["pool_id","source_class","target_class","n","m"],validate="one_to_one"))
    receipt=dict(phase="B",condition="n20/m4; target is highest held-out-building class mean Q and slower than source",
        condition_selected_after_phase_A_outcomes=True,new_members_and_backgrounds_chosen_without_their_outcomes=True,
        not_new_building_blind_test=True,not_part_of_initial_primary_layer=True,source_reservoir_partitions_exhaustive=True,
        target_reservoir_subsets_exhaustive=True,whole_pool_concrete_combinations_exhaustive=False,
        new_background_seeds=[100,101],events=len(E),unique_teams=len(T),also_registered_phase_A=int(T.also_registered_phase_A.sum()),
        images=E.image.nunique(),buildings=E.building.nunique(),panels=len(panels),
        native_fusion_calls=0,events_sha256=sha(OUT/"EVENTS_REGISTERED.csv.gz"),request_sha256=sha(OUT/"TEAM_REQUEST.csv.gz"),
        label_reference="../INPUT_MANUAL_JOINT_LABELS_LOBO.csv.gz",label_sha256=sha(HERE/"INPUT_MANUAL_JOINT_LABELS_LOBO.csv.gz"))
    save(OUT/"DESIGN_FREEZE.json",receipt)
    print(receipt,flush=True)


if __name__=="__main__":main()
