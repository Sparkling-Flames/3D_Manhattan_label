"""Nested real-person replay with re-clustering at every prefix.
Stores each distinct prefix partition plus arrival orders: no duplicated votes.
A fixed-full-pool label view is always explicitly retrospective.
"""
from __future__ import annotations
import csv,io,gzip,collections,itertools,functools,json,math
import numpy as np,pandas as pd
from common import *
STAT_NAMES=['clusters','singletons','supported_clusters','largest_share','fixed_clusters','fixed_singletons','fixed_largest_share',
 'pair_incompatible','remaining_pair_uncovered','fixed_unseen_full_mass','fixed_unseen_remaining_mass',
 'fixed_unseen_repeated_minority_mass','fixed_repeated_minority_total_mass','prefix_vs_full_relation_disagreement']

class PrefixEngine:
    def __init__(self,matrices,ids,cuts=CUTS):
        self.ids=ids;self.n=len(ids);self.d={m:np.round(np.asarray(v,float),8) for m,v in matrices.items()}
        self.methods=[(m,kind,t) for m in ('sphere','image') for t in cuts for kind in ('complete','representative')]
        self.full={};self.cache={};self._indices={}
        for method in self.methods:
            metric,kind,t0=method;t=nominal_cut(metric,t0)
            self.full[method]=partition(self.d[metric],ids,t,kind)[0]
    def indices(self,mask):
        if mask not in self._indices:self._indices[mask]=np.array([i for i in range(self.n) if mask>>i&1],int)
        return self._indices[mask]
    def node(self,mask):
        if mask in self.cache:return self.cache[mask]
        ix=self.indices(mask);k=len(ix);remaining=np.array([i for i in range(self.n) if not mask>>i&1],int)
        ids=[self.ids[i] for i in ix];labels=[];reps=[];stats=[];tri=np.triu_indices(k,1)
        # The public linkage primitive is reused; matrices and downstream statistics
        # are assembled independently, with the same deterministic identity order.
        trees={m:linkage(squareform(d[np.ix_(ix,ix)]),method='complete') if k>1 else None for m,d in self.d.items()}
        for method in self.methods:
            metric,kind,t0=method;t=nominal_cut(metric,t0);D=self.d[metric];d=D[np.ix_(ix,ix)]
            if kind=='complete':
                l=canonical_labels(fcluster(trees[metric],t,criterion='distance')) if k>1 else np.ones(1,int)
                centers=[]
                for kk in range(1,l.max()+1):
                    z=np.flatnonzero(l==kk);centers.append(int(ix[z[np.argmin(np.round(d[np.ix_(z,z)].sum(1),8))]]))
            else:
                l,c=partition(d,ids,t,kind);centers=[self.ids.index(x) for x in c]
            full=self.full[method];lf=full[ix];counts=np.bincount(l)[1:];fc=collections.Counter(lf)
            fullcnt=collections.Counter(full);unseen=set(fullcnt)-set(lf)
            unseen_mass=sum(fullcnt[x] for x in unseen)/self.n
            remmass=float(np.isin(full[remaining],list(unseen)).mean()) if len(remaining) else np.nan
            minor={x for x,z in fullcnt.items() if z>=2 and z/self.n<=.2}
            pairbad=float((d[tri]>t).mean()) if k>1 else np.nan
            rembad=float((D[np.ix_(remaining,ix)]>t).all(1).mean()) if len(remaining) else np.nan
            disagree=float((coassign(l)[tri]!=coassign(lf)[tri]).mean()) if k>1 else np.nan
            vals=[len(counts),int((counts==1).sum()),int((counts>=2).sum()),counts.max()/k,len(fc),sum(x==1 for x in fc.values()),max(fc.values())/k,
                pairbad,rembad,unseen_mass,remmass,sum(fullcnt[x] for x in minor&unseen)/self.n,sum(fullcnt[x] for x in minor)/self.n,disagree]
            labels.append(l.astype(np.uint8));reps.append(centers);stats.append(vals)
        self.cache[mask]=(np.array(stats,float),labels,reps)
        return self.cache[mask]
    def sample(self,orders):
        b=len(orders);M=len(self.methods);S=len(STAT_NAMES)
        values=np.empty((b,self.n,M,S),float);churn=np.full((b,self.n,M),np.nan);drops=np.zeros((b,self.n,M),bool)
        arrivals=[];events=[]
        for r,order in enumerate(orders):
            mask=0;previous=None
            for k0,i in enumerate(order):
                oldmask=mask;mask|=1<<int(i);stats,labels,_=self.node(mask);values[r,k0]=stats
                arrivals.append((r,k0+1,mask,int(order[k0+1]) if k0+1<self.n else -1))
                if previous is not None:
                    oldstats,oldlabs,_=previous;oldix=self.indices(oldmask);newix=self.indices(mask);pos=np.searchsorted(newix,oldix)
                    tri=np.triu_indices(len(oldix),1)
                    for m,l in enumerate(labels):
                        bad=int((coassign(oldlabs[m])[tri]!=coassign(l[pos])[tri]).sum())
                        denom=len(tri[0]);churn[r,k0,m]=bad/denom if denom else np.nan
                        drops[r,k0,m]=stats[m,0]<oldstats[m,0]
                        if bad or drops[r,k0,m]:events.append((r,k0+1,m,bad,denom,int(stats[m,0]-oldstats[m,0]),oldmask,mask))
                previous=(stats,labels,None)
        rows=[]
        for k0 in range(self.n):
            for m,method in enumerate(self.methods):
                row=dict(metric=method[0],partition=method[1],nominal_cut=method[2],k=k0+1,replicates=b)
                for j,name in enumerate(STAT_NAMES):
                    z=values[:,k0,m,j];ok=np.isfinite(z)
                    row[name+'_mean']=float(z[ok].mean()) if ok.any() else np.nan
                    if name in ['clusters','singletons','largest_share','remaining_pair_uncovered']:
                        row[name+'_p10']=float(np.quantile(z[ok],.1)) if ok.any() else np.nan
                        row[name+'_p90']=float(np.quantile(z[ok],.9)) if ok.any() else np.nan
                z=churn[:,k0,m];ok=np.isfinite(z)
                row['mean_old_pair_churn']=float(z[ok].mean()) if ok.any() else np.nan
                row['probability_any_old_pair_change']=float((z[ok]>0).mean()) if ok.any() else np.nan
                row['probability_cluster_count_drop']=float(drops[:,k0,m].mean()) if k0 else np.nan
                row['prefix_minus_fixed_clusters']=row['clusters_mean']-row['fixed_clusters_mean']
                row['prefix_minus_fixed_singletons']=row['singletons_mean']-row['fixed_singletons_mean']
                rows.append(row)
        return rows,arrivals,events

