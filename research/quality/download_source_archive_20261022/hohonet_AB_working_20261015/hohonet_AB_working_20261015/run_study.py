from __future__ import annotations
import argparse,json,sys,itertools,math
from dataclasses import asdict,replace
from pathlib import Path
import numpy as np,pandas as pd
from scipy.stats import spearmanr
from shapely.geometry import Polygon,Point
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from working_models import Parameters,WQ,A,B,MODELS,score,floor_upper_bound,attribution
from native_geometry import project,erp_triples,direction,iou,bottom_distance,height_components,prism_iou

KEYS=['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']
TWO=['B6ByNegPMKs-37','UwV83HsGsw3-10']
GRADE={'poor':0,'average_poor':1,'average':2,'good_average':3,'good':4}

def dump(p,x):
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def write(p,rows):pd.DataFrame(rows).to_csv(p,index=False)

def values(d):return [d[k].to_numpy(float) for k in KEYS]

def attach(d,models=MODELS):
    d=d.copy();mask=d[KEYS].notna().all(axis=1)
    for name,par in models.items():
        d['Q_'+name]=np.nan;d.loc[mask,'Q_'+name]=score(*values(d.loc[mask]),par)
    if 'IoU3D100' in d:d['Q_IoU3D']=d.IoU3D100
    return d

def groups(d):
    d=d.copy();d['new_two_image_hold']=d.image_code.isin(TWO)
    d['comparison_layer']=np.select([
        d.new_two_image_hold,
        d.role.eq('manual_development_candidate')&~d.latest_step_reference_pending&~d.same_target_quality_hold,
        d.role.eq('manual_development_candidate'),d.role.eq('semi_secondary_candidate'),
        d.role.eq('severe_exception_candidate'),d.stage.eq('doorway')&~d.same_target_quality_hold,
        d.stage.eq('doorway')],['two_image_scope_diagnostic','ordinary_manual_conditional',
        'ordinary_target_hold','semi_secondary','severe_exception','doorway_conditional','doorway_target_hold'],default='historical_diagnostic')
    return d

def human(inp):
    # Binding source retained exactly; use original receipts rather than old derived grades.
    d=pd.read_csv(inp/'selection_provenance.csv')
    cards=json.loads((inp/'coarse_manifest.json').read_text(encoding='utf-8'))['cards']
    receipts=json.loads((inp/'human_receipt_44.json').read_text(encoding='utf-8'))['decisions']
    rows=[]
    for c in cards:
        b=c['bindings'][0];r=receipts[c['id']];z=d[d.record_id.eq(b['record_id'])].iloc[0].to_dict()
        assert z['object_id']==b['object_id'] and z['reference_id']==b['reference_object_id']
        z.update(card_id=c['id'],grade=r['grade'],grade_order=GRADE.get(r['grade'],np.nan),
                 human_comment=r.get('comment',''),exposed_here=bool(r.get('score_revealed_at')),blind_validation=False)
        rows.append(z)
    return pd.DataFrame(rows)

def ordinal_order(q,h):
    g=h.grade_order.to_numpy();a,b=np.triu_indices(len(h),1);delta=g[a]-g[b]
    valid=np.isfinite(delta)&(delta!=0);wrong=(q[a]-q[b])*delta < -1e-8
    return dict(comparisons=int(valid.sum()),opposite=int((wrong&valid).sum()),
                nonadjacent_comparisons=int((valid&(abs(delta)>=2)).sum()),
                nonadjacent_opposite=int((wrong&valid&(abs(delta)>=2)).sum()))

def measure(c,n=2048):
    a=np.array(c['a'],float);g=np.array(c['g'],float);ah=np.array(c['ah'],float);gh=np.array(c['gh'],float)
    hm,hc=height_components(a,ah,g,gh,4096)
    return dict(case=c['case'],family=c['family'],amplitude=c.get('amplitude'),
          iou_2d=iou(a,g),S_bottom_deg=bottom_distance(a,g,n),dir=direction(a),Hmean=hm,Hcenter=hc,
          IoU3D100=100*prism_iou(a,ah,g,gh),reference_D=direction(g),
          physical_camera_below_all_top=bool(min(ah)>1 and min(gh)>1),
          camera_strictly_inside_candidate=Polygon(a).contains(Point(0,0)),
          camera_strictly_inside_reference=Polygon(g).contains(Point(0,0)))

