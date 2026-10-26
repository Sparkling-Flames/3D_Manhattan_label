"""Analytic discrete P10 boundary note from actual complete finite catalogues.

No extra random orders, simulations, or fusion calls. Select the two largest
positive gaps exactly at the conditional valid-Q 10% boundary. Registered k1
paths are looked up by their actual first person in the complete saved catalogue.
"""
from __future__ import annotations
import argparse,hashlib,inspect,json,math,sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import binom

VERSIONS={'old48':{'old24','prior_new24'},'stage1_104':{'extension_stage1_104'},
          'stage2_104':{'extension_stage2_104'},'new208':{'extension_stage1_104','extension_stage2_104'},
          'pooled256':{'old24','prior_new24','extension_stage1_104','extension_stage2_104'}}


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def order_info(R,p=.1):
    h=p*(R-1);lo=int(np.floor(h))+1;hi=int(np.ceil(h))+1;w=h-np.floor(h)
    if lo==hi:
        low=float(binom.sf(lo-1,R,p));high=float(binom.cdf(lo-1,R,p));cross=0.
    else:
        low=float(binom.sf(hi-1,R,p));high=float(binom.cdf(lo-1,R,p));cross=float(binom.pmf(lo,R,p))
    assert abs(low+high+cross-1)<1e-12
    return dict(R_valid_iid_draws=R,lower_order_rank=lo,upper_order_rank=hi,upper_interpolation_weight=float(w),
                prob_both_interpolation_orders_low_side=low,prob_orders_straddle_boundary=cross,
                prob_both_interpolation_orders_high_side=high)