def writer(path,fields):
    raw=open(path,'wb');gz=gzip.GzipFile(fileobj=raw,mode='wb',mtime=0);txt=io.TextIOWrapper(gz,encoding='utf-8',newline='')
    w=csv.writer(txt);w.writerow(fields);return raw,txt,w

def process_job(job):
    jobid,g,pool,keep,view,global_orders=job
    unit=g['unit'];key=g['key'];ids=[g['ids'][i] for i in keep];ws=[g['workers'][i] for i in keep];n=len(ids)
    wind={w:i for i,w in enumerate(ws)};orders=[[wind[w] for w in o if w in wind] for o in global_orders]
    matrices={m:np.array(d)[np.ix_(keep,keep)] for m,d in g['matrices'][view].items()}
    engine=PrefixEngine(matrices,ids);ss,arrivals,events=engine.sample(orders)
    meta=dict(unit=unit,key=key,code=g['code'],building=g['building'],condition=g['condition'],N=n,pool=pool,view=view)
    part=OUT/'prefix_parts';part.mkdir(exist_ok=True)
    paths={name:part/f'{jobid:04d}_{name}.csv.gz' for name in ['nodes','arrivals','events']}
    nr,nt,nw=writer(paths['nodes'],NODE_FIELDS)
    for mask,(stats,labels,reps) in sorted(engine.cache.items()):
        for m,(metric,kind,t0) in enumerate(engine.methods):
            nw.writerow([unit,pool,view,f'{metric}:{kind}:{t0:g}',mask,mask.bit_count(),labels[m].tobytes().hex(),'|'.join(map(str,reps[m])),*['' if not np.isfinite(z) else f'{z:.12g}' for z in stats[m]]])
    nt.close();nr.close()
    ar,at,aw=writer(paths['arrivals'],ARRIVAL_FIELDS)
    if view=='automatic':aw.writerows((unit,pool,*r) for r in arrivals)
    at.close();ar.close()
    er,et,ew=writer(paths['events'],EVENT_FIELDS)
    ew.writerows((unit,pool,view,*r) for r in events);et.close();er.close()
    exact=[]
    for (metric,kind,t0),lab in engine.full.items():
        t=nominal_cut(metric,t0);d=matrices[metric]
        for k in range(1,n+1):exact.append(dict(**meta,metric=metric,partition=kind,nominal_cut=t0,k=k,next_uncovered=next_uncovered(d,k,t),**fixed_stats(lab,k)))
    man=dict(unit=unit,key=key,code=g['code'],condition=g['condition'],building=g['building'],pool=pool,N=n,ids=ids,workers=ws,
        human_view_reuses_automatic=g['matrices']['automatic']==g['matrices']['human_correspondence'],borrowed_records_omitted=len(g['ids'])-n,
        prefix_views_are_historical_replays_not_prospective_guarantees=True)
    print('PREFIX',unit,g['code'],pool,view,'N',n,'distinct_prefixes',len(engine.cache),flush=True)
    return dict(summary=[dict(**meta,**r) for r in ss],exact=exact,manifest=man if view=='automatic' else None,paths=paths,
        nodes=len(engine.cache)*len(engine.methods),steps=len(arrivals) if view=='automatic' else 0,events=len(events))

