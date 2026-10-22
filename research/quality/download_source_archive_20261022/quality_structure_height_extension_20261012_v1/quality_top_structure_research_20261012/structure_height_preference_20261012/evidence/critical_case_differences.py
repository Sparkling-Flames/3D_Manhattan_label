#!/usr/bin/env python3
"""Locate actual candidate disagreements without creating human preferences."""
from __future__ import annotations
import argparse,csv,itertools
from pathlib import Path
from apply_exposure_and_audit import read,write,sha
from recheck_comparisons import csvout


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workspace',type=Path,default=Path(__file__).resolve().parents[2]);a=ap.parse_args();W=a.workspace.resolve()
    E=W/'structure_height_preference_20261012/evidence';O=E/'critical_cases';O.mkdir(parents=True,exist_ok=True)
    sp=W/'structure_height_preference_20261012/height/results/initial15_before_log_addendum/candidate_scores_39.json';rows=read(sp)
    old=read(W/'study_borderline/results/old24_evidence.json');grades={r['case_id']:r['quality_ordinal_original'] for r in old}
    by={r['old_case_id'] or r['new_case_id']:r for r in rows}
    comparisons=[('Q_dbounded1_hsplit','Q_dbounded2_hsplit'),('Q_dbounded1_hsplit','Q_dunbounded_hsplit'),
                 ('Q_dbounded1_hsplit','Q_dbounded1_hsplit_weakTop'),('Q_dbounded1_hsplit','Q_dbounded1_local05'),
                 ('Q_dbounded1_hsplit','Q_dbounded1_Fguard')]
    allchanges=[];oldchanges=[]
    for ma,mb in comparisons:
        for ca,cb in itertools.combinations(by,2):
            x,y=by[ca],by[cb];d0=x[ma]-y[ma];d1=x[mb]-y[mb]
            if d0*d1>=0:continue
            r=dict(method_a=ma,method_b=mb,case_a=ca,case_b=cb,record_a=x['record_id'],record_b=y['record_id'],
                image_a=x['image_code'],image_b=y['image_code'],same_image=x['image_id']==y['image_id'],
                score_a_method_a=x[ma],score_b_method_a=y[ma],score_a_method_b=x[mb],score_b_method_b=y[mb],
                grade_a=grades.get(ca),grade_b=grades.get(cb),new_human_preference_assigned=False)
            if ca in grades and cb in grades and grades[ca]!=grades[cb]:
                r['old_grade_order_improved']=(d0*(grades[cb]-grades[ca])<0 and d1*(grades[cb]-grades[ca])>0)
                oldchanges.append(r)
            allchanges.append(r)
    csvout(O/'all39_changed_orders.csv',allchanges);csvout(O/'old24_changed_grade_orders.csv',oldchanges)
    desired=[('T09','T22'),('T21','T05'),('T21','T12'),('T22','T07'),('T20','S034'),('S071','S066'),('S052','S066'),('S107','S012'),('T13','S066')]
    allmethods=['Q_v11','Q_floor_iou','Q_official_iou3d','Q_no_topS','Q_split_local025','Q_dbounded1_hsplit','Q_dbounded2_hsplit','Q_dunbounded_hsplit','Q_dbounded1_hsplit_weakTop','Q_dbounded1_local05','Q_dbounded1_Fguard']
    chosen=[]
    for ca,cb in desired:
        for cid in [ca,cb]:
            r=by[cid];chosen.append(dict(pair=ca+'/'+cb,case_id=cid,record_id=r['record_id'],image_code=r['image_code'],
                same_image_pair=by[ca]['image_id']==by[cb]['image_id'],source_evidence_layer=r['evidence_layer'],
                old_grade=grades.get(cid),D=r['dir'],F=r['flat'],Hmean=r['Hmean'],Hcenter=r['Hcenter'],St=r['S_top_deg'],Sb=r['S_bottom_deg'],
                **{m:r[m] for m in allmethods}))
    csvout(O/'selected_real_contrasts_research_only.csv',chosen)
    pending=list(csv.DictReader((E/'new_candidate_comparison/pending_decision_influence.csv').open(encoding='utf-8-sig')))
    wanted={(a,b) for a,b in comparisons}
    dp=[r for r in pending if (r['method_a'],r['method_b']) in wanted]
    csvout(O/'pending_mechanism_influence.csv',dp)
    ad=list(csv.DictReader((E/'new_candidate_comparison/all24_adjacent_scenarios.csv').open(encoding='utf-8-sig')))
    ss=[]
    for ma,mb in comparisons:
        for n in [1,2]:
            rs=[r for r in ad if int(r['changed_count'])==n];v=[int(r[mb])-int(r[ma]) for r in rs]
            ss.append(dict(method_a=ma,method_b=mb,changed_records=n,scenarios=len(rs),method_b_minus_a_min=min(v),method_b_minus_a_max=max(v),scenario_frequency_is_probability=False))
    write(O/'local_candidate_label_sensitivity.json',ss)
    capchanges=[r for r in oldchanges if r['method_b']=='Q_dbounded2_hsplit']
    topchanges=[r for r in oldchanges if r['method_b']=='Q_dbounded1_hsplit_weakTop']
    notes=dict(scores_sha256=sha(sp),cap1_to_cap2_old24_changed_orders=len(capchanges),
        cap_changes_incident_to_T21=sum('T21' in [r['case_a'],r['case_b']] for r in capchanges),
        cap_changed_orders_same_image=sum(r['same_image'] for r in capchanges),
        weak_top_addition_old24_cross_grade_order_changes=len(topchanges),
        pending_cap1_vs_cap2_all6_scenarios_distinguish=False,
        pending_weak_vs_no_top_all6_scenarios_distinguish=False,
        priorities=[
            dict(cases=['T09','T22'],purpose='Keep existing same-image comparison; both cap1/cap2 fix the previous noTop reversal, so this pair supports a structure tradeoff but does not identify the cap.',no_new_review_requested_now=True),
            dict(cases=['T21','T05','T12'],purpose='Four of five cap1->cap2 old24 order changes share T21. Compare the severity of reference-range loss and missing/crooked structure; the images differ and this is not a pure D experiment.',answer_effect='Would strengthen/weaken the evidence for stronger bounded structural action, not define a universal angle threshold.'),
            dict(cases=['S071'],purpose='Largest currently pending influence on local-height scale .25 vs .5; mixed scope, structure and height makes it unsuitable as a pure height calibration.',answer_effect='Pending->severe changes the relative inversion difference between local scales by two under the defined scenarios; affects whether it can act as a non-severe counterweight.'),
            dict(cases=['S107','S012'],purpose='S107 versus currently severe S012 is the sole reversal if all six numeric pending are treated as obvious in the cap1/cap2 families; current relative grades are not fixed paired preference.',answer_effect='A non-severe S107 judgment questions the present scale/order around this case; severe classification removes this cross-grade constraint. It does not alone select cap1 versus cap2.'),
            dict(cases=['S052','S071','S066'],purpose='Unbounded D heavily reverses these combinations compared with a bounded structural loss; S052/S071 relabeling has high scenario influence, but errors and images are mixed.',answer_effect='Useful if unbounded D remains under consideration; lower priority if it is already ruled out on projection and severity tradeoff evidence.'),
            dict(cases=['T20','S034'],purpose='Retain top-state question: global level shift versus uneven local wall height; there are also different floor/range errors and images.',answer_effect='Can inform global/local and weak-top treatment; cannot set complete Q by one forced global ranking.')],
        need_not_block_progress=['S034 and S079 do not change relative cap1/cap2, weak-top/no-top or the local-height-scale comparison in the current six-case binary scenario analysis.',
            'The five pending cases without reliable full geometry remain in the ledger; no fabricated Q is needed to continue the scored mechanism comparisons.',
            'Anonymous re-review of exposed images is not a new independent blind validation.'],
        no_user_review_requested_in_this_script=True)
    write(O/'selection_notes.json',notes)
    print(__import__('json').dumps(notes,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
