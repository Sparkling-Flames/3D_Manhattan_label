"""Finite declared grid and analytic affine roots; all events retained."""
import itertools,json,math
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from common import read,save,csvwrite
ROOT=Path(__file__).resolve().parents[1]
THRESHOLDS=[95,85,50,90,75,60]

def root(intercept,slope,level,lo,hi):
    numerator=intercept-level
    if slope==0.0:
        return {'root':None,'root_status':'identical_all_parameters' if numerator==0.0 else 'zero_slope_no_crossing','root_residual':abs(numerator),'left_difference':None,'right_difference':None}
    x=numerator/slope;inside=lo-1e-12<=x<=hi+1e-12;eps=1e-7
    left=max(lo,x-eps) if inside and x>lo else None
    right=min(hi,x+eps) if inside and x<hi else None
    result={'root':x,'root_status':'in_domain' if inside else 'outside_domain','root_residual':abs(intercept-slope*x-level),'left_difference':intercept-slope*left-level if left is not None else None,'right_difference':intercept-slope*right-level if right is not None else None}
    if inside:
        assert result['root_residual']<1e-8
        if left is not None and right is not None:assert result['left_difference']*result['right_difference']<=1e-12
    return result

def main():
    rows=read(ROOT/'results/current_components.json')
    available=[r for r in rows if r['current_Q_status']=='available']
    for r in available:
        r['B']=100*r['iou_2d']/(1+(r['boundary_rms_deg']/4)**2+(r['Hstar']/.5)**2)
        r['G']=.5*(r['direction_bounded_loss']+r['flatness_bounded_loss'])
        assert abs(r['B']*(1-.15*r['G'])-r['Q'])<1e-9
        r['severity_group']='mild_Dle5_Fle2' if r['dir']<=5 and r['flat']<=2 else 'severe_Dge10' if r['dir']>=10 else 'intermediate_or_flatness_dominant'
        r['main_Manhattan_comparison']=r['primary_included'] and r['Manhattan_applicability_group']=='ordinary_scene_supports_Manhattan'
    B=np.array([r['B'] for r in available]);G=np.array([r['G'] for r in available])
    Q=np.array([r['Q'] for r in available]);D=np.array([r['dir'] for r in available]);F=np.array([r['flat'] for r in available])
    families=[{'family':'constant_alpha','domain':[0,.75],'intercept':B,'slope':B*G,'strengths':[0,.15,.3,.45,.6,.75],'scale':None}]
    for start,end,power in itertools.product([5,8,10],[15,20],[1,2]):
        H=(np.clip((D-start)/(end-start),0,1)**power+np.clip((F-.4*start)/(.4*(end-start)),0,1)**power)/2
        families.append({'family':f'new_extra_stage_D{start}_{end}_p{power}','domain':[0,.45],'intercept':Q,'slope':B*H,'strengths':[.15,.3,.45],'scale':{'D_start':start,'D_end':end,'F_start':.4*start,'F_end':.4*end,'power':power}})
    bandroots=[];pairroots=[];flips=[];scores=[];summaries=[];rootcounts=[]
    groups=defaultdict(list)
    for i,r in enumerate(available):groups[r['image_code']].append(i)
    pairs=[(i,j) for ids in groups.values() for i,j in itertools.combinations(ids,2)]
    for family in families:
        intercept,slope=family['intercept'],family['slope'];lo,hi=family['domain'];counts=Counter()
        for i,r in enumerate(available):
            for q in THRESHOLDS:
                rr=root(float(intercept[i]),float(slope[i]),q,lo,hi);counts['band_'+rr['root_status']]+=1
                bandroots.append({'family':family['family'],'record_id':r['record_id'],'image_code':r['image_code'],'worker_id':r['worker_id'],'main_Manhattan_comparison':r['main_Manhattan_comparison'],'primary_included':r['primary_included'],'threshold':q,'threshold_kind':'historical_frozen' if q in [95,85,50] else 'explanatory_candidate_unapproved',**rr})
        for i,j in pairs:
            a,b=available[i],available[j];rr=root(float(intercept[i]-intercept[j]),float(slope[i]-slope[j]),0,lo,hi);counts['pair_'+rr['root_status']]+=1
            pairroots.append({'family':family['family'],'image_code':a['image_code'],'record_1':a['record_id'],'record_2':b['record_id'],'main_Manhattan_pair':a['main_Manhattan_comparison'] and b['main_Manhattan_comparison'],'primary_pair':a['primary_included'] and b['primary_included'],**rr})
        rootcounts.append({'family':family['family'],'scale':family['scale'],'counts':dict(counts),'n_same_image_pairs':len(pairs)})
        for strength in family['strengths']:
            q=intercept-strength*slope;delta=q-Q
            for i,r in enumerate(available):
                scores.append({'family':family['family'],'strength':strength,'record_id':r['record_id'],'image_code':r['image_code'],'Q_candidate':float(q[i]),'Q_v11':r['Q'],'delta_from_v11':float(delta[i]),'primary_included':r['primary_included'],'main_Manhattan_comparison':r['main_Manhattan_comparison'],'severity_group':r['severity_group']})
            flipped=[]
            for i,j in pairs:
                if (Q[i]-Q[j])*(q[i]-q[j]) < -1e-12:
                    a,b=available[i],available[j];rr=root(float(intercept[i]-intercept[j]),float(slope[i]-slope[j]),0,lo,hi)
                    flip={'family':family['family'],'strength':strength,'image_code':a['image_code'],'record_1':a['record_id'],'record_2':b['record_id'],'worker_1':a['worker_id'],'worker_2':b['worker_id'],'Q_v11_1':a['Q'],'Q_v11_2':b['Q'],'Q_candidate_1':float(q[i]),'Q_candidate_2':float(q[j]),'crossing_strength':rr['root'],'main_Manhattan_pair':a['main_Manhattan_comparison'] and b['main_Manhattan_comparison'],'primary_pair':a['primary_included'] and b['primary_included']}
                    flips.append(flip);flipped.append(flip)
            for population,predicate in [('all_mathematical_diagnostic',lambda r:True),('primary_gate_reference_method',lambda r:r['primary_included']),('main_Manhattan_comparison',lambda r:r['main_Manhattan_comparison']),('x8_09_domain_guard',lambda r:r['image_code']=='x8F5xyUWy9e-09')]:
                for group in ['all','mild_Dle5_Fle2','severe_Dge10','intermediate_or_flatness_dominant']:
                    inds=[i for i,r in enumerate(available) if predicate(r) and (group=='all' or r['severity_group']==group)]
                    changed=[i for i in inds if abs(delta[i])>1e-10]
                    cross={str(th):sum((Q[i]>=th)!=(q[i]>=th) for i in inds) for th in THRESHOLDS}
                    def pair_filter(r):
                        return r['main_Manhattan_pair'] if population=='main_Manhattan_comparison' else r['primary_pair'] if population=='primary_gate_reference_method' else r['image_code']=='x8F5xyUWy9e-09' if population=='x8_09_domain_guard' else True
                    relevant=[r for r in flipped if pair_filter(r)] if group=='all' else []
                    summaries.append({'family':family['family'],'strength':strength,'scale':family['scale'],'population':population,'severity_group':group,'n_records':len(inds),'n_changed_records':len(changed),'n_changed_images':len(set(available[i]['image_code'] for i in changed)),'n_changed_workers':len(set(available[i]['worker_id'] for i in changed)),'mean_delta':float(np.mean(delta[inds])) if inds else None,'median_delta':float(np.median(delta[inds])) if inds else None,'min_delta':float(np.min(delta[inds])) if inds else None,'max_delta':float(np.max(delta[inds])) if inds else None,'threshold_crossings':cross,'n_pair_rank_flips':len(relevant) if group=='all' else None,'n_flip_images':len(set(r['image_code'] for r in relevant)) if group=='all' else None,'n_flip_workers':len({r[k] for r in relevant for k in ['worker_1','worker_2']}) if group=='all' else None})
    csvwrite(ROOT/'results/penalty_scores_finite_grid.csv',scores)
    csvwrite(ROOT/'results/penalty_group_summaries.csv',summaries)
    csvwrite(ROOT/'results/band_crossing_roots.csv',bandroots)
    csvwrite(ROOT/'results/same_image_pair_crossing_roots.csv',pairroots)
    csvwrite(ROOT/'results/real_same_image_rank_flips.csv',flips)
    save(ROOT/'results/analytic_root_status_summary.json',rootcounts)
    checks=[root(100,20,95,0,.75)['root']==.25,root(1,0,1,0,.75)['root_status']=='identical_all_parameters',root(1,0,2,0,.75)['root_status']=='zero_slope_no_crossing',root(1,1,3,0,.75)['root_status']=='outside_domain']
    assert all(checks)
    summary={'n_all_events':len(rows),'n_mathematical_available':len(available),'n_primary_available':sum(r['primary_included'] for r in available),'n_main_Manhattan_comparison':sum(r['main_Manhattan_comparison'] for r in available),'finite_variants':sum(len(f['strengths']) for f in families),'family_count':len(families),'scores':len(scores),'same_image_pairs':len(pairs),'band_roots':len(bandroots),'pair_roots':len(pairroots),'rank_flip_rows':len(flips),'root_edge_case_tests_passed':all(checks),'missing_Pro_stage13_stage24':True,'final_formula_or_threshold_selected':False}
    save(ROOT/'results/stage3_summary.json',summary);print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
