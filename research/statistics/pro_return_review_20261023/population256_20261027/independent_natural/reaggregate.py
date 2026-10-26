from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd

ap=argparse.ArgumentParser()
ap.add_argument('--input-root',type=Path,default=Path(__file__).resolve().parents[1])
ap.add_argument('--output',type=Path,default=Path(__file__).parent)
args=ap.parse_args()
ROOT = args.input_root
P = ROOT / 'analysis_precision26/results_stage2'
O = args.output
O.mkdir(parents=True,exist_ok=True)
c = pd.read_csv(P/'NATURAL_CURVES.csv.gz')
i = pd.read_csv(P/'NATURAL_INTERVALS.csv.gz')
checks=[]
def check(name, a, b, tol=1e-8):
    a,b=np.asarray(a,dtype=float),np.asarray(b,dtype=float)
    assert np.array_equal(np.isnan(a),np.isnan(b)), name+' NaNs'
    delta=np.abs(a-b)
    mx=float(np.nanmax(delta)) if np.isfinite(delta).any() else 0.0
    assert mx<tol,(name,mx)
    checks.append(dict(name=name,n=int(a.size),max_abs_error=mx))

assert not c.duplicated(['pool_id','cohort','k']).any()
assert not i.duplicated(['pool_id','cohort','interval']).any()
check('MCSE',c.Q_mean_MCSE_analytic,c.Q_sd_ddof1/np.sqrt(c.quality_valid_paths))
for rate,num,den in [
 ('actual_consensus_failure_rate','actual_consensus_failure_paths','actual_executed_nondeferred_paths'),
 ('output_unscoreable_rate','output_unscoreable_paths','actual_executed_nondeferred_paths'),
 ('failure_rate','failure_paths','nondeferred_attempts')]:
    check(rate,c[rate],c[num]/c[den].replace(0,np.nan))

# Rebuild marginal interval differences, independent of supplied interval code.
mi={'marginal_Q_delta':'Q_mean','Q_p10_delta':'Q_p10','Q_sd_delta':'Q_sd_ddof1',
    'failure_delta':'failure_rate','actual_consensus_failure_delta':'actual_consensus_failure_rate',
    'output_unscoreable_delta':'output_unscoreable_rate'}
for dest,source in mi.items():
    lookup=c.set_index(['pool_id','cohort','k'])[source]
    a=lookup.reindex(pd.MultiIndex.from_frame(i[['pool_id','cohort','k_from']])).to_numpy()
    b=lookup.reindex(pd.MultiIndex.from_frame(i[['pool_id','cohort','k_to']])).to_numpy()
    check('interval '+dest,i[dest],b-a)

# Union mean, sample variance and status counts must equal old48+new208.
z=c[c.cohort=='old48'].merge(c[c.cohort=='new208'],on=['pool_id','k'],suffixes=('_o','_n'),validate='one_to_one')
z=z.merge(c[c.cohort=='pooled256'],on=['pool_id','k'],validate='one_to_one')
for count in ['paths_attempted','quality_valid_paths','actual_consensus_failure_paths','output_unscoreable_paths','actual_executed_nondeferred_paths','failure_paths']:
    check('union '+count,z[count],z[count+'_o']+z[count+'_n'])
n0,n1=z.quality_valid_paths_o,z.quality_valid_paths_n
mu=(z.Q_mean_o.fillna(0)*n0+z.Q_mean_n.fillna(0)*n1)/(n0+n1).replace(0,np.nan)
check('union Q mean',z.Q_mean,mu)
ss0=(n0-1)*z.Q_sd_ddof1_o.fillna(0)**2+n0*(z.Q_mean_o.fillna(0)-mu)**2
ss1=(n1-1)*z.Q_sd_ddof1_n.fillna(0)**2+n1*(z.Q_mean_n.fillna(0)-mu)**2
check('union Q SD',z.Q_sd_ddof1,np.sqrt((ss0+ss1)/(n0+n1-1).where(n0+n1>1)))

