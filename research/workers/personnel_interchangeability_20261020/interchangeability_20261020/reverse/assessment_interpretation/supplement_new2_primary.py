#!/usr/bin/env python3
"""History-only explanation and exact primary-panel support; no new inference fit."""
import itertools
import json
from pathlib import Path
import numpy as np
import pandas as pd
from assessment_summary_common import BASE,ROOT,HERE,sha,load_exact,write_csv,write_json

METHOD='R_directswap_geometry_partition_b2_K2__ordinary_new__mixed_history_v1'

SPECS=[
    ('q_abs_mean','个人绝对Q均值','B8L2分','core_supported','core_records','core_buildings'),
    ('q_beta','控制历史任务后的相对Q','B8L2分','core_supported','core_records','core_buildings'),
    ('q_abs_p10','个人绝对Q的10%分位','B8L2分','core_supported','q_abs_n','core_buildings'),
    ('q_abs_sd','个人绝对Q标准差','B8L2分','core_supported','q_abs_n','core_buildings'),
    ('q_residual_p10','相对任务残差Q的10%分位','B8L2分','core_supported','core_records','core_buildings'),
    ('q_residual_sd','相对任务残差Q标准差','B8L2分','core_supported','core_records','core_buildings'),
    ('t_source_origin_effect','控制任务和来源后的原报时长效应','log时间','t_supported','t_records','t_buildings'),
    ('t_log_residual_tail','个人log时间残差高尾幅度','log时间','t_supported','t_records','t_buildings'),
    ('pair_count_effect','历史点对/底面节点数量效应','节点数','core_supported','core_records','core_buildings'),
    ('pair_count_residual_sd','个人点对数量残差标准差','节点数','core_supported','core_records','core_buildings'),
    ('reference_fewer_pairs_fraction','点对少于参考的比例','比例','core_supported','core_records','core_buildings'),
    ('reference_more_pairs_fraction','点对多于参考的比例','比例','core_supported','core_records','core_buildings'),
    ('bottom_y_effect','底边归一化ERP y效应','归一化y','core_supported','core_records','core_buildings'),
    ('top_y_effect','顶边归一化ERP y效应','归一化y','core_supported','core_records','core_buildings'),
    ('height_log_effect','历史高度log效应','log高度','core_supported','core_records','core_buildings'),
    ('theta_easy','简单条件相对Q','B8L2分','easy_supported','easy_records','easy_buildings'),
    ('theta_medium','中等条件相对Q','B8L2分','medium_supported','medium_records','medium_buildings'),
    ('theta_hard','困难条件相对Q','B8L2分','hard_supported','hard_records','hard_buildings'),
    ('hard_minus_easy','困难相对简单的Q效应差','B8L2分','hard_supported','hard_tasks','hard_buildings'),
    ('semi_new_error_nonedit_effect','新批报告初始有错时未修改倾向效应','概率差','semi_new_error_nonedit_supported','semi_new_error_nonedit_records','semi_new_error_nonedit_buildings'),
    ('semi_new_error_nonedit_raw_rate','新批报告初始有错时未修改率','比例','semi_new_error_nonedit_supported','semi_new_error_nonedit_records','semi_new_error_nonedit_buildings'),
    ('semi_new_edit_effect','新批Semi任意修改倾向效应','概率差','semi_new_edit_supported','semi_new_edit_records','semi_new_edit_buildings'),
    ('semi_new_edit_raw_rate','新批Semi任意修改率','比例','semi_new_edit_supported','semi_new_edit_records','semi_new_edit_buildings'),
    ('semi_old_error_nonedit_effect','旧批已确认初始错误时未修改效应','概率差','semi_old_error_nonedit_supported','semi_old_error_nonedit_records','semi_old_error_nonedit_buildings'),
    ('semi_old_edit_effect','旧批Semi任意修改倾向效应','概率差','semi_old_edit_supported','semi_old_edit_records','semi_old_edit_buildings'),
    ('scope_out_effect','回答目标范围外的倾向效应','概率差','scope_supported','scope_records','scope_buildings'),
    ('scope_out_raw_rate','回答目标范围外的原比例','比例','scope_supported','scope_records','scope_buildings'),
]


