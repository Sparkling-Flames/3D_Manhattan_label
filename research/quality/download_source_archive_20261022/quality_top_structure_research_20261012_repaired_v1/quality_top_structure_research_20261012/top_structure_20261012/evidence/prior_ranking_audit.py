#!/usr/bin/env python3
"""Describe the actual dependency structure behind prior 42 -> 19 inversions."""
import argparse, collections, itertools, json
from pathlib import Path
from audit_qualification import read,dump,csvout,digest

def main():
    a=argparse.ArgumentParser();a.add_argument('--workspace',type=Path,default=Path.cwd());a.add_argument('--out',type=Path);x=a.parse_args()
    W=x.workspace;O=x.out or W/'top_structure_20261012/evidence/results';O.mkdir(parents=True,exist_ok=True)
    ep=W/'study_borderline/results/old24_evidence.json';sp=W/'study_quality/results/candidate_scores.json'
    E=read(ep);S={r['record_id']:r for r in read(sp)};pairs=[]
    for a,b in itertools.combinations(E,2):
        if a['quality_ordinal_original']==b['quality_ordinal_original']:continue
        if a['quality_ordinal_original']>b['quality_ordinal_original']:a,b=b,a
        sa,sb=S[a['record_id']],S[b['record_id']]
        pairs.append(dict(higher_case=a['case_id'],lower_case=b['case_id'],higher_image=a['image_code'],lower_image=b['image_code'],
            higher_building=a['building_id'],lower_building=b['building_id'],higher_group=a['room_group'],lower_group=b['room_group'],
            same_image=a['image_code']==b['image_code'],same_group=a['room_group']==b['room_group'],same_building=a['building_id']==b['building_id'],
            same_worker=a['worker_id']==b['worker_id'],old_inverse=sa['Q_v11']<sb['Q_v11'],no_top_inverse=sa['Q_no_topS']<sb['Q_no_topS'],
            old_margin=sa['Q_v11']-sb['Q_v11'],no_top_margin=sa['Q_no_topS']-sb['Q_no_topS']))
    def sums(rr):return dict(n_pairs=len(rr),old_inversions=sum(r['old_inverse'] for r in rr),no_top_inversions=sum(r['no_top_inverse'] for r in rr))
    strata=[dict(stratum=f'{field}={v}',**sums([r for r in pairs if r[field]==v])) for field in ['same_image','same_group','same_building','same_worker'] for v in [True,False]]
    omissions=[]
    for field,key in [('case','case_id'),('image','image_code'),('building','building_id'),('group','room_group')]:
        for v in sorted({e[key] for e in E}):
            omit={e['case_id'] for e in E if e[key]==v};rr=[p for p in pairs if p['higher_case'] not in omit and p['lower_case'] not in omit]
            omissions.append(dict(omitted_unit=field,omitted_value=v,omitted_cases=sorted(omit),**sums(rr)))
    improvements=[r for r in pairs if r['old_inverse'] and not r['no_top_inverse']];newfail=[r for r in pairs if not r['old_inverse'] and r['no_top_inverse']]
    assert sums(pairs)==dict(n_pairs=164,old_inversions=42,no_top_inversions=19)
    assert len(improvements)==25 and len(newfail)==2
    assert all(not r['same_image'] for r in improvements)
    summary=dict(schema='prior_ranking_evidence_limit_audit_v1',overall=sums(pairs),strata=strata,
        improvements=len(improvements),new_failures=newfail,all_improvements_cross_image=True,
        case_label_counts=dict(collections.Counter(e['quality_ordinal_original'] for e in E)),
        label_count_identity='2*10 + 2*12 + 10*12 = 164; each chosen case participates in many pairs.',
        dependency='Rows share records, images, buildings and sometimes personnel; 164 is not an independent sample size.',
        selection='Deliberately chosen development examples, not a random population sample or an untouched validation set.',
        correct_interpretation='No-top-S better agrees with the selected uncertain ordinal judgments, mostly across image conditions. It does not establish same-image quality, population error rate, worker ability, or a unique final scale.',
        same_image_evidence='Only two unequal-grade within-image comparisons exist; v1.1 has zero inverse, no-top-S one (T22/T09).',
        equal_calibration_budget='For each frozen scalar use identical two grade cuts, objective, training groups and tie treatment. Preserve all equally optimal intervals or use a predeclared tie-break; do not use heldout labels to choose a cut.',
        model_complexity='Separate formula selection from grade-cut fitting; old24 supports descriptive two-cutpoint calibration, not a multicomponent personnel/image random-effects model.',
        grade_noise='Perturb any old24 adjacent grade, with or without comments. These are sensitivity scenarios, not per-case confidence or probabilities.',
        source_sha256={str(ep.relative_to(W)):digest(ep),str(sp.relative_to(W)):digest(sp)})
    dump(O/'prior_ranking_audit_summary.json',summary);csvout(O/'prior_ranking_pairs_164.csv',pairs);csvout(O/'prior_ranking_leave_unit_out.csv',omissions)
    print(json.dumps(dict(overall=summary['overall'],strata=strata,new_failures=[(r['higher_case'],r['lower_case']) for r in newfail]),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
