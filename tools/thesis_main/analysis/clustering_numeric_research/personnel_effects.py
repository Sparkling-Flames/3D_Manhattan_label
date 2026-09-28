"""Historical personnel reuse plus current-measurement sensitivity.
No target-building feature is used to fit its personnel roster. Full-history old
rosters are retained ONLY as retrospective descriptive objects.
"""
from __future__ import annotations
import os,sys,collections,itertools,hashlib,json,functools
import numpy as np,pandas as pd
from scipy.cluster.hierarchy import linkage,cut_tree
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import adjusted_rand_score
from common import *

def import_history():
    os.environ['RC2_OUTPUT_DIR']=str(OUT/'personnel')
    sys.path.insert(0,str(SOURCE/'rc2_received/code'))
    import reuse_personnel as rp
    rp.save=lambda n,x:save('personnel/'+n,x)
    rp.dump=lambda n,x:dump('personnel/'+n,x)
    return rp

def effect_predict(data,profiles):
    rows=[]
    for b,p in profiles.groupby('heldout_building'):
        for ax,g in data[data.building_id==b].groupby('axis'):
            pp=p[(p.axis==ax)&p.qualified].set_index('worker');g=g[g.worker_id.isin(pp.index)]
            for ctx,z in g.groupby('context_key'):
                if len(z)<2:continue
                y=z.value.to_numpy();beta=pp.loc[z.worker_id,'effect'].to_numpy();y=y-y.mean();beta=beta-beta.mean()
                for r,yy,bb in zip(z.itertuples(),y,beta):
                    rows.append(dict(building=b,axis=ax,image_id=r.image_id,id=r.canonical_annotation_id,worker=r.worker_id,
                         observed_centered=yy,predicted_centered=bb,baseline_squared_error=yy**2,model_squared_error=(yy-bb)**2))
    return pd.DataFrame(rows)

def prediction_summary(pred):
    rows=[]
    for ax,g in pred.groupby('axis'):
        q=g.groupby('building')[['baseline_squared_error','model_squared_error']].mean();delta=q.model_squared_error-q.baseline_squared_error
        rng=np.random.default_rng(20260920);boot=rng.choice(delta.to_numpy(),size=(2000,len(q)),replace=True).mean(1)
        rows.append(dict(axis=ax,rows=len(g),buildings=len(q),workers=g.worker.nunique(),baseline_mse=q.baseline_squared_error.mean(),
          model_mse=q.model_squared_error.mean(),relative_improvement=1-q.model_squared_error.mean()/q.baseline_squared_error.mean(),
          delta_mse=delta.mean(),conditional_building_bootstrap_lower=np.quantile(boot,.025),conditional_building_bootstrap_upper=np.quantile(boot,.975)))
    return pd.DataFrame(rows)

def roster_match(p,q):
    # Labels have no intrinsic semantics: align only to report member migration.
    p,q=p.align(q,join='inner');a=sorted(p.unique());b=sorted(q.unique());tab=np.array([[( (p==x)&(q==y)).sum() for y in b] for x in a])
    i,j=linear_sum_assignment(-tab);matched=tab[i,j].sum();return len(p),int(len(p)-matched),float(adjusted_rand_score(p,q))

