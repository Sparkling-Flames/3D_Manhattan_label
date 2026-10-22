#!/usr/bin/env python3
"""Independent source-to-results audit. Does not import experiment code or alter inputs."""
from pathlib import Path
import argparse, json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,default=HERE.parents[1]/'unpacked/quality_compact_20261007',help='Extracted compact package root or its results directory')
parser.add_argument('--out',type=Path,default=HERE,help='Existing experiment output directory; audit outputs are written here')
args=parser.parse_args()
D=args.out.resolve()
source=args.source.resolve()
S=source if (source/'manual_scored.csv').is_file() else source/'results'
FEATURES=['L','C','U','B','T','T_relative','LC','F','direction_rms_deg','flat_top_angular_rms_deg']
SCALES=['L','C','U','B','T','T_relative','direction_rms_deg','flat_top_angular_rms_deg']
MODELS=['S0','S1','S4','S5','S5_relative','LCn','LCn_T','LCn_G']
TOL={'L':1e-4,'C':1e-4,'U':.1,'B':.1,'T':.01,'F':.01}
raw=pd.read_csv(S/'manual_scored.csv')
q=raw.loc[raw.primary_candidate & raw.reference_version.eq('original')].dropna(subset=['L','C','U','B','T','T_relative'])
assert len(q)==1002 and q.image.nunique()==107 and q.building.nunique()==21
assert not q[['image','worker']].duplicated().any()
assert np.isfinite(q[FEATURES]).all().all()
frozen=pd.read_csv(D/'frozen_eligible_records.csv')
assert set(map(tuple,q[['image','id','worker']].values))==set(map(tuple,frozen[['image','id','worker']].values))
# Independently form every image pair by self-join rather than nested combinations.
z=q[['image','building','worker','id']+FEATURES].merge(q[['image','building','worker','id']+FEATURES],on='image',suffixes=('_a','_b'))
z=z.loc[z.worker_a<z.worker_b].copy()
assert z.building_a.eq(z.building_b).all()
z['building']=z.building_a
z['pair_id']=z.image+'|'+z.worker_a+'|'+z.worker_b
assert not z.pair_id.duplicated().any()
for f in FEATURES:z[f]=z[f+'_a']-z[f+'_b']
z=z.set_index('pair_id',drop=False).sort_index()
p=pd.read_csv(D/'all_pairs_predictions.csv').set_index('pair_id',drop=False).sort_index()
assert set(z.index)==set(p.index) and len(p)==7566
assert np.max(np.abs(z[FEATURES].values-p[['heldout_delta_'+f for f in FEATURES]].values))<1e-12
# Independent scales from explicit per-image arrays, excluding whole held building.
scale={}
for held in sorted(q.building.unique()):
    tr=q[q.building!=held]
    perimage=np.vstack([np.median(g[SCALES].values,axis=0) for _,g in tr.groupby('image')])
    scale[held]=dict(zip(SCALES,np.maximum(np.median(perimage,axis=0),1e-12)))
saved=pd.read_csv(D/'frozen_and_intrinsic_train_scales.csv').set_index('held_building')
scale_error=max(abs(scale[b][f]-saved.loc[b,f]) for b in scale for f in SCALES)
assert scale_error<1e-12
# Independently reconstruct ALL pair predictions and support, from source records.
recon=[]
for (a,b),group in z.groupby(['worker_a','worker_b']):
    for held,test in group.groupby('building'):
        train=group[group.building!=held]
        n=len(train);nb=train.building.nunique(); supported=n>=3 and nb>=2
        assert p.loc[test.index,'supported'].eq(supported).all()
        assert p.loc[test.index,'shared_train_images'].eq(n).all()
        assert p.loc[test.index,'shared_train_buildings'].eq(nb).all()
        if not supported:continue
        d=dict(zip(FEATURES,np.mean(train[FEATURES].values,axis=0)))
        c=scale[held]
        base=sum(d[f]/c[f] for f in ['L','C','U','B'])
        lc=d['L']/c['L']+d['C']/c['C']
        vals=dict(S0=d['L'],S1=d['LC'],S4=base,S5=base+d['T']/c['T'],S5_relative=base+d['T_relative']/c['T_relative'],LCn=lc,LCn_T=lc+d['T']/c['T'],LCn_G=lc+.5*(d['direction_rms_deg']/c['direction_rms_deg']+d['flat_top_angular_rms_deg']/c['flat_top_angular_rms_deg']))
        for pid in test.index:recon.append(dict(pair_id=pid,**vals))
