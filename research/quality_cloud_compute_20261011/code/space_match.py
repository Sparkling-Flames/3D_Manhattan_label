"""Interpretable fixed-camera floor matches, no rigid or scale registration."""
import argparse, itertools, math, sys, time
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
import shapely
from shapely.geometry import Polygon,LineString,Point
from common import read,save,digest,csvwrite
ROOT=Path(__file__).resolve().parents[1]

def canonical(points):
    p=np.asarray(points,dtype=float);keep=list(range(len(p)));eps=1e-10*max(1,float(np.max(np.abs(p))))
    changed=True
    while changed and len(keep)>3:
        changed=False
        for j,i in enumerate(keep):
            a,b,c=p[keep[j-1]],p[i],p[keep[(j+1)%len(keep)]];v=c-a
            cross=v[0]*(b-a)[1]-v[1]*(b-a)[0]
            if np.linalg.norm(v)>eps and abs(cross)/np.linalg.norm(v)<=eps and np.dot(b-a,b-c)<=eps**2:
                keep.pop(j);changed=True;break
    return p[keep],keep

def ordered_rms(a,b):
    if len(a)!=len(b):return {'corner_rms_h':None,'corner_max_correspondence_h':None,'corner_mapping':None}
    best=None
    for rev in [False,True]:
        ids=np.arange(len(b))[::-1] if rev else np.arange(len(b))
        for s in range(len(b)):
            order=np.roll(ids,s);d=np.linalg.norm(a-b[order],axis=1);value=float(np.sqrt(np.mean(d*d)))
            if best is None or value<best[0]:best=(value,float(d.max()),order.tolist())
    return dict(zip(['corner_rms_h','corner_max_correspondence_h','corner_mapping'],best))

def frechet_once(a,b):
    d=np.linalg.norm(a[:,None,:]-b[None,:,:],axis=2);ca=np.full(d.shape,np.inf)
    for i in range(len(a)):
        for j in range(len(b)):
            prev=min(ca[i-1,j] if i else np.inf,ca[i,j-1] if j else np.inf,ca[i-1,j-1] if i and j else np.inf)
            ca[i,j]=max(d[i,j],prev) if i or j else d[i,j]
    return float(ca[-1,-1])

def cyclic_frechet(a,b):
    best=math.inf;bestmap=None
    # Loop closure is duplicated deliberately; all start pairs are required for representation invariance.
    for rev in [False,True]:
        ids=np.arange(len(b))[::-1] if rev else np.arange(len(b))
        for s in range(len(b)):
            bi=np.roll(ids,s);bb=b[bi];bb=np.vstack([bb,bb[0]])
            for t in range(len(a)):
                aa=np.roll(a,t,axis=0);aa=np.vstack([aa,aa[0]])
                v=frechet_once(aa,bb)
                if v<best:best=v;bestmap={'annotation_start_shift':t,'reference_indices':bi.tolist(),'reverse':rev}
    return {'corner_frechet_h':best,'frechet_start_mapping':bestmap}

def samples(p,n):
    q=np.roll(p,-1,axis=0);v=q-p;l=np.linalg.norm(v,axis=1);c=np.r_[0,np.cumsum(l)];d=(np.arange(n)+.5)*c[-1]/n
    k=np.searchsorted(c,d,side='right')-1;return p[k]+((d-c[k])/l[k])[:,None]*v[k]

def boundary(a,b,n=512):
    la=LineString(np.vstack([a,a[0]]));lb=LineString(np.vstack([b,b[0]]));da=shapely.distance(shapely.points(samples(a,n)),lb);db=shapely.distance(shapely.points(samples(b,n)),la)
    return {'boundary_rms_h':float(np.sqrt((np.mean(da**2)+np.mean(db**2))/2)),'boundary_mean_h':float((da.mean()+db.mean())/2),'boundary_AG_rms_h':float(np.sqrt(np.mean(da**2))),'boundary_GA_rms_h':float(np.sqrt(np.mean(db**2))),'boundary_sample_max_h':float(max(da.max(),db.max())),'boundary_vertex_hausdorff_h':float(la.hausdorff_distance(lb)),'boundary_samples_per_direction':n}

