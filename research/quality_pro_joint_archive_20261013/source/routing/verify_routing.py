"""Meaningful routing falsification, invariance, and numerical checks.

These are development and synthetic stress tests, not new human labels.
The --out directory is independent of the scientific routing result files.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,math,sys,time
from pathlib import Path
from collections import Counter
import numpy as np
from shapely.geometry import Polygon,Point
from router import prepare_reference_set,route_floor,strict_polygon,floor_metrics,corners
from run_routing import engine,baseline_score,dump,csvout

ROOT=Path(__file__).resolve().parent
def load(p):return json.loads(Path(p).read_text())
def insert(q,eps):
    a=np.asarray(q,float);b=np.roll(a,-1,axis=0);out=[]
    for p,r in zip(a,b):out.extend([p.tolist(),(p+eps*(r-p)).tolist(),(p+(1-eps)*(r-p)).tolist()])
    return out
def support_vector(route):
    return [v[k] for p in route['pairwise_local_evidence'] for v in p['evidence'].values() for k in ['local_support','boundary_support','corner_support'] if v[k] is not None]
def candidate(cid,floor):return {'candidate_id':cid,'floor_xz_h':floor,'admitted_for_routing':True}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--inputs',type=Path,default=ROOT/'inputs/prepared_input.json');ap.add_argument('--results',type=Path,default=ROOT/'results');ap.add_argument('--config',type=Path,default=ROOT/'config.json');ap.add_argument('--baseline',type=Path,default=ROOT.parent/'baseline');ap.add_argument('--out',type=Path,default=ROOT/'validation');ap.add_argument('--quick',action='store_true');a=ap.parse_args();data=load(a.inputs);cfg=load(a.config);routes=load(a.results/'routes.json')['rows'];byroute={r['record_id']:r for r in routes};au,sp,qv,ch,strict,hm=engine(a.baseline)
    refs={im['image_code']:[c for c in im['candidates'] if c['admitted_for_routing']] for im in data['candidate_images']}; prep={k:prepare_reference_set(v,cfg) for k,v in refs.items()};byrec={r['record_id']:r for r in data['records']}
    positives=[];invariance=[];actual=[]
    # Exact legal targets must route to themselves; reference point density is
    # irrelevant. This also validates automatically extracted local regions.
    for code,cc in refs.items():
        for c in cc:
            r=route_floor(c['floor_xz_h'],prep[code]);assert r['candidate_id']==c['candidate_id'],(code,c['candidate_id'],r['candidate_id'])
            positives.append({'image_code':code,'candidate_id':c['candidate_id'],'route':r['candidate_id'],'reason':r['route_reason'],'I':r['candidate_floor_metrics'][c['candidate_id']]['I']})
    print('Exact-reference positives',len(positives),flush=True)
    eligible=[r for r in data['records'] if byroute[r['record_id']]['status']=='available' and len(refs[r['image_code']])>1]
    if a.quick:eligible=eligible[::max(1,len(eligible)//24)]
    for eps in [1e-3,1e-6]:
        refsp={code:prepare_reference_set([{**c,'floor_xz_h':insert(c['floor_xz_h'],eps)} for c in cc],cfg) for code,cc in refs.items()}
        for r in eligible:
            q=np.asarray(r['geometry']['bottom3d'])[:,[0,2]].tolist();base=byroute[r['record_id']]['automatic_without_manual'];vec=np.array(support_vector(base))
            for which,newq,newp in [('annotation_only',insert(q,eps),prep[r['image_code']]),('reference_only',q,refsp[r['image_code']])]:
                v=route_floor(newq,newp);sv=np.array(support_vector(v));delta=float(np.max(np.abs(sv-vec))) if len(vec)==len(sv) and len(vec) else 0.
                invariance.append({'record_id':r['record_id'],'which':which,'epsilon':eps,'original_candidate':base['candidate_id'],'new_candidate':v['candidate_id'],
                    'candidate_equal':v['candidate_id']==base['candidate_id'],'reason_equal':v['route_reason']==base['route_reason'],'max_local_support_difference':delta})
        print('Collinear density tests epsilon',eps,'done',flush=True)
    assert all(r['candidate_equal'] for r in invariance),'point-density route instability'
    assert all(r['reason_equal'] for r in invariance),'point-density route reason instability'
    assert max(r['max_local_support_difference'] for r in invariance)<1e-7,'point-density local support instability'
    # Common rigid rotation and scale should not change the local protocol.
    transform_checks=[];th=.731;rot=np.array([[math.cos(th),-math.sin(th)],[math.sin(th),math.cos(th)]])
    transformed={code:prepare_reference_set([{**c,'floor_xz_h':(np.asarray(c['floor_xz_h'])@rot.T*3.7).tolist()} for c in cc],cfg) for code,cc in refs.items()}
    for r in eligible[::7]:
        q=np.asarray(r['geometry']['bottom3d'])[:,[0,2]]@rot.T*3.7;v=route_floor(q,transformed[r['image_code']]);old=byroute[r['record_id']]['automatic_without_manual']
        transform_checks.append({'record_id':r['record_id'],'same_candidate':v['candidate_id']==old['candidate_id'],'same_reason':v['route_reason']==old['route_reason']})
    assert all(x['same_candidate'] and x['same_reason'] for x in transform_checks),'coordinate-frame routing instability'
    # Controlled geometry examples cannot supply real human quality labels.
    base=[[-2,-2],[2,-2],[2,2],[-2,2]]
    branch=[[-2,-2],[2,-2],[2,-.5],[5,-.5],[5,.5],[2,.5],[2,2],[-2,2]]
    pair=[candidate('large_with_branch',branch),candidate('small_base',base)];pr=prepare_reference_set(pair,cfg)
    controls=[('exact_large',branch),('exact_small',base),('one_distal_corner_missing',branch[:3]+branch[4:]),
        ('one_entry_corner_missing',branch[:2]+branch[3:]),('unapproved_half_size',[[-1,-1],[1,-1],[1,1],[-1,1]]),
        ('diagonal_crossing_extension',[[-2,-2],[2,-2],[5,.5],[2,2],[-2,2]])]
    synthetic=[]
    for name,q in controls:
        p=strict_polygon(q);v=route_floor(q,pr);g={'bottom3d':np.column_stack((np.array(q)[:,0],np.full(len(q),-1),np.array(q)[:,1])).tolist()};D=au.direction_residual(g,au.direction_axis(g));sc={}
        for c in pair:
            qr=np.array(c['floor_xz_h']);rb=np.column_stack((qr[:,0],np.full(len(qr),-1),qr[:,1]));Sb=sp.spherical_sym_distance(g['bottom3d'],rb,2048);I=v['candidate_floor_metrics'][c['candidate_id']]['I'];sc[c['candidate_id']]={'I':I,'Sb_deg':Sb,'D_deg':D,'Q_floor_baseline':baseline_score(I,Sb,D)}
        synthetic.append({'case_id':name,'annotation':q,'references':pair,'route':v,'quality_diagnostic':sc,'real_human_label':False})
    assert synthetic[2]['route']['candidate_id']=='large_with_branch','one missing corner mechanically changed space'
    assert synthetic[3]['route']['candidate_id']=='large_with_branch','one missing entry corner mechanically changed space'
    assert synthetic[4]['quality_diagnostic'][synthetic[4]['route']['candidate_id']]['Q_floor_baseline']<30,'routing wrongly treated tiny drawing as good'
    # Equal area provides no positional or shape information: both options
    # contain the camera and are valid orthogonal polygons with the same area.
    x=[[-4,-1],[1,-1],[1,1],[-4,1]];z=[[-1,-4],[1,-4],[1,1],[-1,1]]
    eq=prepare_reference_set([candidate('A_horizontal',x),candidate('B_vertical',z)],cfg);ev=route_floor(z,eq)
    assert ev['area_only_gap']==0 and ev['candidate_id']=='B_vertical' and ev['area_only_best']=='A_horizontal'
    synthetic.append({'case_id':'equal_area_wrong_location_shape','annotation':z,'references':[candidate('A_horizontal',x),candidate('B_vertical',z)],'route':ev,'real_human_label':False})
    nonidentifiability={'same_observed_floor':base,'latent_history_1':'intentional correct small_base','latent_history_2':'intended large_with_branch, omitted every branch turn',
        'algorithm_observation_identical':True,'actual_route_for_both':route_floor(base,pr)['candidate_id'],
        'self_structure_D_for_both':0.,'impossibility':'Any deterministic geometry-only route sees identical input in both histories; independent intent evidence is required to distinguish them.',
        'new_legal_real_space_added':False,'quality_of_history_2_not_identifiable_from_observation':True}
    # Missing-turn robustness across all candidate polygons. A route change is
    # not automatically an error: omission can produce another exact candidate.
    deletion=[]
    for code,cc in refs.items():
        if len(cc)<2:continue
        for c in cc:
            q=c['floor_xz_h']
            for k in range(len(q)):
                if len(q)<5:continue
                q2=q[:k]+q[k+1:]
                try:p=strict_polygon(q2)
                except ValueError:continue
                if not p.contains(Point(0,0)):continue
                v=route_floor(q2,prep[code]);deletion.append({'image_code':code,'source_candidate':c['candidate_id'],'deleted_index_zero_based':k,'new_candidate':v['candidate_id'],'route_reason':v['route_reason'],
                    'changed':v['candidate_id']!=c['candidate_id'],'is_intent_recovery_test':False})
    print('Single point removal controls',len(deletion),flush=True)
    # Local bands / cues are development choices; sensitivity is not an
    # independently estimated routing accuracy.
    variants=[('distance_015',{'local_distance_scale_over_sqrt_union_area':.015}),('distance_020',{'local_distance_scale_over_sqrt_union_area':.02}),
        ('distance_045',{'local_distance_scale_over_sqrt_union_area':.045}),('distance_060',{'local_distance_scale_over_sqrt_union_area':.06}),
        ('support_045',{'local_min_support':.45}),('support_065',{'local_min_support':.65}),
        ('margin_010',{'local_min_margin':.10}),('margin_030',{'local_min_margin':.30}),
        ('boundary_only',{'local_boundary_weight':1.,'local_corner_weight':0.}),('corner_only',{'local_boundary_weight':0.,'local_corner_weight':1.}),
        ('coverage_unguarded',{'local_exclusive_min_coverage':0.,'local_other_exclusive_max_coverage':1.})]
    sensitivity=[]
    for name,changes in variants:
        cf={**cfg,**changes};pp={code:prepare_reference_set(cc,cf) for code,cc in refs.items()}
        for r in eligible:
            q=np.asarray(r['geometry']['bottom3d'])[:,[0,2]];v=route_floor(q,pp[r['image_code']]);old=byroute[r['record_id']]['automatic_without_manual']
            sensitivity.append({'variant':name,'record_id':r['record_id'],'image_code':r['image_code'],'old_candidate':old['candidate_id'],'new_candidate':v['candidate_id'],
               'old_reason':old['route_reason'],'new_reason':v['route_reason'],'route_changed':v['candidate_id']!=old['candidate_id'],
               'local_single_winner':v['route_reason']=='local_differentiating_structure','candidate_iou_margin':v['survivor_iou_gap']})
        print('Sensitivity',name,'done',flush=True)
    # Compare the actual recalculation against the prior frozen 922 overlap.
    m=load(a.results/'all_candidate_metrics.json')['rows'];mi={(r['record_id'],r['reference_object_id']):r for r in m};frozen=[]
    for r in data['records']:
        c=r['calibration_pool_row']
        if not c:continue
        row=mi.get((r['record_id'],c['reference_object_id']))
        if row is None:continue
        old=c['metrics'];checks={'I':row['I']-old['iou_2d'],'Sb_deg':row['Sb_deg']-old['S_bottom_deg'],'D_deg':row['D_deg']-old['dir']}
        if row['Hm'] is not None:checks.update(Hm=row['Hm']-old['Hmean'],Hc=row['Hc']-old['Hcenter'])
        frozen.append({'record_id':r['record_id'],'metric_differences':checks});assert max(abs(x) for x in checks.values())<1e-7,(r['record_id'],checks)
    # Ceiling/full scores remain unavailable for all newly drawn floors.
    top_pending=[r for r in m if r['top_status']=='top_pending']
    assert all(r['Hm'] is None and r['Hc'] is None and r['IoU3D_corner_mean'] is None and r['Q_full_baseline'] is None for r in top_pending)
    assert len(routes)==429 and sum(r['status']=='unavailable' for r in routes)==12
    assert not any(r.get('selected_candidate_id')=='q9vSo1VnCiC-16:A' for r in routes)
    # Source extraction and original byte preservation checks.
    srcvalid=[]
    for p in (ROOT.parent/'sources/routing').rglob('*.provenance.json'):
        meta=load(p);source=Path(str(p).removesuffix('.provenance.json'));b=source.read_bytes();actual=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest();assert actual==meta['sha'];srcvalid.append({'path':str(source.relative_to(ROOT.parent)),'git_blob_sha':actual,'sha256':hashlib.sha256(b).hexdigest()})
    summary={'exact_legal_reference_tests':len(positives),'exact_legal_reference_failures':0,
        'collinear_invariance_tests':len(invariance),'collinear_route_changes':sum(not r['candidate_equal'] for r in invariance),
        'collinear_reason_changes':sum(not r['reason_equal'] for r in invariance),'maximum_collinear_local_support_change':max(r['max_local_support_difference'] for r in invariance),
        'rotation_and_scale_tests':len(transform_checks),'rigid_scale_route_changes':sum(not r['same_candidate'] for r in transform_checks),
        'single_corner_removal_tests':len(deletion),'single_corner_removal_same_candidate':sum(not r['changed'] for r in deletion),
        'sensitivity_records_per_variant':len(eligible),'sensitivity_summary':{n:{'routes_changed':sum(r['route_changed'] for r in sensitivity if r['variant']==n),'local_single_winners':sum(r['local_single_winner'] for r in sensitivity if r['variant']==n)} for n,_ in variants},
        'frozen_922_overlap_metric_pairs_checked':len(frozen),'full_top_pending_rows_checked':len(top_pending),'source_git_blobs_verified':len(srcvalid),
        'synthetic_controls':len(synthetic),'human_labels_added':0,'human_development_not_independent_validation':True,'quick_mode':a.quick}
    for name,value in [('summary',summary),('reference_self_route',positives),('collinear_invariance',invariance),('rotation_scale_invariance',transform_checks),('synthetic_counterexamples',synthetic),('intent_nonidentifiability',nonidentifiability),('single_corner_removal',deletion),('sensitivity_and_ablation',sensitivity),('frozen_metric_consistency',frozen),('source_git_blob_verification',srcvalid)]:dump(a.out/(name+'.json'),value)
    csvout(a.out/'sensitivity_and_ablation.csv',sensitivity);print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