def geometric_study(inp,out):
    controls=json.loads((inp/'synthetic_geometries.json').read_text(encoding='utf-8'))
    base=np.array([[-2.,-2.],[2.,-2.],[2.,2.],[-2.,2.]])
    # Independent versus common mechanisms are labelled constructions, not identified in humans.
    for s in [0.,.025,.05,.1,.2,.4]:
        for shift in [0.,.1,.3,.6]:
            a=base.copy();a[:,0]+=s*a[:,1];a[:,0]+=shift
            controls.append(dict(case=f'factorial_s{s}_t{shift}',family='shear_translation_factorial',amplitude=s,
                a=a.tolist(),g=base.tolist(),ah=[2.4]*4,gh=[2.4]*4))
    controls.append(dict(case='concave_L_self',family='invariance',amplitude=None,
         a=[[-2,-2],[2,-2],[2,.5],[.5,.5],[.5,2],[-2,2]],g=[[-2,-2],[2,-2],[2,.5],[.5,.5],[.5,2],[-2,2]],ah=[2.4]*6,gh=[2.4]*6))
    rows=[measure(c) for c in controls]
    x=attach(pd.DataFrame(rows));x.to_csv(out/'geometric_controls.csv',index=False)
    dump(out/'executed_control_geometries.json',controls)
    return x

def calibration(h,controls,out):
    # Ordinary-only coarse study. Review is exposed and partly stress-selected.
    train=h[h.phase.eq('ordinary')&~h.card_id.isin(['N05','N28'])&h.grade_order.notna()].copy()
    pars=[]
    for c in [math.sqrt(37.5),8.,10.,12.]:
        for bottom in [32.,48.,64.]:pars.append(('A',Parameters(f'A_c{c:g}_b{bottom:g}',c,bottom_scale_squared_deg2=bottom)))
        for p in [1.25,1.5,2.,3.]:pars.append(('B',Parameters(f'B_c{c:g}_p{p:g}',c,pooling_order=p)))
    rows=[];anchor_cases=['shear_0.05','shear_0.1','shear_0.2','rhombus_45','rhombus_1']
    for route,p in pars:
        r=dict(route=route,**asdict(p),**ordinal_order(score(*values(train),p),train))
        strict=train[~train.card_id.isin(['N08','N20'])]
        r.update({'strict_scope_'+k:v for k,v in ordinal_order(score(*values(strict),p),strict).items()})
        for case in anchor_cases:
            z=controls[controls.case.eq(case)];r[case]=float(score(*values(z),p)[0])
        for v in [1.,2.,3.,5.,10.,20.]:r[f'D_only_{v:g}']=float(score(1,0,v,0,0,p))
        r['fourfold_height']=float(score(1,0,0,3,0,p))
        r['working_selected']=(route=='A' and p.direction_scale_deg==10 and p.bottom_scale_squared_deg2==32) or (route=='B' and p.direction_scale_deg==8 and p.pooling_order==2)
        rows.append(r)
    write(out/'ordinary_coarse_grid_28.csv',rows)
    # Chosen by explicit response trade-off, not a claimed unique optimizer.
    decisions={
      'selection_kind':'documented_multiobjective_working_choice_not_unique_optimizer',
      'no_per_case_numeric_targets':True,'human_data':'30 exposed ordinary development cards; 28-card scope-comment sensitivity',
      'ordinary_complete_before_doorway':True,
      'A':asdict(A),'B':asdict(B),
      'A_reason':'Broaden D Hill scale to 10 degrees; 5.71-degree true-angle shear rises from 75.45 to 85.42. Keep Sb unchanged: weakening it can reward omitted details. Retain large-error guard and height response. Zero nonadjacent reversals on the 30-card exposed diagnostic is supporting, not validation.',
      'B_reason':'Use Euclidean pooling between the entire floor-fidelity block O+Sb^2/32 and direction, not among every term. Scale 8 with p=2 combines a milder small-error response and a 29.3% balanced-block loss discount without a hard max plateau. p=3 suppresses secondary errors more; p=1.5 discounts less. No claim that p=2 was statistically estimated or uniquely optimal.',
      'unchanged_fields':['bottom_scale_squared_deg2','direction_cap','global_height_scale','local_height_scale'],
      'unresolved':['D is intrinsic rather than reference-angle error','no causal same-error detector','legitimate nonorthogonal reference self-score remains below 100','missing structure can be underweighted']}
    dump(out/'ORDINARY_FROZEN_WORKING.json',decisions)
    assert (out/'ORDINARY_FROZEN_WORKING.json').exists()
    # Stage 2: weak doorway transfer / local perturbation. No target for low scores.
    door=h[h.phase.eq('doorway')&h.grade_order.notna()&~h.same_target_quality_hold]
    stage=[]
    for route,pp in [('A',A),('B',B)]:
        probes=[replace(pp,version=pp.version+'_door_probe',direction_scale_deg=c,pooling_order=p)
                for c in [pp.direction_scale_deg-1,pp.direction_scale_deg,pp.direction_scale_deg+1]
                for p in ([1.] if route=='A' else [1.5,2.,2.5])]
        ref=score(*values(train),pp)
        for pr in probes:
            stage.append(dict(route=route,**asdict(pr),**ordinal_order(score(*values(door),pr),door),
                n_doorway=len(door),normal_mean_change=float(np.mean(score(*values(train),pr)-ref)),
                normal_max_abs_change=float(np.max(abs(score(*values(train),pr)-ref))),
                adopted_change=False))
    write(out/'doorway_fine_checks.csv',stage)
    dump(out/'DOORWAY_FINAL_WORKING.json',dict(A=asdict(A),B=asdict(B),changed=False,
        decision='Keep both ordinary working versions: weak/mixed-scope doorway feedback does not establish a systematic correction warranting domain-specific tuning. Probes and normal regression retained. No low-doorway-score objective.'))
    return train

