"""Independent input checks and measured mechanism regressions. No data edits.
Subdivision experiments alter comparison copies only and are NOT human data.
"""
from quality import *
from collections import Counter
import pandas as pd
from copy import deepcopy
S=ROOT/'source';R=ROOT/'results'

def subdivision(a,edge=0,n=1):
 out={}
 for key in ('bottom3d','top3d'):
  x=np.array(a[key]);v=[]
  for i in range(len(x)):
   v.append(x[i])
   if i==edge:
    v.extend(x[i]*(1-t)+x[(i+1)%len(x)]*t for t in np.arange(1,n+1)/(n+1))
  out[key]=np.array(v).tolist()
 return out

def audited_inputs(d):
 errors=[];stats=Counter();xr=[]
 known={o['object_id']:o for o in read(S/'ready/data/objects.json')['objects']}
 geomdiff=[];obj={o['object_id']:o for o in d['objects']};images={i['image_id']:i for i in d['images']}
 ids={o['object_id']:f'R{i:05d}' for i,o in enumerate(sorted(d['objects'],key=lambda z:z['object_id']),1)}
 for o in d['objects']:
  oid=o['object_id'];stats[o['preprocessing_status']]+=1
  try:
   assert o['image_id'] in images
   if o['preprocessing_status']=='ready':
    before=np.array(o['before_preprocessing_points']);p=np.array(o['preprocessed_points']);links=o['links_zero_based'];ind=o['ordered_source_point_indices']
    assert len(p)==len(before) and sorted(i for pair in links for i in pair)==list(range(len(p)))
    assert sorted(ind)==list(range(len(p))) and np.array_equal(p[ind],np.array(o['points_1024x512']))
    dx=[]
    for t,b in links:
     delta=(before[b,0]-before[t,0]+512)%1024-512;mid=(before[t,0]+delta/2)%1024
     assert abs(delta)<512-1e-8
     assert np.allclose(p[[t,b],0],mid,atol=1e-8,rtol=0) and np.array_equal(p[[t,b],1],before[[t,b],1])
     dx.append(delta)
    assert o['matterport_links_zero_based']==[[i,i+1] for i in range(0,len(p),2)]
    if o['object_kind']=='annotation':xr.append(dict(record_id=ids[oid],object_id=oid,raw_x_rms_px=float(np.sqrt(np.mean(np.square(dx)))),raw_x_max_px=float(np.max(np.abs(dx))),main_score_penalty=False))
   else:assert o['points_1024x512'] is None and o['preprocessed_points'] is None
   if o['ring_confirmed']:assert o['order_record']['order']==o['ordered_source_pair_indices']
   if oid in known:
    for key in ('before_preprocessing_points','preprocessed_points','points_1024x512','links_zero_based','ordered_source_point_indices','ring_confirmed','order_record'):
     assert key not in known[oid] or known[oid][key]==o[key],key
   if o['geometry']['status']=='surface_valid' and o['points_1024x512'] is not None:
    g=geometry(o['points_1024x512']);stats['geometry_rebuilt']+=1
  except (ValueError,AssertionError,KeyError) as e:errors.append(dict(object_id=oid,error=type(e).__name__+':'+str(e)))
 for im in images.values():
  for kind,oid in im['references'].items():
   if not (obj[oid]['image_id']==im['image_id'] and obj[oid]['object_kind']==kind):errors.append(dict(image_id=im['image_id'],error='reference_identity_mismatch'))
 pd.DataFrame(xr).to_csv(R/'RAW_X_DIAGNOSTICS.csv',index=False)
 out=dict(objects=len(obj),annotations=sum(o['object_kind']=='annotation' for o in obj.values()),ready_overlap=len(known),checks=dict(stats),raw_x_available=len(xr),raw_x_unavailable=3152-len(xr),errors=errors,native_loader_run=False,full_comment_cross_tables_revalidated=False)
 dump(R/'INPUT_RECONSTRUCTION_AUDIT.json',out);return out

