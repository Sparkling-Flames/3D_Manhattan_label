#!/usr/bin/env python3
"""Learn personnel roles from real natural-prefix fusion response, LOBO.

The team outcome is the response. Original individual Q or marking descriptors
are not the response target. Each outer fold removes all target-building teams.
"""
import os
for _v in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_v]='1'
from pathlib import Path
from functools import lru_cache
import argparse,json
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage,cut_tree
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score,adjusted_rand_score
from prepare_natural_training import GEOM,QUALITY,save_csv,save_json,sha

OUTPUTS=GEOM+QUALITY
ALPHAS=[0.1,1.0,10.0]
STRATA=['all','easy','hard']
FAMILIES={'RFUSE_GEOM':['STRUCTURE','BOUNDARY'],'RFUSE_GEOMQ':['STRUCTURE','BOUNDARY','QUALITY']}
OUTPUT_DOMAINS={'STRUCTURE':GEOM[:3],'BOUNDARY':GEOM[3:],'QUALITY':QUALITY}

class Study:
    def __init__(self,path):
        self.input=pd.read_csv(path)
        self.data=self.input[self.input.training_eligible].copy()
        n=self.data.groupby('group_id').team_key.transform('size')
        self.data=self.data[n.ge(4)].copy().reset_index(drop=True)
        self.workers=sorted(set(w for value in self.data.member_workers for w in str(value).split('|')))
        self.windex={w:i for i,w in enumerate(self.workers)}
        self.buildings=sorted(self.input.building.unique())
        self.rows=[];self.stats={};self.statsmeta=[]
        X=np.zeros((len(self.data),len(self.workers)))
        for i,r in enumerate(self.data.itertuples()):
            members=str(r.member_workers).split('|');assert len(members)==r.k
            X[i,[self.windex[w] for w in members]]=1/r.k
        self.X=X;self.Y=self.data[OUTPUTS].to_numpy(float)
        self.meta_support=[]
        # Center both composition shares and observed output within image x n.
        # Occurrence weights preserve the actual natural-order sample after
        # deterministic duplicate endpoints have been collapsed.
        for stratum in STRATA:
            keep=np.ones(len(self.data),bool) if stratum=='all' else self.data.difficulty.eq('简单' if stratum=='easy' else '困难').to_numpy()
            sub=self.data[keep]
            for b,g in sub.groupby('building'):
                group_list=list(g.groupby('group_id'))
                image_n=g.image_id.nunique();k_counts=g[['image_id','group_id']].drop_duplicates().groupby('image_id').size()
                xx=np.zeros((len(self.workers),len(self.workers)));xy=np.zeros((len(self.workers),len(OUTPUTS)));y2=np.zeros(len(OUTPUTS))
                rowcount=0
                for groupid,gg in group_list:
                    ids=gg.index.to_numpy();w=gg.path_occurrences.to_numpy(float);w/=w.sum()
                    x=X[ids];y=self.Y[ids]
                    x=x-np.sum(x*w[:,None],axis=0);y=y-np.sum(y*w[:,None],axis=0)
                    w=w/image_n/k_counts[gg.image_id.iloc[0]]
                    xx+=x.T@(x*w[:,None]);xy+=x.T@(y*w[:,None]);y2+=np.sum(y*y*w[:,None],axis=0);rowcount+=len(gg)
                self.stats[(stratum,b)]=(xx,xy,y2)
                self.statsmeta.append(dict(stratum=stratum,building=b,images=image_n,groups=len(group_list),unique_teams=rowcount,total_building_weight=1.))
            for r in sub.itertuples():
                for w in str(r.member_workers).split('|'):
                    self.meta_support.append(dict(stratum=stratum,building=r.building,image_id=r.image_id,worker_id=w,team_key=r.team_key))
        self.support=pd.DataFrame(self.meta_support).drop_duplicates()

    @lru_cache(maxsize=None)
    def fit(self,stratum,excluded,alpha):
        st=[v for (s,b),v in self.stats.items() if s==stratum and b not in excluded]
        if not st:return None
        xx=np.sum([x[0] for x in st],axis=0);xy=np.sum([x[1] for x in st],axis=0);y2=np.sum([x[2] for x in st],axis=0)
        penalty=alpha*np.trace(xx)/len(self.workers)
        theta=np.linalg.solve(xx+np.eye(len(self.workers))*max(penalty,1e-12),xy)
        scale2=y2/len(st)
        return theta,scale2,penalty,len(st)

    def select(self,outer):
        outerexc=() if outer=='ALL' else (outer,)
        rows=[]
        for inner in self.buildings:
            if inner==outer:continue
            excluded=tuple(sorted(set(outerexc+(inner,))))
            for stratum in STRATA:
                test=self.stats.get((stratum,inner))
                if test is None:continue
                xx,xy,y2=test
                for alpha in ALPHAS:
                    model=self.fit(stratum,excluded,alpha)
                    if model is None:continue
                    theta,scale2,penalty,ntrain=model
                    err=y2-2*np.sum(theta*xy,axis=0)+np.sum(theta*(xx@theta),axis=0)
                    loss=np.where(scale2>1e-10,np.maximum(err,0)/np.maximum(scale2,1e-10),np.nan)
                    for j,c in enumerate(OUTPUTS):
                        if np.isfinite(loss[j]):rows.append(dict(heldout_building=outer,inner_building=inner,stratum=stratum,alpha=alpha,output=c,normalized_mse=float(loss[j]),zero_response_normalized_mse=float(y2[j]/scale2[j]),training_buildings=ntrain,penalty=penalty))
        checks=pd.DataFrame(rows);selected={};registry=[]
        for family,domains in FAMILIES.items():
            choices=[]
            for alpha in ALPHAS:
                scores=[];zero_scores=[]
                for domain in domains:
                    q=checks[checks.alpha.eq(alpha)&checks.output.isin(OUTPUT_DOMAINS[domain])]
                    # Equal output then equal stratum inside each domain.
                    value=q.groupby(['stratum','output']).normalized_mse.mean().groupby('stratum').mean().mean()
                    scores.append(value)
                    zero_scores.append(q.groupby(['stratum','output']).zero_response_normalized_mse.mean().groupby('stratum').mean().mean())
                score=float(np.mean(scores));zero_score=float(np.mean(zero_scores));choices.append((score,alpha))
                registry.append(dict(family=family,heldout_building=outer,alpha=alpha,inner_normalized_mse=score,domains='|'.join(domains),
                    zero_response_reference_nmse=zero_score,relative_mse_to_zero=score/zero_score,outer_target_used=False,selection='minimum mean inner-building normalized response MSE; domain/stratum balanced'))
            selected[family]=min(choices)[1]
        registry=pd.DataFrame(registry);registry['selected']=registry.apply(lambda r:r.alpha==selected[r.family],axis=1)
        return selected,registry,checks

    def response_features(self,outer,alpha):
        excluded=() if outer=='ALL' else (outer,)
        f=pd.DataFrame({'worker_id':self.workers});mat={}
        for stratum in STRATA:
            theta,scale2,penalty,ntrain=self.fit(stratum,excluded,alpha)
            mat[stratum]=theta
            for j,c in enumerate(OUTPUTS):f[f'{stratum}_{c}']=theta[:,j]
            q=self.support[self.support.stratum.eq(stratum)&~self.support.building.isin(excluded)]
            ss=q.groupby('worker_id').agg(images=('image_id','nunique'),buildings=('building','nunique'),teams=('team_key','nunique'))
            for c in ss:f[f'{stratum}_{c}']=f.worker_id.map(ss[c]).fillna(0).astype(int)
        for j,c in enumerate(OUTPUTS):f[f'hard_minus_easy_{c}']=mat['hard'][:,j]-mat['easy'][:,j]
        f['known_response']=f.all_images.ge(8)&f.all_buildings.ge(3)&f.easy_images.ge(5)&f.easy_buildings.ge(2)&f.hard_images.ge(3)&f.hard_buildings.ge(2)
        f['heldout_building']=outer;f['alpha']=alpha
        return f