def pairwise(d,out):
    o=d[d.comparison_layer.eq('ordinary_manual_conditional')]
    sums=[];changed=[]
    for model in ['A10','B8L2','IoU3D']:
        n=inv=large=tie=0
        for _,sub in o.groupby(['image_id','reference_id','condition']):
            for a,b in itertools.combinations(sub.to_dict('records'),2):
                if a['worker_id']==b['worker_id']:continue
                x=a['Q_WQ']-b['Q_WQ'];y=a['Q_'+model]-b['Q_'+model]
                if abs(x)<1e-10 and abs(y)<1e-10:tie+=1;continue
                n+=1
                if x*y < -1e-9:
                    inv+=1;large+=int(abs(x)>=5 and abs(y)>=5)
                    changed.append(dict(model=model,image_id=a['image_id'],image_code=a['image_code'],reference_id=a['reference_id'],
                      record_a=a['record_id'],record_b=b['record_id'],baseline_gap=x,candidate_gap=y,
                      min_abs_gap=min(abs(x),abs(y)),human_preference_known=False))
        sums.append(dict(model=model,n_non_both_tied_pairs=n,both_tied=tie,opposite=inv,both_gaps_ge5=large))
    write(out/'same_cell_pairwise_summary.csv',sums);write(out/'same_cell_reversals.csv',changed)
    # Matched component contexts, NOT a claim of conditional causal identification.
    near=[]
    for _,sub in o.groupby(['image_id','reference_id','condition']):
        for a,b in itertools.combinations(sub.to_dict('records'),2):
            if a['worker_id']==b['worker_id']:continue
            if abs(a['iou_2d']-b['iou_2d'])<=.02 and abs(a['S_bottom_deg']-b['S_bottom_deg'])<=.5 and abs(a['Hmean']-b['Hmean'])<=.03 and abs(a['Hcenter']-b['Hcenter'])<=.02 and abs(a['dir']-b['dir'])>=2:
                near.append(dict(image_id=a['image_id'],reference_id=a['reference_id'],record_a=a['record_id'],record_b=b['record_id'],
                     I_difference=a['iou_2d']-b['iou_2d'],Sb_difference=a['S_bottom_deg']-b['S_bottom_deg'],D_difference=a['dir']-b['dir'],
                     **{m+'_gap':a['Q_'+m]-b['Q_'+m] for m in ['WQ','A10','B8L2','IoU3D']}))
    write(out/'matched_context_pairs.csv',near)
    return sums

