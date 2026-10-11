"""Necessary single-error envelopes and joint condition; never quality pass criteria."""
from pathlib import Path
import math,numpy as np
from common import csvwrite,save
ROOT=Path(__file__).resolve().parents[1]
def stage_cap(q,start,end):
 k=2*(1-q/100);amin=.15;amax=.45
 if k>=amax:return None,'unbounded_single_component_envelope'
 roots=[]
 if k<amin:
  u=math.sqrt(k/(amin-k))
  if u<=start:roots.append((u,'constant_min_alpha_segment'))
 coeff=[(amax-amin)/(end-start),amin-(amax-amin)*start/(end-start)-k,0,-k]
 for r in np.roots(coeff):
  if abs(r.imag)<1e-10 and start<=r.real<=end:roots.append((float(r.real),'cubic_middle_segment'))
 u=math.sqrt(k/(amax-k))
 if u>=end:roots.append((u,'constant_max_alpha_segment'))
 assert len(roots)==1
 u,status=roots[0];alpha=amin+(amax-amin)*min(1,max(0,(u-start)/(end-start)));assert abs(100*(1-alpha*(u*u/(1+u*u))/2)-q)<1e-8
 return u,status
rows=[]
for q in [95,85,50,90,75,60]:
 t=100/q-1
 for method in ['v11_alpha15','alpha30','alpha45','Pro_stage13','Pro_stage24']:
  if method.startswith('Pro_'):u,status=stage_cap(q,1 if method.endswith('13') else 2,3 if method.endswith('13') else 4)
  else:
   alpha={'v11_alpha15':.15,'alpha30':.3,'alpha45':.45}[method];loss=2*(1-q/100)/alpha;u=math.sqrt(loss/(1-loss)) if loss<1 else None;status='analytic_constant_alpha' if u is not None else 'unbounded_single_component_envelope'
  rows.append({'Q_boundary':q,'boundary_status':'historical' if q in [95,85,50] else 'unapproved_explanatory','method':method,'necessary_I_min':q/100,'necessary_intrinsic_retention_min':q/100,'necessary_total_SH_budget_max':t,'S_single_error_max_deg':4*math.sqrt(t),'Hstar_single_error_max':.5*math.sqrt(t),'D_single_error_max_deg':5*u if u is not None else None,'F_single_error_max_deg':2*u if u is not None else None,'DF_cap_status':status,'individual_bounds_jointly_sufficient':False,'single_error_assumptions':'I=1, other errors=0; maximum-score envelope only'})
csvwrite(ROOT/'results/quality_threshold_necessary_envelopes.csv',rows)
q=95;t=100/q-1;joint=100/(1+2*t);assert joint<q
save(ROOT/'results/quality_joint_condition_evidence.json',{'exact_formula':'Q=100*I*R/(1+T), T=(S/4)^2+(Hstar/.5)^2; R=frozen intrinsic retention','exact_necessary_and_sufficient_condition_for_fixed_finite_components':'Q>=q iff 100*I*R>=q*(1+T)','individual_bounds_not_sufficient_counterexample':{'q':q,'I':1,'R':1,'S':4*math.sqrt(t),'Hstar':.5*math.sqrt(t),'each_single_error_envelope_reaches_q':True,'joint_Q':joint},'sufficient_box_condition':'For declared I>=I0, R>=R0, T<=100*I0*R0/q-1 with nonnegative budget, Q>=q. Choosing this box is not calibration.','D5_F2_are_half_loss_scales_not_pass_thresholds':True,'no_final_quality_categories_selected':True})
print('30 necessary-envelope rows; piecewise cubic and joint counterexample checked; no pass criteria selected.')
