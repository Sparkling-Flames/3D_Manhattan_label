#!/usr/bin/env python3
"""Frozen Semi evidence, paired geometry, and redundant-information audit.

This is a statistical replay of audited inputs, not independent collection or
screen-rendering validation. No correction outcome is inferred from score gain.
"""
from pathlib import Path
import gzip, hashlib, json
import numpy as np
import pandas as pd
from initialization_ring import recover_declared_initial_ring

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
SRC=ROOT/'repo_main_20261019/research/statistics/v2_evidence_audit_20261019/records.json.gz'

def fe(d,y):
    workers=sorted(d.worker_id.unique()); tasks=sorted(d.initial_task.unique())
    X=np.eye(len(workers))[pd.Categorical(d.worker_id,categories=workers).codes]
    X-=pd.DataFrame(X).groupby(d.initial_task.to_numpy()).transform('mean').to_numpy()
    v=d[y].to_numpy(float)-d.groupby('initial_task')[y].transform('mean').to_numpy()
    beta=np.linalg.lstsq(np.vstack([X,np.ones((1,len(workers)))]),np.r_[v,0.],rcond=None)[0]
    return dict(zip(workers,beta)),float(np.max(abs(X@beta-v))),np.linalg.matrix_rank(X)

def stats(d,label):
    out={'panel':label,'n':len(d),'workers':d.worker_id.nunique(),
         'images':d.image_id.nunique(),'buildings':d.building_id.nunique(),
         'initial_tasks':d.initial_task.nunique(),
         'confirmed_initial_ring_permutation_n':int(d.initial_ring_changed.sum())}
    for metric in ['B8L2','D10']:
        gain=d['project_gain_'+metric]; final=d['final_score_'+metric]; initial=d['initial_'+metric]
        for name,a in [('initial',initial),('final',final),('gain',gain),('residual_score_deficit',100-final)]:
            out[f'{name}_{metric}_mean']=a.mean();out[f'{name}_{metric}_median']=a.median()
            out[f'{name}_{metric}_p10']=a.quantile(.1);out[f'{name}_{metric}_p90']=a.quantile(.9)
        out[f'{metric}_gain_positive_n']=int((gain>1e-8).sum())
        out[f'{metric}_gain_zero_n']=int((gain.abs()<=1e-8).sum())
        out[f'{metric}_gain_negative_n']=int((gain< -1e-8).sum())
        byb=d.assign(value=gain).groupby('building_id').value.mean()
        out[f'gain_{metric}_building_equal_mean']=byb.mean()
        if len(byb)>1:
            rng=np.random.default_rng(2026101904)
            bs=rng.choice(byb.to_numpy(),(5000,len(byb)),replace=True).mean(axis=1)
            out[f'gain_{metric}_building_bootstrap_lo'],out[f'gain_{metric}_building_bootstrap_hi']=np.quantile(bs,[.025,.975])
    return out

