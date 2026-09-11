"""Independent numerical audit and new sensitivity analyses, pinned 2026-09-09.

No import of the reviewed estimation functions. NumPy/SciPy implement numerical
primitives. All source measurements, finite-window labels and classifications are
conditional retrospective objects, not physical truth or new-worker validation.
"""
from __future__ import annotations
import argparse, gzip, hashlib, json, math, sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.cluster.hierarchy import linkage, cut_tree
from scipy.stats import spearmanr
from sklearn.metrics import adjusted_rand_score
BASELINE='c091c3457130d225967e2b62b8e484c9205ab638'
SEED=20260909
R=None; O=None; used={}

def path(rel):
    p=R/rel
    if not p.is_file() and rel.endswith('/window_metrics.csv.gz'):
        # Offline delivery may contain the exact selected configs/windows only.
        # This projection is logged separately; it is not the full source file.
        p=p.with_name('window_metrics.selected.csv.gz')
    assert p.is_file(),p
    if rel not in used:used[rel]={'path':rel,'resolved_path':str(p.relative_to(R)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
    return p

def csv(rel):
    return pd.read_csv(path(rel),dtype={'worker_id':str,'fine_label':str,'label':str,'current20_member':str},keep_default_na=True)

def lines(rel):
    p=path(rel)
    with (gzip.open(p,'rt',encoding='utf-8-sig') if p.suffix=='.gz' else p.open(encoding='utf-8-sig')) as f:
        return [json.loads(s) for s in f if s.strip()]

def save(name,data):
    p=O/name;p.parent.mkdir(parents=True,exist_ok=True)
    if name.endswith('.json'):
        p.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else str(x)),encoding='utf-8')
    else:
        (data if isinstance(data,pd.DataFrame) else pd.DataFrame(data)).to_csv(p,index=False,float_format='%.12g',compression={'method':'gzip','mtime':0} if name.endswith('.gz') else None)

def directions(points):
    xy=np.asarray(points,dtype=float)
    if xy.ndim!=2 or xy.shape[1]!=2 or len(xy)==0 or not np.isfinite(xy).all():raise ValueError('invalid_points')
    az=2*np.pi*(xy[:,0]%1024)/1024;el=np.pi/2-np.pi*xy[:,1]/512
    v=np.c_[np.cos(el)*np.cos(az),np.cos(el)*np.sin(az),np.sin(el)]
    return v[np.lexsort(v.T[::-1])]

def ospa(points,ref,c):
    a,b=directions(points),directions(ref)
    angle=np.degrees(np.arctan2(np.linalg.norm(np.cross(a[:,None],b[None]),axis=2),np.clip(a@b.T,-1,1)))
    cost=np.minimum(angle,c);i,j=linear_sum_assignment(cost)
    return (cost[i,j].sum()+c*abs(len(a)-len(b)))/max(len(a),len(b))

def fit_effect(d,value,workers=None):
    d=d[np.isfinite(d[value])].copy()
    d=d[d.groupby('context_key').worker_id.transform('nunique')>=2]
    ids=sorted(d.worker_id.unique()) if workers is None else list(workers)
    if set(d.worker_id)!=set(ids):raise ValueError('missing_workers')
    groups=d.groupby('context_key',sort=False).indices
    x=np.eye(len(ids))[pd.Categorical(d.worker_id,categories=ids).codes]
    y=d[value].to_numpy(float).copy()
    for ix in groups.values():x[ix]-=x[ix].mean(0);y[ix]-=y[ix].mean()
    b,_,rank,_=np.linalg.lstsq(x,y,rcond=1e-10)
    if rank!=len(ids)-1:raise ValueError('disconnected_worker_graph')
    b-=b.mean();b[np.abs(b)<1e-12]=0
    return pd.Series(b,index=ids)