def main():
 d=read(S/'historical_current_formal_loader_data.json');o={x['object_id']:x for x in d['objects']};inp=audited_inputs(d)
 allv=read(R/'all_scores.json');ordinary=[p for p in allv['records'] if p['status']=='complete' and 'ordinary_current' in p['use_layers']]
 controls=[]
 for r in read(S/'ready/data/control_geometries.json'):
  z=measure(r['annotation_geometry'],r['reference_geometry'])
  controls.append(dict(record_id=r['record_id'],source=r['source'],**z))
 dump(R/'CONTROLS_REMEASURED_151.json',controls)
 # Counterexample of vertex-mean prism sensitivity to unchanged piecewise geometry.
 sq=dict(bottom3d=[[-1.,-1.,-1.],[1.,-1.,-1.],[1.,-1.,1.],[-1.,-1.,1.]],top3d=[[-1.,1.5,-1.],[1.,1.5,-1.],[1.,1.5,1.],[-1.,1.5,1.]])
 a=deepcopy(sq)
 for p,h in zip(a['top3d'],[2.,2.,2.,4.]):p[1]=h-1
 synth=[]
 for n in (0,1,3,15):
  aa=a if n==0 else subdivision(a,2,n);synth.append(dict(n_added=n,geometry=aa,**measure(aa,sq)))
 # Keep mean-height estimator change separate from geometric changes.
 rr=[];selves={}
 for seq,r in enumerate(ordinary):
  if seq%100==0:print('subdivision',seq,flush=True)
  a=geometry(o[r['object_id']]['points_1024x512']);g=geometry(o[r['reference_id']]['points_1024x512']);areas=au.area_metrics(a,g)
  hva=trad.vertex_mean_height_h(a);hvg=trad.vertex_mean_height_h(g);hpa=trad.perimeter_mean_height_h(a);hpg=trad.perimeter_mean_height_h(g)
  iv=trad.prism_iou(areas['area_h2'],areas['reference_area_h2'],areas['intersection_area_h2'],hva,hvg);ip=trad.prism_iou(areas['area_h2'],areas['reference_area_h2'],areas['intersection_area_h2'],hpa,hpg)
  aa=subdivision(a,0,3);isb=trad.prism_iou(areas['area_h2'],areas['reference_area_h2'],areas['intersection_area_h2'],trad.vertex_mean_height_h(aa),hvg)
  t={'conditional_iou3d_perimeter_mean':ip,'hohonet_iou3d_vertex_mean':iv};tb={'hohonet_iou3d_vertex_mean':isb}
  m=r['metrics'];sc=r['scores'];z=measure(aa,g) if seq%20==0 else None
  rr.append(dict(record_id=r['record_id'],image_code=r['image_code'],reference_id=r['reference_id'],vertices=len(a['bottom3d']),perimeter_iou3d100=100*t['conditional_iou3d_perimeter_mean'],vertex_iou3d100=100*t['hohonet_iou3d_vertex_mean'],estimator_difference_pp=100*(t['conditional_iou3d_perimeter_mean']-t['hohonet_iou3d_vertex_mean']),subdivision_iou3d_change_pp=100*(tb['hohonet_iou3d_vertex_mean']-t['hohonet_iou3d_vertex_mean']),subdivision_WQ_change=z['scores']['WQ']-sc['WQ'] if z else None,subdivision_Hc_change=z['metrics']['Hcenter']-m['Hcenter'] if z else None,subdivision_D_change=z['metrics']['dir']-m['dir'] if z else None,subdivision_Sb_change=z['metrics']['S_bottom_deg']-m['S_bottom_deg'] if z else None))
  if r['reference_id'] not in selves:selves[r['reference_id']]=dict(reference_id=r['reference_id'],image_code=r['image_code'],**measure(g,g))
 pd.DataFrame(rr).to_csv(R/'HEIGHT_ESTIMATOR_AND_SUBDIVISION_962.csv',index=False);dump(R/'REFERENCE_SELF_SCORES.json',list(selves.values()))
 j=next(r for r in ordinary if r['record_id']=='R03274');p=np.array(o[j['object_id']]['points_1024x512']);q=np.array(o[j['reference_id']]['points_1024x512']);g=geometry(q)
 # Diagnostic correspondence: unique cyclic longitude-cost minimum; no pairing/ring repair.
 costs=[np.square((p[::2,0]-np.roll(q[::2,0],k)+512)%1024-512).sum() for k in range(len(q)//2)]
 k=int(np.argmin(costs));assert sorted(costs)[1]>sorted(costs)[0]+1e-8
 qs=np.roll(q.reshape(-1,2,2),k,axis=0).reshape(-1,2);dy=p[1::2,1]-qs[1::2,1];jc=[]
 for i in range(len(p)//2):
  cp=p.copy();cp[2*i+1,1]=qs[2*i+1,1];jc.append(dict(bottom_index=i,bottom_delta_px=float(dy[i]),**measure(geometry(cp),g)))
 dump(R/'J04_DIAGNOSTIC_RECHECK.json',dict(original=j['scores'],bottom_y_differences=dy,largest_square_share=float(max(dy*dy)/sum(dy*dy)),counterfactuals=jc,used_for_fit=False,source_input_mutated=False))
 def desc(v):return dict(min=float(np.min(v)),median=float(np.median(v)),max=float(np.max(v)),n_ge1=int(sum(abs(np.array(v))>=1)),n_ge5=int(sum(abs(np.array(v))>=5)))
 summary=dict(input_audit=inp,controls=len(controls),control_statuses=dict(Counter(x['status'] for x in controls)),synthetic_subdivision=synth,real_subdivision_records=len(rr),WQ_subdivision_remeasured_records=sum(x['subdivision_WQ_change'] is not None for x in rr),subdivision_IoU_change=desc([x['subdivision_iou3d_change_pp'] for x in rr]),subdivision_WQ_change=desc([x['subdivision_WQ_change'] for x in rr if x['subdivision_WQ_change'] is not None]),height_estimator_sensitivity=desc([x['estimator_difference_pp'] for x in rr]),reference_cells=len(selves),reference_self_WQ=desc([x['scores']['WQ'] for x in selves.values()]),hypotheses_tested_not_assumed=True,no_modified_responses_fitted=True)
 dump(R/'MECHANISM_CHECK_SUMMARY.json',summary);print(json.dumps({k:v for k,v in summary.items() if k!='synthetic_subdivision'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