def encode(f,domains):
    parts=[];description={}
    for domain in domains:
        cc=[f'{s}_{c}' for s in ['all','hard','hard_minus_easy'] for c in OUTPUT_DOMAINS[domain]]
        a=f[cc].to_numpy(float);med=np.median(a,axis=0);scale=np.quantile(a,.85,axis=0)-np.quantile(a,.15,axis=0)
        scale=np.where(scale>1e-9,scale,np.std(a,axis=0));scale=np.where(scale>1e-9,scale,1.)
        z=np.clip((a-med)/scale,-3,3);pca=PCA(n_components=2,svd_solver='full');y=pca.fit_transform(z)
        norm=np.sqrt(np.mean(np.sum(y*y,axis=1)));parts.append(y/max(norm,1e-9)/np.sqrt(len(domains)))
        description[domain]=dict(features=cc,median=med.tolist(),scale=scale.tolist(),components=pca.components_.tolist(),explained_variance_ratio=pca.explained_variance_ratio_.tolist(),normalization=float(norm))
    return np.column_stack(parts),description

def labels_for(f,family,roster):
    g=f[f.known_response].copy().reset_index(drop=True);x,encoding=encode(g,FAMILIES[family]);tree=linkage(x,method='ward',optimal_ordering=True)
    labels=[];centers=[];register=[]
    for k in [2,3]:
        raw=cut_tree(tree,n_clusters=k).ravel()
        sort=['hard_floor_turn5_n','all_bottom_y_mean_px'] if family=='RFUSE_GEOM' else ['all_B8L2','hard_B8L2','hard_floor_turn5_n']
        order=sorted(set(raw),key=lambda c:tuple(g.loc[raw==c,sort].mean()));lab=np.array([order.index(c) for c in raw]);mapping=dict(zip(g.worker_id,[f'C{v+1}' for v in lab]))
        z=roster.merge(f[['worker_id','heldout_building','alpha','all_images','all_buildings','hard_images','hard_buildings','easy_images','easy_buildings']],on='worker_id',how='left',validate='one_to_one')
        z['heldout_building']=f.heldout_building.iloc[0];z['alpha']=f.alpha.iloc[0];z['class_id']=z.worker_id.map(mapping).fillna('unknown');z['known']=z.class_id.ne('unknown')
        z['method']=f'{family}_K{k}';z['family']=family;z['k']=k;z['condition']='manual';z['input_conditions']='manual_natural_fusion_history';z['evaluation_condition']='manual'
        z['coarse_label']=z.class_id;z['fine_label']=z.class_id;z['missing_reason']=np.where(z.known,'','insufficient_natural_fusion_response_history')
        z['label_stage']='all_data_descriptive' if z.heldout_building.iloc[0]=='ALL' else 'target_building_excluded_nested_lambda_selected'
        z['underlying_data_version']='v2';labels.append(z)
        for c in range(k):
            gc=g[lab==c];row=dict(method=f'{family}_K{k}',family=family,k=k,heldout_building=f.heldout_building.iloc[0],class_id=f'C{c+1}',alpha=f.alpha.iloc[0],people=len(gc),members='|'.join(gc.worker_id),history_images_min=int(gc.all_images.min()),hard_images_min=int(gc.hard_images.min()),history_buildings_min=int(gc.all_buildings.min()))
            row.update({col:float(gc[col].mean()) for col in f if col.startswith(('all_','easy_','hard_')) and col not in ['all_images','all_buildings','all_teams','easy_images','easy_buildings','easy_teams','hard_images','hard_buildings','hard_teams']})
            centers.append(row)
        register.append(dict(method=f'{family}_K{k}',heldout_building=f.heldout_building.iloc[0],family=family,alpha=f.alpha.iloc[0],k=k,known_workers=len(g),class_size_vector='|'.join(map(str,np.bincount(lab,minlength=k))),min_class=int(np.bincount(lab,minlength=k).min()),silhouette=float(silhouette_score(x,lab)),domains='|'.join(FAMILIES[family]),selected_on_target_fusion=False))
    return pd.concat(labels,ignore_index=True),pd.DataFrame(centers),pd.DataFrame(register),encoding

