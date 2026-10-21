"""Small wide views of the completed matched summaries; no re-estimation."""
from __future__ import annotations
import json
import pandas as pd
from multin_design import HERE,write_csv,sha,gs

METRICS=['common_quality_within_abs','common_quality_cross_abs','abs_Q_change_advantage',
 'within_joint_stable_main','cross_joint_stable_main','stable_advantage',
 'within_joint_stable_D10_main','cross_joint_stable_D10_main','stable_D10_advantage',
 'same_loss_gt5','cross_loss_gt5','same_loss_gt10','cross_loss_gt10',
 'B_failure','C_failure','net_failure_difference',
 'common_geometry_advantage_floor_jaccard_difference',
 'common_geometry_advantage_mean_height_prism_pair_difference',
 'common_geometry_advantage_structure_bound_cyclic_deg',
 'common_geometry_advantage_centroid_distance_h',
 'common_expression_advantage_fusion_turn_n',
 'common_expression_advantage_fusion_short_turn_edges',
 'common_expression_advantage_fusion_redundancy_n',
 'same_abs_log_time','cross_abs_log_time','time_variation_advantage']


def run():
    tables=[];inputs={}
    for stage in ['PANEL','LARGE','PURE']:
        p=HERE/'matched'/f'{stage}_PRIMARY_SUMMARY.csv'
        if not p.exists():continue
        d=pd.read_csv(p,keep_default_na=False);d=d[d.metric.isin(METRICS)].copy();d['stage']=stage;tables.append(d)
        inputs[str(p.relative_to(HERE))]=sha(p)
    if not tables:raise RuntimeError('No complete primary summary available')
    d=pd.concat(tables,ignore_index=True)
    keys=['stage','method_id','tier','condition','source_domain','design_scope','sensitivity','summary_view','n','m_AB','difficulty']
    support=['events','panels','pools','images','buildings','all_complete_events','all_scored_events']
    value_fields=['mean','lo95','hi95','valid_events','valid_buildings']
    summary=[]
    for key,g in d.groupby(keys,dropna=False,sort=True):
        r=dict(zip(keys,key));r.update({f:g.iloc[0][f] for f in support})
        for metric,gg in g.groupby('metric'):
            if len(gg)!=1:raise ValueError(('duplicate summary identity',key,metric))
            v=gg.iloc[0]
            for col in value_fields:r[metric+'__'+col]=v[col]
        summary.append(r)
    x=pd.DataFrame(summary)
    outputs=[]
    for view,name in [('overall','OVERVIEW'),('by_m','BY_ACTUAL_M'),('by_n','BY_N'),('by_difficulty','BY_DIFFICULTY')]:
        p=HERE/'matched'/f'MATCHED_USEFULNESS_{name}.csv';z=x[x.summary_view.eq(view)].copy();write_csv(p,z)
        outputs.append(dict(path=str(p.relative_to(HERE)),rows=len(z),sha256=sha(p),bytes=p.stat().st_size))
    receipt=dict(status='complete_available_stages',stages=sorted(d.stage.unique()),inputs=inputs,files=outputs,
      no_new_statistical_fit=True,interpretation='Cross minus same absolute differences quantify stability separation, not quality gain. Sources and scopes remain separate; method supports can differ.')
    gs.save(HERE/'matched/MATCHED_USEFULNESS_TABLES_COMPLETE.json',receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)


if __name__=='__main__':run()