def main():
    rp=import_history();data,raw=rp.load_axes();groups=load_groups();buildings=sorted({g['building'] for g in groups.values()})
    # Refit the archived, already-used six candidate settings; no parameter search.
    pp=[];rr=[];coverage=[]
    for b in buildings:
        p=rp.fit_profiles(data,set(data.building_id)-{b},200);p['heldout_building']=b;pp.append(p)
        assert all(b not in s.split('|') for s in p.train_building_ids)
        for name,blocks,k in rp.CONFIGS:
            r,status=rp.classify(p,blocks,k)
            coverage.append(dict(heldout_building=b,config=name,status=status,classified=0 if r is None else len(r),sizes=None if r is None else json.dumps(r.groupby('label').size().tolist())))
            if r is not None:
                for w,x in r.iterrows():rr.append(dict(heldout_building=b,config=name,worker=w,subtype=int(x.label),**{a:x[a] for a in r.columns if a!='label'}))
        print('PERSONNEL old-axis refit',b,flush=True)
    profiles=save('personnel/refitted_lobo_profiles.csv',pd.concat(pp,ignore_index=True))
    rosters=save('personnel/refitted_lobo_rosters.csv',rr);save('personnel/roster_coverage.csv',coverage)
    refp=pd.read_csv(SOURCE/'rc2_received/results/personnel_lobo_profiles.csv');refr=pd.read_csv(SOURCE/'rc2_received/results/personnel_lobo_rosters.csv')
    keys=['heldout_building','axis','worker'];a=profiles.set_index(keys).sort_index();b=refp.set_index(keys).sort_index();assert a.index.equals(b.index)
    profile_error=max(float(np.nanmax(abs(a[c]-b[c]))) for c in ['effect','lower','upper'])
    k=['heldout_building','config','worker'];a=rosters.set_index(k).subtype.sort_index();b=refr.set_index(k).subtype.sort_index();assert a.index.equals(b.index)
    changed=int((a!=b).sum());assert changed==0
    pred=save('personnel/historical_continuous_predictions.csv',effect_predict(data,profiles));save('personnel/historical_continuous_summary.csv',prediction_summary(pred))
    # Inventory and frozen rosters from all historical configurations, not just six.
    hist=SOURCE/'rc2_received/sources/current/personnel_history/worker_four_block_exploration_20260910_v1'
    inv=pd.read_csv(hist/'group_count_extension/group_counts.csv');save('personnel/historical_303_configuration_inventory.csv',inv)
    old=pd.read_csv(hist/'subtype_stage_validation/named_full_profiles.csv')
    old=old.drop_duplicates(['cohort','model','groups','group','worker_ids']).copy()
    old['worker_ids_original']=old.worker_ids;old['worker_ids']=old.worker_ids.map(lambda x:'|'.join(f'W{int(w):03d}' for w in (str(x).split('|') if pd.notna(x) else []) if int(w) not in (19,26)))
    old['roster_origin']='full_history_hindsight_NOT_target_holdout';save('personnel/historical_frozen_rosters.csv',old)
    # New geometry measurements; no reference/quality axis is silently redefined.
    geom=[];workerstates=[];effective_maps={};training_maps={}
    for key,g in groups.items():
        for pool in ['effective_history','no_borrowed_training_view']:
            ix=[i for i,cid in enumerate(g['ids']) if pool=='effective_history' or not raw[cid].get('imputed_point',False)]
            ids=[g['ids'][i] for i in ix];workers=[g['workers'][i] for i in ix];n=len(ids)
            if not n:continue
            matrices={m:np.array(d)[np.ix_(ix,ix)] for m,d in g['matrices']['automatic'].items()};labs={}
            for metric,d0 in matrices.items():
                d=np.round(d0,8);t=nominal_cut(metric,9);near=d<=t;degree=near.sum(1)-1
                for kind in ['complete','representative']:
                    l,reps=partition(d,ids,t,kind);labs[metric,kind]=l;counts=np.bincount(l)
                    for j,cid in enumerate(ids):
                        samecnt=sum(raw[x]['effective_point_count']==raw[cid]['effective_point_count'] for x in ids)-1
                        state='not_singleton' if counts[l[j]]>1 else ('no_same_count_peer' if not samecnt else 'no_near_peer' if not degree[j] else 'partition_isolated_despite_near_peer')
                        workerstates.append(dict(key=key,code=g['code'],building=g['building'],condition=g['condition'],pool=pool,metric=metric,partition=kind,id=cid,worker=workers[j],N=n,same_count_peers=samecnt,near_peers=int(degree[j]),singleton=int(counts[l[j]]==1),singleton_reason=state))
                    if pool=='no_borrowed_training_view' and n>=2:
                        for j,cid in enumerate(ids):
                            for feat,value in [('singleton',float(counts[l[j]]==1)),('pair_disagreement',1-degree[j]/(n-1))]:
                                # Pair disagreement need only be fitted once per metric.
                                if feat=='pair_disagreement' and kind!='complete':continue
                                axis=f'{metric}:{kind}:singleton' if feat=='singleton' else f'{metric}:pair_disagreement'
                                geom.append(dict(canonical_annotation_id=cid,worker_id=workers[j],image_id=g['image_id'],building_id=g['building'],context_key=key,axis=axis,value=value))
            (effective_maps if pool=='effective_history' else training_maps)[key]=(g,ids,workers,matrices,labs)
    states=save('personnel/current_worker_observations.csv.gz',workerstates);gd=save('personnel/current_geometry_training_axes.csv.gz',geom)
    zz=states[states.pool=='effective_history'].groupby(['worker','metric','partition','singleton_reason']).size().unstack(fill_value=0).reset_index()
    zz['N']=zz[[c for c in zz if c not in ['worker','metric','partition']]].sum(axis=1)
    save('personnel/worker_singleton_reason_summary.csv',zz)
    # Geometric phenotype is explicitly a separate descriptive proxy, never Q_GT.
    gp=[];gr=[]
    for b in buildings:
        p=rp.fit_profiles(gd,set(gd.building_id)-{b},200);p['heldout_building']=b;gp.append(p)
        for ax,z in p[p.qualified].groupby('axis'):
            z=z.sort_values('worker');x=z.effect.to_numpy()[:,None]
            if len(x)<4 or x.std()<1e-10:continue
            for kk in [2,3]:
                label=cut_tree(linkage(x,method='ward'),n_clusters=kk).ravel()+1
                means=pd.DataFrame(dict(label=label,effect=x.ravel())).groupby('label').effect.mean();rank={v:j+1 for j,v in enumerate(means.sort_values().index)}
                for w,ll in zip(z.worker,label):gr.append(dict(heldout_building=b,axis=ax,groups=kk,worker=w,subtype=rank[ll],interpretation='geometry phenotype, not ability or motivation'))
        print('PERSONNEL geometry refit',b,flush=True)
    gp=save('personnel/geometry_lobo_profiles.csv',pd.concat(gp,ignore_index=True));gr=save('personnel/geometry_lobo_rosters.csv',gr)
    pred=save('personnel/geometry_continuous_predictions.csv',effect_predict(gd,gp));save('personnel/geometry_continuous_summary.csv',prediction_summary(pred))
    migrations=[]
    axes=sorted(gr.axis.unique())
    for (held,kk),gg in gr.groupby(['heldout_building','groups']):
        for axa,axb in itertools.combinations(axes,2):
            p=gg[gg.axis==axa].set_index('worker').subtype;q=gg[gg.axis==axb].set_index('worker').subtype
            if not len(p) or not len(q):continue
            n,changes,ari=roster_match(p,q);migrations.append(dict(heldout_building=held,groups=kk,axis_a=axa,axis_b=axb,common_workers=n,changed_after_optimal_label_alignment=changes,ARI=ari))
    save('personnel/geometry_method_roster_migration.csv',migrations)
    stability=[]
    for (ax,kk),gg in gr.groupby(['axis','groups']):
        for b1,b2 in itertools.combinations(sorted(gg.heldout_building.unique()),2):
            p=gg[gg.heldout_building==b1].set_index('worker').subtype;q=gg[gg.heldout_building==b2].set_index('worker').subtype
            n,changes,ari=roster_match(p,q);stability.append(dict(axis=ax,groups=kk,fold_a=b1,fold_b=b2,common_workers=n,changed=changes,ARI=ari))
    save('personnel/geometry_leavebuilding_roster_stability.csv',stability)
    save('personnel/geometry_roster_stability_summary.csv',pd.DataFrame(stability).groupby(['axis','groups']).agg(fold_pairs=('ARI','size'),ARI_mean=('ARI','mean'),ARI_min=('ARI','min'),changed_workers_mean=('changed','mean')).reset_index())
    # FIX rosters first; curves compare measurements on identical people.
    curves=[];cache={};popcounts=[]
    def append_curves(key,cohort,model,kk,subtype,worker_ids,origin):
        g,ids,ws,mats,_=training_maps[key];ix=tuple(i for i,w in enumerate(ws) if w in worker_ids)
        if len(ix)<2:return
        ck=(key,ix)
        if ck not in cache:
            results=[];subids=[ids[i] for i in ix]
            for metric,d in mats.items():
                dd=d[np.ix_(ix,ix)];t=nominal_cut(metric,9)
                for kind in ['complete','representative']:
                    labels,_=partition(dd,subids,t,kind)
                    for k in range(1,len(ix)+1):results.append(dict(metric=metric,partition=kind,N=len(ix),k=k,next_uncovered=next_uncovered(dd,k,t),**fixed_stats(labels,k)))
            cache[ck]=results
        meta=dict(key=key,code=g['code'],building=g['building'],condition=g['condition'],cohort=cohort,model=model,groups=kk,subtype=subtype,workers='|'.join(ws[i] for i in ix),roster_origin=origin,curve_view='fixed_subtype_full_pool_hindsight')
        curves.extend(dict(**meta,**r) for r in cache[ck])
    for key,(g,ids,ws,mats,labs) in training_maps.items():
        if g['N']<19:continue
        for r in old.itertuples():
            append_curves(key,r.cohort,r.model,r.groups,r.group,set(str(r.worker_ids).split('|')),'historical_full_roster_hindsight_only')
        for (cfg,sub),z in rosters[rosters.heldout_building==g['building']].groupby(['config','subtype']):
            append_curves(key,'current24_lobo',cfg,int(cfg.rsplit('_',1)[-1]),sub,set(z.worker),'leave_target_building_out')
    cs=save('personnel/fixed_roster_group_curves.csv.gz',curves)
    chk=cs[(cs.cohort=='current24_lobo')&(cs.k.isin([3,5,8]))&(cs.N>=9)]
    save('personnel/fixed_lobo_roster_checkpoints.csv',chk.groupby(['condition','model','subtype','metric','partition','k']).agg(images=('key','nunique'),next_uncovered=('next_uncovered','mean'),expected_clusters=('fixed_expected_clusters','mean'),expected_singletons=('fixed_expected_singletons','mean')).reset_index())
    # Four-person composition: enumerate ACTUAL teams, keep exactly the same
    # fixed validation persons across configurations/measurements, no new votes.
    teams_meta=[];team_values=[];composition=[];availability=[]
    for key,(g,ids,ws,mats,labs) in training_maps.items():
        if g['condition']!='manual' or g['N']<19:continue
        n=len(ids);validation=sorted(range(n),key=lambda i:hashlib.sha256((key+'|'+ids[i]+'|validation').encode()).hexdigest())[:4]
        rest=[i for i in range(n) if i not in validation];ix=np.array(list(itertools.combinations(rest,4)),int)
        if not len(ix):continue
        teamstats={};tt=np.triu_indices(4,1)
        for m,d0 in mats.items():
            d=np.round(d0,8)
            for t0 in CUTS:
                t=nominal_cut(m,t0);near=d<=t
                incompatible=(d[ix[:,tt[0]],ix[:,tt[1]]]>t).mean(1)
                uncovered=(~near[np.array(validation)[None,:,None],ix[:,None,:]]).all(2).mean(1)
                teamstats[m,t0]=(incompatible,uncovered)
        # Save unique teams once; metrics in a separate table keyed by unit + team.
        for j,z in enumerate(ix):
            teams_meta.append(dict(unit=g['unit'],team=j,ids='|'.join(ids[i] for i in z),workers='|'.join(ws[i] for i in z),validation_ids='|'.join(ids[i] for i in validation),validation_workers='|'.join(ws[i] for i in validation)))
        vals=pd.DataFrame(dict(unit=g['unit'],team=np.arange(len(ix))))
        for (m,t),(a,b) in teamstats.items():vals[f'{m}_{t:g}_pair_incompatible']=a;vals[f'{m}_{t:g}_validation_uncovered']=b
        team_values.append(vals)
        for cfg,z in rosters[rosters.heldout_building==g['building']].groupby('config'):
            labmap=z.set_index('worker').subtype.to_dict();ql=np.array([labmap.get(w,0) for w in ws]);labels=ql[ix];valid=(labels>0).all(1)
            availability.append(dict(unit=g['unit'],key=key,code=g['code'],building=g['building'],config=cfg,qualified_pool=int((ql[rest]>0).sum()),valid_teams=int(valid.sum()),validation_workers='|'.join(ws[i] for i in validation)))
            groupix=collections.defaultdict(list)
            for j in np.flatnonzero(valid):
                co=collections.Counter(labels[j]);signature='|'.join(f'{x}:{co[x]}' for x in sorted(co));pattern={(4,):'AAAA',(3,1):'AAAB',(2,2):'AABB',(2,1,1):'AABC',(1,1,1,1):'ABCD'}[tuple(sorted(co.values(),reverse=True))]
                groupix[pattern,signature].append(j)
            for (pattern,signature),ji in groupix.items():
                for (m,t),(a,b) in teamstats.items():composition.append(dict(unit=g['unit'],key=key,code=g['code'],building=g['building'],config=cfg,pattern=pattern,signature=signature,metric=m,nominal_cut=t,teams=len(ji),team_pair_incompatible=float(a[ji].mean()),validation_uncovered=float(b[ji].mean()),partition='not_used_pair_metric',indices='|'.join(map(str,ji))))
        print('PERSONNEL four-person enumeration',g['code'],len(ix),flush=True)
    save('personnel/actual_fourperson_teams.csv.gz',teams_meta);save('personnel/actual_team_measurements.csv.gz',pd.concat(team_values,ignore_index=True));save('personnel/composition_coverage.csv',availability)
    comp=save('personnel/compositions_by_exact_subtype.csv.gz',composition)
    agg=[]
    for (cfg,m,t),z in comp.groupby(['config','metric','nominal_cut']):
        unit=[]
        for (key,b,pat),q in z.groupby(['key','building','pattern']):unit.append(dict(key=key,building=b,pattern=pat,value=np.average(q.validation_uncovered,weights=q.teams),within=np.average(q.team_pair_incompatible,weights=q.teams)))
        uu=pd.DataFrame(unit)
        for arm_a,arm_b in [('AAAA','AABC'),('AAAB','AABC'),('AABB','AABC')]:
            a=uu[uu.pattern==arm_a].set_index('key');b=uu[uu.pattern==arm_b].set_index('key');ii=a.index.intersection(b.index)
            if not len(ii):continue
            d=(b.loc[ii].value-a.loc[ii].value);db=pd.DataFrame(dict(delta=d,building=a.loc[ii].building)).groupby('building').delta.mean()
            rng=np.random.default_rng(20260920);boot=rng.choice(db.to_numpy(),size=(2000,len(db)),replace=True).mean(1)
            agg.append(dict(config=cfg,metric=m,nominal_cut=t,arm_a=arm_a,arm_b=arm_b,images=len(ii),buildings=len(db),a_uncovered=a.loc[ii].value.mean(),b_uncovered=b.loc[ii].value.mean(),image_equal_delta=d.mean(),building_equal_delta=db.mean(),conditional_building_bootstrap_lower=np.quantile(boot,.025),conditional_building_bootstrap_upper=np.quantile(boot,.975),causal_effect=False))
    save('personnel/composition_paired_summary.csv',agg)
    # Time is not recomputed by any partition operation, and the original frozen
    # source audit is linked by SHA rather than imputed with lead_time.
    dump('PERSONNEL_AUDIT.json',dict(historical_configurations=len(inv),historical_unique_roster_groups=len(old),old_axes_refit_rows=len(profiles),old_roster_rows=len(rosters),old_profile_max_rounding_error=profile_error,changed_old_roster_rows=changed,
      geometry_axis_rows=len(gd),geometry_lobo_rows=len(gp),distinct_fixed_person_subsets=len(cache),group_curve_rows=len(cs),unique_actual_fourperson_teams=len(teams_meta),high_support_manual_composition_images=len({x['unit'] for x in teams_meta}),
      frozen_time_sha256=sha(STUDY/'inputs/frozen_time_audit.csv'),frozen_time_changed=False,reference_axes_are_versioned_historical_not_recomputed_current_geometry=True,training_excludes_target_building=True,borrowed_imputations_excluded_from_both_training_and_composition_validation=True,
      group_curves_are_fixed_subtype_pool_hindsight=True,full_population_prefix_reclustering_in_separate_module=True,final_personality_taxonomy_selected=False,new_person_exclusions=False))
    print('PERSONNEL COMPLETE',flush=True)
if __name__=='__main__':main()
