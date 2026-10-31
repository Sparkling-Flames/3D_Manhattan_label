"""Join corrected native endpoints to real paths and deliver revised curves."""
import gzip,io,json,zipfile,itertools,math
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from tools.thesis_main.analysis.audit_doorway_delivery_20261031 import paired_metric
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'research/data/doorway_review_20261030/pro_delivery_independent_audit_20261031'
OUT=BASE/'computed_delta'
P='HOHONET_doorway_v21_20261031/'

def compatibility_bands(merged,orders):
    images=sorted(orders.image.unique());ks=list(range(3,14));B=2000
    rng=np.random.default_rng(20261031);pathweights={}
    for im in images:
        o=orders[orders.image==im].sort_values('base_replicate');assert list(o.base_replicate)==list(range(256))
        w=np.zeros((B,256))
        for _,g in o.groupby('origin_stratum'):
            ids=g.base_replicate.to_numpy();w[:,ids]=rng.multinomial(len(ids),np.ones(len(ids))/len(ids),size=B)
        pathweights[im]=w
    buildings={im:merged[merged.image==im].building.iloc[0] for im in images}
    unique=sorted(set(buildings.values()));cluster=rng.multinomial(len(unique),np.ones(len(unique))/len(unique),size=B)
    imageweights=np.array([cluster[:,unique.index(buildings[im])] for im in images]).T
    rows=[]
    for metric in ['B8L2','D10','IoU3D100','complete_evaluable']:
        means=[];draws=[]
        for im in images:
            arrays=[]
            for family in ['overall_after','whole_compatible']:
                g=merged[(merged.image==im)&(merged.family==family)&merged.k.isin(ks)]
                arrays.append(g.pivot(index='base_replicate',columns='k',values=metric).reindex(index=range(256),columns=ks).to_numpy(dtype=float))
            delta=arrays[1]-arrays[0];valid=np.isfinite(delta);means.append(np.nanmean(delta,axis=0))
            num=pathweights[im]@np.nan_to_num(delta);den=pathweights[im]@valid.astype(float)
            draws.append(np.divide(num,den,out=np.full_like(num,np.nan),where=den>0))
        means=np.array(means);point=np.nanmean(means,axis=0);pathdraw=np.nanmean(draws,axis=0)
        den=imageweights@np.isfinite(means).astype(float)
        buildingdraw=np.divide(imageweights@np.nan_to_num(means),den,out=np.full_like(den,np.nan),where=den>0)
        for kind,bootstrap in [('path_stratified',pathdraw),('building_cluster',buildingdraw)]:
            low,high=np.nanquantile(bootstrap,[.025,.975],axis=0);se=np.nanstd(bootstrap,axis=0,ddof=1)
            standard=np.divide(np.abs(bootstrap-point),se,out=np.zeros_like(bootstrap),where=se>0)
            critical=float(np.nanquantile(np.nanmax(standard,axis=1),.95))
            for j,k in enumerate(ks):rows.append(dict(metric=metric,k=k,delta=point[j],pointwise_low=low[j],pointwise_high=high[j],simultaneous_low=point[j]-critical*se[j],simultaneous_high=point[j]+critical*se[j],bootstrap=kind,replicates=B,seed=20261031,capacity_images=len(set(merged[(merged.family=='overall_after')&(merged.k==k)].image)&set(merged[(merged.family=='whole_compatible')&(merged.k==k)].image)),valid_images=int(np.isfinite(means[:,j]).sum()),buildings=len(unique)))
    pd.DataFrame(rows).to_csv(OUT/'COMPATIBILITY_PAIRED_CURVE_BANDS.csv',index=False)
    poolrows=[]
    changed={r['pool_id'] for r in json.loads((BASE/'CHANGED_POOLS.json').read_text(encoding='utf8'))}
    for poolid,g in merged[merged.pool_id.isin(changed)&(merged.k>=3)].groupby('pool_id'):
        im=g.image.iloc[0];weights=pathweights[im]
        for metric in ['B8L2','D10','IoU3D100','complete_evaluable']:
            values=g.pivot(index='base_replicate',columns='k',values=metric).reindex(index=range(256))
            array=values.to_numpy(dtype=float);valid=np.isfinite(array)
            den=weights@valid.astype(float);num=weights@np.nan_to_num(array)
            boot=np.divide(num,den,out=np.full_like(num,np.nan),where=den>0)
            point=np.divide(np.nansum(array,axis=0),valid.sum(axis=0),out=np.full(array.shape[1],np.nan),where=valid.sum(axis=0)>0)
            estimable=valid.sum(axis=0)>0
            se=np.full(array.shape[1],np.nan);lo=se.copy();hi=se.copy()
            if estimable.any():
                se[estimable]=np.nanstd(boot[:,estimable],axis=0,ddof=1)
                lo[estimable],hi[estimable]=np.nanquantile(boot[:,estimable],[.025,.975],axis=0)
            scaled=np.divide(np.abs(boot-point),se,out=np.zeros_like(boot),where=se>0)
            critical=float(np.nanquantile(np.nanmax(scaled,axis=1),.95))
            for j,k in enumerate(values.columns):poolrows.append(dict(pool_id=poolid,image=im,k=k,metric=metric,mean=point[j],valid_paths=int(valid[:,j].sum()),pointwise_low=lo[j],pointwise_high=hi[j],simultaneous_low=point[j]-critical*se[j],simultaneous_high=point[j]+critical*se[j],replicates=B,seed=20261031,status='computed' if estimable[j] else 'metric_unavailable_no_valid_output',uncertainty='path_MC_only_single_image'))
    pd.DataFrame(poolrows).to_csv(OUT/'CHANGED_POOL_PATH_BANDS.csv',index=False)