r=pd.DataFrame(recon).set_index('pair_id').sort_index()
assert len(r)==7550 and len(MODELS)==8
prediction_error=np.max(np.abs(r[MODELS].values-p.loc[r.index,MODELS].values))
assert prediction_error<1e-10
pred=pd.DataFrame(np.where(np.abs(r)<=1e-12,0,np.sign(r)),index=r.index,columns=r.columns)
assert np.array_equal(pred[MODELS].values,p.loc[r.index,['pred_'+s for s in MODELS]].values)
# Independently label every pair from original metrics, preserving tolerance arithmetic.
labels={}
for name,f in [('I','L'),('C','C'),('U','U'),('B','B'),('T','T'),('F','F')]:
    status=np.where(np.abs(z[f])<=TOL[f],'tie','ordered')
    labels[name]=pd.DataFrame({'target_status':status,'expected_sign':np.where(status=='tie',0,np.sign(z[f]))},index=z.index)
for name,fs in [('LCUB_Pareto',['L','C','U','B']),('LCUBT_Pareto',['L','C','U','B','T'])]:
    aa=z[[f+'_a' for f in fs]].values;bb=z[[f+'_b' for f in fs]].values;tol=np.array([TOL[f] for f in fs])
    ab=np.all(bb<=aa+tol,axis=1)&np.any(bb<aa-tol,axis=1)
    ba=np.all(aa<=bb+tol,axis=1)&np.any(aa<bb-tol,axis=1)
    near=np.all(np.abs(aa-bb)<=tol,axis=1)
    labels[name]=pd.DataFrame({'target_status':np.where(ab!=ba,'ordered',np.where(near,'tie','incomparable')),'expected_sign':np.where(ab!=ba,np.where(ab,1,-1),0)},index=z.index)
nab=(z.L_b<z.L_a-TOL['L']);nba=(z.L_a<z.L_b-TOL['L'])
for f in ['C','U','B']:
    nab&=z[f+'_b']<=z[f+'_a']+TOL[f]; nba&=z[f+'_a']<=z[f+'_b']+TOL[f]
nab&=z.T_b>z.T_a+TOL['T'];nba&=z.T_a>z.T_b+TOL['T']
cs=labels['LCUB_Pareto'];ts=labels['T']
conflict=cs.target_status.eq('ordered')&ts.target_status.eq('ordered')&cs.expected_sign.ne(ts.expected_sign)
for name,flag,sgn in [('original_natural_conflict',nab|nba,np.where(nab,1,-1)),('LCUB_T_conflict',conflict,cs.expected_sign)]:
    for suffix,factor in [('core',1),('T',-1)]:
        labels[name+'_'+suffix]=pd.DataFrame({'target_status':np.where(flag,'ordered','outside_stratum'),'expected_sign':np.where(flag,factor*sgn,0)},index=z.index)
savedtargets=pd.read_csv(D/'all_pair_targets.csv')
for name,lab in labels.items():
    a=savedtargets[savedtargets.target==name].set_index('pair_id').sort_index()
    assert np.array_equal(lab.target_status,a.target_status),name
    assert np.array_equal(lab.expected_sign,a.expected_sign),name
# Original label/prediction baseline equality from original artifact, not experiment claims.
orig=pd.read_csv(S/'broad_lobo_pairs.csv')
orig['pair_id']=orig.image+'|'+orig.a_worker+'|'+orig.b_worker
originalids=set(orig.pair_id)
core=labels['LCUB_Pareto'];assert set(core.index[core.target_status.eq('ordered')])&set(r.index)==originalids
for s in MODELS[:5]:
    oo=orig[orig.scheme==s].set_index('pair_id').sort_index()
    assert np.max(np.abs(oo.score_difference-r.loc[oo.index,s]))<1e-10
    assert np.array_equal(oo.expected_sign,labels['LCUB_Pareto'].loc[oo.index,'expected_sign'])
