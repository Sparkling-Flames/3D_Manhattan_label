"""Memory-bounded target construction. This is the execution entry for tiers.

The complete sensitivity grid is streamed to gzip; counts, transition tables and
per-image evidence are retained. No prediction score chooses a definition.
"""
from __future__ import annotations
import csv as csvlib
import gzip,itertools,collections,json
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_core import *


def run():
    (OUT/'targets').mkdir(parents=True,exist_ok=True)
    keys=['image_id','condition','cut']
    st=pd.read_csv(OLD/'process/image_uncertainty_structure.csv')
    rr=pd.read_csv(OLD/'process/replay_states.csv.gz')
    cv=pd.read_csv(OLD/'process/image_growth_curves.csv.gz')
    mm=pd.read_csv(OLD/'process/mode_memberships.csv.gz')
    raw=pd.read_csv(OUT/'inputs/response_metrics_sanitized.csv.gz')
    allowed=set(raw.loc[raw.main_worker_included&raw.geometry_valid,'canonical_annotation_id'])
    assert set(mm.canonical_annotation_id)<=allowed
    assert not mm.worker_id.isin(['W019','W026']).any()
    actual=raw[raw.main_worker_included&raw.raw_condition.isin(['manual','semi'])].groupby(['image_id','raw_condition']).size()
    for a in st.to_dict('records'):assert int(a['n_observed'])==int(actual.loc[(a['image_id'],a['condition'])])
    cg={k:g.sort_values('k') for k,g in cv.groupby(keys)}
    rg={k:g for k,g in rr.groupby(keys+['rule'])}
    params=['cut','rule','confirmation','early_k','late_h','max_few_modes','max_singleton_mass','order_fraction_required','medium_definition']
    fields=['image_id','condition',*params,'grade','status','p_early','p_cumulative','p_late_interval','actual_late_limit','horizon_censored']
    counts=collections.Counter();sensitivity=collections.defaultdict(collections.Counter)
    evidence=[];anchors=[];changes=[];grid_n=0
    with gzip.open(OUT/'targets/definition_grid.csv.gz','wt',encoding='utf-8',newline='') as fh:
        writer=csvlib.DictWriter(fh,fieldnames=fields);writer.writeheader()
        for a in st.to_dict('records'):
            ident=(a['image_id'],a['condition'],a['cut']);n=int(a['n_valid']);invalid=int(a['n_invalid'])
            modes=int(a.get('n_supported_modes',0)) if pd.notna(a.get('n_supported_modes')) else 0
            single=float(a.get('singleton_mass',1)) if pd.notna(a.get('singleton_mass')) else 1.
            curve=cg.get(ident,pd.DataFrame());late=curve[curve.k>n/2] if len(curve) else curve
            def avg(c):return float(late[c].mean()) if c in late and len(late) else np.nan
            novelty=avg('new_incompatible_mode');repartition=avg('repartition_pair_change');drift=avg('within_mode_step_delta');promote=avg('support_promotions')
            mid=curve.iloc[(curve.k-n/2).abs().argmin()] if len(curve) else {}
            half_tv=float(mid.get('TV_full_observed',np.nan))
            change=bool((np.isfinite(novelty) and novelty>.05) or (np.isfinite(repartition) and repartition>.05) or (np.isfinite(drift) and drift>.02))
            for rule in RULES:
                replay=rg.get(ident+(rule,));onsets=replay.onset.to_numpy(float) if replay is not None else np.array([np.nan])
                tail=replay.state.isin(['observed_unified','stable_multicluster']).to_numpy() if replay is not None else np.array([False])
                base=dict(image_id=ident[0],condition=ident[1],cut=ident[2],building=ident[0].split('_')[0],rule=rule,n_observed=int(a['n_observed']),n_valid=n,n_invalid=invalid,n_supported_modes=modes,n_singletons=int(round(single*n)),singleton_mass=single,n_modes=a.get('n_modes',0),same_point_count_multimodality=a.get('same_topology_multimodality',False),point_count_disagreement=a.get('topology_disagreement',np.nan),within_mode_median=a.get('within_mode_median_d',np.nan),late_new_geometry=novelty,late_repartition=repartition,late_geometry_step=drift,late_support_promotions=promote,half_tv=half_tv,p_tail_stable=float(tail.mean()),onset_median_conditional=finite_median(onsets))
                for confirm in ('suffix','suffix_and_tail'):
                    onset=np.where(tail,onsets,np.nan) if confirm=='suffix_and_tail' else onsets
                    pany=float(np.mean(np.isfinite(onset)))
                    for k in range(2,9):
                        pe=float(np.mean(onset<=k));ev=dict(base,confirmation=confirm,early_k=k,p_early=pe,p_any_stable=pany,observed_early_limit=min(k,max(0,n-1)),observations_after_k=max(0,n-k),early_limit_censored=n<=k)
                        evidence.append(ev)
                        for h,x,smax,q in itertools.product((10,12,15,18,19),(2,3,4),(0.,.1),(.8,.9)):
                            pc=float(np.mean(onset<=h));pl=float(np.mean((onset>k)&(onset<=h)));oldnew={}
                            for mode in ('interval','cumulative'):
                                grade,status=classify(n,invalid,modes,single,pe,pc,pl,pany,change,k,h,x,smax,q,mode)
                                row=dict(image_id=ident[0],condition=ident[1],cut=ident[2],rule=rule,confirmation=confirm,early_k=k,late_h=h,max_few_modes=x,max_singleton_mass=smax,order_fraction_required=q,medium_definition=mode,grade=grade,status=status,p_early=pe,p_cumulative=pc,p_late_interval=pl,actual_late_limit=min(h,max(0,n-1)),horizon_censored=n<h)
                                writer.writerow(row);grid_n+=1;counts[tuple(row[p] for p in params)+ (ident[1],grade,status)]+=1
                                oldnew[mode]=grade
                                if all(row[p]==v for p,v in ANCHOR.items()):anchors.append(dict(ev,**{p:v for p,v in row.items() if p not in ev}))
                                if rule in ('D10_distribution','G10_geometry') and k in (7,8) and h in (15,19) and x==3 and smax==.1 and q==.8 and mode=='cumulative':sensitivity[ident[:2]][grade]+=1
                            if oldnew['interval']!=oldnew['cumulative']:
                                changes.append(dict(image_id=ident[0],condition=ident[1],cut=ident[2],rule=rule,confirmation=confirm,early_k=k,late_h=h,max_few_modes=x,max_singleton_mass=smax,order_fraction_required=q,interval_grade=oldnew['interval'],cumulative_grade=oldnew['cumulative'],p_early=pe,p_cumulative=pc,p_late_interval=pl,n_valid=n))
    csv('targets/onset_evidence.csv.gz',evidence)
    csv('targets/definition_counts.csv',[dict(zip(params+['condition','grade','status'],k),n_images=v) for k,v in counts.items()])
    anchor=csv('targets/primary_per_image.csv',anchors)
    robust=[]
    for (i,arm),co in sensitivity.items():
        winner,nw=co.most_common(1)[0];nd=sum(co.values());prop=nw/nd
        robust.append(dict(image_id=i,condition=arm,modal_grade=winner,agreement_across_definitions=prop,robust_assigned_grade=winner if winner in GRADES and prop>=.8 else '',distinct_assigned_grades=sum(1 for s in co if s in GRADES),status='definition_disagreement' if len(co)>1 else 'same_output_across_family',n_definitions=nd))
    robust=csv('targets/robustness_per_image.csv',robust)
    csv('targets/primary_with_robustness.csv',anchor.merge(robust,on=['image_id','condition']))
    csv('targets/interval_to_cumulative_changes.csv.gz',changes)
    csv('targets/growth_curves_reused.csv.gz',cv.drop(columns=['scene'],errors='ignore'))
    csv('targets/mode_memberships_reused.csv.gz',mm.drop(columns=['scene'],errors='ignore'))
    cont=anchor.copy();eligible=(cont.n_valid>=4)&cont.n_invalid.eq(0)&(cont.singleton_mass<=.1+1e-10)
    cont['cdf_early7']=cont.p_early.where(eligible);cont['cdf_observed_by19']=cont.p_cumulative.where(eligible)
    for name in ('late_new_geometry','half_tv','within_mode_median'):cont.loc[cont.n_valid<4,name]=np.nan
    cont.loc[cont.n_valid<2,'singleton_mass']=np.nan
    csv('targets/continuous_targets.csv',cont)
    tags=pd.read_csv(OUT/'expert/independent_tags106.csv');over=anchor.merge(tags,on='image_id');csv('expert/overlap_per_image.csv',over)
    csv('expert/overlap_cross_tab.csv',over.groupby(['condition','expert_tag','grade','status'],dropna=False).size().reset_index(name='images'))
    eid=set(tags.image_id);hid=set(anchor.image_id);assigned=anchor[anchor.grade.isin(GRADES)];rid=set(robust.loc[robust.robust_assigned_grade.isin(GRADES),'image_id'])
    coverage=dict(historical_unique_images=len(hid),historical_image_conditions=len(anchor),expert_images=len(eid),overlap_images=len(hid&eid),historical_outside_expert=len(hid-eid),primary_assigned_images=assigned.image_id.nunique(),primary_assigned_image_conditions=len(assigned),new_primary_assigned_images=len(set(assigned.image_id)-eid),robust_assigned_images=len(rid),new_robust_assigned_images=len(rid-eid),union_descriptive_images=len(hid|eid),union_expert_or_primary_assigned=len(eid|set(assigned.image_id)),grid_rows=grid_n,grade_counts=assigned.groupby(['condition','grade']).size().to_dict(),status_counts=anchor.groupby(['condition','status']).size().to_dict())
    js('targets/coverage.json',coverage)
    js('METHOD.json',dict(version='history_difficulty_v1_followup',anchor=ANCHOR,early_k=list(range(2,9)),late_h=[10,12,15,18,19],mode_caps=[2,3,4],singleton_caps=[0,.1],order_proportions=[.8,.9],cuts=[.05,.1,.2],rules=RULES,medium_definitions=['interval','cumulative'],confirmation=['suffix','suffix_and_tail'],difficulty_candidate='n>=10, total modes>=5, >=2 singleton people and share>=.2, plus observed latter-half novelty>.05 or repartition>.05 or within-mode step>.02',actual_n_is_primary=True,grade_and_status_separate=True,old_experimental_difficulty_used=False,expert_tags_used_for_tiers=False,retrospective_full_partition_used_only_for_targets=True,replays_are_not_independent_samples=True,short_suffix_is_not_long_term_stability=True,unresolved_singletons_may_be_rare_modes=True,robustness='cut/rule/k/h/confirmation family, agreement is sensitivity not confidence',classification_k8='latest user request supersedes old k<8 text',entry='history_difficulty_v1_targets'))
    print('TARGET COVERAGE',json.dumps(safe(coverage),ensure_ascii=False),flush=True)

if __name__=='__main__':run()