def main():
    out=HERE/'nested_new2'
    feature=ROOT/'analysis/forward/results/features_train.csv.gz'
    lab=BASE/'reverse/mixed_fit/worker_labels.csv.gz'
    labels=pd.read_csv(lab);labels=labels[labels.method_id.eq(METHOD)&labels.known.astype(str).str.lower().isin(['true','1','1.0'])]
    f=pd.read_csv(feature);assert f.train_key.nunique()==1 and f.train_key.iloc[0]=='history_d199d7b13dccfe7e'
    d=labels[['worker_id','class_id']].merge(f,on='worker_id',validate='one_to_one')
    # No absent evidence is assigned zero. Means are equal among supported people.
    rows=[]
    for cl,g in d.groupby('class_id'):
        for metric,zh,unit,gate,opp,bld in SPECS:
            valid=g[gate].astype(str).str.lower().isin(['true','1','1.0'])&g[metric].notna()
            z=g.loc[valid,metric]
            if opp not in g:opp=opp.replace('_records','_tasks')
            rows.append(dict(class_id=cl,class_people=len(g),metric=metric,variable_zh=zh,unit=unit,
                supported_people=int(valid.sum()),mean_people=float(z.mean()),median_people=float(z.median()),
                sd_between_people=float(z.std()),min_people=float(z.min()),max_people=float(z.max()),
                opportunity_column=opp,opportunities_all_class_people=int(g[opp].sum()) if opp in g else None,
                opportunities_supported_people=int(g.loc[valid,opp].sum()) if opp in g else None,
                supported_worker_buildings_min=int(g.loc[valid,bld].min()) if valid.any() else None,
                supported_worker_buildings_max=int(g.loc[valid,bld].max()) if valid.any() else None,
                gate=gate,missing_people=int((~valid).sum())))
    write_csv(out/'NEW2_HISTORY_CLASS_FEATURES.csv',pd.DataFrame(rows))
    write_csv(out/'NEW2_HISTORY_WORKERS.csv.gz',d[['worker_id','class_id','person_origin','train_key']+list(dict.fromkeys([s[0] for s in SPECS]))])
    write_json(out/'NEW2_CLASS_MEMBERS.json',dict(method_id=METHOD,train_key=f.train_key.iloc[0],classes=[dict(
        class_id=cl,people=len(g),worker_ids=sorted(g.worker_id),origin_counts=g.person_origin.value_counts().to_dict(),
        proposed_name_zh='关系簇C01（历史Q较高、节点习惯较多样）' if cl=='C01' else '关系簇C02（历史Q较低、节点习惯较收敛）') for cl,g in d.groupby('class_id')]))

    frame,md,meta=load_exact('nested_new2',[METHOD]);p=frame[frame.n.eq(13)]
    def sets(values):return {tuple(sorted(v)) for v in values}
    def workers(values):return set(itertools.chain.from_iterable(values))
    def counts(g):
        row=dict(events=len(g),pools=g.pool_id.nunique(),true_images=g.image_id.nunique(),buildings=g.building.nunique(),
            unique_team_keys=len(set(g.A_team_key)|set(g.B_team_key)|set(g.C_team_key)),
            unique_team_worker_sets=len(sets(g.A_workers)|sets(g.B_workers)|sets(g.C_workers)),
            unique_AB_unordered_pairs=g.within_unordered_team_pair.nunique(),
            fixed_paths=g.path_id.nunique(),unique_core_worker_sets=len(sets(g.core_workers)),
            pool_scoped_core_instances=len({(r.pool_id,tuple(sorted(r.core_workers))) for r in g.itertuples()}),
            actual_people=len(workers(g.A_workers)|workers(g.B_workers)|workers(g.C_workers)),
            actual_outgoing_class_people=len(workers(g.outgoing_workers)|workers(g.within_incoming)),
            actual_incoming_class_people=len(workers(g.cross_incoming)),actual_core_people=len(workers(g.core_workers)),
            outgoing_AB_block_worker_sets=len(sets(g.outgoing_workers)|sets(g.within_incoming)),
            incoming_C_block_worker_sets=len(sets(g.cross_incoming)),
            pool_scoped_outgoing_AB_blocks=len({(r.pool_id,tuple(sorted(v))) for r in g.itertuples() for v in [r.outgoing_workers,r.within_incoming]}),
            pool_scoped_incoming_C_blocks=len({(r.pool_id,tuple(sorted(r.cross_incoming))) for r in g.itertuples()}),
            finite_net_Q_events=int(g.net_B8L2_change.notna().sum()))
        allteams={}
        for arm in 'ABC':
            row[arm+'_attempt_events']=len(g);row[arm+'_unique_teams']=g[arm+'_team_key'].nunique()
            row[arm+'_incomplete_events']=int((~g[arm+'_complete']).sum())
            row[arm+'_unscored_events']=int(g[arm+'_B8L2'].isna().sum())
            row[arm+'_complete_but_unscored_events']=int((g[arm+'_complete']&g[arm+'_B8L2'].isna()).sum())
            for key,co,q in g[[arm+'_team_key',arm+'_complete',arm+'_B8L2']].itertuples(index=False,name=None):
                val=(bool(co),None if pd.isna(q) else float(q))
                if key in allteams:assert allteams[key]==val
                allteams[key]=val
        row['unique_incomplete_teams']=sum(not a for a,b in allteams.values())
        row['unique_unscored_teams']=sum(b is None for a,b in allteams.values())
        return row
    rows=[]
    for (oc,ic,m),g in p.groupby(['outgoing_class','incoming_class','m']):
        z=counts(g);assert z['unique_team_keys']==z['unique_team_worker_sets']==174
        rows.append(dict(outgoing_class=oc,incoming_class=ic,n=13,m=m,
            frozen_outgoing_class_people=int(d.class_id.eq(oc).sum()),frozen_incoming_class_people=int(d.class_id.eq(ic).sum()))|z)
    write_csv(out/'PRIMARY_EXACT_MEMBER_SUPPORT.csv',pd.DataFrame(rows))
    write_json(out/'PRIMARY_UNION_SUPPORT.json',dict(counts(p),
        supports_are_not_added_across_cells=True,interpretation='Four panels reuse the same 35 people and 29 image IDs; team hashes include pool/reference. Both pool-scoped and global concrete-member sets are reported.',
        source_request_sha256=meta['request_sha256']))
    write_json(out/'HISTORY_EXPLANATION_AND_SUPPORT_RECEIPT.json',dict(
        method_id=METHOD,history_features_sha256=sha(feature),frozen_labels_sha256=sha(lab),
        history_only=True,explanatory_features_did_not_relabel_clusters=True,
        class_means='Equal supported people; per-worker low-tail means are not a pooled annotation percentile.',
        denominators='Opportunity records are sums over people; min/max building counts are per supported worker and are not independent-image counts.',
        cautions=['New reported initial error is not independently adjudicated old confirmed error.','Editing does not prove correction.','Scope response tendency does not establish adjudicated scope accuracy.','All members are new-source; absent old opportunities remain missing.','No individual initial geometry was invented.'],
        assessment_request_sha256=meta['request_sha256'],code_sha256=sha(Path(__file__))
    ))
    print(pd.DataFrame(rows).to_json(orient='records'),flush=True)


if __name__=='__main__':main()
