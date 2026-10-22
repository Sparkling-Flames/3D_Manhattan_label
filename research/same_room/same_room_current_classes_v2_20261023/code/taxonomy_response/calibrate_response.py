"""Building-held-out response calibration using existing target-excluded maps.

For held-out building b, every training AND test team is described with the
already frozen label/profile map heldout_building=b. This avoids combining
training-building maps whose history includes b. Team experiment designs stay
fixed; no new classes, fusion, scores, or target-dependent member selection.
The study is internal validation in this fixed finite panel bank.
"""
from pathlib import Path
from collections import Counter,defaultdict
import argparse, json, os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import numpy as np
import pandas as pd
from analyze_response import hierarchy,write_csv,corr,PROFILE,analysis_layer,annotate_budget,source_continuous_ridge,label_path
MODELS={
 'source_mean':[],
 'source_exact_no_calibration':['source_deviation'],
 'source_linear_calibration':['source_deviation'],
 'source_plus_continuous':['source_deviation']+['profile_'+c for c in PROFILE],
 'source_continuous_response':['source_deviation','continuous_response_deviation'],
 'source_full_continuous':['source_deviation','continuous_response_deviation']+['profile_'+c for c in PROFILE],
 'source_plus_structure':['source_deviation','structure_composition_deviation'],
 'source_plus_joint':['source_deviation','joint_composition_deviation'],
 'source_continuous_plus_structure':['source_deviation','continuous_response_deviation']+['profile_'+c for c in PROFILE]+['structure_composition_deviation'],
 'source_continuous_plus_joint':['source_deviation','continuous_response_deviation']+['profile_'+c for c in PROFILE]+['joint_composition_deviation']}


def panel_weights(panels):
    # panels have already been restricted to each metric's common support.
    d=panels[['panel_id','pair_key','groups','building']].drop_duplicates()
    n_panel=d.groupby('pair_key').size().to_dict()
    pairs=d[['pair_key','groups','building']].drop_duplicates();pairs['group_id']=pairs.groups.str.split('|');pairs=pairs.explode('group_id')
    n_pairs=pairs.groupby(['building','group_id']).pair_key.nunique().to_dict();n_groups=pairs.groupby('building').group_id.nunique().to_dict()
    pair_w=defaultdict(float)
    for z in pairs.itertuples(index=False):pair_w[z.pair_key]+=1/(n_pairs[(z.building,z.group_id)]*n_groups[z.building])
    return {z.panel_id:pair_w[z.pair_key]/n_panel[z.pair_key] for z in d.itertuples(index=False)}


def mapped_teams(g,building,labels,profile_labels):
    s=labels[(labels.heldout_building==building)&(labels.method=='V3_BEHAVIOR')].set_index('worker_id');j=profile_labels[profile_labels.heldout_building==building].set_index('worker_id')
    sl=s.coarse_label.to_dict();jl=j.coarse_label.to_dict();sk=s.known.to_dict();jk=j.known.to_dict();pp={w:np.array(vals,float) for w,vals in zip(j.index,j[PROFILE].to_numpy())}
    cache={}
    for members in g.member_set_key.unique():
        ws=members.split('|');ok=all(sk.get(w,False) and jk.get(w,False) for w in ws)
        if not ok:cache[members]=(False,'','',np.full(len(PROFILE),np.nan));continue
        features=np.mean(np.stack([pp[w] for w in ws]),axis=0)
        sv=json.dumps(dict(sorted(Counter(sl[w] for w in ws).items())),separators=(',',':'))
        jv=json.dumps(dict(sorted(Counter(jl[w] for w in ws).items())),separators=(',',':'))
        cache[members]=(bool(np.isfinite(features).all()),sv,jv,features)
    z=g.copy();z['map_known']=z.member_set_key.map(lambda x:cache[x][0]);z['map_structure']=z.member_set_key.map(lambda x:cache[x][1]);z['map_joint']=z.member_set_key.map(lambda x:cache[x][2]);features=np.vstack(z.member_set_key.map(lambda x:cache[x][3]))
    for k,c in enumerate(PROFILE):z['mapped_'+c]=features[:,k]
    return z


