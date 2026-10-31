"""Membership-only delta for the 584/533 doorway experiment; frozen data unchanged."""
import os
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
import argparse
import gzip
import io
import itertools
import json
import math
import zipfile
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.run_doorway_delta_20261031 import run_image, plain
from tools.thesis_main.analysis.audit_doorway_delivery_20261031 import paired_metric

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'research/data/doorway_review_20261030'
AUDIT = BASE / 'pro_delivery_independent_audit_20261031'
OUT = BASE / 'screen533_results_20261031'
PREFIX = 'HOHONET_doorway_v21_20261031/'
SCREENED = 533
METRICS = ['B8L2', 'D10', 'IoU3D100', 'complete_evaluable']

def read(path):
    return json.loads(path.read_text(encoding='utf8'))

def write(name, value):
    (OUT / name).write_text(json.dumps(plain(value), ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf8')

def table(z, name, **kwargs):
    return pd.read_csv(io.BytesIO(z.read(PREFIX+name)), compression='gzip', **kwargs)

def team_key(image, members):
    return image, tuple(sorted(members))

def changed_pools(old, ledger):
    byid = {r['object_id']: r for r in ledger}
    result, changes = [], []
    for pool in old:
        p = dict(pool)
        if p['family'] in ['overall_before', 'overall_after']:
            p['target'] = '全部'
        if p['family'] != 'overall_before':
            members = [x for x in p['records'] if byid[x]['eligibility'] == '保留']
            if SCREENED == 439 and p['family'] in ['space1','space2','whole_compatible']:
                members = sorted(x for x,r in byid.items() if r['image']==p['image'] and r['eligibility']=='保留' and r['scope']==p['target'])
                members = [x for x in p['records'] if x in members]+[x for x in members if x not in p['records']]
            # Both review batches only rejected records or retained the old scope.
            if p['family'] in ['space1','space2','whole_compatible']:
                assert all(byid[x]['scope'] == p['target'] for x in members)
            p.update(records=members, workers=[byid[x]['worker'] for x in members], n=len(members))
        if p['records'] != pool['records']:
            changes.append(dict(pool_id=p['pool_id'], image=p['image'], family=p['family'], before_n=pool['n'], after_n=p['n'], removed=sorted(set(pool['records'])-set(p['records'])),added=sorted(set(p['records'])-set(pool['records']))))
        for stale in ['human_n','visual_n','automatic_n','raw_geometry_present_n','before_after_identical']:
            p.pop(stale,None)
        p['n_inherited_quality_hold']=sum(not byid[x]['inherited_quality_eligible'] for x in p['records'])
        p['screening_version']='frozen_before_584' if p['family']=='overall_before' else ('user_final_after_439' if SCREENED==439 else 'user52_after_533')
        result.append(p)
    return result, changes

def load_cache():
    """Exact image/member identities; all caches share frozen input and references."""
    with zipfile.ZipFile('C:/Users/ASUS/Downloads/DOORWAY_04_PHYSICAL_GEOMETRY.zip') as z:
        index = table(z,'stage04_computation/PHYSICAL_ENDPOINT_INDEX.csv.gz')
        scores = table(z,'stage04_computation/ENDPOINT_TARGET_SCORES.csv.gz',usecols=['physical_team_key','target']+METRICS)
    identity = {r.physical_team_key:team_key(r.image,r.member_object_ids.split('|')) for r in index.itertuples()}
    cache = defaultdict(dict)
    for r in scores.to_dict('records'):
        key = identity[r['physical_team_key']]
        cache[key][r['target']] = {**{m:r[m] for m in METRICS}, 'endpoint_source':'Pro_stage04', 'physical_team_key':r['physical_team_key']}
    for folder in dict.fromkeys([AUDIT/'computed_delta', AUDIT/'computed_exclude13_selected', BASE/'screen533_results_20261031/native', OUT/'native']):
        if not folder.exists():
            continue
        for path in sorted(folder.glob('*.jsonl')):
            with path.open(encoding='utf8') as stream:
                for lineno,line in enumerate(stream,1):
                    r=json.loads(line);key=team_key(r['image'],r['members'])
                    for target,s in r['scores'].items():
                        value={m:s[m] for m in METRICS}
                        if target in cache[key]:
                            old=cache[key][target]
                            for m in METRICS:
                                a,b=old[m],value[m]
                                assert (pd.isna(a) and pd.isna(b)) or np.isclose(float(a),float(b),atol=1e-7), (key,target,m,a,b)
                        cache[key][target]={**value,'endpoint_source':str(path.relative_to(BASE)), 'physical_team_key':str(path.relative_to(BASE))+':'+str(lineno)}
    if SCREENED == 439:
        supplement=OUT/'ADDED_SINGLE_TARGET_SCORES.json'
        if supplement.exists():
            rows=read(supplement)
        else:
            from tools.thesis_main.analysis.run_doorway_delta_20261031 import scoring_engine, dual_scores
            with zipfile.ZipFile('C:/Users/ASUS/Downloads/DOORWAY_04_PHYSICAL_GEOMETRY.zip') as z:
                frozen=json.loads(gzip.decompress(z.read(PREFIX+'stage04_computation/design/FROZEN_RECORDS.json.gz')))
                refs={(r['image'],r['target']):r for r in json.loads(z.read(PREFIX+'stage04_computation/recovered_reference_scores/FINAL_REFERENCES.json'))}
            needed={(p['image'],oid,p['target']) for p in read(OUT/'POOLS.json') for oid in p['records'] if p['target'] not in cache.get(team_key(p['image'],[oid]),{})}
            rows=[]
            engine_dir=ROOT/'research/statistics/b8l2_shared_v6_20261016/inputs'
            with scoring_engine(engine_dir/'measurement_engine.zip',engine_dir/'working_models.py') as (engine,models):
                for im,oid,target in sorted(needed):
                    measurement=engine.measure(engine.geometry(frozen[oid]['points']),engine.geometry(refs[im,target]['points_1024x512']))
                    complete=measurement['status']=='complete'
                    scores=dual_scores(measurement['metrics'],models) if complete else dict(B8L2=None,D10=None,IoU3D100=None)
                    if complete:scores['IoU3D100']=100*measurement['metrics']['iou_3d_corner_mean']
                    rows.append(dict(image=im,object_id=oid,target=target,complete_evaluable=complete,**scores))
            write('ADDED_SINGLE_TARGET_SCORES.json',rows)
        for r in rows:
            cache[team_key(r['image'],[r['object_id']])][r['target']]={**{m:r[m] for m in METRICS},'endpoint_source':supplement.name,'physical_team_key':r['image']+'::'+r['object_id']}
    return cache

def design():
    OUT.mkdir(exist_ok=True);(OUT/'native').mkdir(exist_ok=True)
    ledger=read(BASE/('expanded_visual_review_20261031/FINAL_SCREENING_LEDGER.json' if SCREENED==439 else 'scope_recheck40_20261031/EFFECTIVE_SCREENING_LEDGER.json'))['records']
    oldpools=read(AUDIT/'CORRECTED_PRIMARY_POOLS.json')
    pools,changes=changed_pools(oldpools,ledger)
    assert sum(p['n'] for p in pools if p['family']=='overall_before')==584
    assert sum(p['n'] for p in pools if p['family']=='overall_after')==SCREENED
    write('POOLS.json',pools);write('CHANGED_POOLS.json',changes)
    with zipfile.ZipFile('C:/Users/ASUS/Downloads/DOORWAY_02_RESULTS_CURVES_CASES.zip') as z:
        orders=table(z,'stage04_computation/design/BASE_256_ORDERS.csv.gz')
    orders.to_csv(OUT/'BASE_256_ORDERS.csv.gz',index=False)
    requests={};links=[];exact=[];sensitivity=[]
    changed={r['pool_id'] for r in changes}
    held={r['object_id'] for r in read(AUDIT/'INDEPENDENT_HOLDS_13.json')}
    def request(p, team):
        key=team_key(p['image'],team)
        r=requests.setdefault(key,dict(image=p['image'],members=list(key[1]),k=len(team),targets=[]))
        if p['target'] not in r['targets']:r['targets'].append(p['target'])
        return '|'.join(key[1])
    for p in pools:
        members=set(p['records']);n=p['n']
        if p['pool_id'] in changed:
            for row in orders[orders.image==p['image']].itertuples():
                seq=[x for x in row.base_member_object_ids.split('|') if x in members]
                assert len(seq)==n and len(set(seq))==n
                for k in range(1,n+1):
                    team=seq[:k];ids=request(p,team)
                    links.append(dict(pool_id=p['pool_id'],image=p['image'],building=p['building'],family=p['family'],target=p['target'],pool_n=n,k=k,base_replicate=row.base_replicate,origin_stratum=row.origin_stratum,member_object_ids=ids))
            for k in (range(1,n+1) if n<=10 else sorted({1,n-1,n})):
                for team in itertools.combinations(sorted(members),k):
                    exact.append(dict(pool_id=p['pool_id'],image=p['image'],family=p['family'],target=p['target'],pool_n=n,k=k,member_object_ids=request(p,team),finite_population_teams=math.comb(n,k)))
        # Retain the existing k=6/10 historical-qualification sensitivity identity.
        if p['family'] in ['overall_before','overall_after','whole_compatible']:
            for row in orders[orders.image==p['image']].itertuples():
                seq=[x for x in row.base_member_object_ids.split('|') if x in members-held]
                for k in [6,10]:
                    if len(seq)>=k:
                        sensitivity.append(dict(image=p['image'],building=p['building'],family=p['family'],target=p['target'],k=k,base_replicate=row.base_replicate,member_object_ids=request(p,seq[:k])))
    cache=load_cache();missing=[]
    for key,r in requests.items():
        targets=[t for t in r['targets'] if t not in cache.get(key,{})]
        if targets:
            assert r['k']>=2, ('missing single-person endpoint',r)
            missing.append(dict(r,targets=targets))
    write('MISSING_REQUESTS.json',missing)
    pd.DataFrame(links).to_csv(OUT/'CHANGED_PREFIX_DESIGN.csv.gz',index=False)
    pd.DataFrame(exact).to_csv(OUT/'CHANGED_EXACT_DESIGN.csv.gz',index=False)
    pd.DataFrame(sensitivity).to_csv(OUT/'EXCLUDE13_DESIGN.csv.gz',index=False)
    plan=dict(base=584,screened=SCREENED,excluded=584-SCREENED,additional_excluded=553-SCREENED,changed_pools=changes,changed_images=len({r['image'] for r in changes}),unique_teams_requested=len(requests),cached_teams=len(requests)-len(missing),missing_native_teams=len(missing),missing_by_image=dict(pd.Series([r['image'] for r in missing]).value_counts()),changed_prefixes=len(links),changed_exact=len(exact),sensitivity_paths=len(sensitivity),geometry_changed=False,reference_changed=False,base_orders_changed=False)
    write('PLAN.json',plan);print(json.dumps(plain(plan),ensure_ascii=False),flush=True)

def run():
    requests=read(OUT/'MISSING_REQUESTS.json');jobs=defaultdict(list)
    for r in requests:jobs[r['image']].append(r)
    receipts=[]
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures=[executor.submit(run_image,im,rows,OUT/'native') for im,rows in jobs.items()]
        for f in as_completed(futures):
            r=f.result();receipts.append(r);print(r,flush=True)
    assert sum(r['new']+r['already_saved'] for r in receipts)==len(requests)
    write('COMPUTATION_RECEIPT.json',receipts)

def main():
    global OUT, SCREENED
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['design','run','report']);parser.add_argument('--screen439',action='store_true');args=parser.parse_args()
    if args.screen439:
        SCREENED=439;OUT=BASE/'screen439_results_20261031'
    {'design':design,'run':run,'report':report}[args.phase]()

def report():
    assert (OUT/'COMPUTATION_RECEIPT.json').exists()
    cache=load_cache();pools=read(OUT/'POOLS.json');changed={r['pool_id'] for r in read(OUT/'CHANGED_POOLS.json')}
    with zipfile.ZipFile('C:/Users/ASUS/Downloads/DOORWAY_04_PHYSICAL_GEOMETRY.zip') as z:
        oldscores=table(z,'stage04_computation/ENDPOINT_TARGET_SCORES.csv.gz',usecols=['score_key','physical_team_key']+METRICS)
        index=table(z,'stage04_computation/PHYSICAL_ENDPOINT_INDEX.csv.gz',usecols=['physical_team_key','member_object_ids'])
    oldscores=pd.concat([oldscores,pd.read_csv(AUDIT/'computed_delta/NEW_TARGET_SCORES.csv.gz')[['score_key','physical_team_key']+METRICS]],ignore_index=True)
    index=pd.concat([index,pd.read_csv(AUDIT/'computed_delta/NEW_PHYSICAL_INDEX.csv.gz')[['physical_team_key','member_object_ids']]],ignore_index=True)
    assert not oldscores.score_key.duplicated().any()
    oldlinks=pd.read_csv(AUDIT/'computed_delta/CORRECTED_PREFIX_LINKS.csv.gz')
    old=oldlinks.merge(oldscores,on=['score_key','physical_team_key'],how='left',validate='many_to_one',indicator=True)
    assert old['_merge'].eq('both').all();old=old.drop(columns='_merge')
    old=old.merge(index,on='physical_team_key',how='left',validate='many_to_one');assert old.member_object_ids.notna().all()
    def values(filename):
        frame=pd.read_csv(OUT/filename);scored=[]
        for r in frame.to_dict('records'):
            score=cache[team_key(r['image'],r['member_object_ids'].split('|'))][r['target']]
            scored.append(dict(r,**score))
        result=pd.DataFrame(scored)
        assert result.complete_evaluable.notna().all()
        result['complete_evaluable']=result.complete_evaluable.astype(bool)
        for m in METRICS[:-1]:
            result[m]=pd.to_numeric(result[m])
            # k=1 retains the original answer's diagnostic score, not fusion eligibility.
            assert result.loc[(result.k>=3)&~result.complete_evaluable,m].isna().all()
        return result
    new=values('CHANGED_PREFIX_DESIGN.csv.gz')
    columns=['pool_id','image','building','family','target','pool_n','k','base_replicate','origin_stratum','member_object_ids','physical_team_key']+METRICS
    current=pd.concat([old.loc[~old.pool_id.isin(changed),columns],new[columns]],ignore_index=True)
    assert current.groupby(['pool_id','k']).size().eq(256).all()
    assert not current.duplicated(['pool_id','base_replicate','k']).any()
    assert current[current.family=='overall_before'][columns].reset_index(drop=True).equals(old[old.family=='overall_before'][columns].reset_index(drop=True))
    current.to_csv(OUT/'PAIRED_PATH_VALUES.csv.gz',index=False)
    def stats(frame,exact=False):
        rows=[]
        grouping=['pool_id','image','family','pool_n','k']
        for key,g in frame.groupby(grouping):
            common=dict(zip(grouping,key));common.update(attempts=len(g),unique_teams=g.physical_team_key.nunique(),complete_rate=float(g.complete_evaluable.mean()),two_person_supplement=int(key[-1])==2)
            if exact:assert len(g)==g.member_object_ids.nunique()==math.comb(int(key[-2]),int(key[-1]))
            for metric in METRICS[:-1]:
                v=g[metric].dropna();rows.append(dict(common,metric=metric,valid=len(v),mean=v.mean(),sd=v.std(ddof=0 if exact else 1),p10=v.quantile(.1) if len(v) else np.nan))
        return pd.DataFrame(rows)
    oldstats=pd.read_csv(AUDIT/'computed_delta/CORRECTED_NATURAL_CURVES.csv')
    summary=pd.concat([oldstats[~oldstats.pool_id.isin(changed)],stats(new)],ignore_index=True)
    summary['building']=summary.image.str.split('-').str[0]
    summary.to_csv(OUT/'NATURAL_CURVES.csv',index=False)
    newexact=values('CHANGED_EXACT_DESIGN.csv.gz');newexact.to_csv(OUT/'CHANGED_EXACT_VALUES.csv.gz',index=False)
    exactstats=stats(newexact,True)
    previous_exact=pd.read_csv(AUDIT/'computed_delta/CORRECTED_EXACT_MARGINALS.csv')
    pd.concat([previous_exact[~previous_exact.pool_id.isin(changed)],exactstats],ignore_index=True).to_csv(OUT/'EXACT_MARGINALS.csv',index=False)
    oldexact=pd.read_csv(AUDIT/'computed_delta/CORRECTED_EXACT_LINKS.csv.gz')
    newexact['score_key']=newexact.physical_team_key+'::'+newexact.target
    pd.concat([oldexact[~oldexact.pool_id.isin(changed)],newexact],ignore_index=True).to_csv(OUT/'EXACT_LINKS.csv.gz',index=False)
    def paired(a,b):
        p=a.merge(b,on=['image','base_replicate'],suffixes=('_a','_b'),validate='one_to_one')
        return {m:paired_metric(p[m+'_a'],p[m+'_b'],p.image,set()) for m in METRICS}
    def comparisons(frame):
        return {name:paired(frame[(frame.family==fa)&(frame.k==ka)],frame[(frame.family==fb)&(frame.k==kb)])
                for name,fa,fb,ka,kb in [('screening_k10','overall_before','overall_after',10,10),('whole_compatible_k10','overall_after','whole_compatible',10,10),('screened_6_to_10','overall_after','overall_after',6,10)]}
    headline=comparisons(current)
    headline['additional_screening_k10']=paired(old[(old.family=='overall_after')&(old.k==10)],current[(current.family=='overall_after')&(current.k==10)])
    write('HEADLINES.json',headline)
    sensitivity=values('EXCLUDE13_DESIGN.csv.gz');sensitivity.to_csv(OUT/'EXCLUDE13_PATH_VALUES.csv.gz',index=False)
    sens=comparisons(sensitivity)
    for name,metrics in sens.items():
        for metric,result in metrics.items():
            supported=set(result['per_image']);baseline=headline[name][metric]['per_image']
            result['baseline_same_image_panel_mean']=np.mean([baseline[im] for im in supported])
    write('EXCLUDE13_HEADLINES.json',sens)
    paired_rows=[]
    for k in sorted(current.k.unique()):
        if k<3:continue
        for name,a,b in [('screening',current[current.family=='overall_before'],current[current.family=='overall_after']),('additional_screening',old[old.family=='overall_after'],current[current.family=='overall_after'])]:
            result=paired(a[a.k==k],b[b.k==k])
            for m,v in result.items():paired_rows.append(dict(comparison=name,k=k,metric=m,**{key:value for key,value in v.items() if key!='per_image'}))
    pd.DataFrame(paired_rows).to_csv(OUT/'PAIRED_CURVE_CHANGES.csv',index=False)
    paired_bands(current,old)
    from tools.thesis_main.analysis import report_doorway_delta_20261031 as previous_report
    previous_report.BASE=OUT;previous_report.OUT=OUT
    previous_report.compatibility_bands(current,pd.read_csv(OUT/'BASE_256_ORDERS.csv.gz'))
    distribution=[]
    for label,frame in [('before584',current[current.family=='overall_before']),('previous_after553',old[old.family=='overall_after']),(f'after{SCREENED}',current[current.family=='overall_after'])]:
        for im,g in frame[frame.k==10].groupby('image'):
            v=g.B8L2.dropna();distribution.append(dict(version=label,image=im,pool_n=int(g.pool_n.iloc[0]),attempts=len(g),valid=len(v),mean=v.mean(),sd=v.std(ddof=1),p10=v.quantile(.1),complete_rate=g.complete_evaluable.mean()))
    pd.DataFrame(distribution).to_csv(OUT/'K10_DISTRIBUTIONS.csv',index=False)
    figures(summary)
    # Individual scores are unchanged; only membership of the reported side groups changes.
    with zipfile.ZipFile('C:/Users/ASUS/Downloads/DOORWAY_02_RESULTS_CURVES_CASES.zip') as z:
        individuals=pd.read_csv(io.BytesIO(z.read(PREFIX+'stage04_computation/INDIVIDUAL_TARGET_SCORES.csv')))
    if SCREENED == 439:
        individuals=pd.concat([individuals,pd.DataFrame(read(OUT/'ADDED_SINGLE_TARGET_SCORES.json'))],ignore_index=True)
    raw_answers=[]
    for family in ['overall_before','overall_after']:
        ids={oid for p in pools if p['family']==family for oid in p['records']}
        selected=individuals[individuals.object_id.isin(ids)&individuals.target.eq('全部')]
        assert len(selected)==len(ids) and not selected.object_id.duplicated().any()
        for im,g in selected.groupby('image'):
            for metric in METRICS[:-1]:
                raw_answers.append(dict(version=family,image=im,metric=metric,records=len(g),valid=g[metric].notna().sum(),mean=g[metric].mean()))
    pd.DataFrame(raw_answers).to_csv(OUT/'RAW_ANSWER_COMMON_REFERENCE.csv',index=False)
    raw=[]
    for target in ['空间1','空间2']:
        ids={oid for p in pools if p['target']==target for oid in p['records']}
        a=individuals[(individuals.object_id.isin(ids))&(individuals.target=='全部')];b=individuals[(individuals.object_id.isin(ids))&(individuals.target==target)]
        joined=a.merge(b,on='object_id',suffixes=('_a','_b'),validate='one_to_one');assert len(joined)==len(ids)
        for m in METRICS[:-1]:
            delta=joined[m+'_b']-joined[m+'_a'];g=delta.groupby(joined.image_a).mean().dropna()
            raw.append(dict(target=target,metric=m,records=len(ids),paired_finite=delta.notna().sum(),images=len(g),mean=g.mean(),positive=(g>1e-9).sum(),negative=(g< -1e-9).sum()))
    pd.DataFrame(raw).to_csv(OUT/'INDIVIDUAL_TARGET_COMPARISON.csv',index=False)
    verification=dict(status='complete',new_native_teams=sum(r['new']+r['already_saved'] for r in read(OUT/'COMPUTATION_RECEIPT.json')),prefix_rows=len(current),curve_rows=len(summary),exact_changed_rows=len(newexact),unchanged_pools=len(pools)-len(changed),base_version_584_unchanged=True,all_prefix_groups_256=True,missing_scores=0,geometry_reference_and_orders_unchanged=True,sensitivity='historical 13 holds; k6/k10 only')
    write('CHECKS.json',verification)
    print(json.dumps(plain(headline),ensure_ascii=False),flush=True)

def paired_bands(current,old):
    """Whole-path resampling preserves repeated teams and origin strata."""
    orders=pd.read_csv(OUT/'BASE_256_ORDERS.csv.gz');images=sorted(orders.image.unique());ks=list(range(3,15 if SCREENED==439 else 14));B=2000
    rng=np.random.default_rng(20261031);weights={}
    for im in images:
        w=np.zeros((B,256))
        for _,g in orders[orders.image==im].groupby('origin_stratum'):
            ids=g.base_replicate.to_numpy();w[:,ids]=rng.multinomial(len(ids),np.ones(len(ids))/len(ids),size=B)
        weights[im]=w
    buildings=[im.split('-')[0] for im in images];unique=sorted(set(buildings));clusters=rng.multinomial(len(unique),np.ones(len(unique))/len(unique),size=B)
    iw=np.array([clusters[:,unique.index(building)] for building in buildings]).T
    rows=[]
    comparisons=[('screening',current[current.family=='overall_before'],current[current.family=='overall_after']),('additional_screening',old[old.family=='overall_after'],current[current.family=='overall_after']),('compatibility',current[current.family=='overall_after'],current[current.family=='whole_compatible'])]
    for name,a,b in comparisons:
        for metric in METRICS:
            means=[];draws=[]
            for im in images:
                arrays=[f[f.image==im].pivot(index='base_replicate',columns='k',values=metric).reindex(index=range(256),columns=ks).to_numpy(dtype=float) for f in [a,b]]
                delta=arrays[1]-arrays[0];valid=np.isfinite(delta);counts=valid.sum(axis=0)
                means.append(np.divide(np.nansum(delta,axis=0),counts,out=np.full(len(ks),np.nan),where=counts>0))
                den=weights[im]@valid.astype(float);num=weights[im]@np.nan_to_num(delta)
                draws.append(np.divide(num,den,out=np.full_like(num,np.nan),where=den>0))
            means=np.array(means);point=np.nanmean(means,axis=0);pathdraw=np.nanmean(draws,axis=0)
            den=iw@np.isfinite(means).astype(float);cluster=np.divide(iw@np.nan_to_num(means),den,out=np.full_like(den,np.nan),where=den>0)
            for kind,boot in [('path_stratified',pathdraw),('building_cluster',cluster)]:
                low,high=np.nanquantile(boot,[.025,.975],axis=0);se=np.nanstd(boot,axis=0,ddof=1)
                z=np.divide(np.abs(boot-point),se,out=np.zeros_like(boot),where=se>0);critical=np.nanquantile(np.nanmax(z,axis=1),.95)
                for j,k in enumerate(ks):rows.append(dict(comparison=name,metric=metric,k=k,delta=point[j],pointwise_low=low[j],pointwise_high=high[j],simultaneous_low=point[j]-critical*se[j],simultaneous_high=point[j]+critical*se[j],bootstrap=kind,replicates=B,seed=20261031,valid_images=int(np.isfinite(means[:,j]).sum()),buildings=len(unique)))
    pd.DataFrame(rows).to_csv(OUT/'PAIRED_CURVE_BANDS.csv',index=False)

def figures(summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.ticker import MaxNLocator
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']
    plt.rcParams['axes.unicode_minus']=False
    figures=OUT/'figures';figures.mkdir(exist_ok=True)
    html=[f'<!doctype html><meta charset="utf-8"><title>门洞双版本584/{SCREENED}</title><style>body{{font:18px sans-serif;margin:24px}}img{{width:100%;max-width:1300px}}p{{line-height:1.6}}</style><h1>门洞：筛前584份／筛后{SCREENED}份</h1><p>固定原图、参考、256条人员顺序；仅成员筛除改变。质量为形成完整可评输出条件下的分数；完整共识可评率包含失败尝试。2人仅补充，图中从3人起。各图人数池大小见图例，超过容量不外推。</p><p><a href="RESULTS_ZH.md">结果说明</a> · <a href="CURVES.pdf">完整曲线册</a> · <a href="NATURAL_CURVES.csv">逐图曲线表</a></p>']
    with PdfPages(OUT/'CURVES.pdf') as pdf:
        for im in sorted(summary.image.unique()):
            g=summary[(summary.image==im)&(summary.metric=='B8L2')&(summary.k>=3)]
            fig,axs=plt.subplots(2,2,figsize=(13,8))
            for family,color,label in [('overall_before','#777777','筛前'),('overall_after','#0079b8','筛后')]:
                h=g[g.family==family].sort_values('k')
                for ax,y in zip(axs[0],['mean','complete_rate']):ax.plot(h.k,h[y]*(100 if y=='complete_rate' else 1),color=color,marker='.',label=f'{label} n={int(h.pool_n.iloc[0])}')
            for family,color,label in [('space1','#00a5ad','空间1'),('space2','#ed8a22','空间2'),('whole_compatible','#6b55b5','全部兼容')]:
                h=g[g.family==family].sort_values('k')
                if h.empty:continue
                for ax,y in zip(axs[1],['mean','complete_rate']):ax.plot(h.k,h[y]*(100 if y=='complete_rate' else 1),color=color,marker='.',label=f'{label} n={int(h.pool_n.iloc[0])}')
            for row in axs:
                for ax,ylabel in zip(row,['条件质量 B8L2','完整共识可评率 (%)']):ax.set_xlabel('团队人数');ax.set_ylabel(ylabel);ax.grid(alpha=.2);ax.legend(fontsize=8);ax.set_ylim(0,102);ax.xaxis.set_major_locator(MaxNLocator(integer=True))
            fig.suptitle(im+'：双版本与筛后空间兼容池'+('\n筛后仅14人；k>14无支持，满员只有1种团队，近满员波动受有限池影响' if im=='B6ByNegPMKs-43' and SCREENED==439 else ''));fig.tight_layout();pdf.savefig(fig);fig.savefig(figures/(im+'.png'),dpi=120);plt.close(fig)
            html.append(f'<h2>{im}</h2><img loading="lazy" src="figures/{im}.png" alt="{im}双版本与空间兼容曲线">')
    (OUT/'index.html').write_text('\n'.join(html),encoding='utf8')

if __name__=='__main__':
    main()
