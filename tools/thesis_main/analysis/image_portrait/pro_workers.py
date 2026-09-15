"""E: train-outside-building worker profiles, all information blocks and group counts.

Historical axes retain their OSPA/time/reference provenance. Current endpoint
predictions are measured anew; rule correctness and geometric similarity remain
separate axes. Missing persons are never made into a class.
"""
from __future__ import annotations
import argparse,collections,itertools,json,math,time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage,cut_tree
from sklearn.metrics import adjusted_rand_score,silhouette_score
from tools.thesis_main.analysis.fit_worker_evidence_strata_20260908 import sufficient,solve,informative
from tools.thesis_main.analysis.image_portrait.pro_core import *
from tools.thesis_main.analysis.image_portrait.pro_core import _d_mask
BLOCKS={'Q':['quality'],'T':['time'],'S':['scope_reject','scope_accept'],'B':['edit','benefit']}
COMBOS={''.join(c):[BLOCKS[b] for b in c] for k in range(1,5)for c in itertools.combinations(BLOCKS,k)}
COMBOS['quality_time_edit']=[['quality'],['time'],['edit']]
ALL_AXES=[a for b in BLOCKS.values() for a in b]

class ProfileCache:
    """Exact within-task intercept elimination; training support checked per axis."""
    def __init__(self,data):
        self.data=data.copy();self.caches={};self.memo={}
        for axis,g in data.groupby('axis'):
            g=informative(g)
            if len(g):self.caches[axis]=sufficient(g)
    def fit(self,excluded=(),minimum_rows=6,minimum_buildings=3):
        key=(tuple(sorted(excluded)),minimum_rows,minimum_buildings)
        if key in self.memo:return self.memo[key]
        values={};audit=[]
        for axis,s in self.caches.items():
            weights=np.array([b not in set(excluded) for b in s['buildings']],float);nr=weights@s['support'];nb=weights@(s['support']>0);present=nr>0
            if present.sum()<2:continue
            local=dict(s,workers=np.array(s['workers'])[present].tolist(),A=s['A'][:,present][:,:,present],rhs=s['rhs'][:,present],support=s['support'][:,present])
            effect,status,rank=solve(local,weights)
            for j,w in enumerate(local['workers']):
                nrw=nr[present][j];nbw=nb[present][j];eligible=status=='usable' and nrw>=minimum_rows and nbw>=minimum_buildings
                audit.append(dict(axis=axis,worker_id=w,rows=int(nrw),buildings=int(nbw),eligible=eligible,fit_status=status,rank=rank,effect=float(effect[j]) if effect is not None else np.nan))
                if eligible:values.setdefault(w,{})[axis]=float(effect[j])
        frame=pd.DataFrame.from_dict(values,orient='index');frame.index.name='worker_id';self.memo[key]=(frame,pd.DataFrame(audit));return self.memo[key]


def inputs():
    old=pd.DataFrame(load(BUNDLE/'history/worker_axes_historical.jsonl.gz'));old=old[old.main_worker_included].copy();old['value']=old.value.astype(float)
    r=pd.read_csv(OUT/'human/response_metrics.csv.gz');r=r[r.main_worker_included].copy();rows=[]
    for arm,g in r.groupby('raw_condition'):
        if arm not in ['manual','semi','oos']:continue
        for col,new in [('quality','reference_error'),('active_seconds','log_active_seconds'),('effective_point_count','point_count'),('band_width_bias_pixels','reference_band_bias'),('scope','scope_rejection_propensity')]:
            if col=='scope':q=g[g.scope!='unknown'].copy();q['value']=(q.scope!='normal').astype(float)
            elif col=='active_seconds':q=g[g[col].notna()].copy();q['value']=np.log1p(q[col])
            else:q=g[g[col].notna() & (g.geometry_valid if col in ['quality','effective_point_count','band_width_bias_pixels'] else True)].copy();q['value']=q[col].astype(float)
            if not len(q):continue
            q['axis']=arm+'__'+new;q['building_id']=q.building
            # Current conditions stay separate; stage/context intercepts retained.
            rows.append(q[['canonical_annotation_id','worker_id','image_id','building_id','context_key','value','axis']])
    for axis in ['scope_reject','scope_accept']:
        q=old[old.axis==axis].copy();q['axis']='historical_rule__'+axis;rows.append(q[['canonical_annotation_id','worker_id','image_id','building_id','context_key','value','axis']])
    current=pd.concat(rows,ignore_index=True)
    write_csv('E/current_axes.csv.gz',current);write_csv('E/historical_axis_inventory.csv',old.groupby('axis').agg(rows=('value','size'),workers=('worker_id','nunique'),images=('image_id','nunique'),buildings=('building_id','nunique'),minimum=('value','min'),maximum=('value','max')).reset_index())
    return old,current,r


