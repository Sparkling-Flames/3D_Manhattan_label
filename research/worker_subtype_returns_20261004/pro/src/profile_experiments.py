"""Exploratory finite-panel Q models, no target-building leakage or class-size quota."""
from pathlib import Path
import os
import itertools,json
import numpy as np,pandas as pd
from scipy.cluster.hierarchy import linkage,cut_tree
from scipy.stats import rankdata,spearmanr
from sklearn.metrics import adjusted_rand_score
ROOT=Path(os.environ.get('WORKER_RESEARCH_ROOT',Path(__file__).resolve().parents[1]))

def cluster_q(x,k):
    if k==1:return np.zeros(len(x),int)
    z=cut_tree(linkage(np.asarray(x)[:,None],method='ward'),n_clusters=[k]).ravel()
    order=sorted(set(z),key=lambda a:float(np.mean(x[z==a])))
    return np.array([order.index(i) for i in z])

def fit(x,method):
    if method=='individual':return x.copy(),np.arange(len(x))
    if method=='no_worker':return np.zeros_like(x),np.zeros(len(x),int)
    if method=='median2':
        med=float(np.median(x))
        if (x==med).any(): return None,None # no identity-based tie break
        z=(x>med).astype(int)
    else:z=cluster_q(x,int(method[4:]))
    pred=np.array([x[z==i].mean() for i in z])
    return pred,z

def main():
    out=ROOT/'results';out.mkdir(exist_ok=True)
    rows=[];assign=[];cells=[];learning=[];size_rows=[]
    for policy in ['original','revised_where_available']:
        df=pd.read_csv(ROOT/'inputs'/f'matrix_{policy}_iou.csv')
        workers=list(df.columns[2:]); y=df[workers].to_numpy();b=df.building.to_numpy();bs=sorted(set(b)); r=y-y.mean(axis=1,keepdims=True)
        for target in bs:
            tr=b!=target;te=~tr;x=r[tr].mean(axis=0)
            for method in ['no_worker','individual','median2','ward2','ward3','ward4']:
                pred,z=fit(x,method)
                if pred is None:
                    rows.append(dict(policy=policy,target=target,method=method,status='median_tie'));continue
                rows.append(dict(policy=policy,target=target,method=method,status='ok',train_images=int(tr.sum()),test_images=int(te.sum()),sse=float(((r[te]-pred)**2).sum()),baseline_sse=float((r[te]**2).sum()),image_n=int(te.sum()),worker_n=len(workers),sizes='|'.join(str(int((z==j).sum())) for j in sorted(set(z)))))
                for w,zz,xx,pp in zip(workers,z,x,pred):assign.append(dict(policy=policy,target=target,method=method,worker=w,subtype=int(zz),calibration_centered_iou=float(xx),prediction=float(pp)))
                for ind in np.flatnonzero(te):
                    for group in sorted(set(z)):
                        ix=z==group
                        cells.append(dict(policy=policy,image=df.image.iloc[ind],building=target,method=method,subtype=int(group),n=int(ix.sum()),mean_iou=float(y[ind,ix].mean()),sd_iou=float(y[ind,ix].std()),warning='reference_score_dispersion_NOT_annotation_shape_stability'))
        # Independent disjoint building sets, no shared calibration images; uniform finite list.
        for m in range(1,5):
            seen=0
            for a in itertools.combinations(bs,m):
                for c in itertools.combinations([q for q in bs if q not in a],m):
                    if a>=c:continue
                    aa=y[np.isin(b,a)].mean(0);cc=y[np.isin(b,c)].mean(0)
                    for meth in ['median2','ward2','ward3','ward4']:
                        _,la=fit(aa-aa.mean(),meth);_,lc=fit(cc-cc.mean(),meth)
                        sizesA='|'.join(str(int((la==k).sum())) for k in sorted(set(la))) if la is not None else ''
                        if la is None or lc is None:
                            learning.append(dict(policy=policy,m=m,a='|'.join(a),b='|'.join(c),method=meth,status='median_tie'));continue
                        # Highest-mean class is a named subtype; not label-matched using evaluation.
                        A=set(np.flatnonzero(la==la.max()));C=set(np.flatnonzero(lc==lc.max()))
                        learning.append(dict(policy=policy,m=m,a='|'.join(a),b='|'.join(c),method=meth,status='ok',ari=adjusted_rand_score(la,lc),rank_rho=float(spearmanr(aa,cc).statistic),upper_jaccard=len(A&C)/len(A|C),upper_n_a=len(A),upper_n_b=len(C),sizes_a=sizesA))
    for name,v in [('profile_prediction_folds',rows),('profile_assignments',assign),('subtype_reference_description',cells),('disjoint_calibration_learning',learning)]:pd.DataFrame(v).to_csv(out/(name+'.csv'),index=False)
    f=pd.DataFrame(rows);g=f[f.status=='ok'].groupby(['policy','method'])
    s=g[['sse','baseline_sse']].sum();s['relative_mse_improvement']=1-s.sse/s.baseline_sse;s.to_csv(out/'profile_prediction_summary.csv')
    l=pd.DataFrame(learning);l[l.status=='ok'].groupby(['policy','m','method']).agg(n=('ari','size'),ari_median=('ari','median'),named_upper_jaccard=('upper_jaccard','median'),upper_n_median=('upper_n_a','median')).to_csv(out/'disjoint_learning_summary.csv')
    print(s.to_string());print('\nFOLD SIZES:');print(f[['policy','target','method','sizes']].query("method == 'ward2'").to_string(index=False))
if __name__=='__main__':main()