# Rebuild cross-version common observed supports, then every observed aggregate.
for kind,data,at,file in [('curve',c,'k','COMMON_SUPPORT_CURVE_SUMMARY.csv.gz'),('interval',i,'interval','COMMON_SUPPORT_INTERVAL_SUMMARY.csv.gz')]:
    ref=pd.read_csv(P/file)
    metrics=ref.metric.unique().tolist()
    d=data.melt(id_vars=['pool_id','cohort','layer','difficulty','pool_n','building',at],value_vars=metrics,var_name='metric',value_name='value').dropna(subset=['value'])
    primary=d[d.cohort.isin(['old48','new208','pooled256'])]
    good=primary.groupby(['pool_id',at,'metric']).cohort.nunique()
    good=good[good==3].reset_index()[['pool_id',at,'metric']]
    d=d.merge(good,on=['pool_id',at,'metric'],validate='many_to_one')
    panels=[]
    for pan,cut in [(('all_available_at_k' if kind=='curve' else 'interval_eligible'),0),('fixed_N_ge_30',30),('fixed_N_ge_35',35)]:
        p=d[d.pool_n>=cut].copy()
        if kind=='curve' and cut:p=p[p.k<=cut]
        p['panel']=pan
        aggregate=p.copy()
        aggregate['difficulty']=np.where(aggregate.layer=='ordinary_manual','\u5168\u90e8','\u5355\u5217')
        detail=p[p.layer=='ordinary_manual']
        panels.extend([aggregate,detail])
    d=pd.concat(panels,ignore_index=True)
    keys=['cohort','panel','layer','difficulty',at,'metric']
    g=d.groupby(keys,sort=False)
    stats=g.agg(estimate=('value','mean'),images=('value','size'),buildings=('building','nunique'),positive_images=('value',lambda s:(s>1e-9).sum()),negative_images=('value',lambda s:(s< -1e-9).sum()),near_zero_images=('value',lambda s:(s.abs()<=1e-9).sum()),image_median=('value','median'),image_p10=('value',lambda s:s.quantile(.1)),image_p90=('value',lambda s:s.quantile(.9))).reset_index()
    bmeans=d.groupby(keys+['building']).value.mean().groupby(keys).mean().rename('bestimate').reset_index()
    stats=stats.merge(bmeans,on=keys)
    a=stats.copy();a['weighting']='image_equal'
    b=stats.copy();b['weighting']='building_equal';b['estimate']=b.bestimate
    built=pd.concat([a,b],ignore_index=True)
    joined=ref.merge(built,on=keys+['weighting'],suffixes=('_ref','_calc'),validate='one_to_one',indicator=True)
    assert len(joined)==len(ref)==len(built) and (joined._merge=='both').all()
    for f in ['estimate','images','buildings','positive_images','negative_images','near_zero_images','image_median','image_p10','image_p90']:
        check(kind+' summary '+f,joined[f+'_ref'],joined[f+'_calc'])

out=[]
for cohort in ['old48','stage1_104','stage2_104','new208','pooled256']:
 for layer,diff,minn,interval in [('ordinary_manual','\u56f0\u96be',30,'20_to_30'),('ordinary_manual','\u56f0\u96be',30,'3_to_6'),('doorway_manual',None,0,'6_to_10'),('doorway_manual',None,0,'20_to_30')]:
  d=i[(i.cohort==cohort)&(i.layer==layer)&(i.pool_n>=minn)&(i.interval==interval)]
  if diff:d=d[d.difficulty==diff]
  for metric in mi:
   x=d.dropna(subset=[metric]);v=x[metric]
   out.append(dict(cohort=cohort,layer=layer,difficulty=diff,minimum_n=minn,interval=interval,metric=metric,images=len(x),buildings=x.building.nunique(),mean=v.mean(),positive=int((v>1e-9).sum()),negative=int((v< -1e-9).sum()),zero=int((v.abs()<=1e-9).sum())))
pd.DataFrame(out).to_csv(O/'INDEPENDENT_KEY_INTERVALS.csv',index=False)
pr=[]
for cohort in ['old48','pooled256']:
 for k in [3,6,10,20,30]:
  d=c[(c.cohort==cohort)&(c.layer=='ordinary_manual')&(c.pool_n>=30)&(c.k==k)]
  pr.append(dict(cohort=cohort,k=k,images=len(d),meanQ=d.Q_mean.mean(),mean_MCSE_gt1=int((d.Q_mean_MCSE_analytic>1).sum()),P10_halfwidth_gt2=int((((d.Q_p10_boot_high-d.Q_p10_boot_low)/2)>2).sum())))
pd.DataFrame(pr).to_csv(O/'INDEPENDENT_PRECISION_READOUT.csv',index=False)
(O/'CHECKS.json').write_text(json.dumps(checks,indent=2),encoding='utf8')
print(json.dumps(checks,indent=2))
print(pd.DataFrame(pr).to_string(index=False))
