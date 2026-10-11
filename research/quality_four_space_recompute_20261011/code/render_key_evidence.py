"""Small static figure from actual GT/current points; no new top/3D reconstruction."""
from pathlib import Path
import json
import numpy as np
import os;os.environ.setdefault('MPLCONFIGDIR','/tmp/quality-four-space-mpl')
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
from recompute_floor import ROOT,project
def main():
 seed=json.loads((ROOT/'inputs/previous/editor_seed_data.json').read_text());c=seed['images'][0];GT=project(c['reference_points_1024x512']);local=json.loads((ROOT/'results/local_structure_20.json').read_text());loc={r['record_id']:r for r in local['rows']};prev=ROOT.parent/'quality_four_space_recheck_20261011';im=Image.open(prev/'user/editor/assets/T30_original.jpg').convert('RGB')
 fig=plt.figure(figsize=(13,9),layout='constrained');gs=fig.add_gridspec(2,3,height_ratios=[1,1.4]);ax=fig.add_subplot(gs[0,:]);ax.imshow(im);ax.axis('off');points=np.asarray(c['reference_points_1024x512']);sx,sy=im.width/1024,im.height/512
 for i in [4,5,6,7]:
  for j in [0,1]:
   p=points[2*i+j]*[sx,sy];ax.scatter(*p,s=45,color='#b83259',edgecolor='white');ax.annotate(f'GT {i+1}',p,xytext=(5,5),textcoords='offset points',color='#701833',weight='bold')
 ax.set_title('Actual panorama + unchanged GT pair numbers: 5/8 entrance; 6/7 far end')
 for col,id in enumerate(['R03258','R01412','R02963']):
  a=next(v for v in c['annotations'] if v['record_id']==id);p=project(a['points']);e=loc[id];ax=fig.add_subplot(gs[1,col]);ax.fill(GT[[4,5,6,7],0],GT[[4,5,6,7],1],color='#f4da93',alpha=.6,label='GT5-8 protrusion');q=np.vstack((GT,GT[0]));ax.plot(q[:,0],q[:,1],color='#bb3b60',lw=1.7,label='GT A');q=np.vstack((p,p[0]));ax.plot(q[:,0],q[:,1],color='#2868b1',lw=1.7,label='current annotation');ax.scatter(p[:,0],p[:,1],color='#2868b1',s=12)
  for i in [4,5,6,7]:ax.annotate(str(i+1),GT[i],xytext=(4,3),textcoords='offset points',color='#bb3b60',weight='bold')
  ax.set_aspect('equal');ax.set_xlim(-3.1,1.7);ax.set_ylim(-4.3,3.0);ax.grid(alpha=.15);ax.set_xlabel('x / camera height');ax.set_ylabel('z / camera height');ax.legend(fontsize=8,loc='lower right');status='manual current candidate' if id!='R02963' else 'excluded; rebuilt diagnostic only';ax.set_title(f'{id} / {a["worker_id"]}\n{status}\nextension {100*e["front_difference_coverage"]:.2f}%; far half {100*e["far_half_coverage"]:.2f}%',fontsize=10)
 out=ROOT/'results/figures';out.mkdir(exist_ok=True);fig.savefig(out/'local_structure_key_examples.png',dpi=160);plt.close(fig)
 print('Actual panorama and 3 same-scale BEV examples rendered; no new top or 3D')
if __name__=='__main__':main()
