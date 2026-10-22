#!/usr/bin/env python3
"""Score only prespecified development evidence; never use unchecked as negatives."""
from __future__ import annotations
import argparse,csv,hashlib,json,sys
from pathlib import Path
from scoring_candidates import candidate_scores, component_ablation


def read(p): return json.loads(p.read_text())
def dump(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def csvwrite(p,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path.cwd());a=ap.parse_args();r=a.root.resolve()
    p=r/'previous_research/quality_calibration_research_20261011';b=p/'inputs_extracted/quality_cloud_compute_review_20261010'
    out=r/'study_quality/results';out.mkdir(parents=True,exist_ok=True)
    old=read(p/'work_blind/analysis_input.json')['quality']; oldmap={x['record_id']:x['selection']['case_id'] for x in old}
    allowed=[x for x in read(r/'study_severe/results/scorable_records.json') if x['judgment'] in ('severe','borderline')]
    newmap={x['record_id']:x for x in allowed};assert len(allowed)==15
    comp={x['record_id']:x for x in read(b/'results/current_components.json')}
    with (b/'results/room_holdout_manifest.csv').open(encoding='utf-8-sig') as f:hold={x['record_id']:x for x in csv.DictReader(f)}
    with (r/'study_x/results/raw_boundary_cases.csv').open(encoding='utf-8-sig') as f:raw={x['record_id']:x for x in csv.DictReader(f)}
    keys=sorted(set(oldmap)|set(newmap));rows=[];changes=[]
    for rid in keys:
        c=comp[rid]; assert str(hold[rid]['held_out_of_sample_and_future_calibration']).lower()=='false',rid
        rx=raw.get(rid,{});rt=float(rx['S_top_raw_deg']) if rx.get('S_top_raw_deg') else None;rb=float(rx['S_bottom_raw_deg']) if rx.get('S_bottom_raw_deg') else None
        scores=candidate_scores(c,rt,rb)
        assert abs(scores['Q_v11']-c['Q'])<1e-9
        row={k:c[k] for k in ['record_id','object_id','image_id','image_code','worker_id','building_id','reference_object_id','reference_points_sha256','current_points_sha256','iou_2d','iou_3d_corner_mean','S_top_deg','S_bottom_deg','Hmean','Hlocal','Hstar','dir','flat']}
        row.update(old_case_id=oldmap.get(rid,''),new_case_id=newmap.get(rid,{}).get('case_id',''),evidence_layer='old24_development' if rid in oldmap else 'new_'+newmap[rid]['judgment']+'_conditional_development',original_holdout=False,scope_reference_acceptance='preserve_existing_eligibility; screen does not newly approve reference',raw_boundary_available=rt is not None,**scores)
        rows.append(row)
        changes.append({'record_id':rid,'old_case_id':row['old_case_id'],'new_case_id':row['new_case_id'],'ablation':component_ablation(c)})
    csvwrite(out/'candidate_scores.csv',rows);dump(out/'candidate_scores.json',rows);dump(out/'component_ablations.json',changes)
    dump(out/'real_candidate_run_manifest.json',{'n_records':len(rows),'old24':len(oldmap),'new_severe':sum(x['judgment']=='severe' for x in allowed),'new_borderline':sum(x['judgment']=='borderline' for x in allowed),'parameters_fitted':False,'candidate_config_sha256':sha(r/'study_quality/candidates.json'),'component_sha256':sha(b/'results/current_components.json'),'old_evidence_sha256':sha(p/'work_blind/analysis_input.json'),'allowed_geometry_sha256':sha(r/'study_severe/results/scorable_records.json'),'max_v11_parity_error':max(abs(x['Q_v11']-comp[x['record_id']]['Q']) for x in rows),'no_heldout_or_unchecked_labels_used':True})
    print(json.dumps({'n':len(rows),'T20':next(x for x in rows if x['old_case_id']=='T20')},ensure_ascii=False,indent=2))


if __name__=='__main__': main()