def main(a):
    inp=Path(a.inputs);out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    study=Study(inp/'NATURAL_TRAINING_ENDPOINTS.csv.gz');save_csv(pd.DataFrame(study.statsmeta),out/'FIT_BUILDING_STRATUM_SUPPORT.csv')
    roster=pd.read_csv(a.roster)[['worker_id','origin']].drop_duplicates().sort_values('worker_id')
    labels=[];centers=[];reg=[];selects=[];cv=[];features=[];transforms={}
    for outer in ['ALL']+study.buildings:
        selected,selection,checks=study.select(outer);selects.append(selection);cv.append(checks)
        ll=[];cc=[]
        for family,alpha in selected.items():
            f=study.response_features(outer,alpha);f['family']=family;features.append(f)
            l,c,r,enc=labels_for(f,family,roster);labels.append(l);centers.append(c);reg.append(r);ll.append(l);cc.append(c);transforms[f'{outer}:{family}']=enc
        save_csv(pd.concat(ll,ignore_index=True),out/'folds'/f'LABELS_{outer}.csv.gz');save_csv(pd.concat(cc,ignore_index=True),out/'folds'/f'CENTERS_{outer}.csv')
        print('saved',outer,'selected',selected,flush=True)
    ls=pd.concat(labels,ignore_index=True);cs=pd.concat(centers,ignore_index=True);rs=pd.concat(reg,ignore_index=True)
    save_csv(ls,out/'REVERSE_LABELS_ALL_LOBO.csv.gz');save_csv(ls[ls.heldout_building.eq('ALL')],out/'REVERSE_LABELS_ALL.csv');save_csv(cs,out/'REVERSE_CLASS_CENTERS_ALL_LOBO.csv.gz');save_csv(cs[cs.heldout_building.eq('ALL')],out/'REVERSE_CLASS_CENTERS_ALL.csv')
    save_csv(rs,out/'REVERSE_CANDIDATE_REGISTRY.csv');save_csv(pd.concat(selects,ignore_index=True),out/'NESTED_LAMBDA_SELECTION.csv');save_csv(pd.concat(cv,ignore_index=True),out/'INNER_BUILDING_RESPONSE_ERRORS.csv.gz');save_csv(pd.concat(features,ignore_index=True),out/'WORKER_FUSION_RESPONSE_FEATURES_ALL_LOBO.csv.gz');save_json(transforms,out/'DOMAIN_ENCODINGS_ALL_LOBO.json')
    stability=[]
    for method,g in ls[ls.known].groupby('method'):
        full=g[g.heldout_building.eq('ALL')].set_index('worker_id').class_id
        for b,h in g[g.heldout_building.ne('ALL')].groupby('heldout_building'):
            target=h.set_index('worker_id').class_id;common=full.index.intersection(target.index)
            stability.append(dict(method=method,heldout_building=b,workers=len(common),ari=adjusted_rand_score(full.loc[common],target.loc[common])))
    save_csv(pd.DataFrame(stability),out/'REVERSE_LABEL_STABILITY.csv')
    receipt=dict(actual_commit='972857b2b3f548316be215400e42d6ef6e639250',underlying_data_version='v2',
      method='Nested-LOBO multi-output ridge on actual natural-prefix fusion responses, Ward K2/K3',
      model_rows=len(study.data),training_images=study.data.image_id.nunique(),training_buildings=len(study.buildings),raw_training_workers=len(study.workers),
      outputs=OUTPUTS,strata=STRATA,alphas=ALPHAS,
      input_design='person membership fraction 1/n; X and each outcome centered within image x n, natural-order occurrence weighted',
      weights='equal building, equal image within building, equal n within image, natural-order empirical weights within image x n',
      ridge_penalty='alpha times average diagonal of training XTX; alpha selected using only other training buildings',
      class_features='All, hard, hard-minus-easy fitted worker response; per-domain robust scaling, 2 PCs, equal domain weight; Ward K2/K3 same tree',
      qualification='ordinary_manual natural_random only; category-priority orders, special ranges and doorways excluded from reverse training',
      missing='Failure endpoints retained in input inventory, no zero Q; common finite-output response rows used; insufficient worker history unknown',
      unknown_rule='>=8 images/3 buildings overall, >=5 easy images/2 buildings, >=3 hard images/2 buildings',
      target_exclusion='All target-building teams omitted from outer fit and from every inner hyperparameter evaluation',
      differs_from_previous='Learns actual n10..24 fusion endpoint response to member composition, not original-answer Q/features or single-person/m2 replacement relationships',
      no_new_fusion=True,exploration='v2 internal material reused; not a new external blind test',source_input_sha256=sha(inp/'NATURAL_TRAINING_ENDPOINTS.csv.gz'),code_sha256=sha(__file__))
    save_json(receipt,out/'REVERSE_BUILD_RECEIPT.json');print(rs[rs.heldout_building.eq('ALL')].to_string(index=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--output',required=True);p.add_argument('--roster',required=True);main(p.parse_args())