def match(a,b):
    a,ai=canonical(a);b,bi=canonical(b);A=Polygon(a);B=Polygon(b);inter=A.intersection(B).area
    return {'annotation_canonical_indices':ai,'reference_canonical_indices':bi,'annotation_corners':len(a),'reference_corners':len(b),'corner_pairwise_distance_matrix_h':np.linalg.norm(a[:,None,:]-b[None,:,:],axis=2).tolist(),**ordered_rms(a,b),**cyclic_frechet(a,b),**boundary(a,b),'bev_iou':inter/A.union(B).area,'reference_missing_fraction':B.difference(A).area/B.area,'annotation_outside_fraction':A.difference(B).area/A.area,'annotation_symmetric_difference_over_reference':A.symmetric_difference(B).area/B.area}

def project(points):
    if points is None or len(points)<6 or len(points)%2:return None,'invalid_pairs'
    p=np.asarray(points,dtype=float)
    if not np.isfinite(p).all() or np.any(p<0) or np.any(p[:,0]>1024) or np.any(p[:,1]>512):return None,'outside_canvas_or_nonfinite'
    bt=p[1::2];v=(bt[:,1]/512-.5)*np.pi
    if np.any(v<=0) or np.any(v>=np.pi/2):return None,'floor_not_below_horizon'
    u=(bt[:,0]/1024-.5)*2*np.pi;r=1/np.tan(v);xz=np.column_stack([r*np.sin(u),-r*np.cos(u)]);P=Polygon(xz)
    if not P.is_valid or P.area<=0:return None,'invalid_polygon'
    if not P.contains(Point(0,0)):return None,'camera_not_inside'
    return xz,'valid'

def compatibility(vals,absolute,gap):
    """Absolute compatibility and relative preference are independent outputs."""
    within={k:(v<=absolute if v is not None else None) for k,v in vals.items()}
    complete=all(v is not None for v in vals.values())
    if not complete:state='measurement_unavailable'
    elif len(vals)==1:state='only_A_compatible' if within['A'] else 'both_unmatched'
    elif within['A'] and within['B']:state='both_compatible'
    elif within['A']:state='only_A_compatible'
    elif within['B']:state='only_B_compatible'
    else:state='both_unmatched'
    delta=vals['B']-vals['A'] if complete and 'B' in vals else None
    preference=('near_tie' if abs(delta)<=gap else 'A' if delta>0 else 'B') if delta is not None else 'single_target_A' if complete else 'unavailable'
    return {'state':state,'A_within':within.get('A'),'B_within':within.get('B'),'B_present':'B' in vals,'compatible_targets':[k for k,v in within.items() if v is True],'relative_preference':preference,'signed_B_minus_A_h':delta,'relative_margin_h':abs(delta) if delta is not None else None,'unique_target_assignment':None,'actual_intention_inferred':False}

