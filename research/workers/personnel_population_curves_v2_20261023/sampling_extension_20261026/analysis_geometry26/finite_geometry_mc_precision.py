"""Known finite-population U-statistic variance for the three fixed cases.

No new people, permutations or endpoint/fusion calculations. Monte Carlo here
only calibrates an estimator against already fully known finite team distances.
It is explicitly conditional on each observed count of valid geometry q.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,math,os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
from pathlib import Path
import numpy as np
import pandas as pd
from geometry_extension import distance_matrices,save_json
from safe_io import install_safe_csv_writer
install_safe_csv_writer()

def seed_for(*parts):
    s=json.dumps(['finite_geometry_estimator_calibration_20261026',2026102606,*parts],separators=(',',':')).encode()
    return int.from_bytes(hashlib.sha256(s).digest()[:8],'little')

def moments(h):
    theta=float(h.mean());z1=float(np.var(h.mean(axis=1)));vh=float(np.var(h));z2=vh-2*z1
    assert z2>=-1e-12
    return theta,z1,max(0.,z2),vh

def simulated_u_and_jackknife(h,counts,attempts):
    q=counts.sum(axis=1);assert np.unique(q).size==1;q=int(q[0])
    scores=counts@h;total=np.sum(scores*counts,axis=1);u=total/(q*(q-1))
    leave=(total[:,None]-2*scores)/((q-1)*(q-2))
    # The mean leave-one-attempt estimate equals U exactly; invalid attempts
    # leave it unchanged and contribute zero to the jackknife squared sum.
    se=np.sqrt((attempts-1)/attempts*np.sum(counts*(leave-u[:,None])**2,axis=1))
    return u,se

def main(folder,replicates):
    with gzip.open(folder/'FINITE_TEAM_GEOMETRY_AND_REFERENCES.json.gz','rt') as f:cases=json.load(f)
    saved=pd.read_csv(folder/'FINITE_CATALOGUE_GEOMETRY_COMPARISON.csv')
    exactteam=pd.read_csv(folder/'EXACT_TEAMS_AND_NEW_PATH_FREQUENCIES.csv')
    components=[];estimates=[];simulation=[]
    for case in cases:
        pid=case['pool_id'];rows={r['team_key']:r for r in case['teams']};keys=list(rows)
        matrices,_=distance_matrices(keys,rows)
        for metric,d in matrices.items():
            valid=np.isfinite(np.diag(d));h=d[np.ix_(valid,valid)];M=len(h)
            theta,z1,z2,vh=moments(h)
            components.append(dict(pool_id=pid,image=case['image'],k=case['k'],metric=metric,
                finite_teams_total=len(d),finite_valid_teams=M,exact_pair_denominator=M*M,
                exact_mean=theta,variance_first_projection=z1,variance_second_component=z2,variance_kernel=vh,
                sampling_target='two independent uniform valid teams; same-team draws included'))
            observed=saved[saved.pool_id.eq(pid)&saved.metric.eq(metric)&~saved.cohort.eq('exact_uniform_catalogue')]
            for r in observed.itertuples():
                q=int(r.valid_paths);R=int(r.attempted_paths)
                first=4*z1/q;second=2*z2/(q*(q-1));var=first+second;se=math.sqrt(var)
                estimates.append(dict(pool_id=pid,image=case['image'],k=case['k'],metric=metric,cohort=r.cohort,
                    attempted_paths=R,valid_paths=q,observed_estimate=r.mean,exact_mean=theta,
                    error_from_exact=r.mean-theta,reported_jackknife_mcse=r.mcse,
                    known_population_mcse_conditional_valid_count=se,
                    jackknife_to_known_se_ratio=r.mcse/se if se else np.nan,
                    known_first_order_variance=first,known_second_order_variance=second,
                    known_second_order_fraction=second/var if var else np.nan,
                    exact_population_known=True,conditional_on_valid_count=True))
                if metric!='V_floor':continue
                sd=seed_for(pid,r.cohort,q,R,replicates)
                rng=np.random.default_rng(sd);counts=rng.multinomial(q,np.full(M,1/M),size=replicates)
                u,jack=simulated_u_and_jackknife(h,counts,R)
                # Reconstruct the saved actual jackknife using frequencies to
                # ensure this calibration uses exactly the observed estimator.
                order=[keys[i] for i in np.flatnonzero(valid)]
                c=exactteam[exactteam.pool_id.eq(pid)].set_index('team_key').reindex(order)[r.cohort+'_path_count'].to_numpy(int)
                assert c.sum()==q
                uu,jj=simulated_u_and_jackknife(h,c[None,:],R)
                assert abs(uu[0]-r.mean)<1e-12 and abs(jj[0]-r.mcse)<1e-12
                cover=np.abs(u-theta)<=1.96*jack
                normal_known=np.abs(u-theta)<=1.96*se
                probability=float(cover.mean())
                simulation.append(dict(pool_id=pid,image=case['image'],k=case['k'],metric=metric,cohort=r.cohort,
                    attempted_paths=R,valid_paths=q,simulation_replicates=replicates,simulation_seed=str(sd),
                    exact_mean=theta,known_population_mcse=se,observed_estimate=r.mean,observed_jackknife_mcse=r.mcse,
                    simulation_mean=float(u.mean()),simulation_sd=float(np.std(u,ddof=1)),
                    simulation_bias=float(u.mean()-theta),simulation_P025=float(np.quantile(u,.025)),simulation_P975=float(np.quantile(u,.975)),
                    observed_inside_simulation_central95=bool(np.quantile(u,.025)<=r.mean<=np.quantile(u,.975)),
                    jackknife_median=float(np.median(jack)),jackknife_P10=float(np.quantile(jack,.1)),jackknife_P90=float(np.quantile(jack,.9)),
                    jackknife_normal95_coverage=probability,jackknife_coverage_simulation_mcse=math.sqrt(probability*(1-probability)/replicates),
                    known_se_normal95_coverage=float(normal_known.mean()),
                    probability_jackknife_less_half_known_se=float((jack<.5*se).mean()),
                    interpretation='estimator simulation conditional on q; not new registered paths or native teams'))
    pd.DataFrame(components).to_csv(folder/'EXACT_GEOMETRY_VARIANCE_COMPONENTS.csv',index=False)
    pd.DataFrame(estimates).to_csv(folder/'GEOMETRY_JACKKNIFE_AND_KNOWN_POPULATION_MCSE.csv',index=False)
    pd.DataFrame(simulation).to_csv(folder/'FINITE_GEOMETRY_ESTIMATOR_CALIBRATION.csv',index=False)
    save_json(folder/'FINITE_GEOMETRY_PRECISION_RECEIPT.json',dict(cases=3,variance_component_rows=len(components),
        observed_estimator_rows=len(estimates),calibration_rows=len(simulation),simulations_per_row=replicates,
        new_random_entering_orders=0,new_team_endpoint_evaluations=0,source='complete 89-team geometry case bundle',
        preserved_previous_jackknife=True,exact_variance_formula='4*sigma1_squared/q + 2*sigma2_squared/[q(q-1)]',
        conditional_valid_count=True,finite_team_draws_with_replacement=True,
        simulation_namespace='finite_geometry_estimator_calibration_20261026',master_seed=2026102606))
    print(pd.DataFrame(estimates).query("metric=='V_floor'").to_string(index=False),flush=True)
    print(pd.DataFrame(simulation)[['image','cohort','known_population_mcse','observed_jackknife_mcse','jackknife_normal95_coverage','observed_inside_simulation_central95']].to_string(index=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case-dir',type=Path,required=True);p.add_argument('--replicates',type=int,default=20000);a=p.parse_args();main(a.case_dir.resolve(),a.replicates)
