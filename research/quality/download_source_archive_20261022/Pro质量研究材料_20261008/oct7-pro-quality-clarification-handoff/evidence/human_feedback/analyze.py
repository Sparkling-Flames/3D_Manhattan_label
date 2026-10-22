"""Read-only analysis of the original review-site data and six parent-supplied human comparisons.
No fitting, source edits, reference edits, or rank changes. Writes audit artifacts only.
"""
import hashlib, json, math
from pathlib import Path
import numpy as np
from scipy.optimize import minimize_scalar
ROOT=Path(__file__).resolve().parent.parent
SRC=Path(__file__).resolve().parent/'inputs/site_numeric_geometry.json'
OUT=Path(__file__).resolve().parent
D=json.loads(SRC.read_text()); S=D['sourceInfo']['scales']; INFO=D['sourceInfo']

def intrinsic_from_site_geometry(a):
    # Same edge-length-weighted own-axis and 512-floor-arclength flat residual
    # algorithms as vendor/geometry.py:139-149 and components_reused.py:52-70.
    f=np.asarray(a['bottom3d'],float)[:,[0,2]]; top=np.asarray(a['top3d'],float)
    e=np.roll(f,-1,axis=0)-f; length=np.linalg.norm(e,axis=1); angles=np.arctan2(e[:,1],e[:,0])
    def objective(theta):
        res=(angles-theta+math.pi/4)%(math.pi/2)-math.pi/4
        return float(np.average(res**2,weights=length))
    grid=np.linspace(0,math.pi/2,181,endpoint=False); best=grid[min(range(len(grid)),key=lambda i:objective(grid[i]))]
    fit=minimize_scalar(objective,bounds=(best-math.pi/180,best+math.pi/180),method='bounded',options={'xatol':1e-12})
    axis=float(fit.x%(math.pi/2)); direction=math.sqrt(objective(axis))*180/math.pi
    cum=np.r_[0.,np.cumsum(length)]; d=(np.arange(512)+.5)*length.sum()/512
    ix=np.minimum(np.searchsorted(cum,d,side='right')-1,len(length)-1); t=(d-cum[ix])/length[ix]
    fq=f[ix]+t[:,None]*e[ix]; h=top[:,1]; observed=h[ix]+t*(np.roll(h,-1)-h)[ix]; rho=np.linalg.norm(fq,axis=1)
    alpha=np.arctan2(observed,rho)
    fit=minimize_scalar(lambda logk:float(np.mean((alpha-np.arctan2(np.exp(logk),rho))**2)),bounds=(-9,9),method='bounded',options={'xatol':1e-10})
    flat=math.sqrt(fit.fun)*180/math.pi
    return direction,flat

def decomposed(m):
    return {'range_loss':1-m['iou'],'weighted_centroid':.5*m['C'],
            'weighted_T':.3*S['L']*m['T']/S['T'],
            'weighted_dir':.3*S['L']*.5*m['dir']/S['dir'],
            'weighted_flat':.3*S['L']*.5*m['flat']/S['flat']}

def getrec(im, rid):
    if im['reference']['id']==rid:
        r=im['reference']; di,fl=intrinsic_from_site_geometry(r)
        # Reference-relative self-comparison terms are exactly zero by identity;
        # intrinsic residuals are recomputed and must NOT be assumed exactly zero.
        m={'iou':1.,'C':0.,'U':0.,'B':0.,'T':0.,'F':0.,'omission':0.,'extension':0.,'dir':di,'flat':fl,'LC':0.,'LCT':0.}
        c=decomposed(m); m['LCG']=c['weighted_dir']+c['weighted_flat']
        return {'id':rid,'kind':'original_reference','worker':None,'metrics':m,'ranks':None,'score_source':'analytic reference self-comparison plus recomputed intrinsic residuals; not a stored site candidate score','pairCount':r['pairCount'],'contributions':c}
    a=next(a for a in im['annotations'] if a['id']==rid)
    return {'id':rid,'kind':'manual_annotation','worker':a['worker'],'metrics':a['metrics'],'ranks':a['ranks'],'score_source':'site data.json','pairCount':a['pairCount'],'renderStatus':a['renderStatus'],'contributions':decomposed(a['metrics'])}