# Independently aggregate via explicit per-image, per-building means and check all rows.
summary=pd.read_csv(D/'target_score_summary.csv').set_index(['panel','target','scheme'])
perimage=pd.read_csv(D/'target_score_per_image.csv').set_index(['panel','target','scheme','building','image'])
perbuilding=pd.read_csv(D/'target_score_per_building.csv').set_index(['panel','target','scheme','building'])
coverage=pd.read_csv(D/'target_coverage.csv').set_index(['panel','target'])
originalims=set(orig.image)
panels={'all_supported_pairs':r.index,'original_83_images':r.index[z.loc[r.index,'image'].isin(originalims)],'original_3494_pairs':r.index[r.index.isin(originalids)]}
recalc={}; agg_error=0.;coverage_rows=[]
for panel,ids in panels.items():
    for target,lab in sorted(labels.items()):
        alltarget=lab.loc[ids]; ordered=alltarget.index[alltarget.target_status.eq('ordered')]
        cov=coverage.loc[(panel,target)]
        assert len(ordered)==cov.ordered_pairs and len(ids)==cov.total_supported_pairs
        for status in ['tie','incomparable','missing','outside_stratum']:
            assert (alltarget.target_status==status).sum()==cov[status+'_pairs']
        for model in MODELS:
            pp=pred.loc[ordered,model]; expected=lab.loc[ordered,'expected_sign']
            acc=pd.Series(np.where(pp==0,.5,pp.eq(expected).astype(float)),index=ordered)
            buildings={};images=[]
            for building,bg in z.loc[ordered].groupby('building'):
                imvalues=[]
                for im,ig in bg.groupby('image'):
                    v=acc.loc[ig.index].mean();imvalues.append(v);images.append(v)
                    si=perimage.loc[(panel,target,model,building,im)]
                    assert si.n_pairs==len(ig)
                    agg_error=max(agg_error,abs(v-si.accuracy))
                v=float(np.mean(imvalues));buildings[building]=v
                sb=perbuilding.loc[(panel,target,model,building)]
                assert sb.n_images==len(imvalues) and sb.n_pairs==len(bg)
                agg_error=max(agg_error,abs(v-sb.accuracy))
            row=summary.loc[(panel,target,model)]
            assert row.buildings==len(buildings) and row.images==len(images) and row.ordered_pairs==len(acc)
            for actual,field in [(np.mean(list(buildings.values())),'building_equal_accuracy'),(np.mean(images),'image_equal_accuracy'),(acc.mean(),'pair_pooled_accuracy_not_headline')]:
                agg_error=max(agg_error,abs(actual-row[field]))
            recalc[(panel,target,model)]=pd.Series(buildings)
        coverage_rows.append({'panel':panel,'target':target,'pairs':len(ordered),'images':z.loc[ordered,'image'].nunique(),'buildings':z.loc[ordered,'building'].nunique()})
assert agg_error<1e-12
# Check every paired effect, sign count, and delete-one-building value.
effects=pd.read_csv(D/'paired_effect_summary.csv'); influence=pd.read_csv(D/'leave_one_building_influence.csv')
effect_error=0.; fragility=[]
for row in effects.itertuples():
    delta=recalc[(row.panel,row.target,row.model)]-recalc[(row.panel,row.target,row.baseline)]
    assert not delta.isna().any()
    effect_error=max(effect_error,abs(delta.mean()-row.paired_delta))
    assert row.buildings_gain==(delta>1e-12).sum() and row.buildings_loss==(delta < -1e-12).sum() and row.buildings_tie==(abs(delta)<=1e-12).sum()
    inf=influence[(influence.panel==row.panel)&(influence.target==row.target)&(influence.model==row.model)&(influence.baseline==row.baseline)].set_index('omitted_building')
    for b in delta.index:
        v=delta.drop(b).mean();effect_error=max(effect_error,abs(v-inf.loc[b,'leave_one_observed_building_out_delta']))
    if row.panel=='all_supported_pairs' and row.model in ['LCn_G','LCn_T'] and row.baseline=='LCn' and row.target in ['I','B','T','U']:
        for b in delta.index:
            fragility.append(dict(target=row.target,model=row.model,baseline=row.baseline,building=b,building_effect_pp=100*delta[b],full_effect_pp=100*delta.mean(),effect_omitting_building_pp=100*delta.drop(b).mean(),building_images=int(perbuilding.loc[(row.panel,row.target,row.model,b),'n_images']),building_pairs=int(perbuilding.loc[(row.panel,row.target,row.model,b),'n_pairs'])))
assert effect_error<1e-12
pd.DataFrame(fragility).to_csv(D/'independent_building_influence.csv',index=False)
# Independently reproduce the declared cluster resampling; no pair resampling.
saved_effect_buildings=pd.read_csv(D/'paired_effect_per_building.csv')
rng=np.random.default_rng(20261007);bootstrap_error=0.
for panel in panels:
    for target in sorted(labels):
        selected=effects[(effects.panel==panel)&(effects.target==target)]
        n=int(selected.buildings.iloc[0]);draws=rng.integers(n,size=(10000,n))
        for row in selected.itertuples():
            delta=recalc[(panel,target,row.model)]-recalc[(panel,target,row.baseline)]
            values=delta.sort_index().values
            lo,hi=np.quantile(values[draws].mean(axis=1),[.025,.975])
            bootstrap_error=max(bootstrap_error,abs(lo-row.descriptive_cluster_percentile_025),abs(hi-row.descriptive_cluster_percentile_975))
assert bootstrap_error<1e-12
report=dict(status='PASS',independent_source_records=len(q),all_pairs_checked=len(z),supported_predictions_checked=len(r),models_checked=MODELS,labels_checked=len(z)*len(labels),summary_rows_checked=len(summary),per_image_rows_checked=len(perimage),per_building_rows_checked=len(perbuilding),scale_max_error=scale_error,prediction_max_error=float(prediction_error),aggregation_max_error=float(agg_error),paired_effect_max_error=float(effect_error),bootstrap_percentile_max_error=float(bootstrap_error),material_computation_errors_found=0)
(D/'INDEPENDENT_CHECKS.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
print(pd.DataFrame(fragility).query("model=='LCn_G' and target=='I'").sort_values('building_effect_pp').to_string(index=False))
