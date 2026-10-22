#!/usr/bin/env python3
"""Join the independently computed data-v1 personnel evidence without a total score.

Object IDs, worker IDs and context support are preserved. All event proportions
are documented fractions of their stated opportunity/adjudication sets, never
population error-rate estimates. Run after q/ and reliability/ analyses.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--study',type=Path,default=HERE.parent)
    ap.add_argument('--out',type=Path,default=HERE)
    a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    paths={
        'q':a.study/'q/worker_profiles_enriched.csv',
        'absolute':a.study/'q/absolute_quality_by_worker.csv',
        'reliability':a.study/'reliability/worker_reliability_summary.csv',
        'scope':a.study/'reliability/worker_scope_summary.csv',
        'semi':a.study/'reliability/worker_semi_summary.csv',
        'r_objects':a.study/'reliability/reliability_object_ledger.csv',
        's_objects':a.study/'reliability/scope_object_ledger.csv',
        'c_objects':a.study/'reliability/correction_object_ledger.csv',
        'semi_scores':a.study/'reliability/semi_scores_b8l2_d10.csv'}
    inputs={k:pd.read_csv(p) for k,p in paths.items()}
    q=inputs['q']; rel=inputs['reliability']; scope=inputs['scope']; semi=inputs['semi']
    for frame in [rel,scope,semi]: assert frame.worker_id.is_unique
    assert len(rel)==27
    # Start from all inventory people, including historical exclusions and no-Q rows.
    m=rel.copy()
    for axis in ['B8L2','D10']:
        absq=inputs['absolute'].query('pool == "ordinary_manual_all" and axis == @axis')
        cols=['worker_id','n','images','buildings','mean','median','p10','minimum']
        m=m.merge(absq[cols].rename(columns={k:'absolute_manual_'+axis+'_'+k for k in cols if k!='worker_id'}),
                  on='worker_id',how='left',validate='one_to_one')
        sub=q[q.axis.eq(axis)]
        cols=['worker_id','effect','supported','contexts','buildings','effect_ci95_low','effect_ci95_high',
              'label','Q_margin_2','LOBO_same_sign_fraction','half_agreement','raw_mean_rank','Q_effect_rank',
              'actual_task_intercept_mean','task_mix_shift_vs_common','common_task_standardized_prediction']
        m=m.merge(sub[cols].rename(columns={k:'Q_'+axis+'_'+k for k in cols if k!='worker_id'}),
                  on='worker_id',how='left',validate='one_to_one')
    qb=q[q.axis.eq('B8L2')]
    for axis in ['B8L2','D10']:
        for measure in ['n','images','buildings']:
            col='absolute_manual_'+axis+'_'+measure
            m[col]=m[col].fillna(0).astype(int)
    cols=['worker_id','T_effect','T_supported','T_contexts','T_buildings','T_label','QT_label',
          'T_LOBO_folds','T_LOBO_faster_folds']
    m=m.merge(qb[cols],on='worker_id',how='left',validate='one_to_one')
    scol=[c for c in scope if c!='worker_id']
    m=m.merge(scope.rename(columns={c:'scope_'+c for c in scol}),on='worker_id',how='left',validate='one_to_one')
    # The complete Semi table retains separate current-quality and opportunity gates.
    scols=[c for c in semi if c!='worker_id']
    m=m.merge(semi.rename(columns={c:'Semi_'+c for c in scols}),on='worker_id',how='left',validate='one_to_one')
    # Additional absolute Semi means retain the four researcher-repaired records
    # as project output, while all gain means in worker_semi_summary exclude credit.
    ss=inputs['semi_scores']
    og=ss[ss.current_quality_usable & ss.current_quality_use.eq('ordinary_primary')]
    f=og.groupby('worker_id').agg(Semi_ordinary_all_final_n=('object_id','size'),
        Semi_ordinary_all_final_B8L2_mean=('final_B8L2','mean'),
        Semi_ordinary_all_final_B8L2_p10=('final_B8L2',lambda z:z.quantile(.1)))
    m=m.merge(f,on='worker_id',how='left',validate='one_to_one')
    # Object-level evidence is multi-label, with an explicit union for counts.
    ro=inputs['r_objects']; so=inputs['s_objects']; co=inputs['c_objects']
    assert ro.object_id.is_unique and so.object_id.is_unique and co.object_id.is_unique
    e=ro[['object_id','worker_id','image_id','image_code','building_id','condition','cleaning_disposition',
          'independent_vote_eligible','strict_specific_personal_severe','reviewer_personal_nonacceptance']].copy()
    e=e.merge(co[['object_id','confirmed_initialization_error_opportunity','known_error_unchanged',
                 'error_specific_residual_state']],on='object_id',how='left',validate='one_to_one')
    e=e.merge(so[['object_id','current_compatible_outcome','narrow_historical_representation_outcome']],
              on='object_id',how='left',validate='one_to_one')
    for c in ['confirmed_initialization_error_opportunity','known_error_unchanged']:
        e[c]=e[c].eq(True)
    e['scope_current_clear_false_rejection']=e.current_compatible_outcome.eq('false_rejection')
    e['scope_narrow_old_false_acceptance']=e.narrow_historical_representation_outcome.eq('false_acceptance')
    e['strict_union_event']=e.strict_specific_personal_severe | e.known_error_unchanged | e.scope_current_clear_false_rejection
    e['broad_union_event']=e.reviewer_personal_nonacceptance | e.known_error_unchanged | e.scope_current_clear_false_rejection
    e['is_current_Q_worker']=e.worker_id.isin(qb.worker_id)
    e['data_release']='v1'
    union=e.groupby('worker_id').agg(documented_problem_event_union_strict=('strict_union_event','sum'),
        documented_problem_event_union_broad=('broad_union_event','sum'))
    m=m.merge(union,on='worker_id',how='left',validate='one_to_one')
    m['n_strict_adjudication_unknown']=m.n_submissions-m.n_strict_personally_judgable
    m['n_broad_adjudication_unknown']=m.n_submissions-m.n_broad_personally_judgable
    m['strict_adjudication_coverage']=m.n_strict_personally_judgable/m.n_submissions
    m['broad_adjudication_coverage']=m.n_broad_personally_judgable/m.n_submissions
    m['Q_B8L2_D10_sign_disagree']=(m.Q_B8L2_effect*m.Q_D10_effect).lt(0)
    m['Manual_Q_Semi_Q_sign_disagree']=(m.Q_B8L2_effect*m.Semi_semi_B8L2_effect).lt(0)
    m['confirmed_initial_error_unchanged_fraction']=m.Semi_n_known_error_unchanged / m.Semi_n_initialization_error_opportunities.replace(0,np.nan)
    # These are partial-identification bounds on the selected known-error tasks,
    # not binomial confidence intervals and not an extrapolation to other tasks.
    m['known_error_residual_fraction_lower_bound']=m.confirmed_initial_error_unchanged_fraction
    m['known_error_residual_fraction_upper_bound']=(m.Semi_n_known_error_unchanged+m.Semi_n_edited_error_specific_outcome_unknown) / m.Semi_n_initialization_error_opportunities.replace(0,np.nan)
    class_zh={'above_pool|faster':'相对高／快','above_pool|slower':'相对高／慢',
              'below_pool|faster':'相对低／快','below_pool|slower':'相对低／慢',
              'above_pool|time_unknown':'相对高／T未知','below_pool|time_unknown':'相对低／T未知'}
    m['existing_QT_class_zh']=m.QT_label.map(class_zh).fillna('Q未知／T未知')
    candidates=[]
    for _,r in m.iterrows():
        flags=[]
        if r.Q_B8L2_Q_margin_2=='boundary': flags.append('Q在±2分诊断边界')
        if r.Q_B8L2_D10_sign_disagree: flags.append('B8L2/D10的Q跨零')
        if pd.notna(r.T_LOBO_folds) and 0<r.T_LOBO_faster_folds<r.T_LOBO_folds:
            flags.append('T的楼外符号会改变')
        if r.n_strict_personal_severe>0: flags.append(f'明示个人错被剔除{int(r.n_strict_personal_severe)}件')
        elif r.n_reviewer_personal_nonacceptance>0: flags.append(f'较宽个人不接受证据{int(r.n_reviewer_personal_nonacceptance)}件')
        if r.Semi_n_known_error_unchanged>0:
            flags.append(f'已知初始化错误未动{int(r.Semi_n_known_error_unchanged)}/{int(r.Semi_n_initialization_error_opportunities)}')
        sm=r.scope_current_clear_manual_false_rejection; ss=r.scope_current_clear_semi_false_rejection
        if sm+ss>0: flags.append(f'clear任务scope误拒Manual {int(sm)}/{int(r.scope_current_clear_manual_opportunities)}、Semi {int(ss)}/{int(r.scope_current_clear_semi_opportunities)}')
        if r.n_historical_worker_exclusion>0: flags.append('历史整人排除保留，不恢复资格')
        if r.worker_id=='W022': flags.append('仅2份原留出，主Q与纠错均无训练机会')
        candidates.append('；'.join(flags) if flags else '可用证据中未发现上述事件；未知不等于正确')
    m['evidence_flags_zh']=candidates
    m['proposed_profile_zh']=m.existing_QT_class_zh+'；'+m.evidence_flags_zh
    m['data_release']='v1'
    m=m.sort_values('worker_id')
    # A smaller front table is useful for reading; the complete join remains in ZIP.
    front=['worker_id','data_release','n_submissions','absolute_manual_B8L2_n','absolute_manual_B8L2_mean',
        'absolute_manual_B8L2_p10','Q_B8L2_contexts','Q_B8L2_buildings','Q_B8L2_effect',
        'Q_B8L2_effect_ci95_low','Q_B8L2_effect_ci95_high','Q_D10_effect',
        'T_effect','T_supported','T_contexts','existing_QT_class_zh','Q_B8L2_LOBO_same_sign_fraction',
        'Semi_n_semi','Semi_n_initialization_payload_verified','Semi_n_ordinary_attributable',
        'Semi_ordinary_initial_B8L2_mean','Semi_ordinary_final_B8L2_mean',
        'Semi_ordinary_worker_attributable_gain_B8L2_mean','Semi_ordinary_residual_score_deficit_B8L2_mean',
        'Semi_n_initialization_error_opportunities','Semi_n_known_error_unchanged',
        'Semi_n_edited_error_specific_outcome_unknown','Semi_semi_B8L2_effect',
        'scope_n_scope_choice_recorded','scope_n_scope_response_unknown','scope_n_current_task_unknown',
        'scope_current_clear_manual_opportunities','scope_current_clear_manual_false_rejection',
        'scope_current_clear_semi_opportunities','scope_current_clear_semi_false_rejection',
        'n_individual_review_flags','n_explicit_accepted','n_invalid','n_strict_personal_severe',
        'n_strict_personally_judgable','n_reviewer_personal_nonacceptance','n_broad_personally_judgable',
        'n_invalid_reason_unknown_or_nonpersonal','n_historical_worker_exclusion',
        'documented_problem_event_union_strict','documented_problem_event_union_broad','evidence_flags_zh']
    outputs={'personnel_profiles_full.csv':m,'personnel_profiles_v1.csv':m[front],
             'event_evidence_union.csv':e,
             'classification_candidates.csv':m[['worker_id','existing_QT_class_zh','proposed_profile_zh',
                'Q_B8L2_D10_sign_disagree','Manual_Q_Semi_Q_sign_disagree','Q_B8L2_raw_mean_rank','Q_B8L2_Q_effect_rank']]}
    flagcols=['strict_specific_personal_severe','reviewer_personal_nonacceptance','known_error_unchanged','scope_current_clear_false_rejection']
    overlaps=[]
    for subset,frame in [('all_27_inventory_workers',e),('current_24_Q_workers',e[e.is_current_Q_worker])]:
        for first,second in combinations(flagcols,2):
            hits=frame[frame[first]&frame[second]]
            overlaps.append(dict(panel=subset,first=first,second=second,overlap=len(hits),object_ids=json.dumps(hits.object_id.tolist())))
    outputs['event_overlap_counts.csv']=pd.DataFrame(overlaps)
    for name,frame in outputs.items(): frame.to_csv(a.out/name,index=False,encoding='utf-8-sig')
    receipt=dict(data_release='v1',status='completed',workers=27,Q_supported_workers=24,
        no_total_score=True,unchanged_eligibility=True,
        source_sha256={str(p.relative_to(a.study)):sha(p) for p in paths.values()},
        rows={k:len(v) for k,v in outputs.items()},
        counts={c:int(e[c].sum()) for c in flagcols+['strict_union_event','broad_union_event']},
        Q_pool_counts={c:int(e.loc[e.is_current_Q_worker,c].sum()) for c in flagcols+['strict_union_event','broad_union_event']},
        exclusions=['narrow historical OOS diagnostic is not included in current-compatible union',
                    'broad contains strict; the two are never added',
                    'multiple comments and evidence labels remain one object-level event'],
        meaning='evidence union is a count of documented objects across distinct opportunities, not a score or risk estimate')
    (a.out/'INTEGRATION_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:receipt[k] for k in ['workers','Q_supported_workers','rows','counts','Q_pool_counts']},ensure_ascii=False,indent=2))
    print('COMPLETED: 27 people retained; no Q/time/gain unknown filled with zero; event labels deduplicated by object_id.')


if __name__=='__main__': main()
