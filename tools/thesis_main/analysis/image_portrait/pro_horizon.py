"""Exploratory finite-horizon generalization to two withheld REAL people.

Only observed panels with >=10 distinct valid people. Each order draws ten without
replacement; prefixes2/3/5/8 share the same final two held-out persons. Repeated
orders describe the finite pool and never create people, images or formal stopping
labels. Point-count/geometry/supported-mode coverage are kept separate.
"""
import argparse,collections,itertools,json
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.image_portrait import pro_core as core
from tools.thesis_main.analysis.image_portrait.pro_core import *
from tools.thesis_main.analysis.image_portrait.pro_core import _d_mask
from tools.thesis_main.analysis.image_portrait import pro_predict as pred


def run(repeats=200):
    r=pd.read_csv(OUT/'human/response_metrics.csv.gz');r=r[r.main_worker_included & r.geometry_valid & r.raw_condition.isin(['manual','semi'])]
    z=np.load(OUT/'human/dense_boundaries.npz');dense=dict(zip(z['canonical_annotation_ids'],z['boundaries']));rng=np.random.default_rng(SEED);rows=[];coverage=[]
    for (image,arm),g in r.groupby(['image_id','raw_condition']):
        g=g.sort_values('worker_id').reset_index(drop=True);n=len(g);coverage.append(dict(image_id=image,condition=arm,n_valid_workers=n,eligible=n>=10,reason='eligible'if n>=10 else 'fewer_than_10_distinct_real_workers'))
        if n<10:continue
        assert not g.worker_id.duplicated().any()
        pcs=g.effective_point_count.to_numpy();ids=g.canonical_annotation_id.tolist();dm=np.zeros((n,n))
        for i,j in itertools.combinations(range(n),2):dm[i,j]=dm[j,i]=_d_mask(dense[ids[i]],dense[ids[j]]) if pcs[i]==pcs[j] else 2.
        summaries=collections.defaultdict(list)
        for rep in range(repeats):
            order=rng.permutation(n)[:10];future=order[8:10]
            for cut in [.05,.10,.20]:
                for k in [2,3,5,8]:
                    ix=order[:k];lab=topology_clusters(dm[np.ix_(ix,ix)],pcs[ix],cut);med=[];allmed=[];supported=0
                    for l in set(lab):
                        cluster=ix[lab==l];medoid=cluster[np.argmin(dm[np.ix_(cluster,cluster)].sum(1))];allmed.append(medoid)
                        if len(cluster)>=2:med.append(medoid);supported+=1
                    topology=float(np.mean([pc in pcs[ix] for pc in pcs[future]]))
                    anygeom=float(np.mean(np.min(dm[np.ix_(future,allmed)],axis=1)<=cut+1e-12))
                    support=float(np.mean(np.min(dm[np.ix_(future,med)],axis=1)<=cut+1e-12)) if med else 0.
                    summaries[cut,k].append((topology,anygeom,support,supported))
        for (cut,k),values in summaries.items():
            a=np.asarray(values);rows.append(dict(image_id=image,building=image.split('_')[0],condition=arm,n_available_people=n,horizon=10,prefix=k,future_people=2,repetitions=repeats,cut=cut,future_topology_coverage=a[:,0].mean(),future_geometry_coverage_allow_singleton=a[:,1].mean(),future_supported_geometry_coverage=a[:,2].mean(),mean_supported_clusters=a[:,3].mean(),probability_both_future_supported=(a[:,2]==1).mean(),unsupported_both_fraction=(a[:,2]==0).mean()))
    write_csv('stability/fixed_horizon10_image_curves.csv',rows);write_csv('stability/fixed_horizon10_coverage.csv',coverage)
    a=pd.DataFrame(rows);s=a.groupby(['condition','cut','prefix'],as_index=False).agg(n_images=('image_id','nunique'),n_buildings=('building','nunique'),topology_coverage=('future_topology_coverage','mean'),geometry_with_singletons=('future_geometry_coverage_allow_singleton','mean'),supported_geometry_coverage=('future_supported_geometry_coverage','mean'),both_future_supported=('probability_both_future_supported','mean'))
    write_csv('stability/fixed_horizon10_summary.csv',s)
    write_json(OUT/'stability/horizon_method.json',dict(version='exploratory_H10_future2_v1',seed=SEED,orders=repeats,prefixes=[2,3,5,8],cuts=[.05,.10,.20],sampling='10 distinct observed people without replacement; common heldout final2 at all prefixes',unit='image then building; orders not independent samples',singleton='preserved and separately measured; supported mode requires2people',not_formal_stopping_rule=True,limitation='Conditional on historical observed pool and its selection; not chronological recruitment or proof of new-worker generalization'))


def forecasts():
    # Reuse EXACT fixed folds/nested grid, naming the new fractional targets
    # explicitly. Every cut/prefix is reported, not chosen from outer success.
    base=core.OUT;dest=base/'stability/horizon_prediction';dest.mkdir(parents=True,exist_ok=True)
    t=pd.read_csv(base/'stability/fixed_horizon10_image_curves.csv');t=t.pivot(index=['image_id','building','condition'],columns=['cut','prefix'],values='future_supported_geometry_coverage').reset_index();t.columns=['image_id','building','condition']+[f'coverage_cut{cut:g}_prefix{k}'for cut,k in t.columns[3:]]
    root=base/'features';reg=json.loads((root/'registry.json').read_text());names=['A_all_traits','B_feedback','ABC_traits_feedback_shared','C_hohonet_shared_global','C_da3_layer11_global']
    core.OUT=dest;pred.OUT=dest;pred.PTARGETS=list(t.columns[3:])
    pred.baseline_predictions(t,pd.read_csv(base/'A/interpretable_inputs.csv'))
    for name in names:pred.evaluate_feature(name,reg[name],root,t)
    core.OUT=base;pred.OUT=base

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['curves','prediction','all'],default='all');a=p.parse_args()
    if a.stage in ['curves','all']:run()
    if a.stage in ['prediction','all']:forecasts()