NODE_FIELDS=['unit','pool','view','method','subset_mask','k','labels_by_sorted_pool_index','representative_pool_indices',*STAT_NAMES]
ARRIVAL_FIELDS=['unit','pool','replicate','k','subset_mask','next_pool_index']
EVENT_FIELDS=['unit','pool','view','replicate','k','method_index','changed_old_pairs','old_pair_denominator','cluster_count_delta','old_mask','new_mask']

def main():
    from concurrent.futures import ProcessPoolExecutor
    import shutil,os
    groups=load_groups();_,by=rawdata();workers=sorted({w for g in groups.values() for w in g['workers']})
    rng=np.random.default_rng(20260920);global_orders=[rng.permutation(workers).tolist() for _ in range(200)]
    dump('global_worker_orders.json',dict(seed=20260920,replicates=200,workers=workers,orders=global_orders,unit='distinct_real_people',not_new_samples=True))
    jobs=[]
    for key,g in sorted(groups.items()):
        good=[i for i,c in enumerate(g['ids']) if not by[c].get('imputed_point',False)]
        pools=[('effective_history',list(range(len(g['ids']))))]
        if len(good)!=len(g['ids']):pools.append(('no_borrowed_training_view',good))
        for pool,keep in pools:
            if not keep:continue
            views=['automatic','human_correspondence'] if g['matrices']['automatic']!=g['matrices']['human_correspondence'] else ['automatic']
            for view in views:jobs.append((len(jobs),g,pool,keep,view,global_orders))
    handles={name:writer(OUT/filename,fields) for name,filename,fields in [
        ('nodes','prefix_nodes.csv.gz',NODE_FIELDS),('arrivals','prefix_arrivals.csv.gz',ARRIVAL_FIELDS),('events','prefix_churn_events.csv.gz',EVENT_FIELDS)]}
    summaries=[];exact=[];manifest=[];source_diffs=[];nodes=steps=events_total=0
    srcex=pd.read_csv(SOURCE/'results/exact_curves.csv.gz')
    maxworkers=min(int(os.environ.get('CLUSTER_JOBS','4')),os.cpu_count() or 1)
    with ProcessPoolExecutor(max_workers=maxworkers) as executor:
        for z in executor.map(process_job,jobs,chunksize=1):
            summaries.extend(z['summary']);exact.extend(z['exact'])
            if z['manifest'] is not None:manifest.append(z['manifest'])
            nodes+=z['nodes'];steps+=z['steps'];events_total+=z['events']
            for name,p in z['paths'].items():
                with gzip.open(p,'rt',encoding='utf-8',newline='') as f:
                    next(f);shutil.copyfileobj(f,handles[name][1])
                p.unlink()
    for raw,txt,w in handles.values():txt.close();raw.close()
    (OUT/'prefix_parts').rmdir()
    sm=save('prefix_reclustering_summary.csv.gz',summaries);ex=save('exact_finite_pool_curves.csv.gz',exact);dump('prefix_pool_manifest.json',manifest)
    # Verify every applicable source fixed-label curve against the independent formula.
    e=ex[ex.pool=='effective_history'].copy()
    keys=['key','view','metric','partition','nominal_cut','k']
    joined=srcex.merge(e,on=keys,suffixes=('_source','_independent'),validate='one_to_one')
    columns={'next_real_person_uncovered':'next_uncovered','retrospective_expected_modes':'fixed_expected_clusters',
      'retrospective_expected_supported_modes':'fixed_expected_supported','retrospective_unseen_fullpool_mode_mass':'fixed_unseen_pool_mass',
      'retrospective_unseen_repeated_minority_mass':'fixed_unseen_repeated_minority_mass'}
    for a,b in columns.items():
        delta=(joined[a]-joined[b]).abs();err=float(delta.max());source_diffs.append(dict(source_column=a,independent_column=b,rows=len(joined),max_absolute_error=err));assert err<1e-9
    save('exact_curve_formula_audit.csv',source_diffs)
    # Same high-support panel for every k<=18. Condition-specific, no changing mixture.
    high=sm[(sm.pool=='effective_history')&(sm.view=='automatic')&(sm.N>=19)&(sm.k<=18)]
    numeric=[x for x in high if x.endswith('_mean') or x in ['mean_old_pair_churn','probability_any_old_pair_change','probability_cluster_count_drop','prefix_minus_fixed_clusters','prefix_minus_fixed_singletons']]
    agg=high.groupby(['condition','metric','partition','nominal_cut','k'])[numeric].mean().reset_index()
    counts=high.groupby(['condition','metric','partition','nominal_cut','k']).agg(images=('key','nunique'),buildings=('building','nunique')).reset_index()
    save('high_support_prefix_summary.csv',counts.merge(agg))
    he=ex[(ex.pool=='effective_history')&(ex.view=='automatic')&(ex.N>=19)&(ex.k<=18)]
    save('high_support_exact_summary.csv',he.groupby(['condition','metric','partition','nominal_cut','k']).agg(images=('key','nunique'),buildings=('building','nunique'),next_uncovered=('next_uncovered','mean'),fixed_expected_clusters=('fixed_expected_clusters','mean'),fixed_unseen_pool_mass=('fixed_unseen_pool_mass','mean'),minority_unseen_mass=('fixed_unseen_repeated_minority_mass','mean')).reset_index())
    # Strict invariance: grouping can change labels, not pair-defined coverage.
    inv=sm.groupby(['unit','pool','view','metric','nominal_cut','k']).remaining_pair_uncovered_mean.nunique(dropna=False).max()
    assert inv==1
    h=sm[(sm.pool=='effective_history')&(sm.view=='automatic')&(sm.N>=19)&sm.k.isin([3,5,8,12,16])]
    save('prefix_vs_hindsight_checkpoints.csv',h.groupby(['condition','metric','partition','nominal_cut','k']).agg(images=('key','nunique'),prefix_K=('clusters_mean','mean'),fixed_K=('fixed_clusters_mean','mean'),prefix_singletons=('singletons_mean','mean'),fixed_singletons=('fixed_singletons_mean','mean'),old_pair_churn=('mean_old_pair_churn','mean'),cluster_drop_probability=('probability_cluster_count_drop','mean')).reset_index())
    dump('PREFIX_AUDIT.json',dict(global_orders=200,seed=20260920,real_worker_count=len(workers),bound_units=len(groups),arrival_steps=steps,
        unique_method_prefix_nodes=nodes,nonzero_churn_or_drop_events=events_total,source_fixed_curve_rows_checked=len(joined),
        coverage_partition_invariance=True,human_view_unmodified_units_reused=True,borrowed_prediction_records_not_independent=True,
        online_safe_geometry_view='automatic + no_borrowed_training_view on affected units, identical automatic on others; historical replay only',
        missing_binding_records='remain in coverage_by_unit.csv, not zeros or fabricated singleton clusters',final_stop_rule=None))
if __name__=='__main__':main()
