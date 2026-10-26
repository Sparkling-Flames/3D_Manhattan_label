"""Post-budget precision accounting; no new order selection or endpoint execution.

Produces descriptive planning quantities from the completed, prespecified sample.
R*(observed SE / target)^2 assumes unchanged outcome variance and scoreability.
It is neither a guarantee nor an adaptive rule used in the current experiment.
"""
from pathlib import Path
import argparse, sys, os, math
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name] = '1'
import numpy as np
import pandas as pd


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True)
    args=ap.parse_args();base=args.base.resolve()
    sys.path.insert(0,str(base/'analysis_precision26'))
    from precision_core import save_csv,save_json
    source=base/'analysis_precision26/results_stage2'
    receipt=__import__('json').loads((source/'ANALYSIS_RECEIPT.json').read_text())
    assert receipt['complete_requested_pool_support'] and receipt['pools']==194
    d=pd.read_csv(source/'NATURAL_CURVES.csv.gz')
    d=d[d.cohort.isin(['old48','stage1_104','stage2_104','new208','pooled256'])].copy()
    prior=base/'prior_recovered/research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025'
    exact=pd.read_csv(prior/'analysis_precision/new_results/EXACT_FINITE_MARGINAL_STATISTICS.csv')
    assert exact.exact_complete.eq(True).all(), 'Do not label an incomplete catalogue as exact'
    finite_keys=set(zip(exact.pool_id,exact.k))
    d['exact_uniform_team_catalogue_available']=[(p,int(k)) in finite_keys for p,k in zip(d.pool_id,d.k)]
    d['Q_p10_empirical95_halfwidth']=(d.Q_p10_boot_high-d.Q_p10_boot_low)/2
    d['Q_p10_order95_halfwidth']=(d.P10_order_high-d.P10_order_low)/2
    d['mean_working_target_MCSE_le1']=d.Q_mean_MCSE_analytic.le(1)&d.Q_mean.notna()
    d['P10_working_target_empirical_halfwidth_le2']=d.Q_p10_empirical95_halfwidth.le(2)&d.Q_p10.notna()
    d['P10_working_target_rank_halfwidth_le2']=d.Q_p10_order95_halfwidth.le(2)&d.Q_p10.notna()
    d['constant_nonfull_is_not_precision_proof']=d.empirical_constant_Q_nonfull
    if 'actual_consensus_failure_rate' in d:
        d['no_observed_consensus_failure']=d.actual_consensus_failure_rate.eq(0)&d.nondeferred_attempts.gt(0)
    rows=[]
    for row in d[d.cohort.eq('pooled256')].itertuples():
        for target in [.5,1.0]:
            estimate=(row.paths_attempted*(row.Q_mean_MCSE_analytic/target)**2
                      if np.isfinite(row.Q_mean_MCSE_analytic) else np.nan)
            exact_available=row.exact_uniform_team_catalogue_available or row.fullN_single_known_team
            if exact_available:
                action='use_existing_complete_uniform_catalogue_for_this_k'
            elif not np.isfinite(estimate):
                action='Q_unavailable_do_not_infer_required_budget'
            elif row.empirical_constant_Q_nonfull:
                action='empirical_constant_nonfull_no_zero_error_guarantee'
            elif estimate<=row.paths_attempted:
                action='working_pointwise_mean_target_met_in_current_sample'
            else:
                action='possible_future_mean_precision_increment_not_executed'
            rows.append(dict(pool_id=row.pool_id,image=row.image,building=row.building,
                layer=row.layer,difficulty=row.difficulty,pool_n=row.pool_n,k=row.k,
                paths=row.paths_attempted,Q_valid=row.quality_valid_paths,
                observed_mean_MCSE=row.Q_mean_MCSE_analytic,target_mean_MCSE=target,
                constant_variance_projected_total_paths=np.ceil(estimate) if np.isfinite(estimate) else np.nan,
                constant_variance_projected_additional_paths=max(0,np.ceil(estimate)-row.paths_attempted) if np.isfinite(estimate) else np.nan,
                exact_uniform_team_catalogue_available=exact_available,assessment=action,
                estimate_is_guarantee=False,used_as_current_stopping_rule=False))
    out=base/'analysis_reporting26/results';out.mkdir(parents=True,exist_ok=True)
    point_budgets=pd.DataFrame(rows)
    save_csv(point_budgets,out/'DESCRIPTIVE_MEAN_PRECISION_BUDGET.csv.gz')
    whole_budgets=[]
    for (pid,target),g in point_budgets.groupby(['pool_id','target_mean_MCSE']):
        internal=g[~g.exact_uniform_team_catalogue_available & g.k.ne(2)]
        finite=internal[internal.constant_variance_projected_total_paths.notna()]
        anchor=g.iloc[0]
        maximum=finite.constant_variance_projected_total_paths.max() if len(finite) else 0
        whole_budgets.append(dict(pool_id=pid,image=anchor.image,building=anchor.building,
            layer=anchor.layer,difficulty=anchor.difficulty,pool_n=int(anchor.pool_n),
            target_pointwise_mean_MCSE=target,internal_nonexact_k=len(internal),
            nonestimable_internal_k=int(internal.constant_variance_projected_total_paths.isna().sum()),
            empirical_constant_nonexact_k=int(internal.assessment.eq('empirical_constant_nonfull_no_zero_error_guarantee').sum()),
            max_internal_pointwise_projected_total_paths=maximum,
            k_at_projected_maximum='|'.join(map(str,finite.loc[finite.constant_variance_projected_total_paths.eq(maximum),'k'].astype(int))),
            current_path_budget=int(anchor.paths),
            possible_next_full_path_budget=(0 if len(internal)==0 else
                next((r for r in [256,512,1024,2048,4096] if r>=maximum),None)
                if len(internal)==len(finite) else None),
            meaning='whole-order allocation covering all k; projection uses pointwise mean SE, not simultaneous confidence guarantee',
            used_to_stop_current_experiment=False))
    save_csv(pd.DataFrame(whole_budgets),out/'WHOLE_ORDER_FUTURE_MEAN_BUDGET_PROJECTIONS.csv')
    columns=['pool_id','image','building','layer','difficulty','pool_n','cohort','k','paths_attempted',
        'quality_valid_paths','unique_teams','Q_mean','Q_sd_ddof1','Q_mean_MCSE_analytic','Q_p10',
        'Q_p10_inverse_cdf','Q_p10_empirical95_halfwidth','Q_p10_order95_halfwidth',
        'mean_working_target_MCSE_le1','P10_working_target_empirical_halfwidth_le2',
        'P10_working_target_rank_halfwidth_le2','exact_uniform_team_catalogue_available',
        'constant_nonfull_is_not_precision_proof','failure_rate','actual_consensus_failure_rate',
        'output_unscoreable_rate','reference_unavailable_rate','not_executed_rate',
        'actual_executed_nondeferred_paths','actual_consensus_failure_paths',
        'actual_consensus_failure_CP_low','actual_consensus_failure_CP_high',
        'actual_consensus_failure_one_sided_CP_high','output_unscoreable_paths',
        'output_unscoreable_CP_low','output_unscoreable_CP_high',
        'output_unscoreable_one_sided_CP_high',
        'failure_one_sided_CP_high','fullN_single_known_team']
    save_csv(d[[c for c in columns if c in d]],out/'POINTWISE_PRECISION_DECISION_TABLE.csv.gz')
    summaries=[]
    for layer in ['ordinary_manual','doorway_manual']:
        for capacity in [0,30,35]:
            g0=d[d.layer.eq(layer)&d.pool_n.ge(capacity)]
            if g0.empty:continue
            groups=[('全部' if layer=='ordinary_manual' else '单列',g0)]
            if layer=='ordinary_manual':groups+=list(g0.groupby('difficulty'))
            for difficulty,g1 in groups:
                for (cohort,k),g in g1.groupby(['cohort','k']):
                    q=g[g.Q_mean.notna()]
                    summaries.append(dict(layer=layer,difficulty=difficulty,minimum_pool_n=capacity,
                        cohort=cohort,k=int(k),candidate_images=g.pool_id.nunique(),
                        candidate_buildings=g.building.nunique(),Q_images=len(q),
                        mean_MCSE_gt1=int(q.Q_mean_MCSE_analytic.gt(1).sum()),
                        median_mean_MCSE=q.Q_mean_MCSE_analytic.median(),
                        P90_mean_MCSE=q.Q_mean_MCSE_analytic.quantile(.9),
                        mean_MCSE_max=q.Q_mean_MCSE_analytic.max(),
                        P10_empirical_halfwidth_gt2=int(q.Q_p10_empirical95_halfwidth.gt(2).sum()),
                        P10_rank_halfwidth_gt2=int(q.Q_p10_order95_halfwidth.gt(2).sum()),
                        median_P10_empirical_halfwidth=q.Q_p10_empirical95_halfwidth.median(),
                        median_P10_rank_halfwidth=q.Q_p10_order95_halfwidth.median(),
                        exact_uniform_catalogue_images=int(g.exact_uniform_team_catalogue_available.sum()),
                        empirical_constant_nonfull_images=int(g.empirical_constant_Q_nonfull.sum())))
    save_csv(pd.DataFrame(summaries),out/'PRECISION_RECOMMENDATION_COUNTS.csv')
    # Exact, one-sided binomial upper limits after zero observed failures.
    # Independent order draws sample finite teams with replacement across paths;
    # full enumeration is different and needs no such upper-limit calculation.
    failure=[]
    for r in [24,48,96,104,208,256,304,512,1000]:
        failure.append(dict(independent_order_draws=r,observed_failures=0,
            one_sided_95_upper_probability=1-.05**(1/r),
            actual_new_sample_in_this_study=r in [104,208],
            meaning='binomial sampling calculation; not proof of zero finite-population failures'))
    save_csv(pd.DataFrame(failure),out/'ZERO_OBSERVED_FAILURE_PRECISION_SCALE.csv')
    # Planning examples for nonzero failure probabilities.  These are analytic
    # binomial intervals at rounded expected counts, not observed new outcomes.
    # The interval must not be read as a confidence guarantee on every image.
    from scipy.stats import binomtest
    interval_examples=[]
    for r in [48,104,208,256,512,1000]:
        for probability in [.01,.05,.10,.50]:
            count=int(np.floor(r*probability+.5))
            interval=binomtest(count,r).proportion_ci(confidence_level=.95,method='exact')
            interval_examples.append(dict(independent_order_draws=r,
                planning_probability=probability,illustrative_observed_failures=count,
                illustrative_observed_rate=count/r,CP95_low=interval.low,CP95_high=interval.high,
                CP95_halfwidth=(interval.high-interval.low)/2,
                actual_new_observation=False,
                interpretation='planning calculation at rounded expected count; not a result for a study image'))
    save_csv(pd.DataFrame(interval_examples),out/'FAILURE_PROBABILITY_PLANNING_INTERVALS_NOT_OBSERVED.csv')
    # A finite marginal can be cheaper than many additional complete orders.
    # This upper bound uses only teams seen by the main natural sample. Policy
    # and other historical caches can reduce the remaining requests further.
    catalogue_plans=[]
    for row in d[d.cohort.eq('pooled256')].itertuples():
        n=int(row.pool_n);k=int(row.k)
        if k not in {1,3,n-2,n-1,n} or k==2:continue
        finite=math.comb(n,k)
        is_exact=bool(row.exact_uniform_team_catalogue_available or row.fullN_single_known_team)
        catalogue_plans.append(dict(pool_id=row.pool_id,image=row.image,building=row.building,
            layer=row.layer,difficulty=row.difficulty,pool_n=n,k=k,
            finite_team_count=finite,main256_unique_sampled_teams=int(row.unique_teams),
            existing_complete_catalogue=is_exact,
            additional_endpoint_request_upper_bound=0 if is_exact else max(0,finite-int(row.unique_teams)),
            request_bound_accounts_for_other_policy_caches=False,
            additional_requests_executed_in_this_analysis=0,
            role='future finite-marginal budget comparison; complete-path estimand remains separate'))
    save_csv(pd.DataFrame(catalogue_plans),out/'FINITE_MARGINAL_FUTURE_BUDGET_UPPER_BOUNDS.csv')
    save_json(dict(source_commit='b9bcec809fbaec8ab055931a1abb7baa5db44dac',
        input=str(source/'NATURAL_CURVES.csv.gz'),all194_pools_complete=True,
        new_orders_generated=0,new_endpoints=0,
        projected_budget_assumptions=['same conditional Q variance','same scoreability probability',
            'pointwise mean target, not a simultaneous curve guarantee'],
        quantile_budget='No variance-only extrapolation of P10 sample size',
        future_budget_values_not_executed=True),out/'PRECISION_DECISION_RECEIPT.json')
    print('Saved precision planning tables from complete frozen results',flush=True)


if __name__=='__main__':main()
