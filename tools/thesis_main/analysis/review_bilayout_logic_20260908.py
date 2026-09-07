"""Read-only audit of pinned evidence; not a new neural inference run.
python review_bilayout_logic_20260908.py --repo PATH --out RESULTS
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from itertools import combinations
from collections import defaultdict
import numpy as np
import pandas as pd
from scipy.stats import hypergeom
from scipy.integrate import trapezoid
from shapely.geometry import Point, LineString

def save(out,name,rows):
    (out/name).parent.mkdir(parents=True,exist_ok=True)
    (rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)).to_csv(out/name,index=False,float_format='%.12g')

def independent_recovery(strata,draws,target):
    target=np.asarray(target,dtype=int)
    if len(target)==0 or (target<=0).any():raise ValueError('Nonempty reference groups required')
    if len(strata)!=len(draws) or sum(draws)<=0:raise ValueError('Invalid draws')
    k=sum(draws);p=target/target.sum();tv=missing=seen=0.
    for j,pj in enumerate(p):
        pmf=np.array([1.])
        for counts,n in zip(strata,draws):
            counts=np.asarray(counts,int);N=int(counts.sum())
            if len(counts)!=len(p) or (counts<0).any() or not 0<=n<=N:raise ValueError('Invalid stratum')
            q=np.array([1.]) if n==0 else hypergeom.pmf(np.arange(n+1),N,int(counts[j]),n)
            pmf=np.convolve(pmf,q)
        assert np.isclose(pmf.sum(),1,atol=1e-12)
        tv+=.5*np.sum(pmf*np.abs(np.arange(len(pmf))/k-pj));missing+=pj*pmf[0];seen+=1-pmf[0]
    return dict(expected_tv=tv,expected_missing_mass=missing,expected_cluster_fraction=seen/len(p))

def cycle_equal(x,y):
    x=np.asarray(x,float);y=np.asarray(y,float)
    if x.shape!=y.shape or x.ndim!=2 or len(x)%2:return False
    xx=x.reshape(-1,4);yy=y.reshape(-1,4)
    return any(np.array_equal(xx,np.roll(z,k,axis=0)) for z in (yy,yy[::-1]) for k in range(len(xx)))

def main(repo,out):
    repo=repo.resolve();out.mkdir(parents=True,exist_ok=True);sys.path.insert(0,str(repo))
    from tools.thesis_main.analysis.prepare_uncertainty_visual_review import helpers
    from tools.thesis_main.analysis.analyze_uncertainty_handoff import distribution_recovery,user_bottom_order
    audit,_=helpers();a,im,pa,me,versions,models,refs,raw,norm=audit.load()
    base=repo/'analysis_results/uncertainty_followup_analysis_20260908_v1';conf=base/'confirmed_20260908'
    qa=dict(canonical_rows=len(a),unique_images=a.image_id.nunique(),workers=a.worker_id.nunique(),contexts=a.context_key.nunique(),source_commit='a704dd3d07070c3442c05041dee7ed61e91e3fad',new_human_observations=0,new_neural_inference_runs=0)
    by=defaultdict(dict)
    for m in models:
        if m['model_family']=='Bi-Layout':by[m['image_id']][m['head']]=m
    old=pd.read_csv(base/'model_distances.csv').set_index('image_id');br=[];errors=[]
    for image,h in sorted(by.items()):
        assert set(h)=={'enclosed','extended'};x,y=[h[k]['points_1024x512'] for k in ('enclosed','extended')]
        row=dict(image_id=image,building=image.split('_')[0],split=h['enclosed']['split'],historical=image in set(a.image_id),raw_sequence_equal=x==y,cycle_equal=cycle_equal(x,y),n_ceiling_floor_pairs_enclosed=len(x)//2,n_ceiling_floor_pairs_extended=len(y)//2)
        for metric in ['floor','band','linear','solid']:
            try:
                if metric=='floor':v=audit.dp(audit.footprint(x),audit.footprint(y))
                else:v=audit.db(audit.band(x,linear=metric=='linear'),audit.band(y,linear=metric=='linear'),solid=metric=='solid')
                row[metric]=v;row[metric+'_status']='computable'
            except (ValueError,TypeError,IndexError) as e:row[metric]=np.nan;row[metric+'_status']=str(e)
            v0=float(old.loc[image,metric])
            if np.isfinite(v0) and np.isfinite(row[metric]):errors.append(abs(v0-row[metric]))
            assert (np.isnan(v0) and np.isnan(row[metric])) or np.isclose(v0,row[metric],rtol=0,atol=1e-12),(image,metric)
        br.append(row)
    bd=pd.DataFrame(br);save(out,'bilayout_recomputed_per_image.csv',bd);summary=[]
    for name,g in [('all_380',bd),('historical',bd[bd.historical]),('candidate',bd[~bd.historical]),('test',bd[bd.split=='test']),('val',bd[bd.split=='val'])]:
        row=dict(cohort=name,images=len(g),raw_sequence_equal=int(g.raw_sequence_equal.sum()),cycle_equal=int(g.cycle_equal.sum()))
        for metric in ['floor','band','linear','solid']:
            z=g[metric].dropna();row.update({metric+'_computable':len(z),metric+'_zero':int((z.abs()<=1e-12).sum()),metric+'_median':z.median(),metric+'_p90':z.quantile(.9)})
            for eps in [.005,.01,.02,.05,.1]:row[metric+'_le_'+str(eps)]=int((z<=eps).sum())
        summary.append(row)
    save(out,'bilayout_gap_summary.csv',summary)
    qa['Bi_paired_images']=len(bd);qa['Bi_distance_max_difference']=float(max(errors,default=0.))
    save(out,'bilayout_zero_geometry_not_raw_equal.csv',bd[(bd.floor.abs()<=1e-12)&~bd.raw_sequence_equal])
    tests=[]
    for sizes in ([2,2],[3,2,1],[2,1,1,1]):
        labels=np.repeat(np.arange(len(sizes)),sizes)
        for k in range(1,len(labels)+1):
            estimates=[]
            for s in combinations(range(len(labels)),k):
                q=np.bincount(labels[list(s)],minlength=len(sizes))/k;p=np.array(sizes)/sum(sizes)
                estimates.append([np.abs(q-p).sum()/2,np.sum(p[q==0]),np.mean(q>0)])
            e=np.mean(estimates,axis=0);z=independent_recovery([sizes],[k],sizes);published=distribution_recovery([sizes],[k],sizes)
            assert np.allclose(e,list(z.values()),atol=1e-12)
            assert np.allclose(e,list(published.values()),atol=1e-12)
            tests.append(dict(sizes=str(sizes),k=k,max_abs_error=float(np.max(np.abs(e-list(z.values()))))))
    save(out,'hypergeom_exhaustive_checks.csv',tests)
    current=set(a[a.current20_member.map(audit.yes)].canonical_annotation_id);saved=pd.read_csv(conf/'distribution_recovery.csv');rec=[];mx=0.
    for p in pa[(pa.version=='extended73')&(pa.partition_status=='unique')].to_dict('records'):
        members=me[me.partition_id==p['partition_id']]
        assert len(members)==int(p['member_count']) and not members.worker_id.duplicated().any()
        sizes=members.groupby('cluster_id').size();inside=members[members.canonical_annotation_id.isin(current)].groupby('cluster_id').size().reindex(sizes.index,fill_value=0)
        for pool,ss in [('all_archived',sizes),('current20',inside)]:
            for k in range(1,min(20,int(ss.sum()))+1):
                v=independent_recovery([ss.values],[k],sizes.values);q=saved[(saved.partition_id==p['partition_id'])&(saved.pool==pool)&(saved.k==k)];assert len(q)==1
                err=max(abs(v[key]-float(q.iloc[0][key])) for key in v);mx=max(mx,err)
                rec.append(dict(partition_id=p['partition_id'],image_id=p['image_id'],building=p['image_id'].split('_')[0],stage=p['stage'],condition=p['condition'],pool=pool,k=k,N=int(ss.sum()),current20_complete=int(inside.sum())==20,**v,max_saved_error=err))
    rdf=pd.DataFrame(rec);assert len(rdf)==len(saved);assert mx<1e-12;save(out,'distribution_independently_recomputed.csv',rdf);qa['distribution_rows_reproduced']=len(rec);qa['distribution_max_error']=mx
    fixed=rdf[rdf.current20_complete];save(out,'fixed51_independent_summary.csv',fixed.groupby(['pool','k']).agg(contexts=('partition_id','size'),TV=('expected_tv','mean'),missing_mass=('expected_missing_mass','mean'),coverage=('expected_cluster_fraction','mean')).reset_index())
    savedmix=pd.read_csv(conf/'roster_mixture.csv');mix=[]
    for q in savedmix.to_dict('records'):
        members=me[me.partition_id==q['partition_id']];sizes=members.groupby('cluster_id').size()
        inside=members[members.canonical_annotation_id.isin(current)].groupby('cluster_id').size().reindex(sizes.index,fill_value=0)
        outside=sizes-inside;m=int(q['outside_current20_draws']);k=int(q['total_k'])
        v=independent_recovery([inside.values,outside.values],[k-m,m],sizes.values)
        err=max(abs(v[key]-float(q[key])) for key in v);assert err<1e-12
        mix.append(dict(partition_id=q['partition_id'],outside_draws=m,outside_available=int(outside.sum()),current_complete=int(inside.sum())==20,**v,max_saved_error=err))
    save(out,'roster_mixture_independent.csv',mix);qa['roster_mixture_rows_reproduced']=len(mix)
    savedpred=pd.read_csv(conf/'building_leave_image_out.csv');checks=[]
    for q in savedpred.to_dict('records'):
        g=fixed[(fixed.pool==q['pool'])&(fixed.k==q['k'])];test=g[g.partition_id==q['partition_id']].iloc[0];train=g[g.image_id!=test.image_id]
        if q['conditioning']=='same_stage_condition':train=train[(train.stage==test.stage)&(train.condition==test.condition)]
        same=train[train.building==test.building];assert same.image_id.nunique()>=2
        d=max(abs(float(q['observed'])-test[q['metric']]),abs(float(q['same_building_prediction'])-same[q['metric']].mean()),abs(float(q['global_prediction'])-train[q['metric']].mean()))
        assert d<1e-12;checks.append(dict(partition_id=q['partition_id'],pool=q['pool'],k=q['k'],metric=q['metric'],conditioning=q['conditioning'],max_abs_error=d,train_images=same.image_id.nunique(),training_building_is_test_building=True))
    save(out,'building_prediction_checks.csv',checks);qa['building_prediction_rows_reproduced']=len(checks)
    confirmations=json.loads((conf/'user_confirmations.json').read_text());geometry=[]
    for c in confirmations:
        rawfile=json.loads((repo/c['source']).read_text(encoding='utf-8-sig'));task=next(t for t in rawfile if t['id']==c['task_id']);ann=next(v for v in task['annotations'] if v['id']==c['annotation_id']);kp=[v for v in ann['result'] if v['type']=='keypointlabels'];pts=np.array([[r['value']['x']*10.24,r['value']['y']*5.12] for r in kp]);assert np.array_equal(pts,c['raw_points'])
        ids=user_bottom_order(pts,c['user_bottom_order']);assert ids==c['raw_point_ids'] and np.array_equal(pts[ids],c['derived_points'])
        q=pts[ids];poly=audit.footprint(q);f,t,_=audit.lift(q);edges=np.roll(f[:,[0,2]],-1,axis=0)-f[:,[0,2]];angles=np.degrees(np.arctan2(edges[:,1],edges[:,0]));weights=np.linalg.norm(edges,axis=1)
        theta=np.arange(0,90,.05);residual=np.average(np.abs((angles[None,:]-theta[:,None]+45)%90-45),axis=1,weights=weights).min()
        radius=np.linalg.norm(f[:,[0,2]],axis=1).max()*2;hits=[]
        for phi in (np.arange(720)+.37)*2*np.pi/720:
            inter=poly.boundary.intersection(LineString([(0,0),(radius*np.cos(phi),radius*np.sin(phi))]));hits.append(1 if inter.geom_type=='Point' else len(inter.geoms))
        try:audit.band(q);band_status='computable'
        except ValueError as e:band_status=str(e)
        geometry.append(dict(case_id=c['case_id'],point_count=len(q),all_source_coordinates_retained=True,area=poly.area,camera_inside=poly.contains(Point(0,0)),valid_polygon=poly.is_valid,axis_residual=residual,nonstar_fraction=np.mean(np.array(hits)>1),band_status=band_status,ceiling_height_range=np.ptp(t[:,1]),represents_geometry_adjudication=False))
    save(out,'confirmed_geometry_independent.csv',geometry)
    x=np.linspace(-8,8,20001);normal=lambda m:np.exp(-(x-m)**2/2)/np.sqrt(2*np.pi);info=[]
    for gap in [0,.05,.1,.25,.5,1.,2.,4.]:
        p0,p1=normal(-gap/2),normal(gap/2);f=.5*(p0+p1);I=float(trapezoid((p1-p0)**2/np.maximum(f,1e-300),x));n_for_se=np.nan if I==0 else 1/(.1**2*I)
        info.append(dict(mean_gap_in_noise_SD=gap,mixing_weight=.5,per_observation_Fisher_information=I,local_information_n_for_SE_point1=n_for_se,status='analytic_gaussian_mixture_illustration_not_estimated_human_sample_size'))
    assert info[0]['per_observation_Fisher_information']==0;save(out,'two_candidate_identifiability_math.csv',info)
    qa['warnings']=['One saved inference per image: repeat-run stability untested','380 selected images are not full 648-image inference set','Recovery targets old empirical clusters not accepted alternatives','Floor validity is not full Manhattan/ceiling/scope validity','X pairing changes adjacency','Same-building prediction is not new-building validation']
    (out/'AUDIT_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2));print(json.dumps(qa,ensure_ascii=False,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--out',type=Path,required=True);ns=p.parse_args();main(ns.repo,ns.out)