def plot_saved_curves():
    """Render existing natural-path summaries only; never rerun fusion or bootstrap."""
    with zipfile.ZipFile('C:/Users/ASUS/Downloads/DOORWAY_02_RESULTS_CURVES_CASES.zip') as z:
        old=pd.read_csv(io.BytesIO(z.read(P+'stage05_results/POOL_K_METRICS.csv.gz')),compression='gzip')
    old=old[old.metric.eq('B8L2')&old.estimator.eq('natural256_MC')&~old.sensitivity].copy()
    current=pd.read_csv(OUT/'CORRECTED_NATURAL_CURVES.csv')
    current=current[current.metric.eq('B8L2')].copy()
    changed={r['pool_id'] for r in json.loads((BASE/'CHANGED_POOLS.json').read_text(encoding='utf8'))}
    pools=[p for p in json.loads((BASE/'CORRECTED_PRIMARY_POOLS.json').read_text(encoding='utf8')) if p['pool_id'] in changed]
    assert len(pools)==8
    rows=[]
    for version,data in [('Pro original',old),('Scope corrected',current)]:
        d=data[data.pool_id.isin(changed)][['pool_id','k','mean']].copy()
        assert not d.duplicated(['pool_id','k']).any()
        d['version']=version;rows.append(d)
    data=pd.concat(rows,ignore_index=True)
    data.to_csv(OUT/'CHANGED_POOL_CURVES_DATA.csv',index=False)
    fig,axs=plt.subplots(4,2,figsize=(14,16))
    families={'whole_compatible':'Whole-target compatible','space1':'Space 1','space2':'Space 2'}
    for ax,p in zip(axs.flat,pools):
        for version,color,style in [('Pro original','#666666','--'),('Scope corrected','#087f8c','-')]:
            g=data[data.pool_id.eq(p['pool_id'])&data.version.eq(version)&data.k.ne(2)].set_index('k')['mean']
            if len(g):g=g.reindex(range(1,int(g.index.max())+1))
            ax.plot(g.index,g.values,marker='o',linestyle=style,ms=3,color=color,label=version)
        ax.set_title(p['image']+' / '+families[p['family']]+' / corrected N='+str(p['n']),fontsize=10)
        ax.set_xlabel('Number of annotators (k)');ax.set_ylabel('Mean B8L2 among scoreable outputs (points)')
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        if data[data.pool_id.eq(p['pool_id'])&data.k.ne(2)].k.max()==1:ax.set_xlim(.5,1.5);ax.set_xticks([1])
        ax.set_ylim(0,100);ax.grid(alpha=.2);ax.legend(fontsize=8)
        if p['n']==0:ax.text(.5,.1,'Corrected support = 0; no curve',transform=ax.transAxes,ha='center',color='#a22')
    fig.suptitle('Consensus quality across team sizes before and after scope correction\nfor eight affected doorway pools using MV50',fontsize=15)
    fig.tight_layout(rect=(0,0,1,.955))
    for ext in ['png','pdf','svg']:fig.savefig(OUT/('CHANGED_POOL_CURVES.'+ext),dpi=300)
    plt.close(fig)


