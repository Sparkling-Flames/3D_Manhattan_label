"""E: actual people and composition sensitivity, never replicated annotators.

Reference-alignment and time axes are descriptive scores learned outside the
entire target building. They are not an assertion of care, correctness or type.
"""
from __future__ import annotations
import collections,itertools,math,warnings,time
import numpy as np,pandas as pd
from scipy.cluster.hierarchy import linkage,fcluster
from scipy.spatial.distance import squareform
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_core import *


def dense(pairs):
    from tools.thesis_main.analysis.quality_core.geometry_metrics import _interp_periodic
    x=np.asarray([p['x'] for p in pairs],np.float32)
    top=np.clip(np.rint(_interp_periodic(x,np.asarray([p['y_ceiling'] for p in pairs],np.float32),1024)),0,511).astype(np.int32)
    bot=np.clip(np.rint(_interp_periodic(x,np.asarray([p['y_floor'] for p in pairs],np.float32),1024)),0,511).astype(np.int32)
    return np.stack([np.minimum(top,bot),np.maximum(top,bot)])


def dmask(a,b):
    inter=np.maximum(0,np.minimum(a[1],b[1])-np.maximum(a[0],b[0])+1);union=a[1]-a[0]+b[1]-b[0]+2-inter
    return 1-float(inter.sum()/union.sum())


def clusters(dm,pcs,cut=.1):
    lab=np.zeros(len(pcs),int);last=0
    for p in sorted(set(pcs)):
        ix=np.flatnonzero(pcs==p)
        z=np.array([1]) if len(ix)==1 else fcluster(linkage(squareform(dm[np.ix_(ix,ix)],checks=True),method='complete'),cut,criterion='distance')
        lab[ix]=z+last;last=int(lab.max())
    return lab


def stats(dm,pcs,lab):
    n=len(lab);co=collections.Counter(lab);tri=np.triu_indices(n,1);same=(lab[:,None]==lab[None,:])[tri];eq=(pcs[:,None]==pcs[None,:])[tri]
    within=dm[tri][same];maxmed=[]
    for l,size in co.items():
        if size>=2:
            ix=np.flatnonzero(lab==l);maxmed.append(float(np.median(dm[np.ix_(ix,ix)][np.triu_indices(size,1)])))
    return dict(n_modes=len(co),n_supported_modes=sum(v>=2 for v in co.values()),singleton_mass=sum(v==1 for v in co.values())/n if n else 1.,within_mode_max=max(maxmed) if maxmed else np.nan,within_mode_median=float(np.median(within)) if len(within) else np.nan,point_count_disagreement=float((~eq).mean()) if len(eq) else np.nan,mode_entropy=float(-sum(v/n*np.log2(v/n) for v in co.values())) if n else np.nan)


