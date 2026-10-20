"""Describe fixed global G/R classes with history10-only worker measurements."""
from collections import Counter
import json
from pathlib import Path
import pandas as pd
import design_baseline as d


FIELDS=("q_beta","q_abs_mean","q_abs_p10","q_residual_p10","q_residual_sd","pair_count_effect","bottom_y_effect","top_y_effect","height_log_effect","t_source_origin_effect","t_log_residual_tail","hard_minus_easy","scope_out_effect","semi_old_error_nonedit_effect","semi_new_error_nonedit_effect","semi_old_edit_effect","semi_new_edit_effect")


def main():
    out=Path(__file__).parent;F=pd.read_csv(d.FEATURES).set_index("worker_id");L=d.sg.labels_from_files([d.LABELS]);rows=[];members={}
    for target,rule in d.TARGETS.items():
        lm=L[(rule["method_id"],"all")];members[target]={}
        for cls in sorted(set(lm.values())):
            ids=sorted(w for w,c in lm.items() if c==cls);g=F.loc[ids];members[target][cls]=dict(workers=ids,origins=dict(Counter(g.person_origin)),method_id=rule["method_id"])
            for source in ["all","new","v1"]:
                h=g if source=="all" else g[g.person_origin.eq(source)]
                r=dict(target=target,method_id=rule["method_id"],class_id=cls,source=source,workers=len(h),history_train_key="|".join(sorted(h.train_key.unique())),member_workers="|".join(h.index),status="observed_history_support" if len(h) else "no_members_in_this_source")
                for field in FIELDS:
                    x=h[field].dropna();r[field+"_known_workers"]=len(x);r[field+"_worker_mean"]=float(x.mean()) if len(x) else None;r[field+"_worker_median"]=float(x.median()) if len(x) else None
                rows.append(r)
    d.save_csv(out/"CLASS_HISTORY_PROFILE.csv",rows)
    d.save_json(out/"GLOBAL_CLASS_MEMBERS.json",dict(classes=members,features_sha256=d.sha(d.FEATURES),labels_sha256=d.sha(d.LABELS),interpretation="Descriptive equal-worker summaries of inherited history10 features; source and opportunity missingness kept. FULL/target-building evaluations are not read. Class IDs are algorithm labels, not absolute quality ranks. Q,scope,Semi andT effects have their inherited different definitions; no total score is constructed."))


if __name__=="__main__":main()