def tests():
    a=np.array([[-2,-1],[2,-1],[2,1],[-2,1]],dtype=float);checks=[];evidence=[]
    def ck(name,condition,detail=None):checks.append({'name':name,'passed':bool(condition),'detail':detail});assert condition,name
    c=compatibility({'A':.10,'B':.20},.25,.02);ck('both_compatible_even_when_A_preferred',c['state']=='both_compatible' and c['relative_preference']=='A' and c['unique_target_assignment'] is None)
    c=compatibility({'A':.20,'B':.26},.25,.10);ck('only_A_compatible_even_when_relative_near_tie',c['state']=='only_A_compatible' and c['relative_preference']=='near_tie')
    c=compatibility({'A':1.,'B':1.1},.25,.02);ck('both_unmatched_despite_A_preferred',c['state']=='both_unmatched' and c['relative_preference']=='A')
    c=compatibility({'A':.1,'B':None},.25,.05);ck('partial_measurement_retains_known_A',c['state']=='measurement_unavailable' and c['A_within'] is True and c['B_within'] is None)
    base=match(a,a)
    for name,b in [('start',np.roll(a,2,axis=0)),('reverse',a[::-1]),('collinear',np.insert(a,1,[0,-1],axis=0))]:
        x=match(a,b);ck(name,max(x[k] for k in ['corner_rms_h','corner_frechet_h','boundary_rms_h'])<1e-9);evidence.append({'case':name,**x})
    b=np.insert(a,1,[0,-.8],axis=0);x=match(a,b);ck('true_corner_add',x['corner_rms_h'] is None and x['corner_frechet_h']>0 and x['boundary_rms_h']>0);ck('corner_remove_symmetric',abs(match(b,a)['corner_frechet_h']-x['corner_frechet_h'])<1e-10);evidence.append({'case':'same_space_small_detail',**x})
    ck('unequal_cyclic_invariance',abs(match(np.roll(a,2,axis=0),np.roll(b,3,axis=0))['corner_frechet_h']-x['corner_frechet_h'])<1e-10)
    for name,b in [('translation',a+[1,0]),('scale',a*1.5),('rotation',a@np.array([[0,-1],[1,0]]))]:
        x=match(a,b);ck('no_'+name+'_alignment',x['boundary_rms_h']>.1);evidence.append({'case':name,**x})
    # Wrapped ERP coordinates describe the same physical seam corner.
    p=[[0,170],[0,400],[256,170],[256,400],[512,170],[512,400],[768,170],[768,400]];q=[row[:] for row in p];q[0][0]=q[1][0]=1024
    pp,ps=project(p);qq,qs=project(q);ck('ERP_seam',ps==qs=='valid' and np.max(np.abs(pp-qq))<1e-12)
    A=np.array([[-3,-1],[1,-1],[1,2],[-3,2.]]);B=np.array([[-1,-2],[3,-2],[3,1],[-1,1.]])
    weird=np.array([[-2.5,-1.5],[2.5,-.5],[2.5,1.5],[-2.5,.5]])
    pa,pb,pw=map(Polygon,[A,B,weird]);ea=pa.difference(pb);eb=pb.difference(pa);ca=pw.intersection(ea).area/ea.area;cb=pw.intersection(eb).area/eb.area
    ck('diagonal_cross_both_exclusive_regions',ca>0 and cb>0);evidence.append({'case':'diagonal_cross_AB','A':match(weird,A),'B':match(weird,B),'exclusive_A_coverage':ca,'exclusive_B_coverage':cb})
    far=a+[15,0];fa,fb=match(far,A),match(far,B);ck('both_unmatched_despite_relative_winner',min(fa['boundary_rms_h'],fb['boundary_rms_h'])>.5);evidence.append({'case':'both_far_relative_winner_not_target','A':fa,'B':fb})
    mid=(a+a*.7)/2;evidence.append({'case':'nested_intermediate','A':match(mid,a),'B':match(mid,a*.7)})
    save(ROOT/'results/space_match_tests.json',{'passed':all(x['passed'] for x in checks),'checks':checks,'counterexamples':evidence});return checks

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--recovered',type=Path);ap.add_argument('--scope-inputs',type=Path,default=ROOT/'inputs/scope');args=ap.parse_args();tests()
    folder=args.recovered/'final_scope_reference_integration/inputs' if args.recovered else args.scope_inputs
    formal=read(folder/'current_formal_subset.json');overlay=read(folder/'normalized_confirmation_overlay.json');cmap={r['image_id']:r for r in overlay['records']};ab={r['image_id']:r for r in read(ROOT/'results/AB_mapping.json')}
    rows=[];wide=[];routing=[];convergence=[];t=time.perf_counter()
    for im in formal['images']:
        c=cmap[im['image_id']];mapping=ab[im['image_id']]
        # No-operation full_gt uses the existing selected GT only, never fabricating a new distinct target.
        A,ast=project((im['selected_gt'] if c['decision']=='full_gt' else im['original_gt'])['points_1024x512']);targets={'A':A}
        if mapping['B_distinct_candidate_enabled']:targets['B']=np.asarray(c['polygon'],dtype=float)
        for ann in im['annotations']:
            a,status=project(ann['points_1024x512']);r={'record_id':ann['record_id'],'object_id':ann['object_id'],'image_id':im['image_id'],'image_code':im['image_code'],'worker_id':ann['worker_id'],'condition':ann['condition'],'cleaning_disposition':ann['cleaning_disposition'],'worker_quality_gate':ann['worker_quality_gate'],'independent_vote_eligible':ann['independent_vote_eligible'],'status':status,'target_count':len(targets),'top_status':'top_pending' if 'B' in targets else 'existing_reference_only','primary_reference_restrictions':mapping['A_restrictions'],'actual_intention_inferred':False}
            out={}
            for tag,g in targets.items():
                result=match(a,g) if a is not None and g is not None else None;out[tag]=result
                rows.append({**r,'target':tag,'target_coordinate_sha256':digest(g.tolist()) if g is not None else None,'target_reference_primary_allowed':mapping['A_reference_primary_allowed'] if tag=='A' else True,'metrics_unavailable_reason':status if a is None else ast if g is None else None,**(result or {})})
            if a is not None and all(x is not None for x in out.values()):
                if 'B' in targets:
                    pa,pb,pann=map(Polygon,[targets['A'],targets['B'],a]);ea=pa.difference(pb);eb=pb.difference(pa)
                    r.update(exclusive_A_area_h2=ea.area,exclusive_B_area_h2=eb.area,exclusive_A_coverage=pann.intersection(ea).area/ea.area if ea.area>1e-12 else None,exclusive_B_coverage=pann.intersection(eb).area/eb.area if eb.area>1e-12 else None,annotation_outside_AB_union_fraction=pann.difference(pa.union(pb)).area/pann.area)
                    r['mixed_geometry_evidence']='both_exclusive_regions_intersected' if ea.area>1e-12 and eb.area>1e-12 and pann.intersection(ea).area>1e-12 and pann.intersection(eb).area>1e-12 else 'nested_or_one_exclusive_region_only'
                for metric in ['corner_rms_h','corner_frechet_h','boundary_rms_h','bev_iou']:
                    for tag,x in out.items():r[tag+'_'+metric]=x[metric]
                    if 'B' in out and all(out[x][metric] is not None for x in ['A','B']):
                        da,db=out['A'][metric],out['B'][metric];r[metric+'_B_minus_A']=db-da;r[metric+'_margin_abs']=abs(db-da);r[metric+'_absolute_best']=max(da,db) if metric=='bev_iou' else min(da,db)
                # Retain candidate states independently; no winning metric or threshold is selected.
                for metric,absolute,gap in itertools.product(['corner_rms_h','corner_frechet_h','boundary_rms_h'],[.1,.25,.5],[.02,.05,.1]):
                    vals={k:v[metric] for k,v in out.items()}
                    routing.append({**r,'distance_metric':metric,'absolute_limit_h':absolute,'relative_gap_h':gap,**compatibility(vals,absolute,gap)})
                if len(convergence)<40:
                    for tag,g in targets.items():
                        check=boundary(canonical(a)[0],canonical(g)[0],1024);convergence.append({'record_id':ann['record_id'],'target':tag,'rms_512':out[tag]['boundary_rms_h'],'rms_1024':check['boundary_rms_h'],'delta':check['boundary_rms_h']-out[tag]['boundary_rms_h']})
            else:
                for metric,absolute,gap in itertools.product(['corner_rms_h','corner_frechet_h','boundary_rms_h'],[.1,.25,.5],[.02,.05,.1]):routing.append({**r,'distance_metric':metric,'absolute_limit_h':absolute,'relative_gap_h':gap,**compatibility({k:None for k in targets},absolute,gap),'measurement_unavailable_reason':status})
            wide.append(r)
        print(im['image_code'],len(im['annotations']),'elapsed',round(time.perf_counter()-t,1),flush=True)
    save(ROOT/'results/target_distance_matrix.json',rows);csvwrite(ROOT/'results/target_distance_matrix.csv',rows);save(ROOT/'results/AB_margins_all_events.json',wide);csvwrite(ROOT/'results/AB_margins_all_events.csv',wide);csvwrite(ROOT/'results/routing_sensitivity.csv',routing);save(ROOT/'results/boundary_sampling_convergence.json',convergence)
    summaries=[]
    for metric,absolute,gap in itertools.product(['corner_rms_h','corner_frechet_h','boundary_rms_h'],[.1,.25,.5],[.02,.05,.1]):
        sel=[r for r in routing if (r['distance_metric'],r['absolute_limit_h'],r['relative_gap_h'])==(metric,absolute,gap)];summaries.append({'metric':metric,'absolute_limit_h':absolute,'relative_gap_h':gap,'n_all_events':len(sel),'states':dict(Counter(r['state'] for r in sel)),'n_workers_all_events':len(set(r['worker_id'] for r in sel))})
    csvwrite(ROOT/'results/routing_sensitivity_summary.csv',summaries)
    workers=[]
    for w in sorted(set(r['worker_id'] for r in wide)):
        rs=[r for r in wide if r['worker_id']==w];workers.append({'worker_id':w,'n_all_events':len(rs),'n_geometrically_valid':sum(r['status']=='valid' for r in rs),'n_unavailable':sum(r['status']!='valid' for r in rs),'event_ids':[r['record_id'] for r in rs],'quality_or_skill_inferred':False})
    csvwrite(ROOT/'results/person_event_denominators.csv',workers);summary={'all_events':len(wide),'valid_floor':sum(r['status']=='valid' for r in wide),'unavailable_floor':sum(r['status']!='valid' for r in wide),'target_distance_rows':len(rows),'sensitivity_rows':len(routing),'no_final_threshold_selected':True,'elapsed_seconds':time.perf_counter()-t};save(ROOT/'results/stage2_summary.json',summary);print(summary)
if __name__=='__main__':main()