def hierarchy(manual,semi,forced=None):
    manual=manual.sort_index();semi=semi.sort_index()
    coarse=pd.Series(1+(manual>np.median(manual)).astype(int),index=manual.index)
    ids=manual.index.intersection(semi.index).sort_values()
    p=pd.DataFrame({'manual_effect':manual.loc[ids],'semi_effect':semi.loc[ids],'coarse_label':coarse.loc[ids]})
    X=np.c_[np.ones(len(ids)),p.manual_effect]
    b=np.linalg.lstsq(X,p.semi_effect,rcond=None)[0];p['manual_prediction']=X@b
    XX=np.c_[X,p.manual_effect**2];p['manual_quadratic_prediction']=XX@np.linalg.lstsq(XX,p.semi_effect,rcond=None)[0]
    p['semi_residual']=p.semi_effect-p.manual_prediction
    p['fine_label']=p.coarse_label.astype(str)+'.0'
    for label,g in p.groupby('coarse_label'):
        if len(g)<4 or g.semi_residual.nunique()<2:continue
        v=cut_tree(linkage(g[['semi_residual']].to_numpy(),method='ward'),n_clusters=2).ravel()
        if min(np.bincount(v))<2:continue
        means=pd.Series(g.semi_residual.to_numpy()).groupby(v).mean().sort_values()
        rank={k:j+1 for j,k in enumerate(means.index)}
        p.loc[g.index,'fine_label']=[str(label)+'.'+str(rank[a]) for a in v]
    if forced is not None:
        p['fine_label']=p.index.map(forced)
        if p.fine_label.isna().any():raise ValueError('missing_forced_labels')
    p['layer_value']=p.manual_prediction+p.groupby('fine_label').semi_residual.transform('mean')
    p['coarse_value']=p.groupby('coarse_label').semi_effect.transform('mean')
    p['fine_value']=p.groupby('fine_label').semi_effect.transform('mean')
    return p

def evaluate(test,p,value):
    d=test[test.worker_id.isin(p.index)].copy()
    d=d[d.groupby('context_key').worker_id.transform('size')>=2]
    d['target']=d[value]-d.groupby('context_key')[value].transform('mean')
    for feature in ['manual_prediction','manual_quadratic_prediction','layer_value','semi_effect','coarse_value','fine_value']:
        z=d.worker_id.map(p[feature]);z=z-z.groupby(d.context_key).transform('mean')
        d[feature+'_prediction']=z;d[feature+'_sse']=(d.target-z)**2
    d['baseline_sse']=d.target**2
    return d

REF='analysis_results/worker_reference_feasibility_20260909_v1/'
SEM='analysis_results/semi_subtype_exploration_20260909_v1/'
VIEW='analysis_results/confirmed_point_calculation_view_20260909_v1/'
MULTI='analysis_results/multibuilding_threshold_stability_20260909_v1/revised/'

