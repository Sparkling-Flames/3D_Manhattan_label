"""Same-real-person-composition comparison with 32 alternative common validation splits.
This is a sensitivity to which existing people are held out, not 32 independent replications.
Exact averages over all possible distinct-person teams, without simulating new annotations.
"""
import collections,hashlib,itertools,json,math
from pathlib import Path
import numpy as np,pandas as pd
from release import frame

def avg_team(cov,bins,held,label):
    def ratio(n,d):return n/d if d else np.nan
    if label=='ABCD':
        nteams=math.prod(len(bins[s]) for s in 'ABCD')
        u=np.mean([math.prod(float((~cov[h,bins[s]]).mean()) for s in 'ABCD') for h in held])
        w=np.mean([float((~cov[np.ix_(bins[a],bins[b])]).mean()) for a,b in itertools.combinations('ABCD',2)])
    else:
        a=bins['A'];n=len(a);nteams=math.comb(n,2)*len(bins['B'])*len(bins['C'])
        u=[]
        for h in held:
            bad=int((~cov[h,a]).sum());u.append((math.comb(bad,2)/math.comb(n,2))*float((~cov[h,bins['B']]).mean())*float((~cov[h,bins['C']]).mean()))
        u=np.mean(u);ia,ib=np.triu_indices(n,1)
        aa=(~cov[np.ix_(a,a)])[ia,ib].mean();ab=(~cov[np.ix_(a,bins['B'])]).mean();ac=(~cov[np.ix_(a,bins['C'])]).mean();bc=(~cov[np.ix_(bins['B'],bins['C'])]).mean();w=(aa+2*ab+2*ac+bc)/6
    return float(u),float(w),nteams

def run(root,out):
    cache=json.loads((out/'cache.json').read_text());p=pd.read_csv(out/'out_of_building_profiles.csv');rows=[]
    for key,g in cache.items():
        if key.split('|')[1]!='manual' or len(g['ids'])<12:continue
        z=p[p.target_building==g['building']].set_index('worker');ix=[i for i,w in enumerate(g['workers']) if w in z.index]
        if len(ix)<12:continue
        D=np.array(g['matrices']['split_cyclic'])
        for split in range(32):
            tag='validation20260920' if split==0 else 'validation_sensitivity20260920_'+str(split)
            rank=sorted(ix,key=lambda i:hashlib.sha256((g['ids'][i]+tag).encode()).hexdigest());held=rank[:4];pool=rank[4:];bins={s:[i for i in pool if z.loc[g['workers'][i],'label']==s] for s in 'ABCD'}
            if len(bins['A'])<2 or any(not bins[s] for s in 'BCD'):continue
            for cut in [6,9,12]:
                cov=np.round(D,8)<=cut
                A=avg_team(cov,bins,held,'ABCD');B=avg_team(cov,bins,held,'AABC')
                rows.append(dict(key=key,code=g['code'],building=g['building'],split=split,cut=cut,validation_ids=';'.join(g['ids'][i] for i in held),ABCD_teams=A[2],AABC_teams=B[2],ABCD_uncovered=A[0],AABC_uncovered=B[0],delta_uncovered=B[0]-A[0],delta_within=B[1]-A[1],pool_worker_bins=json.dumps({s:[g['workers'][i] for i in q] for s,q in bins.items()})))
    d=frame(out,'composition_validation_split_sensitivity.csv',rows)
    base=pd.read_csv(out/'composition_paired_contrasts.csv');test=d[d.split==0].merge(base,on=['key','cut'],validate='one_to_one')
    assert np.allclose(test.delta_uncovered,test.delta_uncovered_AABC_minus_ABCD,atol=1e-10)
    assert np.allclose(test.delta_within,test.delta_within_AABC_minus_ABCD,atol=1e-10)
    m=d.groupby(['key','code','building','cut']).agg(splits=('split','nunique'),mean_delta_uncovered=('delta_uncovered','mean'),mean_delta_within=('delta_within','mean'),min_delta_uncovered=('delta_uncovered','min'),max_delta_uncovered=('delta_uncovered','max')).reset_index();frame(out,'composition_validation_image_means.csv',m)
    rng=np.random.default_rng(20260920);rr=[]
    for cut,g in m.groupby('cut'):
        for field in ['mean_delta_uncovered','mean_delta_within']:
            v=g.groupby('building')[field].mean();b=rng.choice(v.values,(4000,len(v)),replace=True).mean(1)
            rr.append(dict(cut=cut,endpoint=field,images=len(g),buildings=len(v),minimum_splits=g.splits.min(),image_equal_mean=g[field].mean(),building_equal_mean=v.mean(),bootstrap_low=np.quantile(b,.025),bootstrap_high=np.quantile(b,.975),interpretation='repeated_role_splits_of_existing_people_not_independent_replications'))
    frame(out,'composition_validation_sensitivity_summary.csv',rr)
if __name__=='__main__':
    r=Path(__file__).resolve().parents[1];run(r,r/'results/release')
