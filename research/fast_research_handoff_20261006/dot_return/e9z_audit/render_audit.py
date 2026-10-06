"""Diagnostic plots from immutable image pixels and saved coordinate data."""
import json,argparse
from pathlib import Path
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--handoff',type=Path,default=Path(__file__).resolve().parent.parent/'oct6-handoff-intake')
parser.add_argument('--out',type=Path,default=Path(__file__).resolve().parent)
parser.add_argument('--include-panel',action='store_true',help='Also render nine source/12-degree overview plots.')
args=parser.parse_args()
ROOT=args.handoff.resolve(); OUT=args.out.resolve(); OUT.mkdir(parents=True,exist_ok=True)
A=json.loads((OUT/'e9z_audit.json').read_text());C=json.loads((OUT/'e9z_candidates_before_evaluation.json').read_text())

def floor(points):
 p=np.asarray(points,float).reshape(-1,2,2)[:,1];lon=2*np.pi*(p[:,0]/1024-.5);r=1/np.tan(np.pi*(p[:,1]/512-.5));return np.c_[r*np.sin(lon),-r*np.cos(lon)]
def xyz_pairs(points):
 ps=np.array(points).reshape(-1,2,2);xz=floor(points);r=np.linalg.norm(xz,axis=1);y=r*np.tan(np.pi*(.5-ps[:,0,1]/512));return np.stack([np.c_[xz[:,0],y,xz[:,1]],np.c_[xz[:,0],-np.ones(len(ps)),xz[:,1]]],axis=1)
def image_points(xyz):
 x,y,z=xyz.T;r=np.hypot(x,z);return np.c_[1024*(np.arctan2(x,-z)/(2*np.pi)+.5),512*(.5-np.arctan2(y,r)/np.pi)]
def plot_ring(ax,points,color,label=None,linewidth=1.5,alpha=1):
 ps=np.array(points).reshape(-1,2,2);xy=xyz_pairs(points)
 for side in (0,1):
  for i in range(len(xy)):
   t=np.linspace(0,1,501)[:,None];line=image_points(xy[i,side]*(1-t)+xy[(i+1)%len(xy),side]*t)
   jumps=np.r_[False,abs(np.diff(line[:,0]))>512];line[jumps]=np.nan
   ax.plot(line[:,0],line[:,1],color=color,lw=linewidth,alpha=alpha)
 for p in ps: ax.plot(p[:,0],p[:,1],color=color,lw=linewidth,alpha=alpha)
 ax.scatter(ps[:,0,0],ps[:,0,1],c=color,s=14,label=label,zorder=5);ax.scatter(ps[:,1,0],ps[:,1,1],c=color,s=14,zorder=5)

im=np.array(Image.open(ROOT/'images/e9zR4mvMWw7-15.png'))
fig,axs=plt.subplots(4,1,figsize=(16,31));case=[('paired_5','Cyan: 5 deg paired, raw 3-pair MV'),('paired_9','Yellow: 9 deg paired, 3 left + 2 right mixed seam cluster'),('paired_12','Orange: 12 deg paired, retains rejected left and right'),('top_5','Green: 5 deg top-anchor candidate; bottom location unresolved')]
for ax,(k,label),color in zip(axs,case,['#00eeff','#ffff00','#ff8c00','#40ff50']):
 ax.imshow(im,extent=[0,1024,512,0]);plot_ring(ax,C[k]['points'],color);ax.set_title(label);ax.set_xlim(0,1024);ax.set_ylim(470,70);ax.set_xlabel('Original continuous x');ax.set_ylabel('y')
fig.tight_layout();fig.savefig(OUT/'e9z_four_candidates.png',dpi=125);plt.close(fig)