def worker_audit():
    orig=csv(REF+'response_measurements.csv.gz');ref={r['image_id']:r for r in lines(REF+'reference_ledger.jsonl')}
    prior={r['canonical_annotation_id']:r for r in lines(VIEW+'calculation_view.jsonl.gz')}
    current={r['canonical_annotation_id']:r for r in lines(VIEW+'reviewed/calculation_view.jsonl.gz')}
    checks=[];version=[];values={}
    for r in orig.to_dict('records'):
        cid=r['canonical_annotation_id'];p=prior[cid];q=current[cid];reference=ref[r['image_id']]
        changed=json.dumps(p['effective_points_1024x512'])!=json.dumps(q['effective_points_1024x512']) or p['calculation_included']!=q['calculation_included']
        if r['measurement_status']=='computable':
            vals={f'ospa{c}':ospa(p['effective_points_1024x512'],reference['points_1024x512'],c) for c in [30,60]}
            err=max(abs(vals[m]-r[m]) for m in vals);assert err<1e-8,(cid,err)
            checks.append(dict(canonical_annotation_id=cid,max_abs_error=err,reference_basis=r['reference_basis']))
            values[cid]=vals
        if changed:
            item=dict(canonical_annotation_id=cid,image_id=r['image_id'],worker_id=r['worker_id'],stage=r['stage'],condition=r['raw_condition'],
                      old_processing=p['processing_status'],new_processing=q['processing_status'],old_included=p['calculation_included'],new_included=q['calculation_included'],
                      old_count=p['effective_point_count'],new_count=q['effective_point_count'],reference_score_allowed=reference['score_allowed'],imputed=q.get('imputed_point',False))
            if r['measurement_status']=='computable':item.update({f'old_{m}':r[m] for m in ['ospa30','ospa60']})
            if q['calculation_included'] and reference['score_allowed']:
                for c in [30,60]:item[f'new_ospa{c}']=ospa(q['effective_points_1024x512'],reference['points_1024x512'],c)
            version.append(item)
    save('reference_distance_independent_checks.csv',checks);save('calculation_version_changes.csv',version)
    score=orig[orig.measurement_status=='computable'].copy()
    man=score[score.raw_condition=='manual'].groupby(['image_id','building_id','worker_id','current20_member'])[['ospa30','ospa60']].mean().reset_index()
    man['context_key']=man.image_id
    semi=csv(SEM+'semi_response_features.csv')
    props=csv('analysis_results/uncertainty_cloud_inputs_20260906_v1/facts/proposal_response.csv.gz').set_index('canonical_annotation_id')
    pp=[]
    for s in semi.to_dict('records'):
        r=props.loc[s['canonical_annotation_id']];initial=json.loads(r.initial_points_json);final=json.loads(r.final_points_json)
        errors=[]
        for c in [30,60]:
            m='ospa'+str(c);err=abs(ospa(initial,final,c)-s['edit_'+m]);errors.append(err)
            if ref[s['image_id']]['score_allowed']:
                refpoints=ref[s['image_id']]['points_1024x512']
                errors += [abs(ospa(initial,refpoints,c)-s['initial_'+m]),abs(ospa(final,refpoints,c)-s['final_'+m])]
                errors += [abs(s['initial_'+m]-s['final_'+m]-s['gain_'+m])]
        assert max(errors)<1e-8
        pp.append(dict(canonical_annotation_id=s['canonical_annotation_id'],max_abs_error=max(errors),raw_final_equals_canonical=np.allclose(final,prior[s['canonical_annotation_id']]['raw_points_1024x512'])))
    save('semi_geometry_independent_checks.csv',pp)
    memberships=csv(SEM+'fold_members.csv');saved=csv(SEM+'heldout_predictions.csv.gz');sums=csv(SEM+'validation_summary.csv')
    allpred=[];coefcheck=[]
    for cohort in ['all26','current20']:
      mm=man if cohort=='all26' else man[man.current20_member.str.lower()=='true'];ss=semi[semi.worker_id.isin(mm.worker_id)]
      for pool in ['all_initializations','without_synthetic']:
       sd=ss if pool=='all_initializations' else ss[ss.source_group!='trap_synthetic_disjoint_source']
       for metric in ['ospa30','ospa60']:
        for outcome in ['edit','final','final_via_edit_labels']:
         val=('edit_' if outcome=='edit' else 'final_')+metric;dd=sd[np.isfinite(sd[val])]
         for b,test in dd.groupby('building_id'):
          mf=fit_effect(mm[mm.building_id!=b],metric);sf=fit_effect(dd[dd.building_id!=b],val)
          forced=None
          if outcome=='final_via_edit_labels':
           ep=hierarchy(mf,fit_effect(sd[sd.building_id!=b],'edit_'+metric));forced=ep.fine_label.to_dict()
          p=hierarchy(mf,sf,forced)
          old=memberships[(memberships.cohort==cohort)&(memberships.pool==pool)&(memberships.metric==metric)&(memberships.outcome==outcome)&(memberships.heldout_building==b)].set_index('worker_id')
          assert set(old.index)==set(p.index)
          numeric=['manual_effect','semi_effect','manual_prediction','manual_quadratic_prediction','layer_value']
          err=float(np.max(np.abs(old.loc[p.index,numeric].to_numpy()-p[numeric].to_numpy())))
          labelmatch=(old.loc[p.index].fine_label==p.fine_label).all()
          assert err<1e-7 and labelmatch,(cohort,pool,metric,outcome,b,err)
          coefcheck.append(dict(cohort=cohort,pool=pool,metric=metric,outcome=outcome,building=b,max_abs_error=err,labels_match=labelmatch))
          pred=evaluate(test,p,val).assign(cohort=cohort,pool=pool,metric=metric,outcome=outcome)
          allpred.append(pred)
    P=pd.concat(allpred,ignore_index=True)
    keys=['canonical_annotation_id','cohort','pool','metric','outcome'];compare=P.merge(saved,on=keys,suffixes=('_new','_old'),validate='one_to_one')
    assert len(compare)==len(saved)==len(P)
    error=float(np.max(np.abs(compare.layer_value_prediction-compare.layer_prediction)))
    assert error<1e-7,error
    save('semi_coefficients_independent_checks.csv',coefcheck)
    result=[];rng=np.random.default_rng(SEED)
    for key,g in P.groupby(['cohort','pool','metric','outcome']):
        meta=dict(zip(['cohort','pool','metric','outcome'],key))
        b=g.groupby('building_id')[['layer_value_sse','manual_quadratic_prediction_sse','semi_effect_sse']].mean()
        layer=b.layer_value_sse.to_numpy();quad=b.manual_quadratic_prediction_sse.to_numpy();individual=b.semi_effect_sse.to_numpy()
        gain=1-layer.mean()/quad.mean();ix=rng.integers(0,len(b),(4000,len(b)));dif=(layer-quad)[ix].mean(1)
        score_old=sums[(sums.cohort==key[0])&(sums.pool==key[1])&(sums.metric==key[2])&(sums.outcome==key[3])].iloc[0]
        assert abs(gain-score_old.manual_plus_fine_vs_quadratic_building_gain)<1e-9
        result.append(dict(**meta,rows=len(g),images=g.image_id.nunique(),buildings=len(b),gain_vs_manual_quadratic=gain,
            layer_MSE=layer.mean(),manual_quadratic_MSE=quad.mean(),semi_individual_MSE=individual.mean(),
            mse_difference=(layer-quad).mean(),conditional_building_bootstrap_low=np.quantile(dif,.025),conditional_building_bootstrap_high=np.quantile(dif,.975),
            buildings_improved=int((layer<quad).sum()),interpretation='conditional_observed_workers_bootstrap_not_confirmatory'))
    save('semi_increment_independent_summary.csv',result)
    result=[]
    for key,g in P[P.cohort=='current20'].groupby(['pool','metric','outcome','stage']):
        b=g.groupby('building_id')[['layer_value_sse','manual_quadratic_prediction_sse']].mean()
        result.append(dict(zip(['pool','metric','outcome','stage'],key))|dict(rows=len(g),images=g.image_id.nunique(),buildings=len(b),gain=1-b.layer_value_sse.mean()/b.manual_quadratic_prediction_sse.mean()))
    save('semi_heldout_stage_breakdown.csv',result)
    save('reference_score_support.csv',score.groupby(['raw_condition','reference_basis']).agg(rows=('worker_id','size'),images=('image_id','nunique'),workers=('worker_id','nunique'),buildings=('building_id','nunique')).reset_index())
    save('WORKER_QA.json',dict(reference_rows=len(checks),semi_rows=len(pp),reproduced_membership_folds=len(coefcheck),reproduced_prediction_rows=len(P),prediction_max_error=error,
        changed_calculation_views=len(version),manual_score_rows=len(score[score.raw_condition=='manual']),latest_unassisted_version='reviewed view differs from classifier source',
        originals_modified=False,readable_source=True,neural_inference_runs=0))
    return man,semi