def workers(d,out):
    o=d[d.comparison_layer.eq('ordinary_manual_conditional')&d.personnel_barriers.eq('[]')&d.context_barriers.eq('[]')&~d.original_holdout].copy()
    metrics=['Q_WQ','Q_A10','Q_B8L2','Q_IoU3D'];o['cell']=o.image_id+'|'+o.reference_id+'|'+o.condition
    cells=o.groupby(['worker_id','cell','building_id'],as_index=False)[metrics].mean()
    for m in metrics:cells['centered_'+m]=cells[m]-cells.groupby('cell')[m].transform('mean')
    counts=cells.groupby('worker_id').cell.nunique();workers=counts[counts>=5].index
    w=cells[cells.worker_id.isin(workers)].groupby('worker_id')[['centered_'+m for m in metrics]].mean();w['n_cells']=counts
    for m in metrics:
        w['rank_'+m]=w['centered_'+m].rank(ascending=False,method='average')
        # Existing exploratory relative tercile sensitivity, NOT human grades or fixed quota allocation.
        w['relative_tercile_'+m]=pd.cut((w['rank_'+m]-1)/len(w),[-.01,1/3,2/3,1.01],labels=['upper','middle','lower'])
    common=(cells[cells.worker_id.isin(workers)].groupby('cell').worker_id.nunique()==len(w)).sum()
    rows=[]
    for m in metrics:
        rows.append(dict(metric=m,n_workers=len(w),n_rows=len(o),n_cells=cells.cell.nunique(),all_worker_common_cells=int(common),
           rank_correlation=spearmanr(w.rank_Q_WQ,w['rank_'+m]).statistic,
           maximum_rank_change=float(abs(w.rank_Q_WQ-w['rank_'+m]).max()),
           relative_tercile_changes=int((w.relative_tercile_Q_WQ!=w['relative_tercile_'+m]).sum()),
           formal_classification_changed=False))
    w.to_csv(out/'worker_profiles.csv');cells.to_csv(out/'worker_cell_scores.csv',index=False);write(out/'worker_sensitivity.csv',rows)
    # Leave-target-building selection diagnostic uses only observed historical pool,
    # not future-worker prediction. Scores frozen; no ref is chosen for high score.
    selection=[]
    for target,cell in o.groupby('cell'):
        building=cell.building_id.iloc[0];train=cells[cells.building_id.ne(building)].copy()
        for m in metrics:train['ctr_'+m]=train[m]-train.groupby('cell')[m].transform('mean')
        n=train.groupby('worker_id').cell.nunique();eligible=n[n>=5].index.intersection(cell.worker_id.unique())
        if len(eligible)<5:continue
        ranking=train[train.worker_id.isin(eligible)].groupby('worker_id')[['ctr_'+m for m in metrics]].mean()
        observed=cell.groupby('worker_id')[metrics].mean()
        for k in [1,3,5]:
            teams={m:ranking.sort_values(['ctr_'+m],ascending=False,kind='stable').head(k).index.tolist() for m in metrics}
            for m in metrics:
                selection.append(dict(target_cell=target,building_id=building,selection_metric=m,k=k,n_available=len(eligible),
                    selected=json.dumps(teams[m]),same_team_as_WQ=set(teams[m])==set(teams['Q_WQ']),
                    **{'selected_mean_'+q:float(observed.loc[teams[m],q].mean()) for q in metrics},
                    target_building_excluded=True,refused_interpretation='This is selected-individual mean; not fusion or validated policy benefit'))
    write(out/'leave_building_selection_diagnostic.csv',selection)
    return rows