def prepare_tasks(mapped,panels,metric,layer):
    eligible=panels[panels.analysis_layer==layer].copy();pmap=eligible.set_index('panel_id');parts=[];supported=[]
    for pid,all_z in mapped[mapped.panel_id.isin(pmap.index)].groupby('panel_id',sort=False):
        all_z=all_z[all_z.map_known].copy()
        for direct,sv,tv in [('a_to_b','a','b'),('b_to_a','b','a')]:
            # Predictor construction sees only source availability. Targets are
            # filtered for loss evaluation after all source means are fixed.
            z=all_z[np.isfinite(all_z[metric+'_'+sv])].copy()
            if len(z)<6:continue
            profiles=z[['mapped_'+c for c in PROFILE]].to_numpy();profiles-=profiles.mean(axis=0)
            source=z[metric+'_'+sv].to_numpy(float);target=z[metric+'_'+tv].to_numpy(float)
            evaluate=np.isfinite(target)
            if evaluate.sum()<6:continue
            supported.append(pid)
            d=pd.DataFrame({'panel_id':pid,'direction':direct,'member_set_key':z.member_set_key.to_numpy(),
             'source':source,'target':target,'source_mean':source.mean(),'target_mean':np.nanmean(target),
             'source_deviation':source-source.mean(),'target_deviation':target-np.nanmean(target),
             'source_bank_n':len(z),'target_unscored_in_source_bank':int((~evaluate).sum())})
            for scheme in ['structure','joint']:
                code=pd.factorize(z['map_'+scheme])[0];counts=np.bincount(code);mu=np.bincount(code,weights=source)/counts
                d[scheme+'_composition_deviation']=mu[code]-source.mean();d[scheme+'_cells']=len(counts)
            for k,c in enumerate(PROFILE):d['profile_'+c]=profiles[:,k]
            cp,info=source_continuous_ridge(profiles,source)
            d['continuous_response_deviation']=cp-source.mean()
            parts.append(d.loc[evaluate].copy())
    if not parts:return pd.DataFrame()
    tasks=pd.concat(parts,ignore_index=True);meta=eligible[eligible.panel_id.isin(supported)];weights=panel_weights(meta)
    tasksize=tasks.groupby(['panel_id','direction']).size().to_dict();ndir=tasks.groupby('panel_id').direction.nunique().to_dict()
    tasks['weight']=[weights[p]/(ndir[p]*tasksize[(p,d)]) for p,d in tasks[['panel_id','direction']].itertuples(index=False,name=None)]
    return tasks.merge(meta[['panel_id','pair_key','groups','building','n','replicate','ordinary_comparable']],on='panel_id',how='left')


