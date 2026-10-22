"""Paired role-to-role contrasts using the same base order and prefix size.

No new fusion. The natural/priority variable names are an internal adapter to
the main summarizer; saved results call them comparison/focal and specify both
policies. Positive deltas mean focal minus comparison, never versus natural.
"""
from __future__ import annotations

import argparse
import functools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from analyze_policy_curves import METRICS, FLAGS, per_image_k, focal_rows, aggregate_focal
from register_population_orders import save_csv, write_bytes


CONTRASTS = [
    ("structure_moreturn_minus_dominant", "structure_moreturn_first", "structure_dominant_first"),
    ("joint_highq_minus_fast", "joint_highq_first", "joint_fast_first"),
]


@functools.lru_cache(maxsize=100000)
def unpack_vector(text):
    return json.loads(text)


def seat_delta(a, b):
    a, b = unpack_vector(a), unpack_vector(b)
    assert a.keys() == b.keys()
    return sum(abs(a[c]-b[c]) for c in a)/2


def role_to_role(p, orders, vectors):
    bypath=orders.set_index("path_id")
    metrics=[m for m in METRICS if m+"_priority" in p]
    flags=[f for f in FLAGS if f+"_priority" in p]
    outcomes=metrics+flags
    merges=["pool_id","base_path_id","k"]
    meta=[c for c in p if not any(c==x+s for x in outcomes for s in ["_priority","_natural","_delta"])]
    # Recompute all comparisons from the two actual endpoints rather than
    # subtracting aggregate effects against potentially different baselines.
    drop=["natural_team_key","natural_target_n","priority_target_n","actual_m","shared_n",
          "target_seat_change","actual_replacement_fraction","target_seat_fraction_change",
          "abs_B8L2_change","Q_loss_gt5","Q_gain_gt5","source_time_logratio","target_time_logratio",
          "QT_Q_delta","QT_time_logratio"]
    meta=[c for c in meta if c not in drop and not c.startswith("achieved_Q")]
    frames=[]
    for name, focal, comparison in CONTRASTS:
        a=p[p.policy.eq(focal)][meta+[m+"_priority" for m in outcomes]].copy()
        b=p[p.policy.eq(comparison)][merges+["path_id","priority_team_key"]+[m+"_priority" for m in outcomes]].copy()
        b=b.rename(columns={"path_id":"comparison_path_id","priority_team_key":"natural_team_key",
                            **{m+"_priority":m+"_natural" for m in outcomes}})
        z=a.merge(b,on=merges,how="inner",validate="one_to_one")
        z["policy"]=name;z["focal_policy"]=focal;z["comparison_policy"]=comparison
        differences=[]
        for path,g in z.groupby("path_id",sort=False):
            left=bypath.loc[path];right=bypath.loc[g.comparison_path_id.iloc[0]]
            wa=left.worker_order.split("|");wb=right.worker_order.split("|")
            ta=set(str(left.target_members).split("|"))-{ "", "nan" }
            tb=set(str(right.target_members).split("|"))-{ "", "nan" }
            sa,sb=set(),set()
            for k,(xa,xb) in enumerate(zip(wa,wb),1):
                sa.add(xa);sb.add(xb)
                differences.append(dict(path_id=path,k=k,actual_m=len(sa-sb),shared_n=len(sa&sb),
                    priority_target_n=len(sa&ta),natural_target_n=len(sb&ta),
                    target_seat_change=len(sa&ta)-len(sb&ta),
                    comparison_role_seat_change=len(sa&tb)-len(sb&tb),
                    same_target_member_set=ta==tb,target_overlap_n=len(ta&tb),
                    focal_role_capacity=len(ta),comparison_role_capacity=len(tb),
                    same_full_order=wa==wb))
        z=z.merge(pd.DataFrame(differences),on=["path_id","k"],validate="one_to_one")
        z["actual_replacement_fraction"]=z.actual_m/z.k
        z["target_seat_fraction_change"]=z.target_seat_change/z.k
        for m in outcomes:z[m+"_delta"]=z[m+"_priority"]-z[m+"_natural"]
        z["abs_B8L2_change"]=z.B8L2_delta.abs()
        z["Q_loss_gt5"]=z.B8L2_delta.lt(-5).where(z.B8L2_delta.notna()).astype(float)
        z["Q_gain_gt5"]=z.B8L2_delta.gt(5).where(z.B8L2_delta.notna()).astype(float)
        for goal in (80,90):
            for side in ("priority","natural"):z[f"achieved_Q{goal}_{side}"]=z["B8L2_"+side].ge(goal).astype(float)
            z[f"achieved_Q{goal}_delta"]=z[f"achieved_Q{goal}_priority"]-z[f"achieved_Q{goal}_natural"]
        for prefix in ("source","target"):
            t=prefix+"_time_total_seconds"
            if t in metrics:
                valid=z[t+"_priority"].gt(0)&z[t+"_natural"].gt(0)
                z[prefix+"_time_logratio"]=np.log(z[t+"_priority"]/z[t+"_natural"]).where(valid)
        if "source_time_logratio" in z:
            valid=z.B8L2_delta.notna()&z.source_time_logratio.notna()
            z["QT_Q_delta"]=z.B8L2_delta.where(valid)
            z["QT_time_logratio"]=z.source_time_logratio.where(valid)
        for feature in ("structure_coarse","structure_fine","joint_coarse","joint_fine"):
            text=vectors[feature+"_vector"]
            va=z.priority_team_key.map(text);vb=z.natural_team_key.map(text)
            assert va.notna().all() and vb.notna().all()
            z[feature+"_net_seat_changes"]=[seat_delta(x,y) for x,y in zip(va,vb)]
        final=z[z.at_full_pool]
        assert final.priority_team_key.equals(final.natural_team_key)
        assert final.actual_m.eq(0).all()
        assert final.B8L2_delta.dropna().abs().lt(1e-10).all()
        assert z[z.same_target_member_set].actual_m.eq(0).all()
        frames.append(z)
    return pd.concat(frames,ignore_index=True),metrics,flags