specs=[
('wc2JMjhGNzB-15','R00205','R02740','close_both_acceptable','worker_vs_original_GT',False,'A worker annotation and B original GT both judged acceptable; no strict preference'),
('wc2JMjhGNzB-15','R00205','R00448','close_both_acceptable','worker_vs_worker',False,'Both acceptable, B slightly better in 3D; weak dimension-specific preference only'),
('wc2JMjhGNzB-15','R01204','R01288','A_better','worker_vs_worker',True,'A near GT; B obvious difference, especially 3D'),
('yqstnuAEVhm-34','R01398','R00921','close_both_acceptable','worker_vs_worker',False,'User correction after rechecking GT: B07/R01398 (A) top height is near GT, B02/R00921 (B) is slightly lower; overall close and 3D similar unchanged; no overall A preference inferred'),
('yqstnuAEVhm-34','R02399','R00621','B_slightly_better_corrected_in_chat','worker_vs_worker',True,'Original UI A selection was mistaken; user clarification says B better if forced, small gap; original comment A slightly worse, third bottom point tilts wall; both 3D okay'),
('X7HyMhZNoso-19','R00916','R01646','dimension_tradeoffs','worker_vs_worker',False,'A omits partition like GT and 3D okay but less scene-faithful; B retains reasonable partition with some walls less orthogonal')]
rows=[]
for idx,(code,aid,bid,human,kind,usable,comment) in enumerate(specs,1):
    im=next(im for im in D['images'] if im['code']==code); a=getrec(im,aid);b=getrec(im,bid)
    mA=a['metrics'];mB=b['metrics']; deltas={k:mA[k]-mB[k] if mA[k] is not None and mB[k] is not None else None for k in mA}
    scores={k:{'A':mA[k],'B':mB[k],'A_minus_B':deltas[k],'preferred':'A' if deltas[k]<0 else 'B' if deltas[k]>0 else 'tie','absolute_margin':abs(deltas[k])} for k in ['LC','LCT','LCG']}
    rows.append({'comparison':idx,'image':code,'comparison_kind':kind,'human_label':human,'human_comment':comment,'eligible_for_overall_direction_check':usable,'preference_strength':'clear' if idx==3 else 'weak' if idx==5 else 'dimension_specific_weak' if idx==2 else None,'A':a,'B':b,'metrics_delta_A_minus_B':deltas,'scores':scores,'contribution_delta_A_minus_B':{k:a['contributions'][k]-b['contributions'][k] for k in a['contributions']}})
# Verify formulas and duplicated intrinsic computation against every stored annotation.
formula_diffs=[]; intrinsic_diffs=[]
for im in D['images']:
    for a in im['annotations']:
        m=a['metrics'];c=decomposed(m)
        formula_diffs += [abs(m['LC']-c['range_loss']-c['weighted_centroid']), abs(m['LCT']-m['LC']-c['weighted_T']),abs(m['LCG']-m['LC']-c['weighted_dir']-c['weighted_flat'])]
        di,fl=intrinsic_from_site_geometry(a)
        intrinsic_diffs += [abs(di-m['dir']),abs(fl-m['flat'])]
assert max(formula_diffs)<1e-12,max(formula_diffs)
assert max(intrinsic_diffs)<1e-8,max(intrinsic_diffs)
result={'source':str(SRC.relative_to(ROOT)),'source_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest(),
        'human_provenance':'Six comparisons transcribed by parent task plus chat corrections Sentinel_5286a4dfd04c819197c78eb66623735a and Sentinel_85109639c0b48191ac054e0dccf9ca3c; original raw user export not read or modified by this analysis',
        'rank_blindness':'User explicitly did not view algorithm ranks; export scheme LC is UI state, not endorsement',
        'formulas':INFO['formulas'],'scales':S,'delta_convention':'A minus B; negative favors A for loss metrics and scores; positive favors A for IoU',
        'checks':{'annotations_checked':sum(len(im['annotations']) for im in D['images']),'max_formula_absolute_difference':max(formula_diffs),'max_recomputed_intrinsic_difference':max(intrinsic_diffs),'clear_overall_direction_pairs':1,'agreement_on_clear_pair':{'LC':True,'LCT':True,'LCG':True},'weak_corrected_overall_direction_pairs':1,'agreement_on_weak_corrected_pair':{'LC':False,'LCT':False,'LCG':True},'scientific_validation_or_tuning_performed':False},
        'comparisons':rows,
        'limits':['Three close/both-acceptable judgments do not establish exact score ties or error thresholds.','Original UI/comment conflict resolved by later user chat; raw A selection is retained separately and superseded, not silently changed.','One dimension-tradeoff case has no unambiguous overall winner.','One comparison is worker versus original GT, not two workers.','One clear direction pair plus one weak corrected direction pair is insufficient to estimate predictive accuracy or choose weights.','Reference self-score is derived, not a stored candidate score/rank.','LC/LCT/LCG margins are reported within each formula, not as comparable absolute scores across formulas.','U and B remain unavailable for X7 R01646; never imputed as zero.','No algorithm ranks were shown to the human according to parent task; displayed LC scheme does not endorse LC.']}