def replay(g,boundaries,cut=.1,orders=30):
    observed=len(g);v=g[g.geometry_valid].sort_values('worker_id').reset_index(drop=True);n=len(v)
    assert g.worker_id.nunique()==observed
    if n==0:return dict(n_observed=observed,n_valid=0,n_invalid=observed,grade='',status='invalid_response_evidence')
    pcs=v.effective_point_count.to_numpy(int);dm=np.zeros((n,n))
    for i,j in itertools.combinations(range(n),2):dm[i,j]=dm[j,i]=dmask(boundaries[v.canonical_annotation_id.iloc[i]],boundaries[v.canonical_annotation_id.iloc[j]]) if pcs[i]==pcs[j] else 2.
    full=clusters(dm,pcs,cut);end=stats(dm,pcs,full);fc=collections.Counter(full);invalid=observed-n
    if n<4 or invalid:
        grade,status=classify(n,invalid,end['n_supported_modes'],end['singleton_mass'],0,0,0,0,False)
        return dict(end,n_observed=observed,n_valid=n,n_invalid=invalid,grade=grade,status=status,p_early7=np.nan,p_by19=np.nan,p_tail=np.nan,late_new=np.nan)
    rng=np.random.default_rng(seed('composition',g.image_id.iloc[0],g.raw_condition.iloc[0],','.join(v.worker_id),cut));cache={};onsets=[];tailpasses=[];late_new=[];curve=[]
    for rep in range(orders):
        order=rng.permutation(n);seq=[];previx=None;prevlab=None
        for k in range(1,n+1):
            ix=np.sort(order[:k]);key=tuple(ix)
            if key not in cache:
                small=dm[np.ix_(ix,ix)];ll=clusters(small,pcs[ix],cut);s=stats(small,pcs[ix],ll);count=collections.Counter(full[ix]);s['tv']=.5*sum(abs(count[l]/k-fc[l]/n) for l in fc);cache[key]=(s,ll)
            s,ll=cache[key];s=s.copy();s['repartition']=0.;s['new']=0.
            if previx is not None:
                shared=np.searchsorted(ix,previx);old=(prevlab[:,None]==prevlab[None,:]);new=(ll[shared,None]==ll[None,shared]);tr=np.triu_indices(k-1,1)
                s['repartition']=float((old[tr]!=new[tr]).mean()) if len(tr[0]) else 0.
                s['new']=float(dm[order[k-1],previx].min()>cut+1e-12)
            seq.append(s);previx=ix;prevlab=ll
        def good(a):
            z=[r['within_mode_max'] for r in a]
            return len({(r['n_modes'],r['n_supported_modes']) for r in a})==1 and max(r['repartition'] for r in a[1:])<=.05 and max(r['tv'] for r in a)<=.1+1e-12 and np.isfinite(z).all() and max(z)-min(z)<=.02+1e-12
        onset=np.nan
        if end['singleton_mass']<=.1+1e-12:
            for k in range(2,n):
                if good(seq[k-1:]):onset=k;break
        onsets.append(onset);w=min(3,n-2);tailpasses.append(good(seq[n-w-1:]) and end['singleton_mass']<=.1+1e-12);late_new.append(np.mean([r['new'] for r in seq if seq.index(r)+1>n/2]) if False else np.mean([seq[k-1]['new'] for k in range(1,n+1) if k>n/2]))
        for k in [2,3,4,5,6,7,8,10,12]:
            if k<=n:curve.append(dict(replay=rep,k=k,**seq[k-1]))
    onset=np.asarray(onsets);early=float((onset<=7).mean());cum=float((onset<=19).mean());between=float(((onset>7)&(onset<=19)).mean());anys=float(np.isfinite(onset).mean());ln=float(np.mean(late_new))
    grade,status=classify(n,invalid,end['n_supported_modes'],end['singleton_mass'],early,cum,between,anys,ln>.05)
    return dict(end,n_observed=observed,n_valid=n,n_invalid=invalid,grade=grade,status=status,p_early7=early,p_by19=cum,p_tail=float(np.mean(tailpasses)),late_new=ln,onset_median=finite_median(onset),observed_after7=max(0,n-7),replay_orders=orders)


def boundaries_and_audit(raw):
    from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
    source={r['canonical_annotation_id']:r for r in read(B/'human/responses.jsonl.gz')};bd={};failure=[]
    for r in raw[raw.main_worker_included&raw.geometry_valid&raw.raw_condition.isin(['manual','semi'])].to_dict('records'):
        try:
            norm=normalize_geometry(source[r['canonical_annotation_id']]['effective_points_1024x512']);assert norm['valid'];bd[r['canonical_annotation_id']]=dense(norm['pairs'])
        except Exception as e:failure.append(dict(canonical_annotation_id=r['canonical_annotation_id'],error=repr(e)))
    csv('E/geometry_recompute_failures.csv',failure)
    assert not failure,'Do not silently remove previously valid source responses'
    old=pd.read_csv(OLD/'process/image_uncertainty_structure.csv');old=old[old.cut==.1].set_index(['image_id','condition']);audit=[]
    for (i,arm),g in raw[raw.main_worker_included&raw.raw_condition.isin(['manual','semi'])].groupby(['image_id','raw_condition']):
        a=replay(g,bd,orders=1);p=old.loc[(i,arm)];bad=[]
        for col in ('n_valid','n_invalid','n_modes','n_supported_modes','singleton_mass'):
            if col in a and pd.notna(p.get(col)) and abs(float(a[col])-float(p[col]))>1e-9:bad.append(col)
        audit.append(dict(image_id=i,condition=arm,recomputed_people=a['n_valid'],old_people=int(p.n_valid),mismatched_fields=';'.join(bad)))
    csv('E/full_geometry_cache_recompute_audit.csv',audit)
    assert not any(r['mismatched_fields'] for r in audit),'Old process cache mismatch; do not reuse without reconciliation'
    return bd