fig,axs=plt.subplots(1,2,figsize=(17,8))
# Roll exactly 128 continuous-coordinate pixels so that the original seam appears at x=128.
rolled=np.roll(im,im.shape[1]//8,axis=1)
for ax in axs:
 ax.imshow(rolled,extent=[0,1024,512,0]);ax.set_xlim(65,210);ax.set_ylim(410,180);ax.set_xlabel('Display x = (original x + 128) modulo 1024');ax.axvline(128,color='white',ls=':',lw=1);ax.grid(alpha=.15)
colors=plt.cm.tab10(np.linspace(0,1,8))
for j,(r,col) in enumerate(zip(A['right_observations'],colors)):
 p=np.array(r['points']);x=(p[0,0]+128)%1024
 axs[0].plot([x,x],p[:,1],color=col,lw=1);axs[0].scatter([x,x],p[:,1],color=col,s=30)
 axs[0].annotate(f"{r['id']} p{r['pair_index']}: y={p[1,1]:.1f}",(x,p[1,1]),(151,218+j*22),color=col,fontsize=9,arrowprops=dict(arrowstyle='-',color=col,lw=.7))
for r in A['left_observations']:
 p=np.array(r['points']);p[:,0]=(p[:,0]+128)%1024;axs[0].scatter(p[:,0],p[:,1],marker='x',c='#ff00ff',s=50)
axs[0].set_title('8 original right observations; magenta x = 3 original left observations')
for key,col,label in [('paired_9','#ffff00','9 deg mixed seam'),('paired_12','#ff8c00','12 deg right'),('top_5','#00ff55','5 deg top-anchor')]:
 ps=np.array(C[key]['points']).reshape(-1,2,2)
 pair=next(p for p in ps if (p[0,0]<10 if key=='paired_9' else p[0,0]>1000));pair[:,0]=(pair[:,0]+128)%1024
 axs[1].plot(pair[:,0],pair[:,1],color=col,lw=2,label=label);axs[1].scatter(pair[:,0],pair[:,1],color=col,s=45)
axs[1].legend(loc='lower right');axs[1].set_title('Candidate seam positions, no reference coordinates shown')
fig.tight_layout();fig.savefig(OUT/'e9z_seam_sources.png',dpi=150);plt.close(fig)

fig,ax=plt.subplots(figsize=(9,8));ref=floor(A['reference']['points']);ax.fill(ref[:,0],ref[:,1],color='lightgray',label='Fixed historical reference, evaluation only')
for points,col,label in [(C['paired_12']['points'],'#f18a00','12 deg paired: 5 pairs'),(A['manual_delete_points'],'#cb176e','12 deg user-specified left deletion: 4 pairs'),(C['top_5']['points'],'#008a44','5 deg top-anchor: 4 pairs')]:
 p=floor(points);p=np.vstack([p,p[0]]);ax.plot(p[:,0],p[:,1],color=col,lw=2,marker='o',label=label)
ax.scatter([0],[0],c='black',marker='*',s=80,label='Camera');ax.set_aspect('equal');ax.legend(fontsize=9);ax.set_xlabel('x / camera height');ax.set_ylabel('z / camera height');ax.grid(alpha=.2);ax.set_title('e9z range compensation: wrong turn can increase reference overlap')
fig.tight_layout();fig.savefig(OUT/'e9z_range_compensation.png',dpi=150);plt.close(fig)

D=json.loads((ROOT/'inputs.json').read_text());B=json.loads((ROOT/'baselines.json').read_text())['states']
for image in D['images'] if args.include_panel else []:
 code=image['image'];r=next(s['result'] for s in B if s['image']==code and s['route']=='paired' and s['threshold_deg']==12)
 fig,ax=plt.subplots(figsize=(17,8));ax.imshow(Image.open(ROOT/'images'/f'{code}.png'),extent=[0,1024,512,0])
 for g in r['identity_groups']:
  col='#30ffff' if g['selected'] else '#ff00e6';ps=np.array(g['center']);ax.scatter(ps[:,0],ps[:,1],color=col,s=20,zorder=5)
  ax.text(ps[0,0]+2,ps[0,1]-5,str(g['support']),color=col,fontsize=8,bbox=dict(facecolor='black',alpha=.45,pad=1,edgecolor='none'))
  for m in g['members']:
   p=np.array(m['points']);ax.scatter(p[:,0],p[:,1],c=col,s=3,alpha=.4)
 if r['candidate']['points']:plot_ring(ax,r['candidate']['points'],'#30ffff',linewidth=1.2)
 ax.set_title(f'{code} | n={len(image["records"])} | 12 deg paired: cyan retained, magenta below vote; numerals = group support')
 ax.set_xlim(0,1024);ax.set_ylim(470,40);ax.set_xlabel('Original continuous x');ax.set_ylabel('y')
 fig.tight_layout();fig.savefig(OUT/f'{code}_paired12_evidence.png',dpi=120);plt.close(fig)
print(f'Generated {12 if args.include_panel else 3} diagnostic plots from original pixels and saved coordinates')