def fusion(d,inp,out):
    f=attach(pd.read_csv(inp/'FUSION_220_SCORES.csv'))
    holds=d[d.latest_step_reference_pending|d.same_target_quality_hold|d.new_two_image_hold]
    bad=set(zip(holds.image_id,holds.reference_id))
    f['joined_current_target_hold']=[(r.image_id,r.reference_id) in bad for r in f.itertuples()]
    f['analysis_allowed']=f.status.eq('complete')&f.stage.eq('ordinary')&f.member_restrictions.eq('[]')&f.holdout_members.eq('[]')&~f.joined_current_target_hold
    f['operation']='fixed_endpoint_rescoring_no_reselection_or_refusion'
    f.to_csv(out/'fusion_220_rescored.csv',index=False)
    rows=[]
    for (im,ref),z in f[f.analysis_allowed].groupby(['image_id','reference_id']):
        if len(z)!=2:continue
        z=z.sort_values('version')
        for m in ['Q_WQ','Q_A10','Q_B8L2','Q_IoU3D']:
            rows.append(dict(image_id=im,reference_id=ref,first_version=z.version.iloc[0],second_version=z.version.iloc[1],
               metric=m,second_minus_first=float(z[m].iloc[1]-z[m].iloc[0])))
    write(out/'fusion_matched_endpoint_differences.csv',rows)
    return dict(total=len(f),complete=int(f.status.eq('complete').sum()),current_conservative_complete=int(f.analysis_allowed.sum()),
                matched_two_version_units=len(rows)//4,new_fusions_computed=0)

def two_image(inp,out):
    data=json.loads((inp/'CURRENT_TWO_IMAGE_MINIMAL_38.json').read_text(encoding='utf-8'));print('twoimage schema',type(data))
    objs=data['objects'] if isinstance(data,dict) else data
    if isinstance(objs,dict):objs=list(objs.values())
    delta=json.loads((inp/'TWO_IMAGE_SCOPE_DELTA.json').read_text(encoding='utf-8'))
    # This stage is completed in run_two_images.py, preserving source reference contract.
    return objs,delta

def main(inp,out):
    if out.exists() and any(out.iterdir()):raise ValueError('output must be new or empty')
    out.mkdir(parents=True,exist_ok=True)
    d=groups(attach(pd.read_csv(inp/'JOINT_COMPARISON_1145.csv')))
    assert len(d)==1145 and d.record_id.is_unique
    err=float(abs(d.Q_WQ-d.WQ).max());assert err<1e-9
    assert (~d.formal_eligibility_newly_granted).all()
    h=attach(human(inp));controls=geometric_study(inp,out);train=calibration(h,controls,out)
    d['production_default_changed']=False;d.to_csv(out/'SCORES_1145.csv',index=False)
    h.to_csv(out/'HUMAN44_AB_COMPARISON.csv',index=False)
    descript=[]
    for layer,g in d.groupby('comparison_layer'):
        for m in ['Q_WQ','Q_A10','Q_B8L2','Q_IoU3D']:
            descript.append(dict(layer=layer,metric=m,n=len(g),n_images=g.image_id.nunique(),mean=g[m].mean(),median=g[m].median(),
             minimum=g[m].min(),maximum=g[m].max(),mean_change_vs_WQ=(g[m]-g.Q_WQ).mean(),
             rho=spearmanr(g.Q_WQ,g[m]).statistic if len(g)>2 else np.nan))
    write(out/'layer_summaries.csv',descript)
    attrib=[]
    for r in d.itertuples():
        for m,p in MODELS.items():
            x=[getattr(r,k) for k in KEYS]
            attrib.append(dict(record_id=r.record_id,object_id=r.object_id,reference_id=r.reference_id,model=m,**attribution(*x,p)))
    write(out/'NONLINEAR_ATTRIBUTIONS.csv',attrib)
    rev=pairwise(d,out);ws=workers(d,out);fs=fusion(d,inp,out)
    # Frozen ordinary grade readouts are optional, never used to choose geometric params.
    from ordinal import fit,predict,median_grade,loss_stats
    ordres=[];ordpred=[];cal={}
    for m in ['Q_WQ','Q_A10','Q_B8L2','Q_IoU3D']:
        tr=train;weight=1/tr.groupby('image_id').record_id.transform('size').to_numpy()
        ff=fit(tr[m],tr.grade_order,weight);cal[m]=ff
        for groupcol in ['image_id','building_id']:
            allp=np.zeros((len(tr),5))
            for g in tr[groupcol].unique():
                test=tr[groupcol].eq(g).to_numpy();other=tr[~test];ww=1/other.groupby('image_id').record_id.transform('size').to_numpy()
                ffit=fit(other[m],other.grade_order,ww);pp=predict(ffit,tr.loc[test,m]);allp[test]=pp
            ordres.append(dict(metric=m,split='leave_'+groupcol+'_exposed_development',**loss_stats(allp,tr.grade_order)))
        ordres.append(dict(metric=m,split='ordinary_resubstitution',**loss_stats(predict(ff,tr[m]),tr.grade_order)))
        for r,pp in zip(h.to_dict('records'),predict(ff,h[m])):
            ordpred.append(dict(record_id=r['record_id'],card_id=r['card_id'],metric=m,grade_order=r['grade_order'],
                diagnostic_median=int(np.sum(np.cumsum(pp)<.5)),**{f'diagnostic_p{i}':p for i,p in enumerate(pp)}))
    write(out/'OPTIONAL_ordinal_sensitivity.csv',ordres);write(out/'OPTIONAL_grade_readouts_44.csv',ordpred)
    dump(out/'OPTIONAL_grade_config_not_frozen_standard.json',cal)
    dump(out/'EXECUTION.json',dict(main_commit='e3dcf9d11daf9390d6acc09974101f7b6b88a3dd',
       score_rows=len(d),baseline_max_error=err,coarse_grid_candidates=28,calibration_cards=len(train),
       geometric_controls=len(controls),new_blind_human_reviews=0,full_loader_run=False,full_library_geometry_remeasured=False,
       original_images_read=0,selected_A=asdict(A),selected_B=asdict(B),fusion=fs,
       layer_counts={k:int(v) for k,v in d.comparison_layer.value_counts().items()},
       underlying_frozen_component_reuse=True,default_changed=False))
    print('SUCCESS',err,fs)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,default=ROOT/'inputs');p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();main(a.input,a.output)