def complementary_and_transfer(man,semi):
    man=man[man.current20_member.str.lower()=='true'];semi=semi[semi.worker_id.isin(man.worker_id)]
    ids=sorted(man.worker_id.unique());buildings=sorted(man.building_id.unique());rng=np.random.default_rng(SEED+10)
    splits=[set(rng.permutation(buildings)[:len(buildings)//2]) for _ in range(120)]
    rr=[];trans=[]
    for pool in ['all_initializations','without_synthetic']:
      s=semi if pool=='all_initializations' else semi[semi.source_group!='trap_synthetic_disjoint_source']
      for metric in ['ospa30','ospa60']:
        for repeat,one in enumerate(splits):
          parts=[];why='valid'
          for side in [one,set(buildings)-one]:
            try:
              m=fit_effect(man[man.building_id.isin(side)],metric,ids)
              f=fit_effect(s[s.building_id.isin(side)],'edit_'+metric,ids)
              parts.append(hierarchy(m,f))
            except ValueError as e:why=str(e);break
          item=dict(pool=pool,metric=metric,replicate=repeat,status=why,building_half_a=';'.join(sorted(one)))
          if why=='valid':
            a,b=parts;item.update(manual_rank_correlation=spearmanr(a.manual_effect,b.manual_effect).statistic,
                semi_rank_correlation=spearmanr(a.semi_effect,b.semi_effect).statistic,
                residual_rank_correlation=spearmanr(a.semi_residual,b.semi_residual).statistic,
                coarse_ARI=adjusted_rand_score(a.coarse_label,b.coarse_label),fine_ARI=adjusted_rand_score(a.fine_label,b.fine_label),
                minimum_group_a=int(a.groupby('fine_label').size().min()),minimum_group_b=int(b.groupby('fine_label').size().min()))
          rr.append(item)
        for b,target in s[s.stage=='C1'].groupby('building_id'):
          train=s[(s.stage=='P1')&(s.building_id!=b)]
          try:
            mf=fit_effect(man[man.building_id!=b],metric,ids)
            ef=fit_effect(train,'edit_'+metric,ids);p=hierarchy(mf,ef)
            for outcome in ['edit','final_via_edit_labels']:
              value=('edit_' if outcome=='edit' else 'final_')+metric
              if outcome=='edit':model=p
              else:
                ff=fit_effect(train[np.isfinite(train[value])],value,ids)
                model=hierarchy(mf,ff,p.fine_label.to_dict())
              z=evaluate(target[np.isfinite(target[value])],model,value)
              trans.append(z.assign(pool=pool,metric=metric,outcome=outcome,training='P1_only_outside_C1_target_building'))
          except ValueError as e:
            trans.append(pd.DataFrame([dict(pool=pool,metric=metric,building_id=b,status=str(e))]))
    d=pd.DataFrame(rr);save('complementary_building_group_stability.csv',d)
    summary=[]
    for key,g in d.groupby(['pool','metric']):
      z=g[g.status=='valid'];r=dict(pool=key[0],metric=key[1],requested=len(g),valid=len(z))
      for c in ['manual_rank_correlation','semi_rank_correlation','residual_rank_correlation','coarse_ARI','fine_ARI']:
        for name,q in [('q25',.25),('median',.5),('q75',.75)]:r[c+'_'+name]=z[c].quantile(q) if len(z) else None
      summary.append(r)
    save('complementary_building_stability_summary.csv',summary)
    d=pd.concat(trans,ignore_index=True);save('P1_to_C1_transport_predictions.csv.gz',d)
    ss=[]
    for key,g in d.groupby(['pool','metric','outcome']):
      cols=['baseline_sse','layer_value_sse','manual_quadratic_prediction_sse','semi_effect_sse'];b=g.groupby('building_id')[cols].mean()
      item=dict(pool=key[0],metric=key[1],outcome=key[2],rows=int(g.target.notna().sum()),images=g.image_id.nunique(),buildings=len(b))
      for c in cols[1:]:item[c+'_gain_vs_no_workers']=1-b[c].mean()/b.baseline_sse.mean()
      item['layer_gain_vs_manual_quadratic']=1-b.layer_value_sse.mean()/b.manual_quadratic_prediction_sse.mean();ss.append(item)
    save('P1_to_C1_transport_summary.csv',ss)

def tv_math():
    rng=np.random.default_rng(SEED);rows=[]
    for k in [1,2,4,9,15,20]:
      for h in [1,2,3,5]:
        j=k+h;labels=np.r_[np.zeros(k,int),np.ones(h,int)]
        vals=[]
        for _ in range(100):
          lab=rng.integers(0,5,j);x=np.bincount(lab[:k],minlength=5)/k;y=np.bincount(lab,minlength=5)/j;v=.5*abs(x-y).sum()
          assert v<=h/j+1e-12;vals.append(v)
        extremal=.5*np.abs(np.array([1.,0])-np.array([k/j,h/j])).sum();assert abs(extremal-h/j)<1e-12
        rows.append(dict(k=k,h=h,universal_TV_bound=h/j,attained_example=extremal,random_test_max=max(vals)))
    save('TV_mechanical_bound_checks.csv',rows)
    save('TV_automatically_satisfied_grid.csv',[dict(h=h,epsilon=e,first_k_guaranteed=math.ceil(h*(1-e)/e-1e-10)) for h in [1,2,3,5] for e in [.05,.1,.2]])

def onset(k,L,U,rate=.8):
    def start(v):
        stable=np.minimum.accumulate(np.asarray(v)[::-1])[::-1]>=rate-1e-12
        return float(np.asarray(k)[np.flatnonzero(stable)[0]]) if stable.any() else np.nan
    lo,hi=start(U),start(L)
    state='identified' if np.isfinite(hi) and lo==hi else 'finite_interval' if np.isfinite(hi) else 'upper_unknown' if np.isfinite(lo) else 'not_reached'
    return lo,hi,state

def building_audit():
    tv_math();check=[];summary=[];foldgains=[];windowfiles={};onsets=[]
    for cohort in ['with_workers','without_workers']:
      cur=csv(MULTI+cohort+'/replay/stability_curves.csv')
      assert ((cur.stable+cur.changing+cur.unknown)==200).all()
      assert np.allclose(cur.stable_lower,cur.stable/200) and np.allclose(cur.stable_upper,(cur.stable+cur.unknown)/200)
      p=path(MULTI+cohort+'/replay/window_metrics.csv.gz');parts=[]
      for q in pd.read_csv(p,chunksize=300000):
        z=q[q.config.isin(['q_0.950','ospa30_t6']) & q.lookahead.isin([1,5])];parts.append(z)
      windows=pd.concat(parts,ignore_index=True)
      save(cohort+'_selected_window_metrics.csv.gz',windows)
      for c in ['prefix_support_1','prefix_support_2','prefix_support_3']:
        windows[c]=pd.to_numeric(windows[c])
      windows['reconstructed_unknown']=(windows.prefix_support_2==0)|(windows.status!='evaluated')
      windows['reconstructed_stable']=(~windows.reconstructed_unknown)&(windows.max_membership<=.1+1e-12)&(windows.max_shares<=.1+1e-12)&(windows.promotion_2==0)
      rec=windows.groupby(['image_id','config','k','lookahead']).agg(rebuilt_unknown=('reconstructed_unknown','sum'),rebuilt_stable=('reconstructed_stable','sum')).reset_index()
      saved_selected=cur[cur.config.isin(['q_0.950','ospa30_t6']) & cur.lookahead.isin([1,5]) & (cur.min_support==2)&np.isclose(cur.epsilon,.1)]
      rc=rec.merge(saved_selected,on=['image_id','config','k','lookahead'],validate='one_to_one')
      assert (rc.rebuilt_unknown==rc.unknown).all() and (rc.rebuilt_stable==rc.stable).all()
      windows['known_prefix_has_no_pair']=(windows.prefix_support_2==0)&(windows.status=='evaluated')
      windows['pass_tv_010']=windows.max_shares<=.1+1e-12
      windows['automatic_tv_010']=windows.lookahead/(windows.k+windows.lookahead)<=.1+1e-12
      ws=windows.groupby(['image_id','config','k','lookahead']).agg(known_insufficient=('known_prefix_has_no_pair','sum'),auto_tv=('automatic_tv_010','first')).reset_index()
      d=cur[cur.config.isin(['q_0.950','ospa30_t6']) & cur.lookahead.isin([1,5]) & (cur.min_support==2)&np.isclose(cur.epsilon,.1)].merge(ws,on=['image_id','config','k','lookahead'],validate='one_to_one')
      assert (d.known_insufficient<=d.unknown).all()
      d['support_separated_upper']=d.stable_upper-d.known_insufficient/200
      save(cohort+'_support_unknown_sensitivity.csv.gz',d)
      for key,g in d.groupby(['image_id','config','lookahead']):
        g=g.sort_values('k');old=onset(g.k,g.stable_lower,g.stable_upper);new=onset(g.k,g.stable_lower,g.support_separated_upper)
        onsets.append(dict(cohort=cohort,image_id=key[0],config=key[1],h=key[2],last_k=int(g.k.max()),old_possible=old[0],old_guaranteed=old[1],old_status=old[2],
                          support_separated_possible=new[0],support_separated_guaranteed=new[1],support_separated_status=new[2],
                          status_changed=old[2]!=new[2],possible_changed=not(np.isclose(old[0],new[0],equal_nan=True)),
                          interpretation='definition_sensitivity_only; at_least_one_supported_cluster_is_required_not_measured'))
      for key,g in windows.groupby(['config','lookahead']):
        evals=g[g.status=='evaluated'];assert (evals.max_shares<=evals.lookahead/(evals.k+evals.lookahead)+1e-12).all()
        summary.append(dict(cohort=cohort,config=key[0],h=key[1],all_windows=len(g),evaluated=len(evals),known_insufficient=int(g.known_prefix_has_no_pair.sum()),
                            automatic_tv_windows=int(g.automatic_tv_010.sum()),valid_TV_bound=True))
      folds=csv(MULTI+'comparison/common_transfer_'+cohort+'/folds.csv.gz')
      b=csv(MULTI+'comparison/common_transfer_'+cohort+'/building_summary.csv');allb=b[b.source_n=='all']
      for conf,g in allb.groupby('config'):
        low=g.outside_error_lower-g.same_error_upper;high=g.outside_error_upper-g.same_error_lower
        assert np.allclose(low,g.benefit_lower) and np.allclose(high,g.benefit_upper)
        summary.append(dict(cohort=cohort,config=conf,summary='building_equal_transfer',buildings=len(g),
                same_error_lower=g.same_error_lower.mean(),same_error_upper=g.same_error_upper.mean(),outside_error_lower=g.outside_error_lower.mean(),outside_error_upper=g.outside_error_upper.mean(),
                benefit_lower=low.mean(),benefit_upper=high.mean(),buildings_positive_lower=int((low>0).sum()),buildings_negative_upper=int((high<0).sum()),
                same_prediction_unknown=g.same_prediction_unknown_mean.mean(),target_unknown=g.target_unknown_mean.mean(),outside_prediction_unknown=g.outside_prediction_unknown_mean.mean()))
      foldgains.append(allb.assign(cohort=cohort))
      subset=cur[(cur.lookahead==5)&(cur.min_support==2)&np.isclose(cur.epsilon,.1)]
      lookup={(i,c):g.sort_values('k')[['stable_lower','stable_upper']].to_numpy() for (i,c),g in subset.groupby(['image_id','config'])}
      for r in folds.to_dict('records'):
        ix=list(range(int(r['k_min']),int(r['k_max'])+1));conf=r['config']
        source=json.loads(r['source_images_json']);targets=json.loads(r['target_images_json'])
        arr=np.stack([lookup[i,conf][int(r['k_min'])-1:int(r['k_max'])] for i in source]);pred=arr.mean(0)
        target=np.stack([lookup[i,conf][int(r['k_min'])-1:int(r['k_max'])] for i in targets])
        lo=np.maximum(0,np.maximum(pred[:,0]-target[:,:,1],target[:,:,0]-pred[:,1])).mean()
        hi=np.maximum(np.abs(pred[:,0]-target[:,:,1]),np.abs(pred[:,1]-target[:,:,0])).mean()
        err=max(abs(lo-r['same_error_lower']),abs(hi-r['same_error_upper']))
        assert err<1e-10
        check.append(dict(cohort=cohort,building=r['building_id'],config=conf,fold_id=r['fold_id'],max_abs_error=err))
    save('building_window_and_transfer_summary.csv',summary);save('building_equal_transfer_details.csv',pd.concat(foldgains,ignore_index=True));save('building_same_source_independent_checks.csv.gz',check)
    save('support_state_onset_sensitivity.csv',onsets)
    save('BUILDING_QA.json',dict(transfer_folds_recomputed=len(check),max_error=max(r['max_abs_error'] for r in check),
            unknown_support_check='conservative_only_fully_evaluated_windows; not full relabel of partially missing future windows',
            rooms_required_for_building_grouping=False,new_worker_validation=False,new_stopping_rule=False))

def main():
    global R,O
    a=argparse.ArgumentParser();a.add_argument('--repo',type=Path,required=True);a.add_argument('--out',type=Path,required=True);a.add_argument('--part',choices=['worker','building','all'],default='all');args=a.parse_args()
    R=args.repo.resolve();O=args.out.resolve();O.mkdir(parents=True,exist_ok=True)
    if args.part in ['worker','all']:
        man,semi=worker_audit();print('REPRODUCED CURRENT WORKER TABLES',flush=True);complementary_and_transfer(man,semi);print('NEW WORKER SENSITIVITIES COMPLETE',flush=True)
    if args.part in ['building','all']:building_audit();print('BUILDING AUDIT COMPLETE',flush=True)
    save('SOURCE_MANIFEST_'+args.part+'.json',dict(baseline=BASELINE,files=list(used.values()),count=len(used),no_original_files_written=True))
if __name__=='__main__':main()
