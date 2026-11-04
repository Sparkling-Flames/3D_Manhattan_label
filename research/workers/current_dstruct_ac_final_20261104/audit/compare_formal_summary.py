"""Compare formal six-direction summaries with independent image/building means."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ANA=HERE.parent/'analysis'


def main():
    formal_path=ANA/'SIX_DIRECTION_Q_BY_BUDGET.csv'
    formal=pd.read_csv(formal_path,low_memory=False)
    independent=pd.read_csv(HERE/'INDEPENDENT_IMAGE_BUILDING_Q_MEANS.csv')
    independent['analysis_cohort']=independent.cohort.replace({'legacy_plus_registered_gap':'legacy_plus_capacity_gap'})
    independent['support']=independent.support.replace({'new_common_after_order':'new_common_after_approved_order'})
    key=['analysis_cohort','version','scope','n','m','class_pair','support']
    f=formal[(formal.orientation_sign_view==1)&(formal.images>0)].set_index(key)
    r=independent.set_index(key)
    failures=[]
    if set(f.index)!=set(r.index):failures.append({'check':'nonempty_summary_key_coverage','detail':str((len(set(f.index)-set(r.index)),len(set(r.index)-set(f.index))))})
    common=f.index.intersection(r.index)
    fields={'image_equal_mean':'image_equal_dQ','building_equal_mean':'building_equal_dQ',
            'abs_dQ_image_equal_mean':'image_equal_abs_dQ','abs_dQ_building_equal_mean':'building_equal_abs_dQ',
            'common_Q_physical_pairs':'common_physical_pairs','images':'images','buildings':'buildings',
            'positive_images':'positive_images','negative_images':'negative_images','exactly_negligible_images':'tie_images',
            'up_gt_1p0_images':'up_over1_images','down_lt_minus_1p0_images':'down_below_minus1_images','within_pm_1p0_images':'small_abs_atmost1_images'}
    checks=[]
    for original,alternate in fields.items():
        a=pd.to_numeric(f.loc[common,original]);b=pd.to_numeric(r.loc[common,alternate]);delta=(a-b).abs()
        maxdiff=float(delta.max()) if len(delta) else 0.
        matched=bool(np.allclose(a,b,rtol=0,atol=1e-9,equal_nan=True))
        checks.append(dict(check='independent_'+original,rows=len(common),max_abs_difference=maxdiff,passed=matched))
        if not matched:failures.append({'check':'independent_'+original,'detail':str(delta.nlargest(5).to_dict())})
    pos=formal[formal.orientation_sign_view==1].set_index(key)
    neg=formal[formal.orientation_sign_view==-1].set_index(key)
    if set(pos.index)!=set(neg.index):failures.append({'check':'six_direction_key_coverage','detail':'positive/negative keys differ'})
    for a,b,sign in [('image_equal_mean','image_equal_mean',-1),('building_equal_mean','building_equal_mean',-1),
                     ('abs_dQ_image_equal_mean','abs_dQ_image_equal_mean',1),('positive_images','negative_images',1),
                     ('negative_images','positive_images',1),('images','images',1),('buildings','buildings',1),
                     ('registered_physical_pairs','registered_physical_pairs',1),('common_Q_physical_pairs','common_Q_physical_pairs',1),
                     ('up_gt_1p0_images','down_lt_minus_1p0_images',1),('within_pm_1p0_images','within_pm_1p0_images',1),
                     ('cluster_bootstrap_low','cluster_bootstrap_high',-1),('cluster_bootstrap_high','cluster_bootstrap_low',-1),
                     ('building_equal_bootstrap_low','building_equal_bootstrap_high',-1),('building_equal_bootstrap_high','building_equal_bootstrap_low',-1)]:
        av=pd.to_numeric(pos[a]);bv=pd.to_numeric(neg.loc[pos.index,b])*sign
        matched=bool(np.allclose(av,bv,rtol=0,atol=1e-9,equal_nan=True))
        checks.append(dict(check='reverse_'+a+'_'+b,rows=len(av),max_abs_difference=float((av-bv).abs().max()) if (av-bv).notna().any() else 0.,passed=matched))
        if not matched:failures.append({'check':'reverse_'+a+'_'+b,'detail':'reverse identity not preserved'})
    empty=formal[formal.images==0]
    if not empty.image_equal_mean.isna().all():failures.append({'check':'empty_support_no_zero_mean','detail':'Some empty support has a numeric mean'})
    # The same original common support must be numerically identical in both
    # automatic and existing-assisted versions, including intervals generated
    # from the same deterministic building-cluster draws.
    original=formal[(formal.orientation_sign_view==1)&(formal.support=='original_common')]
    kk=['analysis_cohort','scope','n','m','class_pair']
    a=original[original.version=='automatic'].set_index(kk)
    b=original[original.version=='manual_order_assisted'].set_index(kk)
    for column in ['image_equal_mean','building_equal_mean','abs_dQ_image_equal_mean','images','common_Q_physical_pairs',
                   'cluster_bootstrap_low','cluster_bootstrap_high',
                   'building_equal_bootstrap_low','building_equal_bootstrap_high']:
        matched=bool(np.allclose(pd.to_numeric(a[column]),pd.to_numeric(b.loc[a.index,column]),rtol=0,atol=1e-10,equal_nan=True))
        checks.append(dict(check='unchanged_original_common_'+column,rows=len(a),max_abs_difference=float((a[column]-b.loc[a.index,column]).abs().max()) if len(a) else 0.,passed=matched))
        if not matched:failures.append({'check':'unchanged_original_common_'+column,'detail':'identical original support has inconsistent estimate or interval'})
    # Original common is a subset of expanded common. Equal physical support
    # counts therefore identify exactly unchanged supports, including automatic
    # original vs expanded displays and assisted conditions without new pairs.
    ks=['analysis_cohort','version','scope','n','m','class_pair']
    orig=pos.reset_index().query("support == 'original_common'").set_index(ks)
    exp=pos.reset_index().query("support == 'expanded_common'").set_index(ks)
    shared=orig.index.intersection(exp.index)
    identical=shared[orig.loc[shared,'common_Q_physical_pairs'].eq(exp.loc[shared,'common_Q_physical_pairs'])]
    for column in ['image_equal_mean','building_equal_mean','abs_dQ_image_equal_mean','images',
                   'cluster_bootstrap_low','cluster_bootstrap_high',
                   'building_equal_bootstrap_low','building_equal_bootstrap_high']:
        av=pd.to_numeric(orig.loc[identical,column]);bv=pd.to_numeric(exp.loc[identical,column])
        matched=bool(np.allclose(av,bv,rtol=0,atol=1e-10,equal_nan=True))
        checks.append(dict(check='same_support_original_expanded_'+column,rows=len(identical),
                           max_abs_difference=float((av-bv).abs().max()) if (av-bv).notna().any() else 0.,passed=matched))
        if not matched:failures.append({'check':'same_support_original_expanded_'+column,'detail':'identical original/expanded support has inconsistent estimate or interval'})
    canonical_fields=[]
    for filename in ['PHYSICAL_PAIRS_AUTOMATIC.csv.gz','PHYSICAL_PAIRS_ASSISTED.csv.gz']:
        columns=['current_source_class','current_target_class','current_direction','source_class_current','target_class_current','direction',
                 'registered_current_source_class','registered_current_target_class','registered_current_direction']
        d=pd.read_csv(ANA/filename,usecols=columns,low_memory=False)
        valid=bool(d.current_source_class.eq(d.source_class_current).all() and d.current_target_class.eq(d.target_class_current).all() and d.current_direction.eq(d.direction).all())
        canonical_fields.append(dict(file=filename,canonical_rows=len(d),current_fields_match_canonical_A_C=valid,
                                     registered_orientation_retained=bool(d.registered_current_direction.notna().all())))
        if not valid:failures.append({'check':'canonical_field_orientation','detail':filename})
    pd.DataFrame(checks).to_csv(HERE/'FORMAL_SUMMARY_INDEPENDENT_COMPARISON.csv',index=False)
    pd.DataFrame(failures,columns=['check','detail']).to_csv(HERE/'FORMAL_SUMMARY_INDEPENDENT_FAILURES.csv',index=False)
    current=HERE/'PAIR_DATASET_INDEPENDENT_REVIEW.json'
    receipt=json.loads(current.read_text(encoding='utf-8'));receipt['formal_summary_comparison']='passed' if not failures else 'failed'
    receipt['formal_summary_nonempty_canonical_rows_compared']=len(common)
    current.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    result=dict(status='passed' if not failures else 'failed',formal_summary_rows=len(formal),
                nonempty_canonical_rows_compared=len(common),six_direction_pair_conditions=len(pos),
                comparisons=len(checks),failures=len(failures),
                max_point_estimate_error=max(x['max_abs_difference'] for x in checks if x['check'].startswith('independent_')),
                canonical_field_checks=canonical_fields,
                original_common_confidence_interval_check='passed' if all(x['passed'] for x in checks if x['check'].startswith('unchanged_original_common_') and 'bootstrap' in x['check']) else 'failed',
                identical_original_expanded_support_conditions=len(identical),
                identical_original_expanded_interval_check='passed' if all(x['passed'] for x in checks if x['check'].startswith('same_support_original_expanded_') and 'bootstrap' in x['check']) else 'failed',
                statistical_source_sha256=hashlib.sha256(formal_path.read_bytes()).hexdigest(),
                uncertainty_note='Building-cluster bootstrap was not independently re-simulated; reversal identities and unchanged-support point/interval identities were checked. Independent point estimates were recomputed at the block, pool, image and building levels.')
    (HERE/'FORMAL_SUMMARY_INDEPENDENT_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
