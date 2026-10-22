"""Round D: geometric information value. Read-only original inputs; derived controls are not votes.
Run: python round_d.py --source SOURCE_DIR --expanded EXPANDED_DIR --out OUTPUT_DIR
"""
from pathlib import Path
import sys,json,csv,itertools,copy,math,argparse
import numpy as np
from scipy.optimize import brentq
from scipy.integrate import quad
ROOT=Path(__file__).resolve().parents[2]
_ap=argparse.ArgumentParser(add_help=True)
_ap.add_argument('--source',type=Path,default=ROOT/'unpacked/full/quality_deep_20261007')
_ap.add_argument('--expanded',type=Path,default=ROOT/'unpacked/expanded_input')
_ap.add_argument('--out',type=Path,default=Path(__file__).resolve().parent)
_ap.add_argument('--density',type=Path,default=ROOT/'research/density_study')
_args,_unknown=_ap.parse_known_args()
SRC=_args.source.resolve()
sys.path[:0]=[str(SRC/'src'),str(SRC/'vendor')]
from components import compare,intrinsic
from arc_excerpt import footprint,paired_wall_proxy,project,Ring
OUT=_args.out.resolve();OUT.mkdir(parents=True,exist_ok=True)
DENSITY=_args.density.resolve()
INPUT=_args.expanded.resolve()/'current/panel.json'
def dump(name,x): (OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False))
def csvout(name,rows):
 keys=list(dict.fromkeys(k for row in rows for k in row))
 with (OUT/name).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def eligible(a):return a.get('condition')=='manual' and a.get('independent') and a.get('consensus_eligible') and a['main_consensus_gate']['status'] in {'main_candidate','oos_doorway_exploratory','stable_nonorthogonal_separate'}
def rawxyz(rec):
 p=np.asarray(rec['points']).reshape(-1,2,2)
 theta=2*np.pi*(p[:,:,0]/1024-.5);phi=np.pi*(.5-p[:,:,1]/512)
 rho=-1/np.tan(phi[:,1]);top=np.c_[rho*np.sin(theta[:,0]),rho*np.tan(phi[:,0]),-rho*np.cos(theta[:,0])]
 bot=np.c_[rho*np.sin(theta[:,1]),-np.ones(len(rho)),-rho*np.cos(theta[:,1])]
 return top,bot

def area_centroid(xz):
 x=xz[:,0];z=xz[:,1];xx=np.roll(x,-1);zz=np.roll(z,-1);cross=x*zz-xx*z;area=cross.sum()/2
 return abs(area),np.array([((x+xx)*cross).sum(),((z+zz)*cross).sum()])/(6*area)
def independent_curve(a,b):
 # Independent per-edge adaptive 1D integration, unlike equal-global-arclength midpoint grid.
 def directed(x,y):
  d=np.roll(y,-1,axis=0)-y;l2=(d*d).sum(1)
  def dist(p):
   t=np.clip(((p-y)*d).sum(1)/l2,0,1)
   return np.sqrt(((p-y-t[:,None]*d)**2).sum(1)).min()
  lengths=np.linalg.norm(np.roll(x,-1,axis=0)-x,axis=1);tot=0.;err=0.
  for i,L in enumerate(lengths):
   v,e=quad(lambda t:float(dist(x[i]+t*(x[(i+1)%len(x)]-x[i]))),0,1,epsabs=2e-9,epsrel=2e-8,limit=150)
   tot+=L*v;err+=L*e
  return tot/lengths.sum(),err/lengths.sum()
 x,e=directed(a,b);y,f=directed(b,a);return (x+y)/2,(e+f)/2