def external_names(frame):
    return frame.rename(columns={c:c.replace("priority", "focal").replace("natural", "comparison") for c in frame})


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--paired",required=True);ap.add_argument("--orders",required=True)
    ap.add_argument("--vectors",required=True);ap.add_argument("--out",required=True);a=ap.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    p=pd.read_csv(a.paired,low_memory=False);orders=pd.read_csv(a.orders,keep_default_na=False)
    vectors=pd.read_csv(a.vectors).set_index("team_key")
    z,metrics,flags=role_to_role(p,orders,vectors)
    save_csv(external_names(z),out/"POLICY_DIRECT_PAIRED_PREFIX_EVENTS.csv.gz")
    perk,mt=per_image_k(z,metrics,flags)
    extra=z.groupby(["pool_id","policy","k"],dropna=False).agg(
        same_target_member_set=("same_target_member_set","first"),same_full_order=("same_full_order","all"),
        comparison_role_seat_change=("comparison_role_seat_change","mean"),
        structure_coarse_net_seat_changes=("structure_coarse_net_seat_changes","mean"),
        structure_fine_net_seat_changes=("structure_fine_net_seat_changes","mean"),
        joint_coarse_net_seat_changes=("joint_coarse_net_seat_changes","mean"),
        joint_fine_net_seat_changes=("joint_fine_net_seat_changes","mean")).reset_index()
    perk=perk.merge(extra,on=["pool_id","policy","k"],validate="one_to_one")
    save_csv(external_names(perk),out/"POLICY_DIRECT_PER_IMAGE_K.csv.gz")
    save_csv(external_names(mt),out/"POLICY_DIRECT_PER_IMAGE_K_METRICS.csv.gz")
    focal=focal_rows(perk);save_csv(external_names(focal),out/"POLICY_DIRECT_FOCAL_PER_IMAGE.csv")
    common=set(p.groupby("pool_id").policy.nunique().loc[lambda x:x.eq(4)].index)
    summary,buildings=aggregate_focal(focal,common_pool_ids=common)
    save_csv(external_names(summary),out/"POLICY_DIRECT_FOCAL_SUMMARY.csv")
    save_csv(external_names(buildings),out/"POLICY_DIRECT_FOCAL_PER_BUILDING.csv.gz")
    receipt=dict(paired_prefixes=len(z),pools=z.pool_id.nunique(),
        comparisons=[dict(name=n,focal=a,comparison=b) for n,a,b in CONTRASTS],
        direct_join="same pool_id, base_path_id, k; no subtraction of unmatched means",
        deltas="focal minus comparison",net_seat_changes="half L1 of complete local-fold category count vectors",
        same_target_sets_retained=True,whole_pool_endpoints_identical_checked=True,
        new_fusion=0,all_four_common_pool_count=len(common))
    write_bytes(out/"POLICY_DIRECT_RECEIPT.json",json.dumps(receipt,ensure_ascii=False,indent=2).encode())
    print(receipt,flush=True)


if __name__=="__main__":main()
