"""Independent sufficient statistics, nested selection and three outer-fold fits."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage,cut_tree
from sklearn.decomposition import PCA

OUT=Path(__file__).resolve().parent
ROOT=OUT.parent/'unpacked/06A/research/workers/personnel_exchange_discrimination_20261025'
allrows=pd.read_csv(ROOT/'reverse/inputs/NATURAL_TRAINING_ENDPOINTS.csv.gz')
geom=['floor_turn5_n','floor_short_edge_03_n','floor_redundant5_n','bottom_y_mean_px','top_y_mean_px','log_floor_area','log_height_mean']
quality=['B8L2','D10','iou2d100','IoU3D100','boundary_loss','direction_loss','height_loss']
outputs=geom+quality
domains={'STRUCTURE':geom[:3],'BOUNDARY':geom[3:],'QUALITY':quality}
families={'RFUSE_GEOM':['STRUCTURE','BOUNDARY'],'RFUSE_GEOMQ':['STRUCTURE','BOUNDARY','QUALITY']}
alphas=[.1,1.,10.]
data=allrows[allrows.training_eligible].copy()
data=data[data.groupby('group_id').team_key.transform('size').ge(4)].reset_index(drop=True)
assert data.layer.eq('ordinary_manual').all() and data.condition.eq('manual').all()
assert not data.team_key.duplicated().any()
people=sorted({w for member in data.member_workers for w in member.split('|')})
index={p:i for i,p in enumerate(people)}
X=np.zeros((len(data),len(people)))
for i,r in enumerate(data.itertuples()):
    p=r.member_workers.split('|');assert len(p)==r.k
    X[i,[index[w] for w in p]]=1/r.k
Y=data[outputs].to_numpy(float)
stats={}
for stratum in ['all','easy','hard']:
    sub=data if stratum=='all' else data[data.difficulty.eq('简单' if stratum=='easy' else '困难')]
    for b,g in sub.groupby('building'):
        ni=g.image_id.nunique();nk=g[['image_id','group_id']].drop_duplicates().groupby('image_id').size()
        xx=np.zeros((len(people),len(people)));xy=np.zeros((len(people),len(outputs)));yy=np.zeros(len(outputs))
        for _,group in g.groupby('group_id'):
            w=group.path_occurrences.to_numpy(float);w/=w.sum();ids=group.index.to_numpy()
            x=X[ids]-w@X[ids];y=Y[ids]-w@Y[ids]
            w/=ni*nk[group.image_id.iloc[0]]
            xx+=(x*w[:,None]).T@x;xy+=(x*w[:,None]).T@y;yy+=np.sum(w[:,None]*y*y,axis=0)
        stats[stratum,b]=(xx,xy,yy)
buildings=sorted(data.building.unique());cache={}
def fit(s,excluded,alpha):
    key=(s,tuple(sorted(excluded)),alpha)
    if key not in cache:
        used=[v for (st,b),v in stats.items() if st==s and b not in excluded]
        xx=sum(v[0] for v in used);xy=sum(v[1] for v in used);scale=sum(v[2] for v in used)/len(used)
        penalty=max(alpha*np.trace(xx)/len(people),1e-12)
        theta=np.linalg.solve(xx+np.eye(len(people))*penalty,xy)
        cache[key]=(theta,scale)
    return cache[key]

saved_select=pd.read_csv(ROOT/'reverse/NESTED_LAMBDA_SELECTION.csv')
saved_feature=pd.read_csv(ROOT/'reverse/WORKER_FUSION_RESPONSE_FEATURES_ALL_LOBO.csv.gz')
saved_labels=pd.read_csv(ROOT/'reverse/REVERSE_LABELS_ALL_LOBO.csv.gz')
findings=[]
for outer in ['ALL','7y3sRwLe3Va','B6ByNegPMKs']:
    chosen={}
    for fam,ds in families.items():
        vals=[]
        for alpha in alphas:
            per=[]
            for inner in buildings:
                if inner==outer:continue
                for st in ['all','easy','hard']:
                    if (st,inner) not in stats:continue
                    xx,xy,yy=stats[st,inner]
                    theta,scale=fit(st,{outer,inner},alpha)
                    err=yy-2*np.sum(theta*xy,axis=0)+np.sum(theta*(xx@theta),axis=0)
                    nmse=np.divide(np.maximum(err,0),scale,out=np.full_like(scale,np.nan),where=scale>1e-10)
                    for j,o in enumerate(outputs):per.append((st,o,nmse[j]))
            per=pd.DataFrame(per,columns=['stratum','output','loss'])
            score=np.mean([per[per.output.isin(domains[d])].groupby(['stratum','output']).loss.mean().groupby('stratum').mean().mean() for d in ds])
            old=saved_select[saved_select.heldout_building.eq(outer)&saved_select.family.eq(fam)&saved_select.alpha.eq(alpha)].iloc[0]
            assert abs(score-old.inner_normalized_mse)<1e-9,(outer,fam,alpha,score,old.inner_normalized_mse)
            vals.append((score,alpha))
        chosen[fam]=min(vals)[1]
        old=saved_select[saved_select.heldout_building.eq(outer)&saved_select.family.eq(fam)&saved_select.selected].iloc[0]
        assert chosen[fam]==old.alpha
        feature=pd.DataFrame({'worker_id':people})
        for st in ['all','easy','hard']:
            theta,_=fit(st,{outer},chosen[fam])
            for j,o in enumerate(outputs):feature[f'{st}_{o}']=theta[:,j]
        for o in outputs:feature[f'hard_minus_easy_{o}']=feature[f'hard_{o}']-feature[f'easy_{o}']
        oldf=saved_feature[saved_feature.heldout_building.eq(outer)&saved_feature.family.eq(fam)].set_index('worker_id').reindex(people)
        numeric=[c for c in feature if c!='worker_id']
        gap=float(np.max(np.abs(feature[numeric].to_numpy()-oldf[numeric].to_numpy())))
        assert np.allclose(feature[numeric],oldf[numeric],rtol=1e-8,atol=1e-8),(outer,fam,gap)
        eligible=oldf.known_response.to_numpy()
        # Recheck every eligibility count using training member rows, not saved labels.
        support=data[data.building.ne(outer)].copy()
        support['worker_id']=support.member_workers.str.split('|');support=support.explode('worker_id')
        count=[]
        for st,rows in [('all',support),('easy',support[support.difficulty.eq('简单')]),('hard',support[support.difficulty.eq('困难')])]:
            c=rows.groupby('worker_id').agg(images=('image_id','nunique'),buildings=('building','nunique')).reindex(people).fillna(0)
            for name in c:assert np.array_equal(c[name],oldf[f'{st}_{name}'])
            count.append(c)
        eligible2=(count[0].images.ge(8)&count[0].buildings.ge(3)&count[1].images.ge(5)&count[1].buildings.ge(2)&count[2].images.ge(3)&count[2].buildings.ge(2)).to_numpy()
        assert np.array_equal(eligible,eligible2)
        d=feature[eligible].reset_index(drop=True);blocks=[]
        for domain in ds:
            cc=[f'{st}_{o}' for st in ['all','hard','hard_minus_easy'] for o in domains[domain]]
            a=d[cc].to_numpy();med=np.median(a,axis=0);scale=np.quantile(a,.85,axis=0)-np.quantile(a,.15,axis=0)
            scale=np.where(scale>1e-9,scale,a.std(axis=0));scale=np.where(scale>1e-9,scale,1.)
            p=PCA(n_components=2,svd_solver='full').fit_transform(np.clip((a-med)/scale,-3,3))
            p/=max(np.sqrt(np.mean(np.sum(p*p,axis=1))),1e-9)*np.sqrt(len(ds));blocks.append(p)
        tree=linkage(np.column_stack(blocks),method='ward',optimal_ordering=True)
        for k in [2,3]:
            cls=cut_tree(tree,n_clusters=k).ravel()
            sort=['hard_floor_turn5_n','all_bottom_y_mean_px'] if fam=='RFUSE_GEOM' else ['all_B8L2','hard_B8L2','hard_floor_turn5_n']
            order=sorted(set(cls),key=lambda c:tuple(d.loc[cls==c,sort].mean()))
            new=pd.Series([f'C{order.index(c)+1}' for c in cls],index=d.worker_id)
            old=saved_labels[saved_labels.heldout_building.eq(outer)&saved_labels.method.eq(f'{fam}_K{k}')].set_index('worker_id').class_id
            assert new.reindex(old.index).fillna('unknown').equals(old)
        findings.append(dict(heldout_building=outer,family=fam,alpha=chosen[fam],coefficient_max_abs_diff=gap,known_people=int(eligible.sum()),nested_alphas_checked=len(alphas),labels_exact=True))
    print('passed',outer,chosen,flush=True)
pd.DataFrame(findings).to_csv(OUT/'CHECKS_REVERSE.csv',index=False)
(OUT/'SUMMARY_REVERSE.json').write_text(json.dumps({'training_rows':len(data),'training_images':data.image_id.nunique(),'buildings':len(buildings),'unique_workers':len(people),'refits':findings},ensure_ascii=False,indent=2),encoding='utf-8')
