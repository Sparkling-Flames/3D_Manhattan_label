"""Numeric figures and exact-geometry photo overlays. Default Matplotlib colors.
Run separately from numerical reproduction; each chart is its own figure.
"""
from quality import *
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
F=ROOT/'figures';F.mkdir(exist_ok=True)
def finish(fig,name):fig.tight_layout();fig.savefig(F/name,dpi=160);plt.close(fig)
def wires(g):
 paths=[]
 for k in ('bottom3d','top3d'):
  if k not in g:continue
  p=np.array(g[k]);paths.extend([p[i][None,:]*(1-np.linspace(0,1,100)[:,None])+p[(i+1)%len(p)][None,:]*np.linspace(0,1,100)[:,None] for i in range(len(p))])
 if 'top3d' in g:
  for a,b in zip(g['bottom3d'],g['top3d']):paths.append(np.array([a,b]))
 return paths

def main():
 r=ROOT/'results';f=pd.read_csv(r/'ORDINARY_962.csv');w=pd.read_csv(r/'WORKER_METRIC_SENSITIVITY.csv');fig,ax=plt.subplots(figsize=(8,7));ax.scatter(f.IoU3D100,f.WQ,s=12,alpha=.45);ax.set(xlabel='Same-reference vertex-mean 3D IoU (%)',ylabel='WQ-LS08 (not a calibrated grade)',title='962 ordinary conditional records');ax.grid(alpha=.3);finish(fig,'ordinary_metric_scatter.png')
 ws=w.sort_values('WQ_rank');fig,ax=plt.subplots(figsize=(12,5));ax.plot(ws.worker_id,ws.WQ_rank,'o-',label='WQ within-cell centered rank');ax.plot(ws.worker_id,ws.IoU3D100_rank,'s--',label='3D IoU within-cell centered rank');ax.invert_yaxis();ax.set(ylabel='Descriptive relative rank (not eligibility)',title='24 workers: same task/reference centering, unequal task coverage');ax.tick_params(axis='x',rotation=45);ax.legend();ax.grid(alpha=.3);finish(fig,'worker_rank_sensitivity.png')
 sr=pd.read_csv(r/'HEIGHT_ESTIMATOR_AND_SUBDIVISION_962.csv');fig,ax=plt.subplots(figsize=(9,5));ax.hist(sr.subdivision_iou3d_change_pp,bins=45);ax.set(xlabel='3D IoU change (percentage points)',ylabel='Responses',title='Same piecewise geometry; add 3 collinear points to one wall (n=962)');finish(fig,'subdivision_iou_sensitivity.png')
 co=read(r/'CONTROLS_REMEASURED_151.json');co=[x for x in co if x['record_id'].startswith('rhombus:')];fig,ax=plt.subplots(figsize=(9,5));x=[90-float(c['record_id'].split(':')[1]) for c in co];ax.plot(x,[c['scores']['WQ'] for c in co],'o-',label='WQ full');ax.plot(x,[c['scores']['current'] for c in co],'s--',label='Current hill08 full');ax.plot(x,[100*c['metrics']['iou_3d_corner_mean'] for c in co],'^:',label='3D IoU');ax.set(xlabel='Shear deficit (90 - theta), degrees',ylabel='Score / IoU percentage',title='Unit-edge rhombus: complete scores, not an ablation');ax.legend();ax.grid(alpha=.3);finish(fig,'rhombus_full_response.png')
 fu=read(r/'FUSION_220_RESULTS.json');pp=fu.get('auto_assisted_pairs',[])
 # Subdivision controls are a measured negative example for the prism estimator.
 sy=read(r/'MECHANISM_CHECK_SUMMARY.json')['synthetic_subdivision'];fig,ax=plt.subplots(figsize=(8,5));ax.plot([x['n_added'] for x in sy],[100*x['metrics']['iou_3d_corner_mean'] for x in sy],'o-',label='3D IoU');ax.plot([x['n_added'] for x in sy],[x['scores']['WQ'] for x in sy],'s--',label='WQ');ax.set(xlabel='Inserted collinear vertices',ylabel='Score / IoU percentage',title='Unchanged piecewise geometry: one synthetic height pattern');ax.legend();finish(fig,'synthetic_subdivision.png')
 obj={o['object_id']:o for o in read(ROOT/'source/historical_current_formal_loader_data.json')['objects']};allf=pd.read_csv(r/'ALL_3152_LEDGER.csv').set_index('record_id')
 viewed=[]
 for name,ids in [('J04',['R03274']),('P01',['R02015','R00637']),('C02',['R03351','R03350']),('Q03',['R01501','R01191']),('Q01_scope',['R03332','R03329']),('Q02_scope',['R02200','R00990'])]:
  rr=[allf.loc[rid] for rid in ids];g=[geometry(obj[a.object_id]['points_1024x512']) for a in rr];labels=ids.copy();ref=rr[0].reference_id
  if isinstance(ref,str) and ref in obj:g.append(geometry(obj[ref]['points_1024x512']));labels.append('Reference (conditional target)')
  image=ROOT/'source/ready/photos'/f'{rr[0].image_id}.png'
  if not image.exists():image=ROOT/'source/additional_photos'/image.name
  if image.exists():
   img=Image.open(image);W,H=img.size;fig,ax=plt.subplots(figsize=(14,7.5));ax.imshow(img)
   for gg,label in zip(g,labels):
    xx=[];yy=[]
    for p in wires(gg):
     rad=np.linalg.norm(p[:,[0,2]],axis=1);x=(np.arctan2(p[:,0],-p[:,2])/(2*np.pi)+.5)*W;y=(.5-np.arctan2(p[:,1],rad)/np.pi)*H
     for i in range(len(x)):
      if i and abs(x[i]-x[i-1])>W/2:xx.append(np.nan);yy.append(np.nan)
      xx.append(x[i]);yy.append(y[i])
     xx.append(np.nan);yy.append(np.nan)
    ax.plot(xx,yy,linewidth=1.5,label=label)
   ax.set_xlim(0,W);ax.set_ylim(H,0);ax.set_title(name+' | unchanged geometry projected onto original panorama');ax.legend(loc='upper center',bbox_to_anchor=(.5,-.03),ncol=3);finish(fig,name+'_overlay.png')
   viewed.append(dict(case_id=name,image_id=rr[0].image_id,source=str(image.relative_to(ROOT)),rendered_overlay=True,assistant_visual_review=False))
  bpts=np.concatenate([np.array(gg['bottom3d'])[:,[0,2]] for gg in g]);ratio=np.ptp(bpts[:,1])/max(np.ptp(bpts[:,0]),1e-9)
  fig,ax=plt.subplots(figsize=(10,max(3.4,min(7.5,8*ratio+1.7))))
  for gg,label in zip(g,labels):
   p=np.array(gg['bottom3d'])[:,[0,2]];p=np.r_[p,p[:1]];ax.plot(p[:,0],p[:,1],'-o',markersize=3,label=label)
  ax.scatter([0],[0],marker='*',s=80,label='Camera');ax.set_aspect('equal');ax.grid(alpha=.3);ax.set(xlabel='X / camera height',ylabel='Z / camera height',title=name+' | same-scale footprint');fig.legend(*ax.get_legend_handles_labels(),loc='lower center',bbox_to_anchor=(.5,.01),ncol=2,fontsize=8);fig.tight_layout(rect=(0,.22,1,1));fig.savefig(F/(name+'_bev.png'),dpi=160);plt.close(fig)
  fig=plt.figure(figsize=(8,7));ax=fig.add_subplot(111,projection='3d');pts=np.concatenate([np.array(gg[k])[:,[0,2,1]] for gg in g for k in ('bottom3d','top3d')]+[np.zeros((1,3))]);mid=(pts.min(0)+pts.max(0))/2;rad=max(np.ptp(pts,axis=0))/2*1.1
  for gg,label in zip(g,labels):
   paths=wires(gg);p=np.concatenate([np.r_[p,np.full((1,3),np.nan)] for p in paths])[:,[0,2,1]];ax.plot(p[:,0],p[:,1],p[:,2],label=label,linewidth=1.3)
  for fun,m in zip([ax.set_xlim,ax.set_ylim,ax.set_zlim],mid):fun(m-rad,m+rad)
  ax.scatter([0],[0],[0],marker='*',s=45,label='Camera');ax.set_box_aspect([1,1,1]);ax.set(xlabel='X / h',ylabel='Z / h',zlabel='Y / h',title=name+' | same-scale 3D');ax.legend(fontsize=8);finish(fig,name+'_3d.png')
 dump(ROOT/'results/FIGURE_MANIFEST.json',dict(figures=[p.name for p in F.glob('*.png')],source_photo_figures=viewed,source_photo_pixels_not_synthetic=True,synthetic_controls_are_explicitly_labelled=True,charts_default_palette=True))
 print('Written',len(list(F.glob('*.png'))),'figures')
if __name__=='__main__':main()
