#!/usr/bin/env python3
"""Mechanistic checks of already fitted ordinal models; no fitting or labels."""
from __future__ import annotations
import argparse,csv
from pathlib import Path
import numpy as np
from apply_exposure_and_audit import read,write,sha
from recheck_comparisons import csvout
from monotone_ordinal_probe import probabilities


def feature(row,name):
    if name=='floor':return 1-float(row['iou_2d'])
    if name=='direction':v=float(row['dir']);return v*v/(v*v+25)
    if name=='global_height':v=float(row['Hmean']);return v*v/(v*v+.25)
    if name=='centered_height':v=float(row['Hcenter']);return v*v/(v*v+.0625)
    if name=='top_boundary':v=float(row['S_top_deg']);return v*v/(v*v+32)
    raise ValueError(name)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workspace',type=Path,default=Path(__file__).resolve().parents[2]);a=ap.parse_args();W=a.workspace.resolve()
    E=W/'structure_height_preference_20261012/evidence';O=E/'model_controls';O.mkdir(parents=True,exist_ok=True)
    pp=[E/'model_results/full_fit_parameters.json',E/'model_extensions/full_fit_parameters.json']
    fits=[r for p in pp for r in read(p) if r['method'] in ['geom4','geom5_top','D_only','geometry2']]
    ip=W/'structure_height_preference_20261012/height/results/matched_control_scores.csv';raw=list(csv.DictReader(ip.open(encoding='utf-8-sig')))
    out=[]
    for r in raw:
        if r['status']!='available':continue
        q=dict(r)
        for f in fits:
            X=np.array([[feature(r,n) for n in f['features']]])
            p,cdf=probabilities(np.asarray(f['params']),X)
            q[f['method']+'_latent_severity']=float(X[0]@np.asarray(f['coefficients']))
            q[f['method']+'_expected_grade']=float(2-cdf.sum())
            q[f['method']+'_model_median_grade']=int((cdf<.5).sum())
            q[f['method']+'_model_probability_not_human_confidence']=p[0].tolist()
        q['human_grade_assigned']=False;out.append(q)
    csvout(O/'controlled_model_outputs.csv',out)
    by={r['case_id']:r for r in out};summary=[]
    for scale in [0.5,10]:
        anchor=by[f'global_extreme_s{scale:g}_r1']
        for ratio in [.1,.25,.5,1.5,2,3,5]:
            r=by[f'global_extreme_s{scale:g}_r{ratio:g}']
            summary.append(dict(case_id=r['case_id'],wall_height_ratio=ratio,horizontal_scale=scale,
                camera_above_annotation_roof=r.get('camera_above_annotation_roof'),
                global_relative_error=float(r['Hmean']),
                Q_old=float(r['Q_v11']),Q_noTop=float(r['Q_no_topS']),Q_Dbounded1_split=float(r['Q_dbounded1_hsplit']),
                geom4_expected_grade_change=r['geom4_expected_grade']-anchor['geom4_expected_grade'],
                geom5_expected_grade_change=r['geom5_top_expected_grade']-anchor['geom5_top_expected_grade'],
                D_only_expected_grade_change=r['D_only_expected_grade']-anchor['D_only_expected_grade'],
                synthetic_control_no_human_grade=True))
    write(O/'global_height_failure_summary.json',summary)
    write(O/'run_manifest.json',dict(source_controls_sha256=sha(ip),fitted_model_sha256={str(p.relative_to(W)):sha(p) for p in pp},
        controls_read=len(raw),controls_evaluated=len(out),fit_calls=0,model_parameters_changed=False,
        controls_with_camera_inside_height_assumption=sum(r.get('camera_inside_height_assumption')=='True' for r in out),
        controls_without_camera_inside_height_assumption=sum(r.get('camera_inside_height_assumption')=='False' for r in out),
        synthetic_cases_are_human_grade_labels=False,independent_validation=False,
        statement='Good selected-development ordinal fit does not ensure required height behavior. Below-camera ceilings are separately marked domain checks.'))
    print(__import__('json').dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