def main():
    records=json.load(gzip.open(SRC,'rt'))['records'];byid={r['object_id']:r for r in records}
    d=pd.read_csv(HERE/'semi_records.csv');rows=[]
    for _,row in d.iterrows():
        r=byid[row.object_id];s=r['semi_evidence'];h=s.get('historical_paired_scores') or {}
        x=row.to_dict();x['initial_ring_changed']=h.get('initial_ring_changed_from_payload') in (True,'True')
        for metric in ['B8L2','D10']:
            x['final_score_'+metric]=r.get('diagnostic_'+metric)
        x['initialization_hash']=(s.get('initialization_audit') or {}).get('initialization_hash')
        c=s.get('correction_evidence') or {}
        x['realized_error_type']=c.get('initialization_error_type')
        x['planned_error_type']=c.get('planned_error_type')
        x['planned_realized_mismatch']=c.get('planned_realized_mismatch')
        x['initialization_kind']=(s.get('initialization_audit') or {}).get('runtime_initialization_kind')
        if s.get('initialization_points'):
            pts,ev=recover_declared_initial_ring(r,byid)
            x['initial_scoring_geometry_sha256']=hashlib.sha256(json.dumps(pts,separators=(',',':')).encode()).hexdigest()
            x['initial_task']='|'.join(str(r.get(k)) for k in ['image_id','condition','reference_id','reference_version'])+'|'+x['initial_scoring_geometry_sha256']
        else:x['initial_task']=None
        rows.append(x)
    d=pd.DataFrame(rows);d.to_csv(HERE/'semi_enriched_records.csv',index=False)
    panels={
        'all_adopted_paired_diagnostic':d[d.paired_initial_scores_adopted],
        'quality_qualified_paired':d[d.qualified_net_gain],
        'worker_attributable_paired':d[d.worker_attributable_gain],
        'qualified_native_ring_only':d[d.qualified_net_gain & ~d.initial_ring_changed],
        'worker_attributable_native_ring_only':d[d.worker_attributable_gain & ~d.initial_ring_changed],
        'worker_attributable_confirmed_error_opportunities':d[d.worker_attributable_gain & d.old_confirmed_opportunity],
        'worker_attributable_other_initializations':d[d.worker_attributable_gain & ~d.old_confirmed_opportunity],
        'worker_attributable_confirmed_opportunity_edited':d[d.worker_attributable_gain & d.old_confirmed_opportunity & d.initialization_edited.eq(True)],
        'worker_attributable_confirmed_opportunity_unchanged':d[d.worker_attributable_gain & d.old_confirmed_opportunity & d.initialization_edited.eq(False)]}
    summaries=[stats(p,k) for k,p in panels.items()]
    pd.DataFrame(summaries).to_csv(HERE/'semi_paired_summary.csv',index=False)
    per=[];redundancy=[];workerfe=[]
    for label,p in panels.items():
        for w,g in p.groupby('worker_id'):
            x=stats(g,label);x['worker_id']=w;per.append(x)
        for metric in ['B8L2','D10']:
            p=p.copy();p['gain']=p['project_gain_'+metric]
            means=p.groupby('initial_task')[[metric,'gain','initial_'+metric]].transform('mean')
            centered_final=p[metric]-means[metric];centered_gain=p.gain-means.gain
            p[metric]=p['final_score_'+metric]
            means=p.groupby('initial_task')[[metric,'gain','initial_'+metric]].transform('mean')
            centered_final=p[metric]-means[metric];centered_gain=p.gain-means.gain
            bf,_,rank=fe(p,metric);bg,_,_=fe(p,'gain')
            init_range=p.groupby('initial_task')['initial_'+metric].agg(lambda a:a.max()-a.min())
            redundancy.append({'panel':label,'metric':metric,'n':len(p),'n_initial_tasks':p.initial_task.nunique(),
                'max_initial_within_task_range':init_range.max(),
                'max_task_centered_final_vs_gain_difference':max(abs(centered_final-centered_gain)),
                'max_worker_fe_final_vs_gain_difference':max(abs(bf[w]-bg[w]) for w in bf),
                'worker_design_rank':rank,'worker_count':len(bf),
                'identifiable_single_connected_worker_graph':rank==len(bf)-1})
            for w in bf:workerfe.append({'panel':label,'metric':metric,'worker_id':w,'final_effect':bf[w],'gain_effect':bg[w]})
    pd.DataFrame(per).to_csv(HERE/'semi_person_paired_metrics.csv',index=False)
    pd.DataFrame(workerfe).to_csv(HERE/'semi_person_task_adjusted_effects.csv',index=False)
    pd.DataFrame(redundancy).to_csv(HERE/'semi_final_gain_redundancy.csv',index=False)
    evidence=[]
    for source,opportunity,miss in [('old_exact_realized','old_confirmed_opportunity','old_confirmed_unchanged'),('new_reported_missing_initial','new_reported_opportunity','new_reported_unchanged')]:
        for w,g in d.groupby('worker_id'):
            o=g[g[opportunity]]
            if not len(o):continue
            evidence.append({'evidence_source':source,'worker_id':w,'semi_total_in_inventory':len(g),
                'opportunities':len(o),'opportunity_images':o.image_id.nunique(),'opportunity_buildings':o.building_id.nunique(),
                'retained_error_events':int(o[miss].eq(True).sum()),
                'edited_but_error_specific_outcome_unknown':int(o.initialization_edited.eq(True).sum()),
                'confirmed_corrections':int(o.error_specific_corrected_confirmed.eq(True).sum()),
                'retained_error_fraction_observed_opportunities':o[miss].eq(True).mean(),
                'population_extrapolation_valid':False})
    pd.DataFrame(evidence).to_csv(HERE/'semi_person_opportunity_evidence.csv',index=False)
    checks={'schema':'semi_statistical_replay_v2_20261019','source_commit':'82c6164b0d4630de5316199c92aa405930973168',
        'source_records_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest(),
        'panels':{k:len(p) for k,p in panels.items()},
        'redundancy_max_effect_difference':max(x['max_worker_fe_final_vs_gain_difference'] for x in redundancy),
        'rank_caveat':'Within each identical task/reference/initialization, final and gain carry the same worker contrast. Absolute gain remains a useful descriptive process measure, not a second independent Q vote.',
        'score_deficit_caveat':'100-final is score deficit, not an adjudicated count of residual initial errors.',
        'all_paired_diagnostic_caveat':'The 519-record panel uses diagnostic final geometry scores, including 54 quality-ineligible records. Qualified personnel summaries use only the explicitly qualified or attributable panels; quality eligibility is never changed.',
        'correction_caveat':'No changed record is declared corrected by these calculations. Source screen-view and acquisition audit are inherited, not independently replayed.',
        'class_or_selector_modified':False}
    (HERE/'SEMI_ANALYSIS_RECEIPT.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
    print(json.dumps(checks,ensure_ascii=False,indent=2))
    print(pd.DataFrame(summaries)[['panel','n','images','buildings','initial_B8L2_mean','final_B8L2_mean','gain_B8L2_mean','B8L2_gain_positive_n','B8L2_gain_zero_n','B8L2_gain_negative_n']].to_string(index=False))

if __name__=='__main__':main()
