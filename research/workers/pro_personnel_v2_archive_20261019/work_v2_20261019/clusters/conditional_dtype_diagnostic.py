"""Within-QT swap association, adjusting residual continuous Q/T contrasts.

Labels and traits are from target-building-excluded profiles. This is a fixed
effects explanatory diagnostic on existing swaps, not another classification
search or a newly blind prediction result. Coefficients cannot establish a
causal effect of changing a person's difficulty category.
"""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;SEED=2026101951

def weights(d):
    ni=d[['pool_id','building_id']].drop_duplicates();b=ni.groupby('building_id').size()
    k=d[['pool_id','k']].drop_duplicates().groupby('pool_id').size()
    st=d[['pool_id','k','stratum_id']].drop_duplicates().groupby(['pool_id','k']).size();n=d.groupby('stratum_id').size()
    return np.asarray([1/(len(b)*b[x]*k[p]*st[p,z]*n[s]) for p,x,z,s in zip(d.pool_id,d.building_id,d.k,d.stratum_id)])

def one_model(d,predictors,outcome):
    cols=[*predictors,outcome];centered=d[cols]-d.groupby('stratum_id')[cols].transform('mean')
    x=centered[predictors].to_numpy(float);y=centered[outcome].to_numpy(float);w=weights(d)
    bld=sorted(d.building_id.unique());xx=[];xy=[]
    for b in bld:
        ix=d.building_id.eq(b).to_numpy();xx.append(x[ix].T@(w[ix,None]*x[ix]));xy.append(x[ix].T@(w[ix]*y[ix]))
    xx=np.asarray(xx);xy=np.asarray(xy);normal=xx.sum(0);rhs=xy.sum(0);beta=np.linalg.lstsq(normal,rhs,rcond=None)[0]
    rng=np.random.default_rng(SEED);draw=rng.integers(0,len(bld),(3000,len(bld)));est=[]
    for r in draw:est.append(np.linalg.lstsq(xx[r].sum(0),xy[r].sum(0),rcond=None)[0][0])
    return dict(cross_dtype_coefficient=beta[0],low=np.quantile(est,.025),high=np.quantile(est,.975),rank=int(np.linalg.matrix_rank(normal)),
        n_predictors=len(predictors),coefficients=json.dumps(dict(zip(predictors,beta.tolist())),separators=(',',':')))

def main():
    out=HERE/'conditional_dtype';out.mkdir(exist_ok=True)
    path=HERE/'forward_swaps/labeled_events.csv.gz';d=pd.read_csv(path)
    d=d[d.common_known & d.equal_entrant_count & d.QT_B8L2_a.eq(d.QT_B8L2_b)].copy().reset_index(drop=True)
    p=pd.read_csv(HERE.parent/'profiles/fold_profiles.csv').set_index(['heldout_building','worker_id'])
    a=p.reindex(pd.MultiIndex.from_arrays([d.building_id,d.entrant_a],names=p.index.names));b=p.reindex(pd.MultiIndex.from_arrays([d.building_id,d.entrant_b],names=p.index.names))
    for c,name in [('Q_effect_B8L2','beta'),('T_source_effect','source_T')]:
        va,vb=a[c].to_numpy(),b[c].to_numpy();d[name+'_mean']=(va+vb)/2;d[name+'_absdiff']=abs(va-vb)
    labels=pd.read_csv(HERE/'assignments.csv');labels=labels[labels.method.eq('affinity') & labels.threshold_deg.eq(9)]
    count={(r.pool_id,r.worker_id):r.pair_count for r in labels.itertuples()}
    d['point_count']=[count[x,w] for x,w in zip(d.pool_id,d.entrant_a)]
    d['stratum_id']=d.pool_id+'|'+d.k.astype(str)+'|'+d.background_id+'|'+d.point_count.astype(str)+'|'+d.QT_B8L2_a
    results=[];coverage=[]
    models={'no_continuous_adjustment':['cross_dtype'],'continuous_Q':['cross_dtype','beta_mean','beta_absdiff'],
            'continuous_Q_T':['cross_dtype','beta_mean','beta_absdiff','source_T_mean','source_T_absdiff']}
    for label in ['difficulty_type','fine_dtype_merged']:
        da=d[label+'_B8L2_a'];db=d[label+'_B8L2_b'];h=d[~da.str.contains('unknown') & ~db.str.contains('unknown')].copy()
        h['cross_dtype']=h[label+'_B8L2_a'].ne(h[label+'_B8L2_b']).astype(float)
        for k in ['all',8,12,16,24]:
            z=h if k=='all' else h[h.k.eq(k)]
            for outcome in ['abs_B8L2_change','floor_jaccard_difference','joint_geometric_stable']:
                g=z.dropna(subset=[outcome,'beta_mean','beta_absdiff','source_T_mean','source_T_absdiff']).copy()
                supported=g.groupby('stratum_id').cross_dtype.nunique();g=g[g.stratum_id.isin(supported[supported.eq(2)].index)].copy()
                coverage.append(dict(label=label,k=k,outcome=outcome,eligible_attempts=len(z),observed_and_contrast_supported=len(g),
                    images=g.image_id.nunique(),buildings=g.building_id.nunique(),matched_strata=g.stratum_id.nunique()))
                if not len(g):continue
                for model,cols in models.items():results.append(dict(label=label,k=k,outcome=outcome,adjustment=model,images=g.image_id.nunique(),buildings=g.building_id.nunique(),
                    pairs=len(g),matched_strata=g.stratum_id.nunique(),**one_model(g,cols,outcome)))
    pd.DataFrame(results).to_csv(out/'summary.csv',index=False);pd.DataFrame(coverage).to_csv(out/'coverage.csv',index=False)
    r=dict(status='explanatory_within_QT_continuous_Q_T_diagnostic',registered_before_this_fit=True,
        motivation='A difficulty subclass may partly re-identify residual continuous Q variation inside a coarse Q bin.',
        labels=['difficulty_type_B8L2','fine_dtype_merged_B8L2'],old_hard_adaptation_fine_candidate_used=False,
        fixed_effects='exact pool/reference,k,background,point count,concrete QT parent',
        weighting='building -> image -> available k -> supported matched stratum -> entrant pair',
        inference='3000 building-cluster bootstrap least-squares moment refits, seed2026101951',
        traits_exclude_target_building=True,classes_or_thresholds_changed=False,causal_interpretation=False,
        input_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    (out/'RECEIPT.json').write_text(json.dumps(r,indent=2)+'\n');print(pd.DataFrame(results).query("k == 'all'").to_string(index=False))

if __name__=='__main__':main()
