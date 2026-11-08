#!/usr/bin/env python3
"""Rebuild the current B candidate, optionally reproduce its three review figures."""
import argparse,subprocess,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--blender',default='blender');p.add_argument('--variant',choices=['B','B_full_model','both'],default='both');p.add_argument('--output',type=Path,default=Path('B_rebuilt_output'));p.add_argument('--render',action='store_true');p.add_argument('--views',nargs='+',choices=['main','rear','plan'],default=['main','rear','plan']);p.add_argument('--percentage',type=int,default=100);p.add_argument('--samples',type=int,default=12)
a=p.parse_args()
if not 1<=a.percentage<=100 or a.samples<1:p.error('Invalid rendering settings')
out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);variants=['B','B_full_model'] if a.variant=='both' else [a.variant];reports=[]
for variant in variants:
    model=out/(variant+'.blend');report=out/(variant+'.validation.json')
    subprocess.run([a.blender,'-b','-t','2','--python-exit-code','1','--python',str(ROOT/'scripts/rebuild_scene.py'),'--','--snapshot',str(ROOT/'snapshots/B'/(variant+'.json')),'--asset',str(ROOT/'assets/B'/(variant+'_shading.blend')),'--output',str(model),'--report',str(report)],check=True)
    reports.append(json.loads(report.read_text(encoding='utf-8')))
    if a.render and variant=='B':
        for view,label in [('main','Main'),('rear','Detail')]:
            if view not in a.views:continue
            raw=out/(label+'_rgba.png');target=out/f'06_Rear_Space_Candidate_{label}_20261107.png'
            subprocess.run([a.blender,'-b',str(model),'-t','2','--python-exit-code','1','--python',str(ROOT/'scripts/render_candidate.py'),'--','--view',view,'--output',str(raw),'--percentage',str(a.percentage),'--samples',str(a.samples)],check=True)
            subprocess.run([sys.executable,str(ROOT/'scripts/png_white.py'),str(raw),str(target)],check=True)
if a.render and 'plan' in a.views:
    subprocess.run([sys.executable,str(ROOT/'draw_plan.py'),'--output',str(out/'06_Rear_Space_Candidate_Plan_20261107.png')],check=True)
(out/'validation_all.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('Finished:',out)
