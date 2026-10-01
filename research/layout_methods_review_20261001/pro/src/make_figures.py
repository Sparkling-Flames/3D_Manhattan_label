"""Separate matplotlib figures with default color cycle (no explicit colors/styles)."""
from pathlib import Path
import json,csv
import numpy as np
import matplotlib.pyplot as plt
BASE=Path(__file__).resolve().parents[1]
OUT=BASE/'figures'
def save(fig,name):
 OUT.mkdir(exist_ok=True);fig.tight_layout();fig.savefig(OUT/(name+'.png'),dpi=170,bbox_inches='tight');fig.savefig(OUT/(name+'.svg'),bbox_inches='tight');plt.close(fig)
def main():
 made=[]
 r=json.load(open(BASE/'results/real_local_windows.json'))[0]
 fig,ax=plt.subplots(figsize=(9.4,4.8))
 for key,label in [('a_paths','R03398: 3 internal pairs'),('b_paths','R02614: 2 internal pairs')]:
  p=np.array(r[key][0]['points']);ax.plot(p[:,1],p[:,0],marker='o',label=label)
  for i,k in enumerate(r[key][0]['interior_vertex_indices'],1):
   offset=([(8,5),(-8,-20),(-27,5)] if key=='a_paths' else [(5,8),(8,8)])[i-1]
   ax.annotate(f'{"A" if key=="a_paths" else "B"}{k+1}',p[i,::-1],xytext=offset,textcoords='offset points')
  ax.scatter(p[[0,-1],1],p[[0,-1],0],marker='x',s=95)
 ax.set_aspect('equal');ax.set(xlabel='Z / camera height',ylabel='X / camera height',title='Real seam-crossing local paths: jtcxE69GiFV-12\n22.85-degree window; boundary distance approximately 0.87 h')
 ax.legend(loc='upper left',fontsize=9);fig.text(.5,.005,'A/B labels are array-pair positions, not established correspondences. Original reference ring is unconfirmed.',ha='center',fontsize=8)
 save(fig,'01_real_two_three_paths');made.append('01_real_two_three_paths.png')
 r=json.load(open(BASE/'results/local_path_cases.json'))[1]
 fig,ax=plt.subplots(figsize=(9,3.8))
 for key,label in [('a','2 genuine turns'),('b','4 genuine turns')]:
  p=np.array(r[key]);ax.plot(p[:,0],p[:,1],marker='o',label=label)
 ax.set_aspect('equal');ax.set(xlabel='X / camera height',ylabel='Z / camera height',title='Same entry and exit directions: valid orthogonal path alternatives\nAn odd difference in the number of genuine 90-degree turns is impossible')
 ax.legend();save(fig,'02_orthogonal_local_paths');made.append('02_orthogonal_local_paths.png')
 rows=list(csv.DictReader(open(BASE/'results/near_collinear_diagnostics.csv')))
 fig,ax=plt.subplots(figsize=(8,4.5));x=np.arange(len(rows));w=.35
 ax.bar(x-w/2,[float(r['floor_to_chord_h']) for r in rows],w,label='Floor endpoint to chord')
 ax.bar(x+w/2,[float(r['top_to_chord_h']) for r in rows],w,label='Top endpoint to 3D chord')
 ax.set_xticks(x,[r['record']+' pair '+str(int(r['pair_index_zero_based'])+1) for r in rows])
 ax.set(ylabel='Distance / camera height',title='Nearly collinear floor nodes need not be collinear at the wall top')
 ax.legend();save(fig,'03_bottom_top_collinearity');made.append('03_bottom_top_collinearity.png')
 r=json.load(open(BASE/'results/subtraction_exhaustive.json'));p=np.array(r['source']);q=p[r['residual_then_complexity']['ids']]
 fig,ax=plt.subplots(figsize=(6.5,6))
 for pts,label in [(p,'Observed 8-node boundary'),(q,'4-node residual/complexity optimum')]:
  z=np.r_[pts,pts[:1]];ax.plot(z[:,0],z[:,1],marker='o',label=label)
 ax.set_aspect('equal');ax.set(xlabel='X / camera height',ylabel='Z / camera height',title='Both have zero Manhattan residual\nIoU = 0.9901, but a 0.4 h feature is removed');ax.legend(loc='lower center')
 save(fig,'04_subtraction_detail_loss');made.append('04_subtraction_detail_loss.png')
 rows=json.load(open(BASE/'results/insertion_noise_summary.json'))
 fig,ax=plt.subplots(figsize=(8.2,4.8))
 for key,label in [('unordered_bound','Unordered bound matching'),('cyclic_bound','Cyclic bound matching'),('split_top','Independent top matching'),('split_bottom','Independent bottom matching')]:
  rr=[r for r in rows if r['record']=='R00705' and r['method']==key]
  ax.plot([r['noise_px'] for r in rr],[r['wrong_per_expected']*100 for r in rr],marker='o',label=label)
 ax.set(xlabel='Added pixel noise standard deviation',ylabel='Wrong correspondences / original pairs (%)',title='Controlled collinear insertion into R00705 geometry\n30 perturbations per setting; not additional human annotators')
 ax.legend();save(fig,'05_insertion_noise');made.append('05_insertion_noise.png')
 r=json.load(open(BASE/'results/consensus_joint_counterexample.json'))
 fig,ax=plt.subplots(figsize=(8,4.4));pat=[''.join(map(str,x['pattern'])) for x in r['patterns']]
 ax.bar(pat,[x['whole_count'] for x in r['patterns']]);ax.set(xlabel='Three local path choices',ylabel='Observed full-layout count',title='Local majority chooses 111; no worker supplied 111\nObserved full responses: 110, 101, 011')
 ax.set_yticks([0,1]);save(fig,'06_local_vs_joint_support');made.append('06_local_vs_joint_support.png')
 r=json.load(open(BASE/'results/order_counterexample.json'));fig,ax=plt.subplots(figsize=(6.7,6))
 for key in ('a','b'):
  pts=np.array(r[key]);pts=np.r_[pts,pts[:1]];ax.plot(pts[:,0],pts[:,1],marker='o',label='Ring '+key.upper())
 ax.set_aspect('equal');ax.set(xlabel='X / camera height',ylabel='Z / camera height',title='Identical point sets, different simple rings\nUnordered point cost = 0; BEV IoU = 0.6417');ax.legend()
 save(fig,'07_order_vs_point_set');made.append('07_order_vs_point_set.png')
 return made
if __name__=='__main__':print(main())
