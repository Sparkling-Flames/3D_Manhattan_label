#!/usr/bin/env python3
"""Replay calibration into a separate directory and compare the actual outputs."""
from __future__ import annotations
import argparse,hashlib,json,platform,subprocess,sys,time
from pathlib import Path
import numpy as np
from PIL import Image
HERE=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=HERE.parent/'baseline')
    p.add_argument('--out',type=Path,required=True);p.add_argument('--experiment-results',type=Path,default=HERE.parent/'experiments/results')
    a=p.parse_args();out=a.out.resolve();source=a.source.resolve()
    if out==HERE or out.is_relative_to(source):raise ValueError('Replay output must be separate from delivered code and frozen source')
    if out.exists() and any(out.iterdir()):raise ValueError('Use a new or empty output directory')
    out.mkdir(parents=True,exist_ok=True);steps=[];start=time.monotonic()
    protected=[source/'inputs/calibration_records.json',source/'inputs/old24_labels_preserved.json',source/'config/frozen_selected_candidates.json']
    before={str(p.relative_to(source)):sha(p) for p in protected}
    commands=[
      ['prepare_inputs.py','--source',str(source),'--out',str(out/'inputs'),'--descriptors',str(a.experiment_results/'real_direction_descriptors.json'),'--joint-hinge',str(a.experiment_results/'joint_hinge_descriptors.json')],
      ['run_search.py','--inputs',str(out/'inputs/search_inputs.json'),'--out',str(out/'results')],
      ['physical_controls.py','--source',str(source),'--out',str(out/'results/physical_controls.json')],
      ['analyze_candidates.py','--inputs',str(out/'inputs/search_inputs.json'),'--out',str(out/'results'),'--experiment-results',str(a.experiment_results)],
      ['verify_calibration.py','--inputs',str(out/'inputs/search_inputs.json'),'--results',str(out/'results'),'--out',str(out/'results/SCALAR_VERIFICATION.json')],
      ['render_calibration.py','--results',str(out/'results'),'--out',str(out/'figures')]
    ]
    for i,cmd in enumerate(commands):
        ts=time.monotonic();r=subprocess.run([sys.executable,str(HERE/cmd[0]),*cmd[1:]],text=True,capture_output=True)
        (out/f'step_{i+1:02d}.log').write_text(r.stdout+r.stderr)
        steps.append(dict(script=cmd[0],returncode=r.returncode,seconds=time.monotonic()-ts))
        if r.returncode:write(out/'REPLAY_VERIFICATION.json',dict(status='failed',steps=steps));raise RuntimeError(cmd[0]+' failed; see log')
        print(json.dumps(steps[-1]),flush=True)
    expected=read(HERE/'results/selected_scores_922.json')['rows'];got=read(out/'results/selected_scores_922.json')['rows']
    assert [r['record_id'] for r in expected]==[r['record_id'] for r in got]
    maxd=0.
    for x,y in zip(expected,got):
        for name,v in x['scores'].items():maxd=max(maxd,abs(v-y['scores'][name]))
        for k in ['current_points_sha256','reference_points_sha256','reference_object_id']:assert x[k]==y[k]
    assert maxd<1e-10
    x=read(HERE/'results/search_summary.json');y=read(out/'results/search_summary.json')
    compared=['coarse','fine','readable','boundary_extensions','total','hard_feasible','joint_feasible','near_region_count']
    for k in compared:assert x[k]==y[k],(k,x[k],y[k])
    pngs=[]
    for pth in sorted((out/'figures').glob('*.png')):
        im=Image.open(pth);im.load();pngs.append(dict(file=pth.name,size=list(im.size),sha256=sha(pth)))
    assert len(pngs)==2
    after={str(p.relative_to(source)):sha(p) for p in protected};assert before==after
    result=dict(status='passed',steps=steps,records=len(got),maximum_score_difference=maxd,
                search_summary_fields_compared=compared,search_counts_identical=True,source_files_unchanged=before==after,
                source_hashes=before,pngs=pngs,total_seconds=time.monotonic()-start,
                human_validation_performed=False,python=platform.python_version())
    write(out/'REPLAY_VERIFICATION.json',result);print(json.dumps(result))

if __name__=='__main__':main()