def main(study,out):
    sys.path.insert(0,str(study/'analysis_precision26'))
    sys.path.insert(0,str(study/'analysis_geometry26'))
    from exact_anchor_and_display import finite_quantile_expectation
    from safe_io import atomic_bytes,install_safe_csv_writer
    install_safe_csv_writer();out.mkdir(exist_ok=True,parents=True)
    prior=study/'prior_recovered/research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025'
    population=study/'repo/research/workers/personnel_population_curves_v2_20261023'
    statfile=prior/'analysis_precision/new_results/EXACT_FINITE_MARGINAL_STATISTICS.csv'
    rawfile=prior/'new_endpoints/EXACT_MARGINAL_VALUES.csv.gz'
    stats=pd.read_csv(statfile);raw=pd.read_csv(rawfile,low_memory=False)
    assert not raw.duplicated(['pool_id','k','team_key']).any()
    valid=stats[stats.condition.eq('manual')&stats.exact_complete.eq(True)&stats.k.ne(2)]
    eligible=valid[valid.quality_valid_teams.ge(10)&valid.quality_valid_teams.mod(10).eq(0)]
    search=[]
    for r in eligible.to_dict('records'):
        g=raw[raw.pool_id.eq(r['pool_id'])&raw.k.eq(r['k'])];q=np.sort(g.B8L2.dropna().to_numpy(float));M=len(q);j=M//10
        assert len(g)==int(r['finite_population_teams'])==math.comb(int(r['pool_n']),int(r['k']))
        assert M==int(r['quality_valid_teams'])
        assert np.allclose(g.marginal_weight,1/len(g),rtol=0,atol=1e-12)
        a,b=q[j-1],q[j];boundary_count=int(np.sum(q<=a));cdf=boundary_count/M
        search.append(dict(**r,catalogue_raw_rows=len(g),complete_count_verified=True,unique_team_keys=g.team_key.nunique(),
            lower_Q=float(a),upper_Q=float(b),gap=float(b-a),lower_side_valid_teams=boundary_count,
            conditional_CDF_lower=float(cdf),exact_boundary=cdf==.1,
            catalogue_P10_linear=float(np.quantile(q,.1,method='linear')),
            population_P10_inverse_cdf=float(np.quantile(q,.1,method='inverted_cdf')),
            asymptotic_mean_of_sample_linear_if_positive_gap=float((a+b)/2)))
    scan=pd.DataFrame(search).sort_values(['gap','pool_id','k'],ascending=[False,True,True]).reset_index(drop=True)
    scan['selected_for_note']=False
    selection=scan[scan.exact_boundary&scan.gap.gt(0)].head(2).index
    scan.loc[selection,'selected_for_note']=True;selected=scan.loc[selection]
    scan.to_csv(out/'BOUNDARY_SEARCH.csv',index=False)
    assert len(selected)==2 and selected.k.eq(1).all()
    ids=set(selected.pool_id)
    exact_raw=raw[raw.pool_id.isin(ids)&raw.k.eq(1)].copy()
    assert exact_raw.B8L2.notna().all()
    exact_raw.to_csv(out/'SELECTED_EXACT_TEAM_VALUES.csv.gz',index=False)
    summary=[];analytics=[]
    for r in selected.to_dict('records'):
        q=exact_raw[exact_raw.pool_id.eq(r['pool_id'])].B8L2.to_numpy(float)
        for R in [48,104,208,256,512,1000]:
            linear,inverse=finite_quantile_expectation(q,R)
            analytics.append(dict(pool_id=r['pool_id'],image=r['image'],building=r['building'],layer=r['layer'],difficulty=r['difficulty'],k=r['k'],
                total_finite_teams=r['finite_population_teams'],valid_Q_teams=r['quality_valid_teams'],
                lower_Q=r['lower_Q'],upper_Q=r['upper_Q'],gap=r['gap'],conditional_CDF_lower=r['conditional_CDF_lower'],
                catalogue_P10_linear=r['catalogue_P10_linear'],population_P10_inverse_cdf=r['population_P10_inverse_cdf'],
                asymptotic_sample_quantile_mean=r['asymptotic_mean_of_sample_linear_if_positive_gap'],
                expected_sample_P10_linear=float(linear),expected_sample_P10_inverse_cdf=float(inverse),
                **order_info(R),calculation='exact binomial order-statistic expectation; no new random draws',new_fusions=0))
    expected=pd.DataFrame(analytics);expected.to_csv(out/'P10_ANALYTIC_EXPECTATION.csv',index=False)
    paths=[];sources=[]
    for orderfile,selector,batch,linkfile in [
        (population/'design/EXACT_ORDER_DESIGN.csv.gz',None,'old24',population/'results/PREFIX_TEAM_LINKS.csv.gz'),
        (prior/'design/NEW_EXACT_ORDER_DESIGN.csv.gz','balanced_new24','prior_new24',prior/'design/NEW_PREFIX_TEAM_LINKS.csv.gz')]:
        orders=pd.read_csv(orderfile,dtype={'seed':str,'master_seed':str},low_memory=False)
        orders=orders[orders.pool_id.isin(ids)&orders.policy.eq('natural_random')].copy()
        if selector:orders=orders[orders.batch.eq(selector)]
        orders['batch']=batch;sources.extend([orderfile,linkfile])
        links=pd.read_csv(linkfile,low_memory=False);links=links[links.path_id.isin(orders.path_id)&links.k.eq(1)].set_index('path_id')
        assert set(links.index)==set(orders.path_id)
        for r in orders.to_dict('records'):
            r['registered_team_key']=links.loc[r['path_id'],'team_key'];paths.append(r)
    for pid in sorted(ids):
        orderfile=study/'design26/orders_by_pool'/f'{pid}.csv.gz';sources.append(orderfile)
        orders=pd.read_csv(orderfile,dtype={'seed':str,'master_seed':str},low_memory=False);orders=orders[orders.policy.eq('natural_random')]
        all_links=[]
        for stage in [1,2]:
            linkfile=study/f'design26/links_by_pool/stage{stage}'/f'{pid}.csv.gz';sources.append(linkfile)
            x=pd.read_csv(linkfile,low_memory=False);all_links.append(x[x.k.eq(1)&x.policy.eq('natural_random')])
        links=pd.concat(all_links).set_index('path_id');assert set(links.index)==set(orders.path_id)
        for r in orders.to_dict('records'):
            r['registered_team_key']=links.loc[r['path_id'],'team_key'];paths.append(r)
    bindings=[]
    for r in paths:
        order=r['worker_order'].split('|');worker=order[0]
        one=exact_raw[exact_raw.pool_id.eq(r['pool_id'])&exact_raw.member_workers.eq(worker)]
        assert len(one)==1;t=one.iloc[0]
        assert t.team_key==r['registered_team_key'];assert len(order)==int(t.pool_n);assert len(set(order))==len(order)
        a=selected[selected.pool_id.eq(r['pool_id'])].iloc[0]
        bindings.append(dict(pool_id=r['pool_id'],image=t.image,path_id=r['path_id'],batch=r['batch'],seed=r.get('seed'),master_seed=r.get('master_seed'),
            generation=r.get('generation'),worker_order=r['worker_order'],k=1,first_worker=worker,
            team_key=t.team_key,member_object_ids=t.member_object_ids,reference_id=t.reference_id,reference_version=t.reference_version,
            B8L2=t.B8L2,low_side=bool(t.B8L2<=a.lower_Q),cached_endpoint=True,
            value_source='complete saved singleton catalogue',path_source='actual saved old / registered new full order',new_fusion=False))
    bindings=pd.DataFrame(bindings);assert not bindings.path_id.duplicated().any();assert len(bindings)==512
    bindings.to_csv(out/'REGISTERED_K1_PATH_BINDINGS.csv.gz',index=False)
    for r in selected.to_dict('records'):
        data=bindings[bindings.pool_id.eq(r['pool_id'])]
        for cohort,batches in VERSIONS.items():
            g=data[data.batch.isin(batches)];q=g.B8L2.to_numpy(float);R=len(q);info=order_info(R)
            assert len(g)==int(cohort.rsplit('_',1)[-1]) if cohort.startswith('stage') else len(g)=={'old48':48,'new208':208,'pooled256':256}[cohort]
            low=int(g.low_side.sum());lo=info['lower_order_rank'];hi=info['upper_order_rank']
            mode='both_orders_low' if low>=hi else 'both_orders_high' if low<lo else 'orders_straddle_boundary'
            e=expected[expected.pool_id.eq(r['pool_id'])&expected.R_valid_iid_draws.eq(R)].iloc[0]
            summary.append(dict(pool_id=r['pool_id'],image=r['image'],k=1,cohort=cohort,paths=R,valid_Q_paths=R,unique_teams=g.team_key.nunique(),
                low_side_count=low,low_side_fraction=low/R,observed_P10_linear=float(np.quantile(q,.1,method='linear')),
                observed_P10_inverse_cdf=float(np.quantile(q,.1,method='inverted_cdf')),observed_interpolation_branch=mode,
                population_low_side_fraction=.1,lower_Q=r['lower_Q'],upper_Q=r['upper_Q'],gap=r['gap'],
                catalogue_P10_linear=r['catalogue_P10_linear'],population_P10_inverse_cdf=r['population_P10_inverse_cdf'],
                expected_sample_P10_linear=e.expected_sample_P10_linear,expected_sample_P10_inverse_cdf=e.expected_sample_P10_inverse_cdf,
                **info,new_fusion_count=0,new_order_generation_in_this_note=0))
    pd.DataFrame(summary).to_csv(out/'ACTUAL_REGISTERED_P10_BOUNDARY_COMPARISON.csv',index=False)
    function_source=inspect.getsource(finite_quantile_expectation)
    header='"""Verbatim existing function from analysis_precision26/exact_anchor_and_display.py.\nNo RNG, simulation or fusion calls.\n"""\nimport numpy as np\nfrom scipy.stats import binom\n\n'
    atomic_bytes(out/'finite_quantile_expectation.py',(header+function_source).encode())
    receipt=dict(source_commit='b9bcec809fbaec8ab055931a1abb7baa5db44dac',complete_Manual_nondeferred_catalogue_cells=len(valid),
        integer_multiple_10_validQ_cells=len(scan),integer_multiple_10_images=scan.image.nunique(),positive_gap_boundary_cells=int((scan.exact_boundary&scan.gap.gt(0)).sum()),
        selected_cases=selected[['pool_id','image','k','gap']].to_dict('records'),selection_rule='largest two strictly positive gaps at exact conditional CDF=0.1; no path outcome selection',
        selected_finite_rows=len(exact_raw),actual_registered_paths=len(bindings),new_orders_in_note=0,new_fusions_in_note=0,simulation_replicates=0,
        analytic_rows=len(expected),observed_cohort_rows=len(summary),function_source_sha256=hashlib.sha256(function_source.encode()).hexdigest(),
        source_files={str(f.relative_to(study)):sha(f) for f in [statfile,rawfile,study/'analysis_precision26/exact_anchor_and_display.py',*sources]})
    for filename,count in [('BOUNDARY_SEARCH.csv',len(scan)),('SELECTED_EXACT_TEAM_VALUES.csv.gz',len(exact_raw)),('P10_ANALYTIC_EXPECTATION.csv',len(expected)),
        ('REGISTERED_K1_PATH_BINDINGS.csv.gz',len(bindings)),('ACTUAL_REGISTERED_P10_BOUNDARY_COMPARISON.csv',len(summary))]:
        a=pd.read_csv(out/filename);assert len(a)==count
    atomic_bytes(out/'RECEIPT.json',json.dumps(receipt,ensure_ascii=False,indent=2).encode());print(json.dumps({k:v for k,v in receipt.items() if k!='source_files'},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--study',type=Path,required=True);p.add_argument('--out',type=Path)
    a=p.parse_args();root=a.study.resolve();main(root,a.out or root/'analysis_geometry26/quantile_boundary_note')
