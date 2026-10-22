#!/usr/bin/env python3
"""Reproduce the mechanism study from immutable, readable supplied artifacts.
Usage: python run_study.py --output results-new
Does not access a network or replace source references / eligibility.
"""
from __future__ import annotations
import argparse,itertools,json,math,sys,platform
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'inputs/prior_runtime/src'))
from mechanisms import MODELS,Model,MODEL_MAP,LAMBDA,pool,score,terms,from_frame
from native_geometry import polygon,project,erp_triples,iou,bottom_distance,direction,height_components,prism_iou,angles
from geometry_candidates import corner_metrics,boundary_coverage,axis_details

GRADES={'poor':0,'average_poor':1,'average':2,'good_average':3,'good':4}
MAIN_MODELS=['WQ','A10','S8','B8L2','C8_anchor_matched','P1.5','P3','MAX8','MIN_SHARE25','IoU3D100']
SCOPE_CASES={'N09':'explicit_adjacent_space_and_geometry_comment',
 'N11':'explicit_behind_door_scope_and_geometry_comment',
 'D02':'explicit_scope_interpretation_primary_comment',
 'D05':'explicit_doorway_scope_omission_comment'}

def dump(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def csv(path,rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 (rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)).to_csv(path,index=False,float_format='%.16g')

def scored(frame):
 out=frame.copy()
 for m in MODELS:out[m.name]=from_frame(frame,m)
 t=terms(*[frame[k].to_numpy(float) for k in ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']],8.)
 for k,v in t.items():out['loss_'+k]=v
 f,d,h=t['F'],t['d'],t['H']
 out['balancedness_min_over_max']=np.divide(np.minimum(f,d),np.maximum(f,d),out=np.zeros_like(f),where=np.maximum(f,d)>0)
 out['pooled_loss_B']=np.hypot(f,d)
 out['loss_credit_vs_S8']=f+d-np.hypot(f,d)
 out['loss_credit_fraction_vs_S8']=np.divide(out.loss_credit_vs_S8,f+d,out=np.zeros_like(f),where=f+d>0)
 out['Q_gain_pool_only_at_c8']=out.B8L2-out.S8
 out['Q_gain_scale_only_from_WQ']=out.S8-out.WQ
 out['Q_scale_pool_interaction']=out.B8L2-out.S8-out.POOL_OLD+out.WQ
 out['Q_gain_scale_shapley']=.5*((out.S8-out.WQ)+(out.B8L2-out.POOL_OLD))
 out['Q_gain_pool_shapley']=.5*((out.POOL_OLD-out.WQ)+(out.B8L2-out.S8))
 for name in ['WQ','A10','S8','B8L2','C8_anchor_matched']:
  vals=[frame[k].to_numpy(float) for k in ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']]
  for label,indices in [('direction',[2]),('global_height',[3]),('local_height',[4]),('all_height',[3,4])]:
   inputs=vals.copy()
   for i in indices:inputs[i]=np.zeros_like(inputs[i])
   out[f'{name}_delete_{label}_gain']=score(*inputs,name)-out[name]
 r=np.hypot(f,d)
 dd=np.divide(3*frame['dir'].to_numpy(float)*64,(frame['dir'].to_numpy(float)**2+64)**2)
 out['abs_S8_derivative_Q_per_Ddeg']=100*dd/(1+f+d+h)**2
 out['abs_B_derivative_Q_per_Ddeg']=100*np.divide(d,r,out=np.zeros_like(d),where=r>0)*dd/(1+r+h)**2
 out['abs_S8_derivative_Q_per_Hloss']=100/(1+f+d+h)**2
 out['abs_B_derivative_Q_per_Hloss']=100/(1+r+h)**2
 out['B_direction_local_slope_stronger_than_S8']=out.abs_B_derivative_Q_per_Ddeg>out.abs_S8_derivative_Q_per_Ddeg+1e-10
 return out

def order_desc(frame,grade_col,models):
 v=frame[grade_col].map(GRADES);idx=np.where(v.notna())[0];out=[]
 for model in models:
  usable=frame.iloc[idx];g=v.iloc[idx].to_numpy(float);q=usable[model].to_numpy(float)
  pairs=[]
  for i,j in itertools.combinations(range(len(usable)),2):
   if g[i]==g[j]:continue
   gap=abs(g[i]-g[j]);sgn=(q[i]-q[j])*(g[i]-g[j]);pairs.append((gap,sgn))
  p=np.asarray(pairs) if pairs else np.empty((0,2))
  severe=p[:,0]>=2 if len(p) else np.array([],bool)
  out.append(dict(model=model,n=len(usable),unequal_grade_pairs=len(p),inversions=int(np.sum(p[:,1]<-1e-9)),score_ties=int(np.sum(np.abs(p[:,1])<=1e-9)),nonadjacent_grade_pairs=int(severe.sum()),nonadjacent_inversions=int(np.sum(p[severe,1]<-1e-9)),description='dependent_pairs_of_exposed_qualitative_grades_not_error_rate'))
 return out

def measure(a,ah,g,gh):
 a=np.asarray(a,float);g=np.asarray(g,float);ah=np.asarray(ah,float);gh=np.asarray(gh,float)
 polygon(a);polygon(g)
 hm,hc=height_components(a,ah,g,gh,4096)
 return dict(iou_2d=iou(a,g),S_bottom_deg=bottom_distance(a,g,2048),dir=direction(a),Hmean=hm,Hcenter=hc,IoU3D100=100*prism_iou(a,ah,g,gh))

def main(out):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 h=ROOT/'inputs/handoff';p=ROOT/'inputs/prior_runtime/inputs'
 source=pd.read_csv(h/'prior_AB/results/SCORES_1145.csv')
 assert len(source)==1145 and source.record_id.is_unique and source.object_id.is_unique
 full=scored(source)
 parity={k:float(np.max(np.abs(full[k]-source[col]))) for k,col in [('WQ','Q_WQ'),('A10','Q_A10'),('B8L2','Q_B8L2')]}
 assert max(parity.values())<1e-9
 csv(out/'SCORES_1145.csv',full)
 receipt=json.loads((h/'quality_ab_human_review_20261015_v1.json').read_text(encoding='utf-8-sig'))
 manifest=json.loads((h/'manifest.json').read_text(encoding='utf-8-sig'))
 joined=pd.read_csv(h/'FEEDBACK_30_JOINED.csv').fillna('')
 decisions=receipt['decisions'];cards={c['id']:c for c in manifest['cards']};rows=[]
 for row in joined.to_dict('records'):
  k=row['case_id'];dec=decisions[k];card=cards[k];bind=card['bindings'][0]
  assert dec['bindings']==card['bindings']
  assert row['record_id']==bind['record_id'] and row['object_id']==bind['object_id'] and row['reference_id']==bind['reference_object_id']
  original=full.set_index('record_id').loc[row['record_id']].to_dict()
  for field in ['object_id','image_id','reference_id']:assert row[field]==original[field]
  assert row['grade']==dec['grade'] and row['comment']==dec.get('comment','')
  row.update({key:value for key,value in original.items() if key not in row})
  for name in MAIN_MODELS+['POOL_OLD']:row[name]=original[name]
  row['first_reveal_grade']=dec.get('grade_at_first_score_reveal') or ''
  row['final_grade']=dec['grade'];row['pre_grade_available']=row['first_reveal_grade'] in GRADES
  row['changed_after_first_reveal']=row['pre_grade_available'] and row['first_reveal_grade']!=row['final_grade']
  row['first_viewed_at']=dec.get('first_viewed_at','');row['updated_at']=dec.get('updated_at','')
  row['comment_at_first_reveal']=None # not recorded, NEVER impute from final comment
  row['scope_comment_flag']=k in SCOPE_CASES;row['scope_comment_reason']=SCOPE_CASES.get(k,'')
  row['feedback_is_independent_blind']=False;rows.append(row)
 fb=pd.DataFrame(rows);csv(out/'FEEDBACK_30_ALL_RECORDS_AND_RAW_COMMENTS.csv',fb)
 audit=dict(n=len(fb),ordinary=int((fb.phase=='ordinary').sum()),doorway=int((fb.phase=='doorway').sum()),
            graded_before_first_reveal=int(fb.pre_grade_available.sum()),no_grade_at_first_reveal=int((~fb.pre_grade_available).sum()),changed_after_first_reveal=int(fb.changed_after_first_reveal.sum()),
            scored_revealed=int((fb.score_revealed_at!='').sum()),source_raw_receipt_copied_unchanged=True,first_reveal_comments_available=False,
            grading_not_used_as_numeric_targets=True,new_model_parameters_fitted_to_feedback=False)
 assert audit['graded_before_first_reveal']==23 and audit['changed_after_first_reveal']==6
 dump(out/'FEEDBACK_AUDIT.json',audit)
 csv(out/'REVEAL_TRANSITIONS.csv',fb[['case_id','record_id','selection','phase','first_reveal_grade','final_grade','pre_grade_available','changed_after_first_reveal','score_revealed_at','comment']])
 desc=[]
 for name,mask in [('ordinary_unused20',fb.selection=='unused_current_calibration'),('ordinary_unused18_no_scope_comments',(fb.selection=='unused_current_calibration')&~fb.scope_comment_flag),('ordinary_all24',fb.phase=='ordinary'),('ordinary_known4',(fb.phase=='ordinary')&(fb.selection=='known_concern')),('doorway6',fb.phase=='doorway'),('doorway4_no_scope_comments',(fb.phase=='doorway')&~fb.scope_comment_flag)]:
  for grade_col in ['final_grade','first_reveal_grade']:
   for x in order_desc(fb[mask],grade_col,MAIN_MODELS):desc.append(dict(subset=name,grade_snapshot=grade_col,**x))
 csv(out/'HUMAN_ORDINAL_ORDER_DESCRIPTIONS.csv',desc)
 old=pd.read_csv(p/'feedback_44_prior.csv')
 old=scored(old)
 old30=old[(old.phase=='ordinary')&~old.record_id.isin(['R01303','R00197'])]
 prior_desc=[dict(subset='historical_ordinary30_exposed',grade_snapshot='prior_final',**x) for x in order_desc(old30,'grade',MAIN_MODELS)]
 csv(out/'HISTORICAL_FEEDBACK_ORDER_DESCRIPTIONS.csv',prior_desc)
 csv(out/'HISTORICAL_44_SCORES.csv',old)
 # Keep historical and new reviews separate. Audit repeats by stable record id.
 repeats=fb.merge(old[['record_id','card_id','grade','comment']],on='record_id',suffixes=('_new','_old'))
 csv(out/'REPEATED_REVIEW_IDS.csv',repeats[['record_id','case_id','card_id','grade_new','grade_old','comment_new','comment_old']])
 # Complete, same-binding numerical panels.
 summ=[]
 for layer,x in full.groupby('comparison_layer',sort=True):
  for name in MAIN_MODELS:
   diff=x[name]-x.WQ
   summ.append(dict(layer=layer,model=name,n=len(x),mean=float(x[name].mean()),median=float(x[name].median()),mean_change_WQ=float(diff.mean()),max_increase_WQ=float(diff.max()),max_decrease_WQ=float(diff.min())))
 csv(out/'LAYER_SUMMARY.csv',summ)
 ordinary=full[full.comparison_layer=='ordinary_manual_conditional'].copy()
 reversals=[];pairsummary=[]
 for baseline in ['WQ','B8L2']:
  for model in [m for m in MAIN_MODELS if m!=baseline]:
   n=inv=large=ties=0
   for _,group in ordinary.groupby(['image_id','reference_id','condition'],sort=True):
    for a,b in itertools.combinations(group.to_dict('records'),2):
     if a['worker_id']==b['worker_id']:continue
     u=a[baseline]-b[baseline];v=a[model]-b[model]
     if abs(u)<1e-9 and abs(v)<1e-9:continue
     n+=1
     if abs(u)<1e-9 or abs(v)<1e-9:ties+=1
     if u*v<0:
      inv+=1;big=abs(u)>=5 and abs(v)>=5;large+=int(big)
      if big or (baseline=='B8L2' and model=='C8_anchor_matched'):
       reversals.append(dict(baseline=baseline,model=model,a=a['record_id'],b=b['record_id'],image_id=a['image_id'],reference_id=a['reference_id'],baseline_delta=u,model_delta=v,both_abs_diff_ge5=big))
   pairsummary.append(dict(baseline=baseline,model=model,n_pairs=n,opposed_pairs=inv,both_abs_diff_ge5=large,one_score_tied=ties))
 csv(out/'SAME_REFERENCE_PAIR_SENSITIVITY.csv',pairsummary);csv(out/'RETAINED_REVERSALS.csv',reversals)
 # Positive orthant geometry of the aggregators, all same component scales.
 ratios=np.unique(np.r_[0.,np.logspace(-4,0,301)])
 theory=[]
 for ratio in ratios:
  for kind,param,name in [('sum',0,'S8'),('l2',0,'B8L2'),('ordered',LAMBDA,'C8_anchor_matched'),('lp',1.5,'P1.5'),('lp',3.,'P3'),('max',0,'MAX8'),('mixed',.25,'MIN_SHARE25')]:
   m=float(pool(np.array(1.),np.array(ratio),kind,param))
   theory.append(dict(model=name,minor_over_major=float(ratio),geometric_loss_over_major=m,minor_increment=m-1.,loss_credit_vs_sum=1+ratio-m))
 csv(out/'EQUAL_SCALE_POOL_SHAPES.csv',theory)
 # Explicit scalar independent-errors counterfactuals and actual height response.
 scalar=[]
 for f,d,H in itertools.product([0.,.05,.2,.5,1.,3.,10.],[0.,.05,.2,.5,1.,1.49],[0.,.04,.25,1.,10.]):
  for model in MODELS[2:]:
   m=float(pool(np.array(f),np.array(d),model.mechanism,model.parameter));v=100/(1+m+H)
   scalar.append(dict(F=f,d=d,H=H,model=model.name,Q=v,incremental_direction_points=100/(1+f+H)-v,incremental_height_points=100/(1+m)-v,loss_credit=f+d-m))
 csv(out/'SCALAR_FACTORIAL_MECHANISMS.csv',scalar)
 # Mapping audit: same losses, mapping only. All strictly monotone maps preserve single-row ordering,
 # but nonlinear averages need not. No human fitting.
 for gamma in [.8,1.,1.2]:
  full[f'MAP_HILL_{gamma:g}']=100/(1+(full.pooled_loss_B+full.loss_H)**gamma)
 full['MAP_EXP_HALF_AT_ONE']=100*np.exp(-np.log(2)*(full.pooled_loss_B+full.loss_H))
 mapcols=['B8L2','MAP_HILL_0.8','MAP_HILL_1','MAP_HILL_1.2','MAP_EXP_HALF_AT_ONE']
 csv(out/'MAPPING_ONLY_1145.csv',full[['record_id','reference_id','comparison_layer','iou_2d']+mapcols])
 mapcheck=[]
 I=np.linspace(.001,1.,1000);K=(1-I)/I
 for label,val in [('B8L2',100/(1+K)),('MAP_HILL_0.8',100/(1+K**.8)),('MAP_HILL_1.2',100/(1+K**1.2)),('MAP_EXP_HALF_AT_ONE',100*np.exp(-np.log(2)*K))]:
  mapcheck.append(dict(mapping=label,pure_iou_max_abs_anchor_error=float(np.max(np.abs(val-100*I))),real_rows_above_100I=int(np.sum(full[label]>100*full.iou_2d+1e-9)) if label in full else 0))
 csv(out/'MAPPING_ANCHOR_CHECKS.csv',mapcheck)
 # Worker comparison: same observed unit composition, not causal ability.
 ordinary=full[full.comparison_layer=='ordinary_manual_conditional'].copy()
 usedmodels=list(dict.fromkeys(MAIN_MODELS+mapcols))
 cells=ordinary.groupby(['worker_id','image_id','reference_id','condition'],as_index=False)[usedmodels].mean()
 for label in usedmodels:
  cells[label+'_centered']=cells[label]-cells.groupby(['image_id','reference_id','condition'])[label].transform('mean')
 counts=cells.groupby('worker_id').size();workers=counts[counts>=5].index
 prof=cells[cells.worker_id.isin(workers)].groupby('worker_id')[[x+'_centered' for x in usedmodels]].mean();prof['n_cells']=counts
 for label in usedmodels:prof[label+'_rank']=prof[label+'_centered'].rank(method='average',ascending=False)
 base=prof['B8L2_rank'];ws=[]
 for label in usedmodels:
  rank=prof[label+'_rank']
  # Exploratory quantile thirds for sensitivity only, NOT human five-grade or formal worker classes.
  qbase=pd.cut((base-1)/len(base),[-.01,1/3,2/3,1.01],labels=['upper','middle','lower']);qrank=pd.cut((rank-1)/len(rank),[-.01,1/3,2/3,1.01],labels=['upper','middle','lower'])
  ws.append(dict(model=label,n_workers=len(prof),spearman_vs_B=float(spearmanr(base,rank).statistic),max_rank_move=float(np.max(np.abs(rank-base))),exploratory_relative_tertile_changes=int(np.sum(qbase!=qrank))))
 for label in usedmodels:prof[label+'_inherited_relative_group']=pd.cut((prof[label+'_rank']-1)/len(prof),[-.01,1/3,2/3,1.01],labels=['upper','middle','lower'])
 csv(out/'WORKER_CELLS.csv',cells);csv(out/'WORKER_PROFILES.csv',prof.reset_index());csv(out/'WORKER_SENSITIVITY.csv',ws)
 # Difficulty target-preserving connection (ID only; source table version retained).
 difficulty=pd.read_csv(p/'difficulty_target_projection_135.csv')
 djoin=ordinary.merge(difficulty,on='image_id',how='left',suffixes=('','_difficulty'))
 target_col='difficulty_reference_id'
 djoin['same_difficulty_reference_id']=djoin.reference_id==djoin[target_col]
 csv(out/'DIFFICULTY_JOIN.csv',djoin)
 dgood=djoin[djoin.same_difficulty_reference_id & djoin.current_class.isin(['简单','中等','困难'])]
 img=dgood.groupby(['image_id','current_class'],as_index=False)[MAIN_MODELS].mean()
 ds=[]
 for cls,x in img.groupby('current_class'):
  for name in MAIN_MODELS:ds.append(dict(difficulty_class=cls,model=name,n_images=len(x),mean_image_equal=float(x[name].mean())))
 csv(out/'DIFFICULTY_IMAGE_UNITS.csv',img);csv(out/'DIFFICULTY_SENSITIVITY.csv',ds)
 # Fixed fusion outputs only; no new selection / voting / fusion.
 fusion=pd.read_csv(p/'FUSION_220_SCORES.csv')
 mask=fusion[['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']].notna().all(axis=1)
 fu=scored(fusion[mask]);csv(out/'FUSION_COMPLETE_FIXED_SCORES.csv',fu)
 holds=full[full.comparison_layer.isin(['two_image_scope_diagnostic','ordinary_target_hold','doorway_target_hold'])].image_id.unique()
 good=fu[(fu.stage=='ordinary')&(fu.member_restrictions=='[]')&(fu.holdout_members=='[]')&~fu.image_id.isin(holds)]
 fpair=[]
 for key,x in good.groupby(['image_id','reference_id']):
  if len(x)!=2:continue
  records=x.to_dict('records');aa=next((z for z in records if z['version']=='automatic'),None)
  bb=next((z for z in records if z['version']=='assisted'),None)
  if aa is None or bb is None:
   # Inspect and use established saved version naming, no inference from score.
   aa=next((z for z in records if z['version']=='auto'),None)
   bb=next((z for z in records if z['version']=='assisted'),None)
  if aa and bb:
   for name in MAIN_MODELS:fpair.append(dict(image_id=key[0],reference_id=key[1],model=name,assisted_minus_automatic=bb[name]-aa[name]))
 csv(out/'FUSION_PAIRED_DIFFERENCES.csv',fpair)
 # Geometry remeasurement of current handoff 30.
 geos=json.loads((h/'geometries.json').read_text())
 parityrows=[];diagnostics=[];georecords=[];edge_rows=[]
 for row in joined.to_dict('records'):
  a,g=[geos[k] for k in [row['object_id'],row['reference_id']]]
  ax=np.asarray(a['bottom3d'])[:,[0,2]];gx=np.asarray(g['bottom3d'])[:,[0,2]]
  ah=np.asarray(a['top3d'])[:,1]-np.asarray(a['bottom3d'])[:,1];gh=np.asarray(g['top3d'])[:,1]-np.asarray(g['bottom3d'])[:,1]
  met=measure(ax,ah,gx,gh);fixed=source.set_index('record_id').loc[row['record_id']]
  rr=dict(case_id=row['case_id'],record_id=row['record_id'])
  rr.update(met)
  for k,val in met.items():rr['abs_error_'+k]=abs(val-fixed[k])
  parityrows.append(rr)
  georecords.append(dict(case_id=row['case_id'],record_id=row['record_id'],object_id=row['object_id'],reference_id=row['reference_id'],a=ax.tolist(),ah=ah.tolist(),g=gx.tolist(),gh=gh.tolist()))
  diag=dict(case_id=row['case_id'],record_id=row['record_id'],reference_self_D=direction(gx))
  sm=dict(iou_2d=1.,S_bottom_deg=0.,dir=direction(gx),Hmean=0.,Hcenter=0.)
  for model in ['WQ','A10','B8L2','C8_anchor_matched']:diag['reference_self_'+model]=float(score(*sm.values(),model))
  for gate in [2.,5.]:
   cm=corner_metrics(ax,gx,gate,10.)
   for k in ['corners_a','corners_g','matched','position_f1','angle_f1','matched_angle_rms_deg','matched_angle_max_deg']:diag[f'gate{gate:g}_{k}']=cm[k]
  cv=boundary_coverage(ax,gx,1.)
  for k in ['coverage','precision','recall','p95_a_deg','p95_g_deg']:diag['boundary1_'+k]=cv[k]
  diagnostics.append(diag)
  phi,res,l,e=axis_details(ax)
  for i in range(len(ax)):edge_rows.append(dict(case_id=row['case_id'],record_id=row['record_id'],edge_index=i,axis_deg=phi,length_h=l[i],perimeter_share=l[i]/sum(l),residual_deg=res[i],D2_contribution=l[i]*res[i]**2/sum(l)))
 csv(out/'GEOMETRY_PARITY_30.csv',parityrows);csv(out/'REFERENCE_STRUCTURAL_DIAGNOSTICS_30.csv',diagnostics);csv(out/'DIRECTION_EDGES_30.csv',edge_rows)
 dump(out/'REVIEW_GEOMETRY_30.json',georecords)
 assert pd.DataFrame(parityrows).filter(like='abs_error_').max().max()<1e-8
 # All 72 previously defined physical controls, remeasured rather than reusing scores.
 controlpath=ROOT/'inputs/prior_runtime/results/executed_control_geometries.json'
 controls=json.loads(controlpath.read_text())
 if isinstance(controls,dict):controls=controls.get('controls',controls.get('geometries',[]))
 crows=[]
 for c in controls:
  a,ah,g,gh=c['a'],c['ah'],c['g'],c['gh']
  met=measure(a,ah,g,gh)
  keep={k:v for k,v in c.items() if k not in ['a','g','ah','gh'] and not isinstance(v,(dict,list))}
  crows.append(keep|met)
 ctrl=scored(pd.DataFrame(crows));csv(out/'PHYSICAL_CONTROLS.csv',ctrl)
 # Mathematical maxima and mapping identities (analytic constants, not fitted).
 ratio_max=math.sqrt(1+LAMBDA**2)
 theory_constants=dict(lambda_ordered=LAMBDA,diagonal_surcharge_B=math.sqrt(2)-1,
    maximum_loss_discount_fraction_B=1-1/math.sqrt(2),C_over_B_max=ratio_max,
    maximum_Q_B_minus_Q_C_all_nonnegative=100*(math.sqrt(ratio_max)-1)/(math.sqrt(ratio_max)+1),
    maximum_Q_B_minus_Q_sum8_all_nonnegative=100*(2**.25-1)/(2**.25+1),
    B_is_idempotent=False,aggregation_independent_of_error_cause=True,
    rho_or_covariance_estimation_performed=False)
 dump(out/'MATHEMATICAL_CONSTANTS.json',theory_constants)
 # Tail and real strong disconfirming contexts.
 tails=[]
 for subset,x in [('ordinary931',ordinary),('I_ge_0.8',ordinary[ordinary.iou_2d>=.8]),('I_le_0.2',full[full.iou_2d<=.2]),('severe9',full[full.comparison_layer=='severe_exception'])]:
  tails.append(dict(subset=subset,n=len(x),mean_B_minus_S8=float((x.B8L2-x.S8).mean()),max_B_minus_S8=float((x.B8L2-x.S8).max()),mean_C_minus_B=float((x.C8_anchor_matched-x.B8L2).mean()),max_B_minus_C=float((x.B8L2-x.C8_anchor_matched).max()),mean_height_drop_change_B_vs_S8=float((x.B8L2_delete_all_height_gain-x.S8_delete_all_height_gain).mean())))
 csv(out/'TAILS_AND_JOINT_COSTS.csv',tails)
 # Incremental slope is different from finite deletion cost.
 csv(out/'ACTUAL_MARGINALS_1145.csv',full[['record_id','reference_id','comparison_layer','dir','loss_F','loss_d','loss_H','S8','B8L2','S8_delete_direction_gain','B8L2_delete_direction_gain','abs_S8_derivative_Q_per_Ddeg','abs_B_derivative_Q_per_Ddeg','abs_S8_derivative_Q_per_Hloss','abs_B_derivative_Q_per_Hloss','B_direction_local_slope_stronger_than_S8']])
 # A plausible covariance-whitening proposal is not monotone as a severity utility.
 rho=.8
 rejected=[dict(proposal='axis_matched_covariance_whitening',F=1.,d=x,rho=rho,
                pooled=math.sqrt(1+x*x-2*rho*x),Q=100/(1+math.sqrt(1+x*x-2*rho*x)),
                status='rejected_for_penalty_monotonicity_not_for_use_in_statistical_inference') for x in [0.,.1,.4,.8,1.]]
 csv(out/'REJECTED_CORRELATION_CORRECTION.csv',rejected)
 # Projected dimensions are not additional independent evidence. Splitting a LOSS block changes B.
 split=[dict(F=1.,d_total=1.,parts=n,B_frozen_two_block=math.sqrt(2),
             incorrectly_repool_after_splitting=math.sqrt(1+1/n),
             note='hold semantic blocks fixed; this is not geometric collinear subdivision') for n in [1,2,4,10,100]]
 csv(out/'LOSS_BLOCK_SPLITTING_COUNTEREXAMPLE.csv',split)
 # Image-level bootstrap is descriptive, not an independent-validation claim. Fixed candidates, no refit.
 rng=np.random.default_rng(20261015);bs=[]
 for subset,mask in [('unused20',fb.selection=='unused_current_calibration'),('all_ordinary24',fb.phase=='ordinary')]:
  for gc in ['final_grade','first_reveal_grade']:
   z=fb[mask & fb[gc].isin(GRADES)].copy();n=len(z);assert z.image_id.is_unique
   y=z[gc].map(GRADES).to_numpy();upper=np.triu(np.ones((n,n),bool),1)&(y[:,None]!=y[None,:])
   den=upper.astype(float)
   for a,b in [('B8L2','WQ'),('B8L2','S8'),('C8_anchor_matched','B8L2')]:
    qa=z[a].to_numpy();qb=z[b].to_numpy()
    da=(((qa[:,None]-qa[None,:])*(y[:,None]-y[None,:]))<0)*den
    db=(((qb[:,None]-qb[None,:])*(y[:,None]-y[None,:]))<0)*den
    vals=[]
    for _ in range(2000):
     w=rng.multinomial(n,[1/n]*n);ww=w[:,None]*w[None,:];dv=(den*ww).sum()
     if dv>0:vals.append(float(((da-db)*ww).sum()/dv))
    bs.append(dict(subset=subset,grade_snapshot=gc,a=a,b=b,n_images=n,
             inversion_fraction_a_minus_b=float((da-db).sum()/den.sum()),
             resample_p05=float(np.quantile(vals,.05)),resample_p95=float(np.quantile(vals,.95)),
             interpretation='descriptive_image_resampling_single_exposed_reviewer_not_confirmatory_CI'))
 csv(out/'DESCRIPTIVE_IMAGE_RESAMPLING.csv',bs)
 # No dataset winner fitted here. Select review cases by fixed competing mechanisms and preserve failures.
 reasons={}
 for k in ['N02','N10','N16','N17','N21','N22','N23','N24','D02','D05']:
  r=fb[fb.case_id==k].iloc[0];reasons[r.record_id]=['existing_human_or_scope_counterexample:'+k]
 for label,col,ascending in [('largest_pure_pooling_credit','Q_gain_pool_only_at_c8',False),('C_vs_B_shape_difference','balancedness_min_over_max',True),('largest_height_cost_reallocation','B8L2_delete_all_height_gain',False)]:
  sel=ordinary.copy()
  if label=='C_vs_B_shape_difference':sel['shape_diff']=sel.B8L2-sel.C8_anchor_matched;col='shape_diff';ascending=False
  for _,r in sel.sort_values(col,ascending=ascending).head(3).iterrows():reasons.setdefault(r.record_id,[]).append(label)
 queue=full[full.record_id.isin(reasons)].copy();queue['selection_reasons']=queue.record_id.map(lambda k:';'.join(reasons[k]));queue['current_photo_visual_review_done']=False
 csv(out/'FOLLOWUP_CHALLENGE_MANIFEST.csv',queue)
 exe=dict(baseline_scores_rows=len(full),unique_answers=int(full.record_id.nunique()),main_commit='e3dcf9d11daf9390d6acc09974101f7b6b88a3dd',source='supplied_increment_not_full_loader',
       layers=full.comparison_layer.value_counts().to_dict(),formula_parity_max_abs=parity,geometry_remeasured_answers=30,physical_controls=len(ctrl),
       raw_feedback_count=len(fb),old_feedback_count=len(old),repeated_old_new_review_records=len(repeats),feedback_audit=audit,
       worker_profiles=len(prof),all_worker_common_cells=int((cells.groupby(['image_id','reference_id','condition']).worker_id.nunique()==len(prof)).sum()),B_local_direction_slope_stronger_ordinary=int(ordinary.B_direction_local_slope_stronger_than_S8.sum()),difficulty_same_id_three_class_rows=len(dgood),difficulty_images=len(img),
       fusion_total_status_rows=len(fusion),fusion_full_rows=len(fu),fusion_conservative_rows=len(good),fusion_paired_units=len(fpair)//len(MAIN_MODELS),fusion_versions=sorted(fu.version.unique()),
       new_model_fit_to_current_ratings=False,new_human_review=False,original_data_changed=False,production_default_changed=False,
       full_library_loader_executed=False,photos_read_this_run=False)
 dump(out/'EXECUTION.json',exe)
 print(json.dumps(exe,ensure_ascii=False,indent=2))

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--output',type=Path,default=ROOT/'results');args=a.parse_args();main(args.output)