def profiles(raw):
    rows=[]
    valid=raw[raw.main_worker_included & raw.raw_condition.isin(['manual','semi'])].copy()
    valid['log_time']=np.log(valid.active_seconds.where(valid.active_seconds>0))
    for b in sorted(valid.building.unique()):
        train=valid[valid.building!=b].copy()
        for axis,col in [('Q','quality'),('T','log_time')]:
            x=train.dropna(subset=[col]).copy();x['residual']=x[col]-x.groupby(['image_id','raw_condition'])[col].transform('median')
            for w,g in x.groupby('worker_id'):
                qualified=len(g)>=6 and g.building.nunique()>=3
                rows.append(dict(target_building=b,worker_id=w,axis=axis,training_responses=len(g),training_buildings=g.building.nunique(),qualified=qualified,score=g.residual.mean() if qualified else np.nan,score_kind='task-median-adjusted outside-building mean; lower alignment error/faster log-time, not care'))
    return csv('E/outside_building_continuous_person_scores.csv',rows)


def run():
    t0=time.monotonic();raw=pd.read_csv(OUT/'inputs/response_metrics_sanitized.csv.gz');raw=raw[raw.main_worker_included].copy();bd=boundaries_and_audit(raw);prof=profiles(raw)
    meta=pd.read_csv(OUT/'inputs/image_metadata_whitelist.csv',keep_default_na=False).set_index('image_id');target=pd.read_csv(OUT/'targets/primary_per_image.csv').set_index(['image_id','condition'])
    geo=raw[raw.raw_condition.isin(['manual','semi'])];groups={(i,a):g for (i,a),g in geo.groupby(['image_id','raw_condition'])};computed={}
    def get(g):
        key=(g.image_id.iloc[0],g.raw_condition.iloc[0],tuple(sorted(g.worker_id)))
        if key not in computed:computed[key]=replay(g,bd,orders=30)
        return computed[key]
    common=[]
    for room in read(B/'evaluation/room_components.jsonl'):
        if room['status']!='supported_component':continue
        for a,b in itertools.combinations(room['image_ids'],2):
            for arm in ('manual','semi'):
                if (a,arm) not in groups or (b,arm) not in groups:continue
                ga,gb=groups[(a,arm)],groups[(b,arm)];ws=set(ga.worker_id)&set(gb.worker_id)
                if len(ws)<2:continue
                left=get(ga[ga.worker_id.isin(ws)]);right=get(gb[gb.worker_id.isin(ws)])
                row=dict(room_id=room['room_id'],image_a=a,image_b=b,building=a.split('_')[0],condition=arm,n_common=len(ws),workers=';'.join(sorted(ws)),same_main_function=meta.loc[a,'main_function_primary']==meta.loc[b,'main_function_primary'],full_grade_a=target.loc[(a,arm),'grade'],full_grade_b=target.loc[(b,arm),'grade'])
                row.update({k+'_a':v for k,v in left.items()});row.update({k+'_b':v for k,v in right.items()});common.append(row)
    csv('E/same_room_exact_common_people.csv',common)
    combo=[];capacity=[]
    for counter,((i,arm),g) in enumerate(groups.items()):
        building=i.split('_')[0]
        for axis in ('Q','T'):
            scores=prof[(prof.target_building==building)&prof.axis.eq(axis)&prof.qualified].set_index('worker_id').score
            pool=g[g.worker_id.isin(scores.index)];capacity.append(dict(image_id=i,condition=arm,axis=axis,observed_people=len(g),qualified_target_people=len(pool),unknown_or_unqualified_people=len(g)-len(pool)))
            if len(pool)<8:continue
            ranked=sorted(pool.worker_id,key=lambda w:(scores[w],w))
            for n in (4,6,8,10,12):
                if len(pool)<2*n:continue
                high=ranked[:n];low=ranked[-n:];mix=ranked[:(n+1)//2]+ranked[-(n//2):]
                selected=[('lower_axis',high),('higher_axis',low),('mixed_axis',mix)]
                rng=np.random.default_rng(seed(i,arm,axis,n,'null'));seen=set()
                for j in range(20):
                    ws=tuple(sorted(rng.choice(ranked,n,replace=False)))
                    if ws not in seen:seen.add(ws);selected.append(('random_same_panel',list(ws)))
                for label,ws in selected:
                    sub=pool[pool.worker_id.isin(ws)];stats_=get(sub)
                    combo.append(dict(image_id=i,building=building,condition=arm,axis=axis,composition=label,n_people=n,workers=';'.join(sorted(ws)),main_function=meta.loc[i,'main_function_primary'],scene=meta.loc[i,'scene_category'],full_observed_people=len(g),full_grade=target.loc[(i,arm),'grade'],**stats_))
        if counter%30==0:print('PEOPLE',counter,'seconds',round(time.monotonic()-t0,1),flush=True)
    cr=csv('E/actual_equal_count_compositions.csv.gz',combo);csv('E/person_score_capacity.csv',capacity)
    if len(cr):
        measures=['point_count_disagreement','singleton_mass','within_mode_median','mode_entropy','n_supported_modes','p_early7','p_by19','p_tail','late_new']
        summary=cr.groupby(['condition','axis','n_people','composition'])[measures].mean().reset_index();csv('E/equal_count_composition_summary.csv',summary)
        contrasts=[]
        for (arm,axis,n),z in cr.groupby(['condition','axis','n_people']):
            avg=z.groupby(['image_id','building','composition'])[measures].mean().reset_index()
            for a,b in [('lower_axis','higher_axis'),('mixed_axis','lower_axis'),('mixed_axis','random_same_panel')]:
                aa=avg[avg.composition==a];bb=avg[avg.composition==b];p=aa.merge(bb,on=['image_id','building'],suffixes=('_a','_b'))
                for measure in measures:
                    p['delta']=p[measure+'_a']-p[measure+'_b'];contrasts.append(dict(condition=arm,axis=axis,n_people=n,composition_a=a,composition_b=b,measure=measure,**paired_ci(p,'delta')))
        csv('E/composition_paired_differences.csv',contrasts)
        csv('E/within_image_random_subset_variation.csv',cr[cr.composition=='random_same_panel'].groupby(['image_id','building','condition','axis','n_people']).agg(distinct_grades=('grade',lambda a:a.fillna('').nunique()),p_early_min=('p_early7','min'),p_early_max=('p_early7','max'),modes_min=('n_supported_modes','min'),modes_max=('n_supported_modes','max'),singleton_min=('singleton_mass','min'),singleton_max=('singleton_mass','max'),actual_unique_subsets=('workers','nunique')).reset_index())
    js('E/executed_summary.json',dict(common_view_pairs=len(common),common_pairs_with4plus=sum(r['n_common']>=4 for r in common),real_composition_rows=len(combo),distinct_target_images=len({r['image_id'] for r in combo}),geometry_source_recomputed=True,worker_scores_outside_building=True,unknown_is_not_type=True,orders_per_pool=30,independent_new_people=0,semantic_type_claim=False,reference_alignment_not_truth=True,limitations=['Finite same-person pools; composition is not randomized treatment.','Q and T are continuous out-of-building axes, not exhaustive worker categories.','Common-person comparisons retain differing image/capture and possible historical contexts.','Exact equal n is supplementary; full actual n remains the primary image-tier evidence.']))
    print('PEOPLE DONE',len(common),len(combo),round(time.monotonic()-t0,1),flush=True)

if __name__=='__main__':run()
