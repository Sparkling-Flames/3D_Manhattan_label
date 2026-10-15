"""Independent controls and real-input-derived diagnostic interventions.
Intervened geometries are never written back to inputs or treated as new human labels.
"""
from __future__ import annotations
from collections import defaultdict,Counter
import numpy as np
from core import *
from compare import configurations,csv_dump,quant

NAMES=['current_hill08','historical_tail12_g1','historical_simple8_g1','loss_sum','max_floor','nearest_normal_hill','ray_normal_hill']
CS={n:c for n,c in configurations().items() if n in NAMES}

def geo(p,height=1.6):
    p=np.asarray(p);return dict(bottom3d=np.c_[p[:,0],np.full(len(p),-1.),p[:,1]].tolist(),top3d=np.c_[p[:,0],np.full(len(p),height),p[:,1]].tolist())

def add_measured(output,id,a,g,**meta):
    value=full_measure(a,g)
    row=dict(case_id=id,**meta,**value)
    row['scores']={n:components(value['metrics'],c,value.get('diagnostics')) for n,c in CS.items()} if value['metrics'] else {}
    output.append(row);return row

def align_for_diagnostic(a,g):
    """Use only a unique circular longitude alignment; no main-score point matching.
    Circular shift/reversal belongs to correspondence diagnostics, not preprocessing.
    """
    a=np.asarray(a);g=np.asarray(g)
    if len(a)!=len(g):return None
    x=a.reshape(-1,2,2);y=g.reshape(-1,2,2);trials=[]
    for reverse in [False,True]:
        yy=y[::-1] if reverse else y
        for k in range(len(y)):
            cand=np.roll(yy,k,axis=0);dx=(x[:,1,0]-cand[:,1,0]+512)%1024-512
            trials.append((float(np.sum(dx*dx)),cand,reverse,k))
    trials.sort(key=lambda z:z[0]);v,cand,rev,k=trials[0]
    dx=(x[:,1,0]-cand[:,1,0]+512)%1024-512
    if np.max(abs(dx))>1024/12 or trials[1][0]<max(v*2,v+1.):return None
    return dict(aligned_reference=cand.reshape(-1,2),reference_reversal=rev,reference_shift=k,longitude_cost=v,runnerup_cost=trials[1][0])

