#!/usr/bin/env python3
"""Fair scalar comparisons with selected, differently worded evidence layers.

Inputs are a wide score CSV, old24_evidence.json and screen_evidence_115.json.
Only explicitly allowed screen record IDs are used for numerical analyses.
All observations retain their original annotation record_id.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
from pathlib import Path

import numpy as np


EPS = 1e-10  # numerical ties only; not a human just-noticeable difference


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def write_csv(path, rows):
    if not rows:
        path.write_text('')
        return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        w.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows)


def scalar_order(a,b):
    """-1 lower, 0 numerical tie, 1 higher."""
    return 0 if abs(a-b)<=EPS else (1 if a>b else -1)


def pair_counts(records, scores, method, grade):
    out=[]
    for a,b in itertools.combinations(records,2):
        ya,yb=grade[a['record_id']],grade[b['record_id']]
        if ya==yb:
            continue
        best,worst=(a,b) if ya<yb else (b,a)
        delta=scores[best['record_id']][method]-scores[worst['record_id']][method]
        out.append(dict(method=method,better_record_id=best['record_id'],worse_record_id=worst['record_id'],
                        better_case_id=best['case_id'],worse_case_id=worst['case_id'],
                        better_grade=grade[best['record_id']],worse_grade=grade[worst['record_id']],
                        same_image=best['image_code']==worst['image_code'],score_margin=delta,
                        inversion=delta < -EPS,tie=abs(delta)<=EPS))
    return out


def unique_canonical(values):
    """Group arithmetic ties while leaving the supplied raw values untouched."""
    u=[]
    for value in sorted(set(float(x) for x in values)):
        if not u or value-u[-1]>EPS:
            u.append(value)
    return np.array(u)


def ranks_against_unique(values,unique):
    # EPS makes a value in the same numerical tie cluster use its first member.
    return np.searchsorted(unique,np.asarray(values)+EPS,side='right')-1


def predict_by_indices(ranks, kbad, kgood):
    return (ranks<kbad).astype(int)+(ranks<kgood).astype(int)


def interval(unique,k):
    return dict(lower_exclusive=None if k==0 else float(unique[k-1]),
                upper_inclusive=None if k==len(unique) else float(unique[k]),
                lower_unbounded=k==0,upper_unbounded=k==len(unique))


def fit_two_cutpoints(train_scores, train_grades, test_scores=None, test_grades=None):
    """Return all training-optimal threshold intervals and set predictions.

    Severity prediction is 2 for q<t_bad, 1 for t_bad<=q<t_good, 0 otherwise.
    No held label chooses a threshold. If test data are supplied, every threshold
    with minimal *training* loss is evaluated to identify a loss range. The test
    scores only enumerate prediction-equivalent possibilities inside training
    intervals; their labels are used for evaluation, never optimization.
    """
    tr=np.asarray(train_scores,float); y=np.asarray(train_grades,int)
    unique=unique_canonical(tr);rank=ranks_against_unique(tr,unique)
    optimum=None;training_solutions=[]
    for kb in range(len(unique)+1):
        for kg in range(kb,len(unique)+1):
            pred=predict_by_indices(rank,kb,kg)
            loss=int(np.abs(pred-y).sum())
            if optimum is None or loss<optimum:
                optimum=loss;training_solutions=[]
            if loss==optimum:
                training_solutions.append(dict(bad_interval=interval(unique,kb),good_interval=interval(unique,kg),
                                               bad_boundary_index=kb,good_boundary_index=kg,
                                               require_bad_threshold_le_good_threshold=True))
    result=dict(training_n=len(y),training_min_absolute_step_loss=optimum,
                training_optimal_interval_pairs=training_solutions,
                training_optimal_interval_pairs_count=len(training_solutions))
    if test_scores is None:
        return result
    te=np.asarray(test_scores,float); yt=np.asarray(test_grades,int)
    allunique=unique_canonical(np.r_[tr,te]);rtr=ranks_against_unique(tr,allunique);rte=ranks_against_unique(te,allunique)
    possible={}
    for kb in range(len(allunique)+1):
        for kg in range(kb,len(allunique)+1):
            ptr=predict_by_indices(rtr,kb,kg)
            if np.abs(ptr-y).sum()!=optimum:
                continue
            pte=predict_by_indices(rte,kb,kg)
            possible[tuple(int(x) for x in pte)]=int(np.abs(pte-yt).sum())
    assert possible
    predictions=list(possible)
    result.update(test_n=len(te),test_joint_prediction_vector_count=len(predictions),
                  test_loss_min=min(possible.values()),test_loss_max=max(possible.values()),
                  test_possible_grades=[sorted(set(p[i] for p in predictions)) for i in range(len(te))],
                  test_joint_prediction_vectors=[dict(grades=list(p),absolute_step_loss=loss) for p,loss in sorted(possible.items())])
    return result


def grouped_calibration(old, scores, methods):
    folds=[];preds=[];summary=[]
    for method in methods:
        method_folds=[]
        for building in sorted(set(r['building_id'] for r in old)):
            train=[r for r in old if r['building_id']!=building]
            test=[r for r in old if r['building_id']==building]
            fit=fit_two_cutpoints([scores[r['record_id']][method] for r in train],
                                 [r['quality_ordinal_original'] for r in train],
                                 [scores[r['record_id']][method] for r in test],
                                 [r['quality_ordinal_original'] for r in test])
            fit.update(method=method,held_development_building=building,
                       training_record_ids=[r['record_id'] for r in train],test_record_ids=[r['record_id'] for r in test])
            folds.append(fit);method_folds.append(fit)
            for r,poss in zip(test,fit['test_possible_grades']):
                preds.append(dict(method=method,case_id=r['case_id'],record_id=r['record_id'],
                                  building_id=building,original_grade=r['quality_ordinal_original'],
                                  score=scores[r['record_id']][method],possible_grade_predictions=poss,
                                  unique_prediction=len(poss)==1))
        full=fit_two_cutpoints([scores[r['record_id']][method] for r in old],[r['quality_ordinal_original'] for r in old])
        summary.append(dict(method=method,n=len(old),development_buildings=len(method_folds),
                            total_held_absolute_step_loss_min=sum(f['test_loss_min'] for f in method_folds),
                            total_held_absolute_step_loss_max=sum(f['test_loss_max'] for f in method_folds),
                            average_held_absolute_step_loss_min=sum(f['test_loss_min'] for f in method_folds)/len(old),
                            average_held_absolute_step_loss_max=sum(f['test_loss_max'] for f in method_folds)/len(old),
                            uniquely_predictable_cases=sum(r['unique_prediction'] for r in preds if r['method']==method),
                            full_development_resubstitution_min_step_loss=full['training_min_absolute_step_loss'],
                            full_development_optimal_interval_pairs=full['training_optimal_interval_pairs']))
    return summary,folds,preds


def severe_bridge(old,severe,scores,methods):
    rows=[];summary=[]
    for method in methods:
        for a in old:
            for s in severe:
                if a['record_id']==s['record_id']:
                    continue
                delta=scores[a['record_id']][method]-scores[s['record_id']][method]
                rows.append(dict(method=method,old_case_id=a['case_id'],old_record_id=a['record_id'],
                                 old_original_grade=a['quality_ordinal_original'],severe_case_id=s['case_id'],
                                 severe_record_id=s['record_id'],same_image=a['image_code']==s['image_code'],
                                 score_margin_old_minus_severe=delta,inversion=delta < -EPS,tie=abs(delta)<=EPS,
                                 different_question_protocols=True))
        for grade in [0,1,2,'all']:
            subset=[r for r in rows if r['method']==method and (grade=='all' or r['old_original_grade']==grade)]
            summary.append(dict(method=method,old_grade=grade,pairs=len(subset),
                                inversions=sum(r['inversion'] for r in subset),ties=sum(r['tie'] for r in subset),
                                same_image_pairs=sum(r['same_image'] for r in subset),
                                same_image_inversions=sum(r['same_image'] and r['inversion'] for r in subset),
                                interpretation='Cross-question selected-evidence compatibility only, not FPR/accuracy/prevalence.'))
    return summary,rows


def borderline_scenarios(severe,borderline,scores,methods):
    """New-protocol only. Every borderline 2/3 assignment is a scenario, not p."""
    allrecords=severe+borderline
    n=len(borderline);allcases=[];by_method={m:[] for m in methods}
    # Pair structure changes when a borderline is called severe, so every row
    # reports its denominator. Compare methods only within the same scenario.
    scenario_vectors=list(itertools.product([2,3],repeat=n))
    for sid,labels in enumerate(scenario_vectors):
        grade={s['record_id']:3 for s in severe};grade.update({r['record_id']:g for r,g in zip(borderline,labels)})
        for method in methods:
            pairs=pair_counts(allrecords,scores,method,grade)
            # The threshold feasibility interval is q(severe)<t<=q(obvious).
            # Empty intervals are reported; a perfect separator is not required.
            sq=[scores[r['record_id']][method] for r in allrecords if grade[r['record_id']]==3]
            oq=[scores[r['record_id']][method] for r in allrecords if grade[r['record_id']]==2]
            lower=max(sq) if sq else None;upper=min(oq) if oq else None
            row=dict(scenario_id=sid,method=method,borderline_labels=list(labels),
                     obvious_count=labels.count(2),severe_count=len(severe)+labels.count(3),pairs=len(pairs),
                     inversions=sum(r['inversion'] for r in pairs),ties=sum(r['tie'] for r in pairs),
                     same_image_pairs=sum(r['same_image'] for r in pairs),
                     same_image_inversions=sum(r['same_image'] and r['inversion'] for r in pairs),
                     perfect_separator_lower_exclusive=lower,perfect_separator_upper_inclusive=upper,
                     perfect_separator_exists=(lower is None or upper is None or lower<upper-EPS),
                     no_obvious_examples=not bool(oq))
            allcases.append(row);by_method[method].append(row)
    summaries=[]
    for method,rows in by_method.items():
        informative=[r for r in rows if r['pairs']]
        summaries.append(dict(method=method,borderline_records=n,severe_records=len(severe),scenarios=len(rows),
                              informative_scenarios=len(informative),
                              inversions_range=[min((r['inversions'] for r in informative),default=None),max((r['inversions'] for r in informative),default=None)],
                              all_borderline_obvious=rows[0],all_borderline_severe=rows[-1],
                              perfect_separation_informative_scenarios=sum(r['perfect_separator_exists'] for r in informative),
                              scenario_frequency_is_probability=False))
    decision=[]
    lookup={labels:sid for sid,labels in enumerate(scenario_vectors)}
    for i,record in enumerate(borderline):
        for ma,mb in itertools.combinations(methods,2):
            changes=[];winnerflips=[]
            for lab in scenario_vectors:
                if lab[i]!=2: continue
                to=list(lab);to[i]=3;other=tuple(to);s0=lookup[lab];s1=lookup[other]
                d0=by_method[ma][s0]['inversions']-by_method[mb][s0]['inversions']
                d1=by_method[ma][s1]['inversions']-by_method[mb][s1]['inversions']
                changes.append(d1-d0)
                if np.sign(d0)!=np.sign(d1):
                    winnerflips.append(dict(from_scenario=s0,to_scenario=s1,difference_before=d0,difference_after=d1,
                                            strict_reversal=d0*d1<0))
            decision.append(dict(case_id=record['case_id'],record_id=record['record_id'],method_a=ma,method_b=mb,
                                 inversion_difference_change_min=min(changes,default=0),inversion_difference_change_max=max(changes,default=0),
                                 candidate_order_or_tie_change_scenario_pairs=len(winnerflips),
                                 strict_reversal_scenario_pairs=sum(x['strict_reversal'] for x in winnerflips),
                                 example_changes=winnerflips[:5],scenario_counts_are_not_probabilities=True))
    return summaries,allcases,decision


def post_result_robustness(old,severe,borderline,scores,methods,source_rows,out):
    """Small audit added after the first fixed-candidate result, no new formulas.

    All old24 observations may vary by an adjacent grade. Finite scenarios are
    not probabilities. Analytic h roots locate ties inside the already proposed
    [0.25,1.0] family; they do not select a parameter or make a human threshold.
    """
    requested=['Q_v11','Q_no_topS','Q_IHC_h050','Q_floor_iou','Q_official_iou3d']
    if not all(m in methods for m in requested):
        return
    labels=[r['quality_ordinal_original'] for r in old]
    def inv(lab,records=old):
        grade={r['record_id']:y for r,y in zip(records,lab)}
        return {m:sum(p['inversion'] for p in pair_counts(records,scores,m,grade)) for m in requested}
    base=inv(labels);omissions=[]
    for row in old:
        sub=[r for r in old if r['record_id']!=row['record_id']]
        val=inv([r['quality_ordinal_original'] for r in sub],sub)
        omissions.append(dict(case_id=row['case_id'],omitted_record_id=row['record_id'],**val,
                              no_top_minus_v11=val['Q_no_topS']-val['Q_v11'],
                              net_improvement_incident_to_case=(base['Q_v11']-base['Q_no_topS'])-(val['Q_v11']-val['Q_no_topS'])))
    write_csv(out/'old24_case_omission_rank_diagnostics.csv',omissions)
    alternatives=[[g for g in range(max(0,y-1),min(3,y+1)+1) if g!=y] for y in labels]
    scenarios=[]
    for changed_n in [1,2]:
        for inds in itertools.combinations(range(len(old)),changed_n):
            for vals in itertools.product(*(alternatives[i] for i in inds)):
                lab=labels.copy()
                for i,y in zip(inds,vals):lab[i]=y
                v=inv(lab)
                scenarios.append(dict(changed_count=changed_n,
                                      changes=[dict(case_id=old[i]['case_id'],old=labels[i],scenario=y) for i,y in zip(inds,vals)],
                                      **v,no_top_minus_v11=v['Q_no_topS']-v['Q_v11'],
                                      IHC050_minus_no_top=v['Q_IHC_h050']-v['Q_no_topS'],
                                      floor_minus_no_top=v['Q_floor_iou']-v['Q_no_topS']))
    write_csv(out/'old24_one_two_adjacent_label_scenarios.csv',scenarios)
    change_summaries={}
    for n in [1,2]:
        subset=[r for r in scenarios if r['changed_count']==n]
        change_summaries[str(n)]=dict(n_scenarios=len(subset),**{k:dict(min=min(r[k] for r in subset),max=max(r[k] for r in subset))
                                                               for k in ['no_top_minus_v11','IHC050_minus_no_top','floor_minus_no_top']})
    dump(out/'old24_adjacent_label_scenario_summary.json',dict(base_inversions=base,change_summaries=change_summaries,
          all24_can_vary_regardless_of_comments=True,scenarios_not_probabilities=True,original_labels_unchanged=True,
          protocol_status='post-result robustness check; no new formula or grid'))
    grade={r['record_id']:r['quality_ordinal_original'] for r in old}
    pair_maps={m:{(p['better_record_id'],p['worse_record_id']):p for p in pair_counts(old,scores,m,grade)} for m in ['Q_v11','Q_no_topS']}
    changed=[]
    for key,a in pair_maps['Q_v11'].items():
        b=pair_maps['Q_no_topS'][key]
        if a['inversion']!=b['inversion'] or a['tie']!=b['tie']:
            changed.append(dict(better_case_id=a['better_case_id'],worse_case_id=a['worse_case_id'],
                                better_record_id=key[0],worse_record_id=key[1],same_image=a['same_image'],
                                original_better_grade=a['better_grade'],original_worse_grade=a['worse_grade'],
                                Q_v11_better=scores[key[0]]['Q_v11'],Q_v11_worse=scores[key[1]]['Q_v11'],
                                Q_no_topS_better=scores[key[0]]['Q_no_topS'],Q_no_topS_worse=scores[key[1]]['Q_no_topS'],
                                old_margin=a['score_margin'],new_margin=b['score_margin'],
                                change='improved_original_cross_grade_order' if a['inversion'] and not b['inversion'] else 'worsened_original_cross_grade_order'))
    write_csv(out/'no_topS_changed_cross_grade_pairs.csv',changed)
    dump(out/'no_topS_pair_change_summary.json',dict(
        improved_pairs=sum(r['change'].startswith('improved') for r in changed),
        worsened_pairs=sum(r['change'].startswith('worsened') for r in changed),
        same_image_improvements=sum(r['same_image'] and r['change'].startswith('improved') for r in changed),
        same_image_worsenings=sum(r['same_image'] and r['change'].startswith('worsened') for r in changed),
        case_omission_is_not_sample_exclusion=True,
        pair_counts_are_not_independent_sample_counts=True))
    if 'Q_IHC_h050' not in methods:
        return
    roots=[]
    for a in borderline:
        for b in severe:
            va,vb=source_rows[a['record_id']],source_rows[b['record_id']]
            Ha,Hb=float(va['Hstar']),float(vb['Hstar'])
            A=scores[a['record_id']]['Q_IHC_h050']*(1+(Ha/.5)**2)
            B=scores[b['record_id']]['Q_IHC_h050']*(1+(Hb/.5)**2)
            den=A-B;num=B*Ha**2-A*Hb**2
            h2=num/den if abs(den)>EPS else None
            root=float(np.sqrt(h2)) if h2 is not None and h2>0 else None
            residual=None
            if root is not None:
                residual=A/(1+(Ha/root)**2)-B/(1+(Hb/root)**2)
                assert abs(residual)<1e-7
            roots.append(dict(borderline_case_id=a['case_id'],borderline_record_id=a['record_id'],
                              severe_case_id=b['case_id'],severe_record_id=b['record_id'],
                              borderline_H=Ha,severe_H=Hb,borderline_IC_times100=A,severe_IC_times100=B,
                              equal_score_positive_h=root,root_in_fixed_025_to_100_family=root is not None and .25<=root<=1,
                              root_score_difference=residual,
                              relative_score_at_h025=A/(1+(Ha/.25)**2)-B/(1+(Hb/.25)**2),
                              relative_score_at_h050=A/(1+(Ha/.5)**2)-B/(1+(Hb/.5)**2),
                              relative_score_at_h100=A/(1+Ha**2)-B/(1+Hb**2),
                              severe_dominates_composed_IHC=(B>A and Hb<Ha),
                              roots_are_algebraic_pair_events_not_independent_critical_cases=True))
    write_csv(out/'IHC_height_scale_pair_roots.csv',roots)
    r071=[r for r in roots if r['borderline_case_id']=='S071']
    if r071:
        dump(out/'IHC_height_scale_interpretation.json',dict(
             expression='q(h)=100 I C /(1+(H/h)^2)',equal_score_condition='h^2=(B*Ha^2-A*Hb^2)/(A-B), A=100 Ia Ca, B=100 Ib Cb',
             S071_if_obvious_and_required_above_each_current_severe=dict(
                 maximum_positive_pair_root=max(r['equal_score_positive_h'] or 0 for r in r071),
                 governing_severe_case_id=max(r071,key=lambda r:r['equal_score_positive_h'] or 0)['severe_case_id'],
                 relation='h strictly above root; equality is a score tie, not a human transition'),
             limitations=['Conditional on the named case being classified obvious, current references/representations, and this IHC family only.',
                          'No human height threshold has been calibrated; no new parameter is recommended from this root.',
                          'Composed IC dominance is not dominance in D and F separately.',
                          'Unresolved borderline geometry is absent numerically and remains in the case ledger.']))


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--scores',type=Path,required=True)
    ap.add_argument('--old-evidence',type=Path,required=True)
    ap.add_argument('--screen-evidence',type=Path,required=True)
    ap.add_argument('--allowed-screen-ids',type=Path,required=True,help='JSON array of record IDs explicitly authorized for numerical comparison after audit')
    ap.add_argument('--methods',nargs='+',required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    old=json.loads(args.old_evidence.read_text());screen=json.loads(args.screen_evidence.read_text())
    allowed=set(json.loads(args.allowed_screen_ids.read_text()))
    scr={r['record_id']:r for r in screen}
    assert all(r in scr and not scr[r]['original_frozen_holdout'] and not scr[r]['calibration_scope_hold_reasons'] for r in allowed)
    desired=set(r['record_id'] for r in old)|allowed
    scores={};source_rows={}
    with args.scores.open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            rid=row['record_id']
            if rid not in desired: continue
            assert rid not in scores, f'Duplicate record_id: {rid}; choose one declared representation.'
            source_rows[rid]=row
            scores[rid]={}
            for method in args.methods:
                value=row.get(method)
                if value not in [None,'','null','None','nan','NaN']:
                    fv=float(value)
                    if np.isfinite(fv): scores[rid][method]=fv
    common={rid for rid,r in scores.items() if all(m in r for m in args.methods)}
    old_primary=[r for r in old if r['record_id'] in common]
    severe=[r for r in screen if r['record_id'] in allowed&common and r['original_judgment']=='severe']
    borderline=[r for r in screen if r['record_id'] in allowed&common and r['original_judgment']=='borderline']
    availability=[]
    for r in old+screen:
        rid=r['record_id'];layer='old24' if r in old else r['original_judgment']
        availability.append(dict(layer=layer,case_id=r['case_id'],record_id=rid,
                                 allowed_screen_numerical=rid in allowed if layer!='old24' else None,
                                 common_score_available=rid in common,
                                 available_methods=[m for m in args.methods if m in scores.get(rid,{})]))
    write_csv(args.out/'analysis_availability.csv',availability)
    grade={r['record_id']:r['quality_ordinal_original'] for r in old_primary}
    opairs=[];osummary=[]
    for method in args.methods:
        pairs=pair_counts(old_primary,scores,method,grade);opairs+=pairs
        osummary.append(dict(method=method,n=len(old_primary),pairs=len(pairs),inversions=sum(r['inversion'] for r in pairs),
                             ties=sum(r['tie'] for r in pairs),same_image_pairs=sum(r['same_image'] for r in pairs),
                             same_image_inversions=sum(r['same_image'] and r['inversion'] for r in pairs)))
    write_csv(args.out/'old24_rank_summary.csv',osummary);write_csv(args.out/'old24_cross_grade_pairs.csv',opairs)
    cal,folds,preds=grouped_calibration(old_primary,scores,args.methods)
    dump(args.out/'old24_two_cutpoint_calibration_summary.json',cal);dump(args.out/'old24_two_cutpoint_folds.json',folds)
    write_csv(args.out/'old24_two_cutpoint_prediction_sets.csv',preds)
    bridge,bpairs=severe_bridge(old_primary,severe,scores,args.methods)
    write_csv(args.out/'severe_old24_bridge_summary.csv',bridge);write_csv(args.out/'severe_old24_bridge_pairs.csv',bpairs)
    bsummary,scenarios,value=borderline_scenarios(severe,borderline,scores,args.methods)
    dump(args.out/'borderline_scenario_summary.json',bsummary);write_csv(args.out/'borderline_scenarios.csv',scenarios)
    write_csv(args.out/'borderline_candidate_decision_value.csv',value)
    summary=dict(methods=args.methods,old24_total=len(old),old24_common_numerical=len(old_primary),
                 new_severe_total=sum(r['original_judgment']=='severe' for r in screen),new_severe_common_numerical=len(severe),
                 borderline_total=sum(r['original_judgment']=='borderline' for r in screen),borderline_common_numerical=len(borderline),
                 borderline_numeric_case_order=[r['case_id'] for r in borderline],
                 borderline_unavailable_case_ids=[r['case_id'] for r in screen if r['original_judgment']=='borderline' and r['record_id'] not in {s['record_id'] for s in borderline}],
                 unreviewed_used_as_labels=0,existing_holdout_used_for_scoring_or_calibration=0,
                 original_record_ids_unchanged=True,numerical_tie_tolerance=EPS,
                 interpretation='Selected development diagnostics. Prediction/scenario ranges are not uncertainty probabilities or confidence intervals.')
    dump(args.out/'summary.json',summary)
    post_result_robustness(old_primary,severe,borderline,scores,args.methods,source_rows,args.out)
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    main()
