#!/usr/bin/env python3
"""Portable final-scene reconstruction/render runner. Python 3.9+; Blender 5.2.3."""
import argparse,subprocess,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
ALLOWED_CASES=('01_doorway','02_oblique','03_sloped_ceiling','04_split_ceiling','05_split_floor')
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--blender',default='blender',help='Blender executable path (not a directory)')
p.add_argument('--case',default='all',choices=['all','01','02','03','04','05',*ALLOWED_CASES],help='all, 01..05, or the complete case folder name')
p.add_argument('--variant',default='both',choices=['presentation','full_model','both'])
p.add_argument('--output',type=Path,default=Path('rebuilt_output'))
p.add_argument('--render',action='store_true',help='Rebuild, check, then render requested views')
p.add_argument('--views',nargs='+',choices=['main','reverse'],default=['main','reverse'])
p.add_argument('--percentage',type=int,default=100);p.add_argument('--samples',type=int,default=96);p.add_argument('--threads',type=int,default=4)
a=p.parse_args()
if not 1<=a.percentage<=100 or a.samples<1 or a.threads<1:p.error('Invalid render settings')
cases=[c for c in sorted((ROOT/'snapshots').iterdir()) if c.is_dir() and c.name in ALLOWED_CASES and (a.case=='all' or c.name==a.case or c.name.startswith(a.case+'_'))]
if not cases:p.error('Case not found')
variants=['presentation','full_model'] if a.variant=='both' else [a.variant];output=a.output.resolve();output.mkdir(parents=True,exist_ok=True)
results=[]
for case in cases:
    for variant in variants:
        dest=output/case.name/variant;dest.mkdir(parents=True,exist_ok=True);blend=dest/(variant+'.blend')
        cmd=[a.blender,'-b','-t',str(a.threads),'--python-exit-code','1','--python',str(ROOT/'scripts/rebuild_scene.py'),'--','--snapshot',str(case/(variant+'.json')),'--asset',str(ROOT/'assets'/case.name/(variant+'_shading.blend')),'--output',str(blend),'--report',str(dest/'validation.json')]
        print('Rebuilding:',case.name,variant,flush=True);subprocess.run(cmd,check=True)
        results.append(json.loads((dest/'validation.json').read_text(encoding='utf-8')))
        if a.render:
            for view in a.views:
                basename=view
                png=dest/(basename+'_rgba.png')
                subprocess.run([a.blender,'-b',str(blend),'-t',str(a.threads),'--python-exit-code','1','--python',str(ROOT/'scripts/render_scene.py'),'--','--output',str(png),'--view',view,'--percentage',str(a.percentage),'--samples',str(a.samples),'--threads',str(a.threads)],check=True)
                subprocess.run([sys.executable,str(ROOT/'scripts/png_white.py'),str(png),str(dest/(basename+'.png'))],check=True)
(output/'validation_all.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Finished:',output)
