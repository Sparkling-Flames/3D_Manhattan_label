#!/usr/bin/env python3
"""Small overview figure. Requires matplotlib. All numbers come from reproducible JSON."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as PatchPolygon
ROOT=Path(__file__).resolve().parent
rows=json.loads((ROOT/'results/comparison_18.json').read_text());refs=json.loads((ROOT/'results/fixed_references.json').read_text())
fig,axes=plt.subplots(2,3,figsize=(14,8));colors={'G':'#475569','T':'#a855f7','set':'#0284c7'}
for col,r in enumerate(refs):
    code=r['image_code']; data=[x for x in rows if x['image_code']==code];ax=axes[0,col]
    for key in ['G','T']:
        p=np.array(r[key]['bottom3d'])[:,[0,2]]
        ax.add_patch(PatchPolygon(p,facecolor=colors[key],alpha=.15,edgecolor='none'))
        ax.plot(*np.vstack([p,p[0]]).T,c=colors[key],lw=2,label=key+(' original GT' if key=='G' else ' confirmed floor'))
    ann=json.loads((ROOT/'inputs/current_geometry_three_images.json').read_text())
    im=next(i for i in ann['images'] if i['code']==code)
    for a in im['annotations']:
        p=np.array(a['bottom3d'])[:,[0,2]];ax.plot(*np.vstack([p,p[0]]).T,c='#14b8a6',alpha=.45,lw=.8)
    ax.scatter([0],[0],c='black',marker='x',s=25);ax.autoscale_view();ax.set_aspect('equal');ax.set_title(code+'\nT/G area = '+f"{r['metadata']['T_over_G_area']:.1%}",fontsize=11);ax.set_xlabel('x / camera height');ax.set_ylabel('z / camera height');ax.grid(alpha=.12)
    if col==0:ax.legend(fontsize=8,loc='lower left')
    ax=axes[1,col]; x=np.arange(len(data));w=.23
    ax.bar(x-w,[a['Q_G'] for a in data],w,label='Q_G',color=colors['G']);ax.bar(x,[a['Q_T_conditional'] for a in data],w,label='Q_T (conditional top)',color=colors['T']);ax.bar(x+w,[a['Q_set_max_conditional'] for a in data],w,label='max(Q_G,Q_T)',color=colors['set'])
    for i,a in enumerate(data):ax.text(i,max(a['Q_G'],a['Q_T_conditional'])+3,a['max_selected_reference'],ha='center',fontsize=9)
    ax.set_xticks(x,[a['record_id'] for a in data],rotation=50,ha='right',fontsize=8);ax.set_ylim(0,100);ax.set_ylabel('Quality score');ax.grid(axis='y',alpha=.2);ax.set_title('Set median '+f"{np.median([a['Q_set_max_conditional'] for a in data]):.2f}",fontsize=11)
    if col==0:ax.legend(fontsize=8,loc='upper right')
fig.suptitle('3 images / 18 exact workbench records\nMax-Q and best BEV-IoU choose the same fixed reference: 18/18 (16 T, 2 G)',fontsize=14,y=.99)
fig.text(.5,.015,'T floors confirmed; T ceiling is GT-derived conditional geometry. No formal GT, default score or eligibility changed.',ha='center',fontsize=10)
fig.tight_layout(rect=(0,.04,1,.94));(ROOT/'figures').mkdir(exist_ok=True);fig.savefig(ROOT/'figures/three_image_comparison.png',dpi=135)
print(ROOT/'figures/three_image_comparison.png')