def main():
    assert (OUT/'COMPUTATION_RECEIPT.json').exists()
    z2=zipfile.ZipFile('C:/Users/ASUS/Downloads/DOORWAY_02_RESULTS_CURVES_CASES.zip')
    z4=zipfile.ZipFile('C:/Users/ASUS/Downloads/DOORWAY_04_PHYSICAL_GEOMETRY.zip')
    def table(z,n,**kw):return pd.read_csv(io.BytesIO(gzip.decompress(z.read(P+n))),**kw)
    oldlinks=table(z2,'stage04_computation/design/PREFIX_LINKS.csv.gz')
    orders=table(z2,'stage04_computation/design/BASE_256_ORDERS.csv.gz')
    fields=['score_key','physical_team_key','image','target','k','B8L2','D10','IoU3D100','complete_evaluable','iou_2d','S_bottom_deg','dir','Hmean','Hcenter']
    scores=table(z4,'stage04_computation/ENDPOINT_TARGET_SCORES.csv.gz',usecols=fields)
    requests=json.loads((BASE/'DELTA_TEAM_REQUESTS.json').read_text(encoding='utf8'))
    mapping={(r['image'],tuple(r['members'])):r['cached_physical_team_key'] for r in requests if r['cached_physical_team_key']}
    new_scores=[];manifest=[]
    for path in sorted(OUT.glob('*.jsonl')):
        for i,line in enumerate(path.read_text(encoding='utf8').splitlines()):
            r=json.loads(line);key='doorway_r1/'+r['image']+'/'+str(i);mapping[(r['image'],tuple(r['members']))]=key
            manifest.append(dict(physical_team_key=key,image=r['image'],k=r['k'],member_object_ids='|'.join(r['members']),endpoint_file=path.name,endpoint_line=i+1))
            for target,values in r['scores'].items():
                new_scores.append(dict(**{k:values.get(k) for k in fields if k not in ['score_key','physical_team_key','image','target','k']},score_key=key+'::'+target,physical_team_key=key,image=r['image'],target=target,k=r['k']))
    new_scores=pd.DataFrame(new_scores);assert not new_scores.score_key.duplicated().any()
    new_scores.to_csv(OUT/'NEW_TARGET_SCORES.csv.gz',index=False)
    pd.DataFrame(manifest).to_csv(OUT/'NEW_PHYSICAL_INDEX.csv.gz',index=False)
    scores=pd.concat([scores,new_scores],ignore_index=True)
    changed={p['pool_id'] for p in json.loads((BASE/'CHANGED_POOLS.json').read_text(encoding='utf8'))}
    pools=json.loads((BASE/'CORRECTED_PRIMARY_POOLS.json').read_text(encoding='utf8'))
    original_index=table(z4,'stage04_computation/PHYSICAL_ENDPOINT_INDEX.csv.gz')
    exact_lookup={(r.image,tuple(sorted(r.member_object_ids.split('|')))):r.physical_team_key for r in original_index.itertuples()}
    exact_lookup.update({(r['image'],tuple(sorted(r['member_object_ids'].split('|')))):r['physical_team_key'] for r in manifest})
    oldexact=table(z2,'stage04_computation/design/EXACT_LINKS.csv.gz');exactrows=[]
    for p in pools:
        if p['pool_id'] not in changed or p['n']==0:continue
        n=p['n']
        for k in (range(1,n+1) if n<=10 else sorted({1,n-1,n})):
            for team in itertools.combinations(sorted(p['records']),k):
                key=exact_lookup[(p['image'],team)]
                exactrows.append(dict(pool_id=p['pool_id'],image=p['image'],family=p['family'],target=p['target'],pool_n=n,k=k,physical_team_key=key,score_key=key+'::'+p['target'],finite_population_teams=math.comb(n,k),two_person_supplement=k==2,sensitivity=False))
    exact=pd.concat([oldexact[~oldexact.pool_id.isin(changed)&~oldexact.sensitivity],pd.DataFrame(exactrows)],ignore_index=True)
    exact.to_csv(OUT/'CORRECTED_EXACT_LINKS.csv.gz',index=False)
    exact_scored=exact.merge(scores.drop(columns=['image','target','k']),on=['score_key','physical_team_key'],validate='many_to_one')
    assert len(exact_scored)==len(exact)
    exact_stats=[]
    for (poolid,k),g in exact_scored.groupby(['pool_id','k']):
        assert g.physical_team_key.nunique()==len(g)==math.comb(int(g.pool_n.iloc[0]),int(k))
        for metric in ['B8L2','D10','IoU3D100']:
            v=g[metric].dropna();exact_stats.append(dict(pool_id=poolid,k=k,metric=metric,teams=len(g),valid=len(v),mean=v.mean(),sd=v.std(ddof=0),p10=v.quantile(.1) if len(v) else np.nan,complete_rate=g.complete_evaluable.mean()))
    pd.DataFrame(exact_stats).to_csv(OUT/'CORRECTED_EXACT_MARGINALS.csv',index=False)
    newlinks=[]
    for p in pools:
        if p['pool_id'] not in changed:continue
        template=oldlinks[oldlinks.pool_id==p['pool_id']].iloc[0].to_dict()
        for r in orders[orders.image==p['image']].itertuples():
            members=[x for x in r.base_member_object_ids.split('|') if x in set(p['records'])]
            for k in range(1,len(members)+1):
                key=mapping[(p['image'],tuple(sorted(members[:k])))];row=dict(template)
                row.update(base_replicate=r.base_replicate,path_id=p['pool_id']+'__r1__'+str(r.base_replicate),k=k,pool_n=len(members),physical_team_key=key,score_key=key+'::'+p['target'],origin_stratum=r.origin_stratum,main_pool_eligible=len(members)>=3,two_person_supplement=k==2,main_band_excluded=k==2)
                newlinks.append(row)
    links=pd.concat([oldlinks[~oldlinks.pool_id.isin(changed)&~oldlinks.sensitivity],pd.DataFrame(newlinks)],ignore_index=True)
    links.to_csv(OUT/'CORRECTED_PREFIX_LINKS.csv.gz',index=False)
    merged=links.merge(scores.drop(columns=['image','target','k']),on=['score_key','physical_team_key'],how='left',validate='many_to_one',indicator=True)
    assert (merged['_merge']=='both').all()
    assert len(newlinks)==30720
    metrics=['B8L2','D10','IoU3D100']
    summaries=[]
    for keys,g in merged.groupby(['pool_id','image','building','family','pool_n','k']):
        common=dict(zip(['pool_id','image','building','family','pool_n','k'],keys));common.update(attempts=len(g),unique_teams=g.physical_team_key.nunique(),complete_rate=float(g.complete_evaluable.mean()),two_person_supplement=keys[-1]==2)
        for metric in metrics:
            v=g[metric].dropna();summaries.append(dict(common,metric=metric,valid=len(v),mean=v.mean(),sd=v.std(ddof=1),p10=v.quantile(.1) if len(v) else np.nan))
    summary=pd.DataFrame(summaries);summary.to_csv(OUT/'CORRECTED_NATURAL_CURVES.csv',index=False)
    ledger=json.loads((BASE/'CORRECTED_RECORD_LEDGER.json').read_text(encoding='utf8'))
    individuals=pd.read_csv(io.BytesIO(z2.read(P+'stage04_computation/INDIVIDUAL_TARGET_SCORES.csv')))
    raw=[]
    for target in ['空间1','空间2']:
        ids={r['object_id'] for r in ledger if r['base_candidate'] and r['final_scope']==target}
        a=individuals[(individuals.object_id.isin(ids))&(individuals.target=='全部')]
        b=individuals[(individuals.object_id.isin(ids))&(individuals.target==target)]
        joined=a.merge(b,on='object_id',suffixes=('_a','_b'),validate='one_to_one');assert len(joined)==len(ids)
        for metric in ['B8L2','D10','IoU3D100']:
            d=joined[metric+'_b']-joined[metric+'_a'];g=d.groupby(joined.image_a).mean().dropna()
            raw.append(dict(target=target,metric=metric,records=len(ids),paired_finite=int(d.notna().sum()),images=len(g),mean=float(g.mean()),positive=int((g>1e-9).sum()),negative=int((g< -1e-9).sum())))
    pd.DataFrame(raw).to_csv(OUT/'CORRECTED_INDIVIDUAL_TARGET_COMPARISON.csv',index=False)
    def pair(fa,fb,ka,kb):
        a=merged[(merged.family==fa)&(merged.k==ka)];b=merged[(merged.family==fb)&(merged.k==kb)]
        p=a.merge(b,on=['image','base_replicate'],suffixes=('_a','_b'),validate='one_to_one')
        return {m:paired_metric(p[m+'_a'],p[m+'_b'],p.image,set()) for m in metrics+['complete_evaluable']}
    headlines=dict(screening_k10=pair('overall_before','overall_after',10,10),whole_compatible_k10=pair('overall_after','whole_compatible',10,10),screened_6_to_10=pair('overall_after','overall_after',6,10))
    (OUT/'CORRECTED_HEADLINES.json').write_text(json.dumps(headlines,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
    compatibility_bands(merged,orders)
    plot_saved_curves()
    print(json.dumps({k:{m:v[m]['mean'] for m in metrics+['complete_evaluable']} for k,v in headlines.items()},ensure_ascii=False))
    print('new endpoints',len(manifest),'new scores',len(new_scores),'prefixes',len(links),'curve metric rows',len(summary))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--figures-only',action='store_true');args=parser.parse_args()
    plot_saved_curves() if args.figures_only else main()
