"""Validate independent answer files and report coverage; never fill human answers."""
import argparse
import json
from collections import Counter
from pathlib import Path
import pandas as pd
from .build_independent_review_20261107 import HERE


DEFECTS={'missing','extra','position','height','connection','other','none','unknown'}
def validate_defects(defects):
    assert isinstance(defects,dict) and set(defects)<= {'left','right'},'invalid defect sides'
    for selected in defects.values():
        assert isinstance(selected,list) and all(isinstance(v,str) for v in selected),'invalid defects'
        assert len(selected)==len(set(selected)) and set(selected)<=DEFECTS,'unknown or duplicate defects'
        assert not (set(selected)&{'none','unknown'}) or len(selected)==1,'conflicting defects'
    return defects


def validate_answer(answer, assignment):
    assert answer.get('schema')=='overall_quality_review_20261107_v3','schema mismatch'
    assert answer.get('formal') is True,'preview answers are not formal evidence'
    reviewer=answer['reviewer'];assert isinstance(reviewer,str) and reviewer.strip(),'missing independent reviewer code'
    packet_id=answer['packet_id'];assert packet_id in assignment,'unknown packet'
    keys={r['case_id']:r for r in assignment[packet_id]['key']}
    assert len(answer['case_ids'])==len(set(answer['case_ids'])) and set(answer['case_ids'])==set(keys),'case set mismatch'
    assert set(answer['answers']).issubset(keys),'unknown answer ID'
    rows=[]
    for cid,a in answer['answers'].items():
        kind='quality';assert cid.startswith('Q'),'not a quality case'
        assert isinstance(a.get('reason',''),str),'reason must be text'
        assert a.get('scope') in (None,'same','different_valid','invalid_scope','unknown'),'invalid scope'
        assert isinstance(a.get('self',False),bool),'invalid opt-out'
        viewed=a.get('score_viewed',False)
        assert isinstance(viewed,bool),'invalid score reveal'
        assert not viewed or (kind=='quality' and isinstance(a.get('before_score'),dict)),'missing pre-score judgment'
        initial=a['before_score'] if viewed else a
        initial_grades=initial.get('grades') or {}; final_grades=a.get('grades') or {}
        for grades in [initial_grades,final_grades]:
            assert set(grades).issubset({'left','right'}),'unknown grade side'
            assert all(v in (None,'good','medium','poor','unknown') for v in grades.values()),'invalid grade'
        if viewed:assert all(initial_grades.get(side) for side in ['left','right']),'incomplete pre-score judgment'
        initial_defects=validate_defects(initial.get('defects',{}));final_defects=validate_defects(a.get('defects',{}))
        if viewed:assert all(initial_defects.get(side) for side in ['left','right']),'missing pre-score defects'
        flip=keys[cid]['flip']
        valid=not a.get('self',False) and all(initial_grades.get(side) and initial_defects.get(side) for side in ['left','right'])
        rows.append(dict(reviewer=reviewer,case_id=cid,kind=kind,
            valid_judgment=bool(valid),self_excluded=a.get('self',False),score_viewed=viewed,
            left_grade_initial=initial_grades.get('right' if flip else 'left'),right_grade_initial=initial_grades.get('left' if flip else 'right'),
            left_grade_final=final_grades.get('right' if flip else 'left'),right_grade_final=final_grades.get('left' if flip else 'right'),
            left_defects_initial=json.dumps(initial_defects.get('right' if flip else 'left',[]),ensure_ascii=False),right_defects_initial=json.dumps(initial_defects.get('left' if flip else 'right',[]),ensure_ascii=False),
            left_defects_final=json.dumps(final_defects.get('right' if flip else 'left',[]),ensure_ascii=False),right_defects_final=json.dumps(final_defects.get('left' if flip else 'right',[]),ensure_ascii=False),
            scope_initial=initial.get('scope'),scope_final=a.get('scope'),reference_viewed_initial=initial.get('reference_viewed',False),
            reason_initial=initial.get('reason',''),reason_final=a.get('reason',''),
            pool_id=keys[cid].get('pool_id','')))
    return rows


def main():
    p=argparse.ArgumentParser();p.add_argument('answers',nargs='+',type=Path);args=p.parse_args()
    assignment=json.loads((HERE/'ASSIGNMENT_PRIVATE.json').read_text(encoding='utf-8'));rows=[];seen=set()
    for path in args.answers:
        a=json.loads(path.read_text(encoding='utf-8-sig'));assert a['reviewer'] not in seen,'duplicate reviewer; choose one export'
        rows.extend(validate_answer(a,assignment));seen.add(a['reviewer'])
    result=HERE/'returned';result.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(result/'ANSWERS_NORMALIZED_PRIVATE.csv',index=False,encoding='utf-8-sig')
    cases=sorted({r['case_id'] for v in assignment.values() for r in v['key'] if not r['case_id'].startswith('P')});summary=[]
    for cid in cases:
        rr=[r for r in rows if r['case_id']==cid];counts=Counter(str(r['left_grade_initial'])+'/'+str(r['right_grade_initial']) for r in rr if r['valid_judgment']);valid=sum(counts.values())
        summary.append(dict(case_id=cid,responded=len(rr),valid_nonself=valid,at_least_three=valid>=3,
                            choices=json.dumps(counts,ensure_ascii=False),score_viewed=sum(bool(r['score_viewed']) for r in rr)))
    pd.DataFrame(summary).to_csv(result/'COVERAGE_AND_DISAGREEMENT.csv',index=False,encoding='utf-8-sig')
    print('reviewers',len(seen),'cases with >=3 nonself answers',sum(r['at_least_three'] for r in summary),'/',len(cases))


if __name__=='__main__':main()
