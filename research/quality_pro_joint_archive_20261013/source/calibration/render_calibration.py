#!/usr/bin/env python3
"""Publication-style diagnostic figures from delivered numerical results."""
from __future__ import annotations
import argparse,csv,gzip,io,json,math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
from score import BASELINE,direction_loss
HERE=Path(__file__).resolve().parent

def save(fig,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    stream=io.BytesIO();fig.savefig(stream,format='png',dpi=180,bbox_inches='tight',facecolor='white')
    blob=stream.getvalue();im=Image.open(io.BytesIO(blob));im.load()
    pending=path.with_suffix('.pending');pending.write_bytes(blob);pending.replace(path)
    plt.close(fig)

def main():
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,default=HERE/'results');p.add_argument('--out',type=Path,default=HERE/'figures');a=p.parse_args()
    data=json.loads((a.results/'selected_scores_922.json').read_text())['rows'];cfg=json.loads((HERE/'recommended_parameters.json').read_text())
    names=['baseline_quad08','J_main_hill_tail12_g1_l025','J_simple_power8_g1_l025']
    cc={'baseline_quad08':BASELINE,**cfg['candidates']};colors=['#6f7785','#1259a7','#c77420']
    labels=['Baseline capped direction','Recommended smooth tail','Simple quadratic alternative']
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.18})
    fig,axes=plt.subplots(2,2,figsize=(12.2,8.8))
    d=np.linspace(0,90/math.sqrt(12),400)
    for n,col,lab in zip(names,colors,labels):axes[0,0].plot(d,100/(1+direction_loss(d,cc[n])),color=col,lw=2,label=lab)
    axes[0,0].set(xlabel='Common-axis direction RMS D (degrees)',ylabel='Quality if all other terms are ideal',ylim=(0,102),title='A  Severe direction no longer reaches an early plateau')
    axes[0,0].axvline(12,color='#1259a7',lw=1,ls=':');axes[0,0].legend(frameon=False,fontsize=8)
    h=np.linspace(0,1,400)
    axes[0,1].plot(h,100/(1+h*h),label='Global mean error: g = 1',color='#1259a7',lw=2)
    axes[0,1].plot(h,100/(1+(h/.25)**2),label='Local centered RMS: l = 0.25',color='#be463b',lw=2)
    axes[0,1].plot(h,100/(1+(h/.8)**2),label='Baseline global: g = 0.8',color='#6f7785',ls='--')
    axes[0,1].set(xlabel='Error / reference mean wall height',ylabel='Quality if all other terms are ideal',title='B  Height response; these are not human grade boundaries',ylim=(0,102))
    axes[0,1].legend(frameon=False,fontsize=8)
    x=np.array([r['metrics']['dir'] for r in data]);delta=np.array([r['scores'][names[1]]-r['scores'][names[0]] for r in data]);el=np.array([r['conditional_personnel_eligible'] for r in data])
    axes[1,0].scatter(x[~el],delta[~el],s=11,c='#a9b1bc',alpha=.45,label='Other frozen computations (779)')
    axes[1,0].scatter(x[el],delta[el],s=21,c='#1259a7',alpha=.85,label='Conditional personnel layer (143)')
    for rid,offset in [('R03274',(-45,9)),('R00637',(7,-2)),('R00397',(6,8))]:
        i=next(i for i,r in enumerate(data) if r['id']==rid)
        axes[1,0].annotate(rid,(x[i],delta[i]),xytext=offset,textcoords='offset points',fontsize=8)
    axes[1,0].axhline(0,color='#333333',lw=.8)
    axes[1,0].set(xlabel='D (degrees)',ylabel='Recommended Q minus baseline Q',title='C  Formula effect with the same fixed reference')
    axes[1,0].legend(frameon=False,fontsize=8)
    trip=json.loads((a.results/'matched_priority_triplets.json').read_text())
    ss=trip['summary'];xx=np.arange(3);width=.35
    spherical=[ss['endpoint_spherical_and_counterexamples'][n]['ordered'] for n in names]
    boundary=[ss['boundary_displacement'][n]['ordered'] for n in names]
    axes[1,1].bar(xx-width/2,np.array(spherical)/30,width,label='Matched angular input budget (30)',color='#1259a7')
    axes[1,1].bar(xx+width/2,np.array(boundary)/16,width,label='Matched 3D boundary budget (16)',color='#63a49a')
    for i in range(3):
        axes[1,1].text(i-width/2,spherical[i]/30+.015,f'{spherical[i]}/30',ha='center',fontsize=9)
        axes[1,1].text(i+width/2,boundary[i]/16+.015,f'{boundary[i]}/16',ha='center',fontsize=9)
    axes[1,1].set_xticks(xx,['Baseline','Recommended','Simple']);axes[1,1].set(ylim=(0,1.14),ylabel='Fraction with Q(structure) < Q(local) < Q(global)',title='D  Controlled response, not human validation')
    axes[1,1].legend(frameon=False,fontsize=8,loc='lower left')
    fig.tight_layout(pad=2.);save(fig,a.out/'joint_response_and_impact.png')
    grid=list(csv.DictReader(gzip.open(a.results/'all_search_results.csv.gz','rt')))
    grid=[r for r in grid if r.get('global_power')=='2.0' and r.get('local_power')=='2.0']
    yes=[r for r in grid if int(r['hard_sign_violations'])==0 and int(r['response_design_violations'])==0 and float(r['clean22_inversions'])==0]
    fig,ax=plt.subplots(figsize=(8.8,6.7))
    ax.scatter([float(r['local_scale']) for r in grid],[float(r['global_scale']) for r in grid],s=6,c='#c2c6cb',alpha=.25,label='Searched candidates with quadratic height')
    ax.scatter([float(r['local_scale']) for r in yes],[float(r['global_scale']) for r in yes],s=9,c='#1259a7',alpha=.5,label='Directions + stated policy + 22-case order feasible')
    ll=np.geomspace(.05,.8,100);ax.plot(ll,2.9738333335*ll,color='#be463b',ls='--',label='P04 conditional boundary: g = 2.97383 l')
    ax.scatter([.25],[1.],marker='*',s=240,c='#ddaa24',edgecolor='black',linewidth=.5,label='Recommended g=1, l=0.25',zorder=10)
    ax.set(xscale='log',yscale='log',xlabel='Local centered-height scale l',ylabel='Global mean-height scale g',title='Projected feasible region is broad; it is not a confidence interval')
    ax.legend(frameon=False,fontsize=9,loc='upper left');fig.tight_layout();save(fig,a.out/'height_parameter_identifiability.png')
    print(json.dumps({'figures':[str(a.out/'joint_response_and_impact.png'),str(a.out/'height_parameter_identifiability.png')],'all_pngs_decoded_before_atomic_write':True}))

if __name__=='__main__':main()
