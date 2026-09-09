"""Additional checks: Manual-only classification, matched onset comparisons.
Uses independent estimators in latest_audit, not the original worker functions.
"""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage,cut_tree
import latest_audit as a

def manual_only():
    d=a.csv(a.REF+'response_measurements.csv.gz');d=d[(d.measurement_status=='computable')&(d.raw_condition=='manual')]
    pred=[];members=[]
    for cohort in ['all26','current20']:
      sample=d if cohort=='all26' else d[d.current20_member.str.lower()=='true']
      sample=sample.copy();sample['context_key']=sample.image_id
      assert not sample.duplicated(['image_id','worker_id']).any()
      for metric in ['ospa30','ospa60']:
       for b,g in sample.groupby('building_id'):
        train=sample[sample.building_id!=b]
        try:e=a.fit_effect(train,metric)
        except ValueError:continue
        z=g[g.worker_id.isin(e.index)].copy();z=z[z.groupby('context_key').worker_id.transform('size')>=2]
        if z.empty:continue
        target=z[metric]-z.groupby('context_key')[metric].transform('mean')
        models={'continuous':e}
        lab=pd.Series(1+(e>e.median()).astype(int),index=e.index)
        models['median_two']=e.groupby(lab).transform('mean')
        for k in [2,3,4]:
          labels=cut_tree(linkage(e.to_numpy()[:,None],method='ward'),n_clusters=k).ravel();l=pd.Series(labels,index=e.index)
          models['ward_'+str(k)]=e.groupby(l).transform('mean')
        for model,effect in models.items():
          yp=z.worker_id.map(effect);yp-=yp.groupby(z.context_key).transform('mean')
          temp=z[['canonical_annotation_id','image_id','building_id','worker_id','reference_basis']].copy()
          temp['target']=target;temp['prediction']=yp;temp['baseline_sse']=target**2;temp['sse']=(target-yp)**2;temp['model']=model;temp['cohort']=cohort;temp['metric']=metric;pred.append(temp)
    p=pd.concat(pred,ignore_index=True);a.save('manual_only_heldout_predictions.csv.gz',p);result=[]
    for key,g in p.groupby(['cohort','metric','model']):
      for evaluation,z in [('all_scoreable',g),('reviewed_reference_only',g[g.reference_basis=='reviewed_reference']),('gt_assumed_only',g[g.reference_basis=='gt_assumed_correct'])]:
        b=z.groupby('building_id')[['sse','baseline_sse']].mean();result.append(dict(zip(['cohort','metric','model'],key))|dict(evaluation=evaluation,rows=len(z),images=z.image_id.nunique(),buildings=len(b),gain_building_equal=1-b.sse.mean()/b.baseline_sse.mean(),buildings_improved=int((b.sse<b.baseline_sse).sum()),note='same_scoreable_heldout_peers_within_image; reference_consistency_not_explicit_rule_truth'))
    a.save('manual_only_group_validation.csv',result)

def matched_N():
    results=[];records=[];sourcecheck=[]
    for cohort in ['with_workers','without_workers']:
      curves=a.csv(a.MULTI+cohort+'/replay/stability_curves.csv');curves=curves[(curves.lookahead==5)&(curves.min_support==2)&np.isclose(curves.epsilon,.1)&curves.config.isin(['q_0.950','ospa30_t6'])]
      lookup={(i,c):g.sort_values('k')[['stable_lower','stable_upper']].to_numpy() for (i,c),g in curves.groupby(['image_id','config'])}
      folder=a.MULTI+'comparison/common_transfer_'+cohort+'/'
      folds=a.csv(folder+'folds.csv.gz');folds=folds[(folds.source_n==1)&folds.config.isin(['q_0.950','ospa30_t6'])]
      groups=a.csv(folder+'baseline_groups.csv');groups=groups[groups.source_n==1]
      cache={}
      def nvalue(image,config,last):
        key=(image,config,last)
        if key not in cache:
          arr=lookup[image,config][:last];k=np.arange(1,last+1);lo,hi,state=a.onset(k,arr[:,0],arr[:,1]);cache[key]=(hi if state=='identified' else np.nan,state)
        return cache[key]
      for r in folds.to_dict('records'):
        b,config,last=r['building_id'],r['config'],int(r['k_max']);src=json.loads(r['source_images_json'])[0];targets=json.loads(r['target_images_json'])
        Nsource,source_state=nvalue(src,config,last)
        outs=[json.loads(s)[0] for s in groups[groups.building_id==b].source_images_json]
        source=np.stack([lookup[i,config][:last] for i in outs]);target=np.stack([lookup[i,config][:last] for i in targets])
        low=np.maximum(0,np.maximum(source[:,None,:,0]-target[None,:,:,1],target[None,:,:,0]-source[:,None,:,1])).mean()
        high=np.maximum(abs(source[:,None,:,0]-target[None,:,:,1]),abs(source[:,None,:,1]-target[None,:,:,0])).mean()
        err=max(abs(low-r['outside_error_lower']),abs(high-r['outside_error_upper']));assert err<1e-10
        sourcecheck.append(dict(cohort=cohort,config=config,building=b,fold=r['fold_id'],max_abs_error=err))
        for t in targets:
          nt,ts=nvalue(t,config,last)
          for outside in outs:
            no,os=nvalue(outside,config,last);common=np.isfinite([Nsource,nt,no]).all()
            records.append(dict(cohort=cohort,config=config,building=b,source=src,target=t,outside_source=outside,
                common_N_budget=int(r['common_people_budget']),source_state=source_state,target_state=ts,outside_state=os,common_identified=common,
                same_error=abs(Nsource-nt) if common else np.nan,outside_error=abs(no-nt) if common else np.nan))
    p=pd.DataFrame(records);a.save('one_source_matched_N_records.csv.gz',p);a.save('outside_single_source_numerical_checks.csv',sourcecheck)
    for key,g in p.groupby(['cohort','config']):
        z=g[g.common_identified];b=z.groupby('building')[['same_error','outside_error']].mean()
        results.append(dict(cohort=key[0],config=key[1],comparison_triples=len(g),matched_identified_triples=len(z),
            all_target_images=g.target.nunique(),matched_target_images=z.target.nunique(),all_buildings=g.building.nunique(),matched_buildings=z.building.nunique(),
            same_MAE_building_equal=b.same_error.mean(),outside_MAE_building_equal=b.outside_error.mean(),
            benefit=(b.outside_error-b.same_error).mean(),warning='one-source, common-identified conditional comparison; not all-target reliability; triples dependent'))
    a.save('one_source_matched_N_summary.csv',results)

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args();a.R=args.repo;a.O=args.out
    manual_only();matched_N();a.save('SOURCE_MANIFEST_focused.json',dict(baseline=a.BASELINE,files=list(a.used.values())))
    print('FOCUSED CHECKS DONE')
if __name__=='__main__':main()
