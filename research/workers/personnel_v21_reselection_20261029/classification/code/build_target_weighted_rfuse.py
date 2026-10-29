#!/usr/bin/env python3
"""Actual target-equal refit; no new fusion; preserves frozen RFUSE inner selection."""
import os
for v in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[v]='1'
import sys,json,hashlib,gzip
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT.parent
sys.path.insert(0,str(WORK/'stage01/old_sources/reverse/code'))
import learn_natural_fusion_roles as core

def save(d,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=d.to_csv(index=False).encode('utf-8-sig')
    if path.suffix=='.gz':raw=gzip.compress(raw,compresslevel=6,mtime=0)
    tmp=path.with_name(path.name+'.partial')
    with tmp.open('wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    tmp.replace(path)
def js(x,path):
    path.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

class TargetStudy(core.Study):
    def __init__(self,path):
        super().__init__(path)
        # Existing group_id already exactly pool x n; preserve that good boundary.
        assert self.data.groupby('group_id').pool_id.nunique().max()==1
        assert self.data.groupby('group_id').k.nunique().max()==1
        self.stats={};self.statsmeta=[];self.weight_comparison=[]
        for stratum in core.STRATA:
            keep=np.ones(len(self.data),bool) if stratum=='all' else self.data.difficulty.eq('简单' if stratum=='easy' else '困难').to_numpy()
            sub=self.data[keep]
            for b,g in sub.groupby('building'):
                image_n=g.image_id.nunique()
                targets_per_image=g.groupby('image_id').pool_id.nunique()
                n_per_target=g[['pool_id','group_id']].drop_duplicates().groupby('pool_id').size()
                old_groups_per_image=g[['image_id','group_id']].drop_duplicates().groupby('image_id').size()
                xx=np.zeros((len(self.workers),len(self.workers)));xy=np.zeros((len(self.workers),len(core.OUTPUTS)));y2=np.zeros(len(core.OUTPUTS))
                rowcount=0;total_weight=0
                for groupid,gg in g.groupby('group_id'):
                    ids=gg.index.to_numpy();w=gg.path_occurrences.to_numpy(float);w/=w.sum()
                    x=self.X[ids];y=self.Y[ids]
                    x=x-np.sum(x*w[:,None],axis=0);y=y-np.sum(y*w[:,None],axis=0)
                    image=gg.image_id.iloc[0];pool=gg.pool_id.iloc[0]
                    group_mass=1/image_n/targets_per_image[image]/n_per_target[pool]
                    w=w*group_mass;total_weight+=w.sum()
                    xx+=x.T@(x*w[:,None]);xy+=x.T@(y*w[:,None]);y2+=np.sum(y*y*w[:,None],axis=0);rowcount+=len(gg)
                    self.weight_comparison.append({'stratum':stratum,'building':b,'image_id':image,'pool_id':pool,'n':int(gg.k.iloc[0]),'group_id':groupid,'unique_teams':len(gg),'old_group_mass':1/image_n/old_groups_per_image[image],'target_equal_group_mass':group_mass,'targets_in_image':int(targets_per_image[image]),'n_levels_in_target':int(n_per_target[pool])})
                assert np.isclose(total_weight,1)
                self.stats[(stratum,b)]=(xx,xy,y2)
                self.statsmeta.append(dict(stratum=stratum,building=b,images=image_n,targets=g.pool_id.nunique(),groups=g.group_id.nunique(),unique_teams=rowcount,total_building_weight=float(total_weight)))

def main():
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);args=ap.parse_args()
    out=ROOT/'target_rfuse';out.mkdir(parents=True,exist_ok=True)
    source=args.repo/'research/data/releases/v2.1/admitted_space_extension/fusion_role_classification/NATURAL_TRAINING_ENDPOINTS.csv.gz'
    config={'data':'v2.1','commit':'a476461d7ede8db95da43de4139e612c05e618bc','new_method_ids':['TARGET_RFUSE_GEOM_K2','TARGET_RFUSE_GEOM_K3','TARGET_RFUSE_GEOMQ_K2','TARGET_RFUSE_GEOMQ_K3'],'centering':'existing correct pool_id x n occurrence-weighted center retained','changed':'building equal -> image equal -> legal target equal -> feasible n equal -> occurrence weight','original_weighting':'building -> image -> all target*n groups, making target mass proportional to feasible n count','alpha_grid':core.ALPHAS,'domains':core.FAMILIES,'formal_difficulty':'unknown admitted targets used only in all stratum; not copied from primary target','selection':'inner buildings normalized response loss, all candidate alphas saved; outer excludes target building across all spaces','new_fusion':False,'source_path':str(source.relative_to(args.repo)),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source_core_sha256':hashlib.sha256((WORK/'stage01/old_sources/reverse/code/learn_natural_fusion_roles.py').read_bytes()).hexdigest(),'frozen_before_new_team_comparison':True}
    js(config,out/'CONFIG_BEFORE_TEAM_RESULTS.json')
    study=TargetStudy(source)
    current=pd.read_csv(WORK/'targets/POOL_TARGET_CONDITIONS.csv')
    assert study.input.pool_id.isin(current.pool_id).all()
    inv=study.input.groupby(['support_origin','pool_id','image_id','building'],dropna=False).agg(inventory_endpoints=('team_key','size'),training_endpoints=('training_eligible','sum'),n_min=('k','min'),n_max=('k','max'),n_levels=('k','nunique')).reset_index()
    save(inv,out/'TRAINING_TARGET_INVENTORY.csv')
    save(pd.DataFrame(study.weight_comparison),out/'EXACT_OLD_NEW_GROUP_WEIGHTS.csv.gz')
    save(pd.DataFrame(study.statsmeta),out/'BUILDING_STRATUM_SUPPORT.csv')
    roster=pd.read_csv(ROOT/'BASELINE20_LABELS_ALL_LOBO.csv.gz')[['worker_id','origin']].drop_duplicates().sort_values('worker_id')
    tabs={k:[] for k in ['LABELS','CENTERS','REGISTRY','SELECTION','INNER_ERRORS','FEATURES']};encodings={}
    for i,outer in enumerate(['ALL']+study.buildings):
        selected,selection,checks=study.select(outer)
        tabs['SELECTION'].append(selection);tabs['INNER_ERRORS'].append(checks)
        for family,alpha in selected.items():
            f=study.response_features(outer,alpha);f['family']=family
            l,c,r,enc=core.labels_for(f,family,roster)
            for d in [l,c,r]:
                d['method']='TARGET_'+d.method;d['family']='TARGET_'+d.family
            l['underlying_data_version']='v2.1';l['source_stage']='new_target_equal_rfuse';l['history_scope']='ordinary_manual_all_admitted_targets_n10_to24';l['evaluation_condition']='manual_and_semi_separately'
            l['label_formed_from']='manual_actual_natural_fusion_response'
            for key,data in [('LABELS',l),('CENTERS',c),('REGISTRY',r),('FEATURES',f)]:tabs[key].append(data)
            encodings[outer+':'+family]=enc
        for key,frames in tabs.items():
            save(pd.concat(frames,ignore_index=True),out/(key+'_ALL_LOBO.csv.gz'))
        js(encodings,out/'TRANSFORMS_ALL_LOBO.json')
        js({'completed_folds':i+1,'total_folds':len(study.buildings)+1,'status':'complete' if i==len(study.buildings) else 'running','selected_last_fold':selected},out/'PROGRESS.json')
        print('target RFUSE',outer,selected,flush=True)
    labels=pd.concat(tabs['LABELS'],ignore_index=True);centers=pd.concat(tabs['CENTERS'],ignore_index=True)
    save(labels[labels.heldout_building.eq('ALL')],out/'LABELS_ALL.csv')
    save(centers[centers.heldout_building.eq('ALL')],out/'CENTERS_ALL.csv')
    checks={'inventory_endpoints':len(study.input),'training_endpoints':len(study.data),'training_pools':study.data.pool_id.nunique(),'training_images':study.data.image_id.nunique(),'buildings':len(study.buildings),'eligible_other_target_endpoints':int(study.data.support_origin.eq('other_admitted_target').sum()),'eligible_other_target_pools':int(study.data[study.data.support_origin.eq('other_admitted_target')].pool_id.nunique()),'multi_target_images':int(study.data.groupby('image_id').pool_id.nunique().gt(1).sum()),'old_centering_target_separate':True,'all_pool_ids_in_current_legal_inventory':True,'target_equal_reweight_actual_refit':True,'labels_rows':len(labels)}
    js(checks,out/'COMPLETION.json')
    print(checks)
if __name__=='__main__':main()

