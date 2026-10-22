"""Compare two time summaries on identical qualified support; no event reread."""
from pathlib import Path
import os,sys,json
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from analyze_expanded_results import save_csv,save_json,sha

def main():
    receipt=json.loads((HERE/'FINAL_ANALYSIS_COMPLETION.json').read_text())
    assert receipt['status']=='FINAL_COMPLETE' and receipt['pending_cells']==0
    source=HERE/'FINAL_ALL_COMPONENT_SUMMARY.csv.gz'
    components=pd.read_csv(source)
    coverage=pd.read_csv(HERE/'FINAL_COVERAGE.csv.gz')
    counts=['valid_events','valid_backgrounds','valid_images','valid_buildings']
    cols=['summary_id','building_mean','building_median']+counts
    arithmetic=components[components.metric.eq('cross_recorded_time_pct')][cols]
    log=components[components.metric.eq('cross_recorded_time_logratio')][cols]
    joined=arithmetic.merge(log,on='summary_id',suffixes=('_arithmetic','_log'),how='outer',validate='one_to_one',indicator=True)
    assert joined['_merge'].eq('both').all(),joined['_merge'].value_counts().to_dict()
    for c in counts:
        assert joined[c+'_arithmetic'].equals(joined[c+'_log']),(c,'support mismatch')
        joined[c]=joined[c+'_arithmetic']
    joined=joined.rename(columns={'building_mean_arithmetic':'arithmetic_percentage_change',
        'building_median_arithmetic':'arithmetic_percentage_building_median',
        'building_mean_log':'balanced_mean_logratio','building_median_log':'logratio_building_median'})
    joined['geometric_percentage_change']=100*np.expm1(joined.balanced_mean_logratio)
    joined['geometric_percentage_building_median']=100*np.expm1(joined.logratio_building_median)
    joined['arithmetic_minus_geometric_percentage_points']=joined.arithmetic_percentage_change-joined.geometric_percentage_change
    assert (joined.arithmetic_minus_geometric_percentage_points.dropna()>=-1e-9).all()
    joined=joined.drop(columns=['_merge']+[c+s for c in counts for s in ['_arithmetic','_log']])
    result=coverage.merge(joined,on='summary_id',how='inner',validate='one_to_one')
    result['time_unit']='recorded_person_seconds'
    result['weighting']='actual_common_background_then_image_then_building_equal'
    result['support']='ABC_same_single_time_source_all_n_members_recorded_finite_positive_totals'
    item=save_csv('FINAL_TIME_AGGREGATION_COMPARISON.csv',result)
    save_json('FINAL_TIME_AGGREGATION_COMPLETION.json',dict(status='complete',result=item,
        source_sha256=sha(source),coverage_sha256=sha(HERE/'FINAL_COVERAGE.csv.gz'),
        exact_support_verified=counts,arithmetic_formula='balanced mean of 100 * (C/A - 1)',
        geometric_formula='100 * expm1(balanced mean of log(C/A))',
        original_results_unchanged=True,native_fusion_calls=0,event_files_reread=0))
    print(json.dumps(item,ensure_ascii=False))
    return result

if __name__=='__main__':main()