def main():
    out=[];square=np.array([[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]])
    # Both family effects and correct L2 definitions; no L1 substitution.
    for angle in [90,75,60,45,30,15,5]:
        t=np.radians(angle);u=np.array([1.,0.]);v=np.array([np.cos(t),np.sin(t)])
        p=np.array([(-u-v)/2,(u-v)/2,(u+v)/2,(-u+v)/2]);a,g=geo(p),geo(square)
        r=add_measured(out,f'rhombus_independent:{angle}',a,g,kind='rhombus',amplitude=90-angle,
            fixed_reference_axis_free_family_RMS=np.sqrt((min(angle,90-angle)**2)/2),
            fixed_reference_axis_locked_family_RMS=(90-angle)/np.sqrt(2),
            free_axis_locked_family_RMS=(90-angle)/2)
        r['independent_IoU_formula']=float(np.sin(t)*(1-np.cos(t)/4)/(1+np.sin(t)*np.cos(t)/4))
        r['independent_D_formula']=min(angle,90-angle)/2
        assert abs(r['metrics']['dir']-r['independent_D_formula'])<1e-8
        assert abs(r['metrics']['iou_2d']-r['independent_IoU_formula'])<1e-8
    # Exact shape preservation, legitimate concave corners, missing branch and
    # an out-of-domain nonorthogonal identity diagnostic (not tuning evidence).
    for scale in [.6,.8,1.,1.2,1.5]:
        add_measured(out,f'homothety:{scale}',geo(square*scale),geo(square),kind='homothety',amplitude=scale,validity_purpose='normal_correspondence_confound_diagnostic')
    for angle in [2,10,20,40]:
        t=np.radians(angle);rot=np.array([[np.cos(t),-np.sin(t)],[np.sin(t),np.cos(t)]])
        add_measured(out,f'rigid_rotation:{angle}',geo(square@rot.T),geo(square),kind='rigid_rotation',amplitude=angle)
    concave=np.array([[-2,-2],[2,-2],[2,1],[.5,1],[.5,3],[-.5,3],[-.5,1],[-2,1]])
    add_measured(out,'concave_identity',geo(concave),geo(concave),kind='concave_identity')
    for width in [.1,.3,.6]:
        ref=np.array([[-2,-2],[2,-2],[2,1],[width/2,1],[width/2,4],[-width/2,4],[-width/2,1],[-2,1]])
        base=np.array([[-2,-2],[2,-2],[2,1],[-2,1]])
        add_measured(out,f'missing_branch:{width}',geo(base),geo(ref),kind='missing_branch',width=width)
    irregular=np.array([[-1,-1],[1,-1],[.8,1],[-.5,1]])
    add_measured(out,'nonorthogonal_identity_domain_only',geo(irregular),geo(irregular),kind='outside_manhattan_domain_diagnostic',used_to_tune=False)
    # Dense bottom controls from original synthetic source points, not substituted top controls.
    bc=read(INPUT/'preparation/BOTTOM_CONTROLS.json')['rows'];dense=[]
    for shape in [(2,2),(1,4)]:
        p=np.array(next(r['reference_points'] for r in bc if r['reference_half_sizes']==list(shape)))
        g=geometry(p)
        for mode in ['single_bottom','distributed_bottom']:
            pattern=np.array([2,0,0,0]) if mode=='single_bottom' else np.array([1,-1,1,-1])
            for sign in [-1,1]:
                for budget in [0,.5,1,2,4,6,8,10,12,14,16,20,24,28]:
                    a=p.copy();a[1::2,1]+=pattern*sign*budget;id=f'dense_{shape[0]}x{shape[1]}:{mode}:{sign}:{budget}'
                    try:r=add_measured(dense,id,geometry(a),g,kind='dense_bottom',shape=list(shape),mode=mode,sign=sign,budget=budget)
                    except ValueError as ex:dense.append(dict(case_id=id,kind='dense_bottom',shape=list(shape),mode=mode,sign=sign,budget=budget,status='unavailable',reason=str(ex)))
    # Path diagnostics derived from ordinary real inputs: fixed x/top y and ring;
    # only bottom y interpolated between matched reference y and observed y.
    # Correspondence is uniquely selected by longitude, not by Q. It is still not
    # a declaration of same semantic target or a new human ordering.
    print('synthetic controls complete',len(out),len(dense),flush=True)
    co=read(INPUT/'data/cohorts.json');oo=read(INPUT/'data/objects.json');objects={o['object_id']:o for o in oo['objects']}
    trajectories=[];excluded=[];matched=[]
    for record_index,r in enumerate(co['ordinary']):
        if record_index%25==0:print('trajectory progress',record_index,flush=True)
        a=np.asarray(objects[r['object_id']]['points_1024x512']);g=np.asarray(objects[r['reference_object_id']]['points_1024x512']);mapping=align_for_diagnostic(a,g)
        if mapping is None:excluded.append(r['record_id']);continue
        ref=mapping.pop('aligned_reference');delta=a[1::2,1]-ref[1::2,1]
        matched.append(dict(record_id=r['record_id'],**mapping))
        for t in [0.,.25,.5,.75,1.,1.25,1.5]:
            p=a.copy();p[1::2,1]=ref[1::2,1]+t*delta
            try:
                ag=geometry(p);gg=geometry(g);m=full_measure(ag,gg,with_diagnostics=False)
                pp=profile(ag)
                trajectories.append(dict(record_id=r['record_id'],image_id=r['image_id'],building_id=r['building_id'],t=t,bottom_y_rms_to_matched_ref=float(np.sqrt(np.mean((t*delta)**2))),
                    status=m['status'],metrics=m['metrics'],profile=pp,scores={n:components(m['metrics'],c) for n,c in CS.items() if c.get('direction_metric','dir')=='dir'} if m['metrics'] else {}))
            except Exception as err:trajectories.append(dict(record_id=r['record_id'],t=t,status='unavailable',error=type(err).__name__+':'+str(err)))
    reversals=[];bins=defaultdict(list)
    for r in trajectories:bins[r['record_id']].append(r)
    for rid,rr in bins.items():
        for a,b in zip(rr,rr[1:]):
            if a['status']!='complete' or b['status']!='complete':continue
            # I and D move in opposite directions as error is increased. Because
            # the starting other coordinates may be wrong, this is NOT a human label.
            if b['metrics']['iou_2d']<a['metrics']['iou_2d']-1e-8 and b['metrics']['dir']<a['metrics']['dir']-1e-8:
                reversals.append(dict(record_id=rid,image_id=b['image_id'],building_id=b['building_id'],t_from=a['t'],t_to=b['t'],I_from=a['metrics']['iou_2d'],I_to=b['metrics']['iou_2d'],D_from=a['metrics']['dir'],D_to=b['metrics']['dir'],
                    score_deltas={n:b['scores'][n]['score']-a['scores'][n]['score'] for n in b['scores']}))
    # J04 single-y intervention in a diagnostic copy; all other coordinates fixed.
    jr=next(r for r in co['ordinary'] if r['record_id']=='R03274');pa=np.asarray(objects[jr['object_id']]['points_1024x512']);pg=np.asarray(objects[jr['reference_object_id']]['points_1024x512']);match=align_for_diagnostic(pa,pg);aligned=match['aligned_reference'];diff=pa-aligned;diff[:,0]=(diff[:,0]+512)%1024-512
    jcases=[]
    for j in range(len(pa)//2):
        cp=pa.copy();cp[2*j+1,1]=aligned[2*j+1,1]
        add_measured(jcases,f'J04_restore_bottom_y_{j+1}',geometry(cp),geometry(pg),kind='diagnostic_single_bottom_y_restoration',original_record='R03274',edited_processed_row_zero_based=2*j+1,delta_y=float(cp[2*j+1,1]-pa[2*j+1,1]),changed_points=1,not_used_as_annotation_or_fit_row=True)
    rd=[]
    for budget in [8,16]:
        row=next(r for r in bc if r['case_id']==f'1x4:distributed_bottom:-1:{budget}');a=geometry(row['points']);g=geometry(row['reference_points']);p=profile(a);p0=profile(g);t=np.array(p['edge_angle_deg']);wg=np.array(p0['weights']);wa=np.array(p['weights']);ax=p0['axis_deg'];res=(t-ax+45)%90-45
        # Known synthetic edge identities, so reference family can be locked.
        target=np.array(p0['edge_angle_deg']);locked=(t-target+180)%360-180
        rd.append(dict(budget=budget,**p,fixed_ref_axis_free_family_actual_weights=float(np.sqrt(wa@(res**2))),fixed_ref_axis_free_family_ref_weights=float(np.sqrt(wg@(res**2))),
           fixed_ref_axis_locked_family_actual_weights=float(np.sqrt(wa@(locked**2))),fixed_ref_axis_locked_family_ref_weights=float(np.sqrt(wg@(locked**2)))))
    dump(ROOT/'results/mechanism_controls.json',dict(records=out,dense_bottom=dense,direction_decomposition=rd))
    dump(ROOT/'results/real_bottom_trajectories.json',dict(criterion='equal_point_count; unique cyclic longitude alignment; max gap 30deg; best/runnerup separated; no Q matching',
        matched=matched,excluded=excluded,records=trajectories,reversal_windows=reversals,independent_human_labels=False,scope_equivalence_not_certified=True))
    dump(ROOT/'results/J04_interventions.json',dict(source_record='R03274',diagnostic_alignment={k:v for k,v in match.items() if k!='aligned_reference'},point_delta_vs_aligned_reference=diff,
        original_points=pa,reference_points=pg,aligned_reference=aligned,records=jcases,source_unchanged=True))
    print('new controls',len(out),'dense',len(dense),'matched ordinary',len(matched),'trajectories',len(trajectories),'I down D down windows',len(reversals),'records',len(set(r['record_id'] for r in reversals)))
    for n in ['historical_tail12_g1','historical_simple8_g1','current_hill08','loss_sum','max_floor']:
        rev=[r for r in reversals if r['score_deltas'][n]>1e-8];print(n,'Q up in I/D counter-response windows',len(rev),'records',len(set(x['record_id'] for x in rev)))
    print('J04 point deltas',diff.tolist())
    print('J04 restorations',[(r['delta_y'],r['metrics']['dir'],r['scores']['current_hill08']['score'],r['scores']['loss_sum']['score']) for r in jcases])
if __name__=='__main__':main()