def standardize_blocks(p,blocks):
    pieces=[];cols=[]
    for axes in blocks:
        x=p[axes].to_numpy(float);sd=x.std(0)
        if np.any(sd<1e-10):return None,dict(status='constant_axis',axes=[axes[j]for j in np.flatnonzero(sd<1e-10)])
        pieces.append((x-x.mean(0))/sd/np.sqrt(len(axes)));cols+=axes
    return np.column_stack(pieces),dict(status='ok',axes=cols)


def labels_for(x,p,k,first_axis):
    lab=cut_tree(linkage(x,method='ward'),n_clusters=k).ravel()
    # Only an auditable within-fold naming convention, not universal semantics.
    order=sorted(set(lab),key=lambda z:(float(p.loc[lab==z,first_axis].mean()),tuple(p.index[lab==z])))
    ren={old:new for new,old in enumerate(order)};return np.array([ren[z]for z in lab],int)


def evaluate_in_image(test,pred,metadata):
    """Target peer centering is the evaluation contrast, never a fitted feature."""
    d=test[test.worker_id.isin(pred)].copy();d['pred']=d.worker_id.map(pred);d=d[np.isfinite(d.pred)]
    output=[]
    for (image,context),g in d.groupby(['image_id','context_key']):
        if g.worker_id.nunique()<2:continue
        assert not g.worker_id.duplicated().any()
        actual=g.value.to_numpy()-g.value.mean();forecast=g.pred.to_numpy()-g.pred.mean()
        output.append(dict(**metadata,image_id=image,context=context,building=g.building_id.iloc[0],n_workers=len(g),baseline_MAE=float(np.mean(np.abs(actual))),method_MAE=float(np.mean(np.abs(actual-forecast))),baseline_MSE=float(np.mean(actual**2)),method_MSE=float(np.mean((actual-forecast)**2))))
    return output