result['interpretation_checks']={
 'U_definition':{'source':'oct7-tuning-review/extracted/quality_parameters_20261007/vendor/quality.py:51-83','definition':'Full-circle mean absolute vertical angular discrepancy at equal longitudes, degrees; mean absolute error is unsigned, not a signed wall-height offset or local selected-wall difference.'},
 'T_definition':{'source':'oct7-tuning-review/extracted/quality_parameters_20261007/vendor/components_reused.py:23-50','definition':'Symmetric mean distance from 512 equal-arclength midpoint samples in each direction to the other finite 3D wall-top polyline; nearest segment, no semantic/corner correspondence. Proxy unit h, not metres; depends on reconstructed floor depth and upper rays.'},
 'intrinsic_definitions':{'source':'oct7-tuning-review/extracted/quality_parameters_20261007/vendor/components_reused.py:52-70','definition':'dir is own best orthogonal-axis consistency; flat is fitted own horizontal-top angular residual. Neither is direct truth/GT accuracy.'},
 'yq34_top_height_discrepancy':{'A':'R01398','B':'R00921','U_A':0.7856647868508609,'U_B':3.493271863370456,'T_A':0.0577475419201967,'T_B':0.0922325588006836,'original_human_observation':'B top/height nearer GT, A higher; overall close','human_observation':'After rechecking GT, user says B07/R01398 (A) height is near GT and B02/R00921 (B) is slightly lower; overall close and 3D similar unchanged','status':'resolved_by_user_reinspection','resolved_by_message_id':'Sentinel_85109639c0b48191ac054e0dccf9ca3c','previous_status':'unresolved','previous_unverified_possible_explanation':'Local visual impression or one height dimension can disagree with full-circle MAE and full reconstructed-boundary distance. This was a possibility, not an established explanation, and is no longer needed to explain the corrected observation.','scope':'Resolves the visual U-direction discrepancy; does not establish an overall A winner or validate a formula.'},
 'X7_positive_weights':{'A':'R00916','B':'R01646','loss_components':['1-iou','C','T','dir','flat'],'A_strictly_better_on_every_listed_component':True,'consequence':'Any nonnegative weighted sum using only these components still favors A whenever any weight is positive. Tuning those weights cannot reverse this pair in favor of the retained partition. The current objectives do not explicitly reward scene-faithful partition retention when the reference omits it.'},
 'wc2_weak_3D_preference':{'A':'R00205','B':'R00448','human':'B slightly better 3D, both acceptable','T_A':0.0737935328888352,'T_B':0.086878169374064,'consequence':'T alone prefers A; adding T narrows the baseline B preference. The overall LCT B ordering cannot be cited as evidence that T itself captures the weak 3D preference.'}}
result['comparisons'][3]['human_comment_original']='A top higher; B judged nearer GT height; 3D close; discrepancy with aggregate U/T unresolved'
result['comparisons'][3]['human_correction_history']=[{
 'message_id':'Sentinel_85109639c0b48191ac054e0dccf9ca3c',
 'timestamp_utc':'2026-10-07T11:39:58Z',
 'verbatim':'这是我的判断失误,我重看了gt,确实07 会和gt的高度差不多,反而02是略低的',
 'corrected_dimension':'top height relative to GT',
 'corrected_observation':'B07/R01398 (A) near GT top height; B02/R00921 (B) slightly lower',
 'overall_judgment':'close_both_acceptable; 3D similar; unchanged',
 'overall_A_winner_inferred':False,
 'raw_export_modified':False,
 'calculations_modified':False}]
result['comparisons'][4]['human_correction']={'original_UI_selection':'A better (mistaken click)','corrected_overall_preference':'B slightly better, small gap','message_id':'Sentinel_5286a4dfd04c819197c78eb66623735a','verbatim':'我点错选项了,如果硬要比较,b更好,但是 差的不是很多','raw_export_modified':False}
(OUT/'analysis.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
for r in rows:
    print(r['comparison'],r['image'],r['A']['id'],r['B']['id'],r['human_label'])
    for k,v in r['scores'].items():print(' ',k,round(v['A'],8),round(v['B'],8),v['preferred'],round(v['absolute_margin'],8))
    print(' contribution delta:',{k:round(v,8) for k,v in r['contribution_delta_A_minus_B'].items()})
print('CHECKS',result['checks']);print('REFERENCE',rows[0]['B']['metrics'])