def independent_angular(a,g,n=32768):
 # 3D ray / edge plane intersection; does not call Ring or its coefficients.
 theta=(np.arange(n)+.5)*2*np.pi/n-np.pi
 def value(rec):
  top,bot=rawxyz(rec);out=[]
  for verts in [top,bot]:
   vals=np.full(n,np.nan);counts=np.zeros(n,int)
   for v,w in zip(verts,np.roll(verts,-1,axis=0)):
    lo=np.arctan2(v[0],-v[2]);hi=np.arctan2(w[0],-w[2]);delta=(hi-lo+np.pi)%(2*np.pi)-np.pi
    t=(theta-lo+np.pi)%(2*np.pi)-np.pi
    mask=(t/delta>=0)&(t/delta<1)
    normal=np.cross(v,w)
    tangent=-(normal[0]*np.sin(theta[mask])-normal[2]*np.cos(theta[mask]))/normal[1]
    vals[mask]=np.arctan(tangent);counts[mask]+=1
   if not np.all(counts==1):raise ValueError('not one-turn single-valued')
   out.append(vals)
  return np.array(out)
 return np.mean(abs(value(a)-value(g)),axis=1)*180/np.pi

def rec_from_xyz(name,top,bot):
 pts=np.empty((len(top)*2,2));pts[::2]=project(top);pts[1::2]=project(bot)
 return {'id':name,'points':pts.tolist(),'derived':True,'not_independent_vote':True}
def controls():
 rows=[];geoms=[]
 def report(family,a,g,**meta):
  m=compare(a,g,nlongitude=16384,ncurve=8192)
  row={'family':family,'id':a['id'],'ref':g['id'],**meta,**m};rows.append(row);geoms.append({'family':family,'a':a,'g':g,**meta});return row
 # Same angular boundary information with global metric scale: no extra observation; metric units differ.
 for scale in [.5,1,2,4]:
  xz=np.array([[-2,-1],[3,-1],[3,5],[-2,5]],float)*scale
  bot=np.c_[xz[:,0],-np.ones(4),xz[:,1]];top=bot.copy();top[:,1]=1.1*scale
  g=rec_from_xyz('scale_ref_'+str(scale),top,bot)
  t=top.copy();t[:,1]+=np.array([.2,-.1,.2,-.1])*scale
  report('global_depth_scale_equal_upper_angular',rec_from_xyz('scale_error_'+str(scale),t,bot),g,scale=scale,known_vertex_height_rms_h=float(np.sqrt(np.mean((t[:,1]-top[:,1])**2))))
 # Fixed asymmetric room, vertex-specific near/far perturbations; match actual full-curve upper MAE.
 xz=np.array([[-1,-1],[2,-1],[2,9],[-1,9]],float);bot=np.c_[xz[:,0],-np.ones(4),xz[:,1]];top=bot.copy();top[:,1]=1.2
 g=rec_from_xyz('asymmetric_fixed_ref',top,bot)
 for vertex in range(4):
  def change(d):
   t=top.copy();t[vertex,1]+=d;return rec_from_xyz('vertex_'+str(vertex),t,bot)
  target=.25
  d=brentq(lambda d:compare(change(d),g,nlongitude=4096,ncurve=32)['top_mae_deg']-target,1e-7,10)
  report('same_floor_matched_upper_mae_different_depth',change(d),g,vertex=vertex,radius_h=float(np.linalg.norm(xz[vertex])),height_displacement_h=d,angular_target_deg=target)
 # Equal-angle full top curves, equal IoU and centroid, but different conditional 3D errors.
 xz=np.array([[-2,-2],[2,-2],[2,2],[-2,2]],float);bot=np.c_[xz[:,0],-np.ones(4),xz[:,1]];top=bot.copy();top[:,1]=1.
 g=rec_from_xyz('centered_fixed_ref',top,bot)
 for scale in [1/1.3,1.3]:
  t=top*scale;b=bot.copy();b[:,[0,2]]*=scale
  report('matched_iou_centroid_upper_but_different_depth',rec_from_xyz('radial_'+str(scale),t,b),g,radial_scale=scale)
 # Same mean height, different spatial frequency. New multi-mode sweep, not old one-counterexample rerun.
 n=16;theta=np.arange(n)*2*np.pi/n;rad=np.full(n,3.);xz=np.c_[rad*np.sin(theta),-rad*np.cos(theta)];bot=np.c_[xz[:,0],-np.ones(n),xz[:,1]];top=bot.copy();top[:,1]=1.2
 g=rec_from_xyz('frequency_ref',top,bot)
 for freq in [1,2,4,8]:
  dz=.3*np.cos(freq*theta);t=top.copy();t[:,1]+=dz
  report('mean_height_cancellation_frequency',rec_from_xyz('frequency_'+str(freq),t,bot),g,frequency=freq,known_vertex_height_rms_h=float(np.sqrt(np.mean(dz*dz))))
 # Pure segmentation stays distinct expression, same geometric locus. Use this room, not historical 2t7.
 i=2;t2=np.insert(top,i+1,(top[i]+top[(i+1)%n])/2,axis=0);b2=np.insert(bot,i+1,(bot[i]+bot[(i+1)%n])/2,axis=0)
 report('segmentation_geometry_vs_expression',rec_from_xyz('frequency_ref_17_pairs',t2,b2),g,old_pair_count=n,new_pair_count=n+1,expression_equal=False)
 csvout('D_controls.csv',rows);dump('D_control_geometries.json',geoms)
 return rows