def worker_evaluation(old,current):
    start=time.monotonic();oc=ProfileCache(old);cc=ProfileCache(current);buildings=sorted(set(old.building_id)|set(current.building_id));
    memberships=[];profiles=[];scores=[];capacity=[];centroids=[];silhouette=[];failures=[];mappings=[]
    for building in buildings:
        op,oa=oc.fit([building]);cp,ca=cc.fit([building]);oa['heldout_building']=building;oa['source']='historical_axes';ca['heldout_building']=building;ca['source']='current_endpoints';profiles += [oa,ca]
        test=current[current.building_id==building]
        common=op.dropna(subset=[a for a in ALL_AXES if a in op]) if set(ALL_AXES)<=set(op) else op.iloc[:0]
        # Target-specific continuous worker effects are a no-typing reference.
        for axis,g in test.groupby('axis'):
            if axis not in cp:continue
            values=cp[axis].dropna().to_dict()
            scores+=evaluate_in_image(g,values,dict(heldout_building=building,panel='native',information='endpoint_history',k=0,algorithm='continuous_endpoint_effect',axis=axis))
        for panel in ['native','common_all_blocks']:
            for info,blocks in COMBOS.items():
                required=[a for b in blocks for a in b]
                if not set(required)<=set(op):
                    failures.append(dict(heldout_building=building,panel=panel,information=info,reason='axis_unavailable'));continue
                p=(op if panel=='native' else common).dropna(subset=required).copy()
                if len(p)<4:
                    failures.append(dict(heldout_building=building,panel=panel,information=info,reason='fewer_than_four_qualified_workers',n=len(p)));continue
                x,meta=standardize_blocks(p,blocks)
                if x is None:
                    failures.append(dict(heldout_building=building,panel=panel,information=info,reason=meta['status'],n=len(p)));continue
                # Continuous block-to-current-endpoint mapping uses training-only
                # task-adjusted worker outcomes. Fixed alpha=10 is a new baseline,
                # not selected after seeing target-building outcomes.
                for axis,g in test.groupby('axis'):
                    if axis not in cp:continue
                    common_workers=p.index.intersection(cp[axis].dropna().index);jx=p.index.get_indexer(common_workers)
                    if len(jx)<4:continue
                    xx=x[jx];yy=cp.loc[common_workers,axis].to_numpy();xm=xx.mean(0);ym=yy.mean();beta=np.linalg.solve((xx-xm).T@(xx-xm)+10*np.eye(x.shape[1]),(xx-xm).T@(yy-ym));pr=(x-xm)@beta+ym
                    pred=dict(zip(p.index,pr));gg=g[g.worker_id.isin(common_workers)] if panel=='common_all_blocks' else g
                    scores+=evaluate_in_image(gg,pred,dict(heldout_building=building,panel=panel,information=info,k=0,algorithm='continuous_blocks_ridge10',axis=axis))
                    mappings.append(dict(heldout_building=building,panel=panel,information=info,axis=axis,coefficients=json.dumps(beta.tolist()),center=json.dumps(xm.tolist()),outcome_center=ym,n_workers=len(jx)))
                for k in range(2,len(p)//2+1):
                    labels=labels_for(x,p,k,required[0]);sizes=collections.Counter(labels)
                    sil=float(silhouette_score(x,labels)) if min(sizes.values())>=2 else np.nan
                    silhouette.append(dict(heldout_building=building,panel=panel,information=info,k=k,n_workers=len(p),smallest_group=min(sizes.values()),singleton_groups=sum(v==1 for v in sizes.values()),training_silhouette=sil))
                    for w,l in zip(p.index,labels):memberships.append(dict(heldout_building=building,panel=panel,information=info,k=k,worker_id=w,label=chr(65+l),class_training_members=sizes[l],supported_class=sizes[l]>=2))
                    for axis,g in test.groupby('axis'):
                        if axis not in cp:continue
                        training_target=cp.reindex(p.index)[axis];pred={}
                        eligible_worker=set(p.index[training_target.notna()])
                        for l in sorted(sizes):
                            mask=(labels==l)&training_target.notna().to_numpy();value=float(training_target.iloc[np.flatnonzero(mask)].mean()) if mask.any() else np.nan
                            for w in p.index[labels==l]:pred[w]=value
                            centroids.append(dict(heldout_building=building,panel=panel,information=info,k=k,axis=axis,label=chr(65+l),training_target_effect=value,n_target_qualified_workers=int(mask.sum())))
                        gg=g[g.worker_id.isin(eligible_worker)] if panel=='common_all_blocks' else g
                        scores+=evaluate_in_image(gg,pred,dict(heldout_building=building,panel=panel,information=info,k=k,algorithm='ward',axis=axis))
                    # Exact real-person combination capacities; unknown workers do
                    # not contribute to any category or synthetic combination.
                    for (image,arm),g in current[current.building_id==building].groupby(['image_id','axis']):
                        if arm not in ['manual__reference_error','semi__reference_error']:continue
                        workers=set(g.worker_id);cnt=collections.Counter(chr(65+l)for w,l in zip(p.index,labels) if w in workers)
                        n=sum(cnt.values())
                        for size in [2,3,4]:
                            allc=math.comb(n,size) if n>=size else 0;pure=sum(math.comb(v,size)for v in cnt.values()if v>=size)
                            distinct=sum(math.prod(cnt[z]for z in comb)for comb in itertools.combinations(cnt,size)) if len(cnt)>=size else 0
                            capacity.append(dict(heldout_building=building,image_id=image,axis=arm,panel=panel,information=info,k=k,people=size,n_observed_workers=len(workers),n_classified_workers=n,n_unknown=len(workers)-n,all_combinations=allc,pure_combinations=pure,all_distinct_combinations=distinct,class_counts=json.dumps(dict(sorted(cnt.items())))))
        print('E held out',building,'old qualified',len(op),'common',len(common),'score rows',len(scores),flush=True)
    write_csv('E/worker_axis_profiles_oof.csv.gz',pd.concat(profiles,ignore_index=True));write_csv('E/worker_memberships_oof.csv.gz',memberships);write_csv('E/heldout_image_contrasts.csv.gz',scores);write_csv('E/combination_capacity.csv.gz',capacity);write_csv('E/type_target_centroids.csv.gz',centroids);write_csv('E/training_group_count_scores.csv',silhouette);write_csv('E/profile_failures.csv',failures);write_csv('E/continuous_block_mappings.csv.gz',mappings)
    a=pd.DataFrame(scores);summary=[]
    for key,g in a.groupby(['panel','information','k','algorithm','axis']):
        im=g.groupby(['building','image_id'])[['baseline_MAE','method_MAE','baseline_MSE','method_MSE']].mean();bm=im.groupby('building').mean()
        summary.append(dict(panel=key[0],information=key[1],k=key[2],algorithm=key[3],axis=key[4],n_images=im.index.get_level_values('image_id').nunique(),n_buildings=len(bm),n_image_contexts=len(g),baseline_image_MAE=im.baseline_MAE.mean(),method_image_MAE=im.method_MAE.mean(),baseline_building_MAE=bm.baseline_MAE.mean(),method_building_MAE=bm.method_MAE.mean(),image_relative_MSE_reduction=1-im.method_MSE.mean()/im.baseline_MSE.mean() if im.baseline_MSE.mean()>1e-15 else np.nan,building_relative_MSE_reduction=1-bm.method_MSE.mean()/bm.baseline_MSE.mean() if bm.baseline_MSE.mean()>1e-15 else np.nan))
    write_csv('E/worker_prediction_summary.csv',summary)
    # Train-only selection of k by silhouette; no outer outcome selects the count.
    sh=pd.DataFrame(silhouette).dropna(subset=['training_silhouette']);selected=sh.sort_values(['training_silhouette','k'],ascending=[False,True]).groupby(['heldout_building','panel','information'],as_index=False).first();write_csv('E/training_selected_group_counts.csv',selected)
    selected_eval=a[a.algorithm=='ward'].merge(selected[['heldout_building','panel','information','k']],on=['heldout_building','panel','information','k']);write_csv('E/training_selected_type_predictions.csv.gz',selected_eval)
    print('E evaluation completed',round(time.monotonic()-start,2),'seconds',flush=True)


def half_reproducibility(old,repeats=100):
    rng=np.random.default_rng(SEED);cache=ProfileCache(old);buildings=np.array(sorted(old.building_id.unique()));rows=[]
    for rep in range(repeats):
        order=rng.permutation(buildings);left=order[:len(order)//2];right=order[len(order)//2:]
        for support,minr,minb in [('primary_6rows_3buildings',6,3),('sensitivity_3rows_2buildings',3,2)]:
            pa,_=cache.fit(right,minr,minb);pb,_=cache.fit(left,minr,minb)
            for name,blocks in COMBOS.items():
                cols=[a for b in blocks for a in b]
                if not(set(cols)<=set(pa) and set(cols)<=set(pb)):
                    rows.append(dict(repetition=rep,support=support,information=name,k=0,status='axis_unavailable',common_workers=0));continue
                a=pa.dropna(subset=cols);b=pb.dropna(subset=cols);common=a.index.intersection(b.index)
                if min(len(a),len(b),len(common))<4:
                    rows.append(dict(repetition=rep,support=support,information=name,k=0,status='insufficient_common_workers',common_workers=len(common)));continue
                xa,ma=standardize_blocks(a,blocks);xb,mb=standardize_blocks(b,blocks)
                if xa is None or xb is None:
                    rows.append(dict(repetition=rep,support=support,information=name,k=0,status='constant_axis',common_workers=len(common)));continue
                for k in range(2,min(len(a),len(b))//2+1):
                    la=pd.Series(labels_for(xa,a,k,cols[0]),index=a.index);lb=pd.Series(labels_for(xb,b,k,cols[0]),index=b.index)
                    ari=float(adjusted_rand_score(la.loc[common],lb.loc[common]));rows.append(dict(repetition=rep,support=support,information=name,k=k,status='evaluated',common_workers=len(common),adjusted_rand=ari,left_workers=len(a),right_workers=len(b),left_singleton_types=sum(la.value_counts()==1),right_singleton_types=sum(lb.value_counts()==1)))
    write_csv('E/disjoint_building_halves.csv.gz',rows);a=pd.DataFrame(rows);s=[]
    for key,g in a.groupby(['support','information','k']):s.append(dict(support=key[0],information=key[1],k=key[2],attempted_repetitions=repeats,evaluated=int((g.status=='evaluated').sum()),median_ARI=median(g.get('adjusted_rand',pd.Series(dtype=float))),mean_ARI=g.get('adjusted_rand',pd.Series(dtype=float)).mean(),median_common_workers=g.common_workers.median()))
    write_csv('E/disjoint_halves_summary.csv',s)


def real_combinations(r,maximum_per_image_size=600):
    rng=np.random.default_rng(SEED);z=np.load(OUT/'human/dense_boundaries.npz');dense=dict(zip(z['canonical_annotation_ids'],z['boundaries']));members=pd.read_csv(OUT/'E/worker_memberships_oof.csv.gz');members=members[members.k.isin([2,3,4]) & (members.panel=='common_all_blocks')]
    base_rows=[];summaries=[];examples=[];combo_id=0
    for (image,arm),g in r[r.raw_condition.isin(['manual','semi']) & r.geometry_valid].groupby(['image_id','raw_condition']):
        g=g.sort_values('worker_id').reset_index(drop=True);n=len(g);workers=g.worker_id.to_numpy();pcs=g.effective_point_count.to_numpy();cids=g.canonical_annotation_id.tolist();q=g.quality.to_numpy();times=g.active_seconds.to_numpy();dm=np.zeros((n,n))
        for i,j in itertools.combinations(range(n),2):dm[i,j]=dm[j,i]=_d_mask(dense[cids[i]],dense[cids[j]]) if pcs[i]==pcs[j] else 2.
        assignments=members[members.heldout_building==image.split('_')[0]]
        for size in [2,3,4]:
            if n<size:continue
            all_combos=list(itertools.combinations(range(n),size));total=len(all_combos)
            chosen=np.arange(total) if total<=maximum_per_image_size else np.sort(rng.choice(total,maximum_per_image_size,replace=False));comb=np.array([all_combos[j]for j in chosen],int);local=[]
            for ix in comb:
                sub=dm[np.ix_(ix,ix)];labels=topology_clusters(sub,pcs[ix],.10);cnt=collections.Counter(labels);med=[]
                for lab,nn in cnt.items():
                    if nn>=2:
                        group=ix[labels==lab];med.append(group[np.argmin(dm[np.ix_(group,group)].sum(1))])
                cover=float(np.mean(np.min(dm[:,med],axis=1)<=.10+1e-12)) if med else 0.
                pairs=list(itertools.combinations(ix,2));same=[dm[i,j]for i,j in pairs if pcs[i]==pcs[j]]
                row=dict(combo_id=combo_id,image_id=image,building=image.split('_')[0],condition=arm,people=size,workers=';'.join(workers[ix]),population_combinations=total,sampled_combinations=len(comb),enumeration='exhaustive' if total==len(comb) else 'uniform_without_replacement_combinations',median_reference_error=median(q[ix]),quality_complete=bool(np.isfinite(q[ix]).all()),total_active_seconds=float(np.sum(times[ix])) if np.isfinite(times[ix]).all() else np.nan,time_complete=bool(np.isfinite(times[ix]).all()),point_count_disagreement=float(np.mean([pcs[i]!=pcs[j]for i,j in pairs])),same_point_geometry_dispersion=median(same),supported_subset_clusters=sum(v>=2 for v in cnt.values()),observed_population_coverage=cover,cut=.10)
                combo_id+=1;local.append(row);base_rows.append(row)
            lf=pd.DataFrame(local)
            for (info,k),mm in assignments.groupby(['information','k']):
                labdict=mm.set_index('worker_id').label.to_dict();supportdict=mm.set_index('worker_id').supported_class.to_dict();labels=np.array([labdict.get(w,'?')for w in workers]);supported=np.array([supportdict.get(w,False)for w in workers]);assigned=labels[comb];valid=np.all(assigned!='?',axis=1);patterns=[''.join(sorted(row)) for row in assigned]
                lf2=lf.copy();lf2['pattern']=patterns;lf2['type_supported']=supported[comb].all(1);lf2=lf2[valid]
                for pattern,h in lf2.groupby('pattern'):
                    summaries.append(dict(image_id=image,building=image.split('_')[0],condition=arm,information=info,k=k,people=size,pattern=pattern,distinct_types=len(set(pattern)),n_combinations=len(h),population_combinations=total,n_unknown_excluded=int((~valid).sum()),all_type_support_fraction=h.type_supported.mean(),mean_median_reference_error=h.median_reference_error.mean(),mean_total_active_seconds=h.total_active_seconds.mean(),n_time_complete=int(h.time_complete.sum()),mean_point_disagreement=h.point_count_disagreement.mean(),mean_same_point_geometry_dispersion=h.same_point_geometry_dispersion.mean(),mean_observed_population_coverage=h.observed_population_coverage.mean(),mean_supported_clusters=h.supported_subset_clusters.mean(),sampling='same_real_subsets_across_information_methods'))
                    if pattern in ['AA','AB','AAB','ACD','AABC','ABCD']:
                        example=h.iloc[0].to_dict();example.update(information=info,k=k,pattern=pattern);examples.append(example)
        print('E combinations',arm,image,'n',n,'total base rows',len(base_rows),flush=True)
    write_csv('E/real_worker_combinations.csv.gz',base_rows);write_csv('E/composition_image_results.csv.gz',summaries);write_csv('E/requested_pattern_real_examples.csv.gz',examples)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['evaluate','halves','combinations','all']);args=ap.parse_args();old,current,r=inputs()
    if args.stage in ['evaluate','all']:worker_evaluation(old,current)
    if args.stage in ['halves','all']:half_reproducibility(old)
    if args.stage in ['combinations','all']:real_combinations(r)