def main(a):
    a.out.mkdir(parents=True,exist_ok=True);g=pd.read_csv(a.responses,low_memory=False);panels=annotate_budget(pd.read_csv(a.design/'PANELS.csv'));panels=panels[panels.panel_id.isin(g.panel_id)].copy();panels['analysis_layer']=panels.apply(analysis_layer,axis=1)
    if a.budget=='mid_n_rep0':panels=panels[panels.is_primary_budget].copy()
    elif a.budget=='all_n_rep0':panels=panels[panels.replicate==0].copy()
    g=g[g.panel_id.isin(panels.panel_id)].copy()
    labels=pd.read_csv(label_path(a.repo,a.labels));labels=labels[labels.condition=='manual'];profile=labels[labels.method=='V3_JOINT_QT']
    result=[];coeff=[];foldsupport=[]
    for b in sorted(panels.building.unique()):
        mapped=mapped_teams(g,b,labels,profile)
        for layer in sorted(panels.analysis_layer.unique()):
            if not ((panels.building==b)&(panels.analysis_layer==layer)).any():continue
            for metric in ['B8L2','D10']:
                tasks=prepare_tasks(mapped,panels,metric,layer)
                if tasks.empty:continue
                train=tasks[tasks.building!=b];test=tasks[tasks.building==b]
                if test.empty or train.building.nunique()<3:continue
                w=train.weight.to_numpy(float);y=train.target_deviation.to_numpy(float)
                foldsupport.append(dict(heldout_building=b,analysis_layer=layer,metric=metric,train_buildings=train.building.nunique(),train_pairs=train.pair_key.nunique(),train_panels=train.panel_id.nunique(),train_team_directions=len(train),test_pairs=test.pair_key.nunique(),test_panels=test.panel_id.nunique(),test_team_directions=len(test)))
                for model,features in MODELS.items():
                    if model=='source_mean':beta=np.zeros(0);prediction=test.source_mean.to_numpy(float)
                    elif model=='source_exact_no_calibration':beta=np.ones(1);prediction=test.source.to_numpy(float)
                    else:
                        X=train[features].to_numpy(float);scale=np.sqrt(np.average(X*X,axis=0,weights=w));scale=np.where(scale>1e-10,scale,1.);Xs=X/scale
                        # Small, fixed regularization, no validation-outcome tuning.
                        gram=Xs.T@(w[:,None]*Xs);rhs=Xs.T@(w*y)
                        standardized=np.linalg.solve(gram+0.01*np.eye(len(features)),rhs);beta=standardized/scale
                        prediction=test.source_mean.to_numpy(float)+test[features].to_numpy(float)@beta
                    for f,v in zip(features,beta):coeff.append(dict(heldout_building=b,analysis_layer=layer,metric=metric,model=model,feature=f,coefficient=float(v),map_used_for_train_and_test=b,fixed_standardized_ridge_penalty=.01))
                    e=test.copy();e['prediction']=prediction
                    for (pid,direction),z in e.groupby(['panel_id','direction'],sort=False):
                        error=z.prediction-z.target;cen=(z.prediction-z.prediction.mean())-z.target_deviation
                        meta=z.iloc[0]
                        result.append(dict(analysis_layer=layer,metric=metric,model=model,panel_id=pid,pair_key=meta.pair_key,groups=meta.groups,building=b,direction=direction,n=meta.n,replicate=meta.replicate,n_teams=len(z),mae=float(abs(error).mean()),mse=float((error*error).mean()),bias=float(error.mean()),contrast_mae=float(abs(cen).mean()),contrast_mse=float((cen*cen).mean()),target_var=float(np.var(z.target)),rho=corr(z.prediction,z.target),structure_cells=z.structure_cells.iloc[0],joint_cells=z.joint_cells.iloc[0]))
        print('completed response fold',b,flush=True)
    r=pd.DataFrame(result);write_csv(a.out/'CALIBRATED_PANEL_RESULTS.csv.gz',r);write_csv(a.out/'FOLD_COEFFICIENTS.csv',pd.DataFrame(coeff));write_csv(a.out/'FOLD_SUPPORT.csv',pd.DataFrame(foldsupport))
    values=['n_teams','mae','mse','bias','contrast_mae','contrast_mse','target_var','rho','structure_cells','joint_cells']
    for name,z in zip(['PAIR','GROUP','BUILDING','SUMMARY'],hierarchy(r,['analysis_layer','metric','model'],values)):
        z['contrast_R2']=1-z.contrast_mse/z.target_var.where(z.target_var>1e-12);write_csv(a.out/('CALIBRATED_'+name+'.csv'),z)
    receipt=dict(source_commit='72a44e80c344975962e1071bd54d894dd86bb4b4',budget=a.budget,new_classification_fits=0,new_fusion=0,new_scoring=0,current_design_fixed=True,label_isolation='each held-out building map is reused for ALL training and test teams; no target-building history in labels/profiles',prediction_mean='source panel mean, never target panel mean',training_response='target panel centered deviation only in outside-building training; target evaluation centered values never fit',regularization='fixed standardized ridge 0.01; no target tuning',continuous_comparator='source deviation; five historical means; source-only fitted linear/quadratic ridge response (degree/penalty chosen by source-only LOOCV); full continuous model includes all',status='internal building-held-out response comparison in the same registered finite design',response_rows=len(r))
    (a.out/'CALIBRATION_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--repo',type=Path);p.add_argument('--labels',type=Path);p.add_argument('--design',type=Path,required=True);p.add_argument('--responses',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--budget',choices=['mid_n_rep0','all_n_rep0','all_panels'],default='mid_n_rep0');main(p.parse_args())