def main():
 panel=json.loads(INPUT.read_text())['images'];rows=[];sources={};byimage={};ind=[]
 for j,im in enumerate(panel):
  anns=[a for a in im['annotations'] if eligible(a)]
  if not anns:continue
  byimage[im['code']]=im
  for a in anns:
   sources[(im['code'],a['id'])]=a
   iv=intrinsic(a)
   for g in im['references']:
    m=compare(a,g)
    rows.append({'image':im['code'],'building':im['building'],'room':im['room'],'id':a['id'],'worker':a['worker'],'gate':a['main_consensus_gate']['status'],'pair_count':len(a.get('points') or [])//2,'reference_pair_count':len(g.get('points') or [])//2,'same_expression':'unknown_even_when_counts_equal','reference_flagged':any(im['review'][k] for k in ['gt_substantive_error_mark','gt_detail_omission_mark','gt_uncertainty_explicit_tag']),**iv,**m})
  if j%20==0:print('metrics',j,len(rows),flush=True)
 csvout('D_full_panel_metrics.csv',rows);dump('D_full_panel_metrics.json',rows)
 # Independent subset: first eligible original-reference row per building, no metric outcome selection.
 seen=set()
 for row in rows:
  if row['reference_version']!='original' or row['building'] in seen:continue
  seen.add(row['building']);a=sources[(row['image'],row['id'])];g=next(x for x in byimage[row['image']]['references'] if x['id']==row['reference_id'])
  try:
   ta,ba=rawxyz(a);tg,bg=rawxyz(g);aa,ca=area_centroid(ba[:,[0,2]]);ag,cg=area_centroid(bg[:,[0,2]])
   d,err=independent_curve(ta,tg)
   rr={'image':row['image'],'building':row['building'],'id':row['id'],'area_abs_difference':abs(aa-row['area_h2']),'centroid_normalized_abs_difference':abs(np.linalg.norm(ca-cg)/np.sqrt(ag)-row['centroid_distance_normalized']),'top3d_independent_h':d,'top3d_source_512_h':row['top3d_symmetric_mean_h'],'top3d_abs_difference_h':abs(d-row['top3d_symmetric_mean_h']),'adaptive_integration_error_h':err}
   try:
    angular=independent_angular(a,g);rr.update(top_mae_independent_deg=angular[0],top_mae_abs_difference_deg=abs(angular[0]-row['top_mae_deg']),bottom_mae_independent_deg=angular[1],bottom_mae_abs_difference_deg=abs(angular[1]-row['bottom_mae_deg']))
   except (ValueError,KeyError):rr['angular_status']='not_single_valued'
   ind.append(rr)
  except (ValueError,KeyError,TypeError) as e:ind.append({'image':row['image'],'id':row['id'],'status':'unavailable','reason':str(e)})
 csvout('D_independent_recomputation.csv',ind)
 # Genuine observed exact floor-equivalence and near-matched finite metric summaries.
 groups={}
 for row in rows:
  if row['reference_version']=='original' and row.get('iou') is not None:groups.setdefault(row['image'],[]).append(row)
 pairrows=[];samefloor=[]
 def pairmeta(a,b):return {'image':a['image'],'building':a['building'],'a':a['id'],'b':b['id'],'a_pair_count':a['pair_count'],'b_pair_count':b['pair_count'],'iou_a':a['iou'],'iou_b':b['iou'],'C_a':a['centroid_distance_normalized'],'C_b':b['centroid_distance_normalized'],'U_a':a.get('top_mae_deg'),'U_b':b.get('top_mae_deg'),'D3_a':a.get('top3d_symmetric_mean_h'),'D3_b':b.get('top3d_symmetric_mean_h')}
 def canfloor(a):
  p=np.asarray(sources[(a['image'],a['id'])]['points'])[1::2].round(9).tolist()
  return min(tuple(tuple(x) for x in seq[i:]+seq[:i]) for seq in [p,p[::-1]] for i in range(len(p)))
 for im,rs in groups.items():
  for a,b in itertools.combinations(rs,2):
   p=pairmeta(a,b)
   if canfloor(a)==canfloor(b):samefloor.append(p)
   if abs(a['iou']-b['iou'])<=.001 and abs(a['centroid_distance_normalized']-b['centroid_distance_normalized'])>=.02:
    pairrows.append({'witness_type':'matched_iou_different_centroid',**p})
   if all(x.get('top_mae_deg') is not None and x.get('top3d_symmetric_mean_h') is not None for x in [a,b]) and abs(a['iou']-b['iou'])<=.005 and abs(a['centroid_distance_normalized']-b['centroid_distance_normalized'])<=.005 and abs(a['top_mae_deg']-b['top_mae_deg'])<=.02 and abs(a['top3d_symmetric_mean_h']-b['top3d_symmetric_mean_h'])>=.03:
    pairrows.append({'witness_type':'matched_iou_C_upper_different_3d',**p})
 csvout('D_actual_same_floor_pairs.csv',samefloor);csvout('D_actual_matched_pairs.csv',pairrows)
 ctrl=controls()
 summary={'population_images':len([im for im in panel if im['population']=='research_annotation_image']),'eligible_manual_records':len(sources),'eligible_images':len(byimage),'eligible_buildings':len({im['building'] for im in byimage.values()}),'reference_comparison_rows':len(rows),'geometry_ok':sum(r.get('iou') is not None for r in rows),'upper_angular_ok':sum(r.get('top_mae_deg') is not None for r in rows),'top_3d_ok':sum(r.get('top3d_symmetric_mean_h') is not None for r in rows),'upper_NA_but_3d_ok':sum(r.get('top_mae_deg') is None and r.get('top3d_symmetric_mean_h') is not None for r in rows),'actual_same_floor_pairs':len(samefloor),'actual_same_floor_images':len({r['image'] for r in samefloor}),'actual_same_floor_upper_difference_gt_0_1':sum(r['U_a'] is not None and r['U_b'] is not None and abs(r['U_a']-r['U_b'])>.1 for r in samefloor),'matched_iou_C_difference_pairs':sum(r['witness_type']=='matched_iou_different_centroid' for r in pairrows),'matched_iou_C_upper_3d_difference_pairs':sum(r['witness_type']=='matched_iou_C_upper_different_3d' for r in pairrows),'independent_recomputations':len(ind)}
 for name in ['area_abs_difference','centroid_normalized_abs_difference','top3d_abs_difference_h','top_mae_abs_difference_deg','bottom_mae_abs_difference_deg']:
  vals=[r[name] for r in ind if name in r];summary['max_'+name]=max(vals) if vals else None
 dump('D_summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
