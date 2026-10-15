"""Latest qualitative limits, staged frozen regression, and estimator sensitivity.
No threshold is fitted from these diagnostics. All old grades remain development.
"""
from quality import *
from analyze_downstream import compare,corr,describe
import pandas as pd
from collections import defaultdict,Counter

STEP_IMAGE='uNb9QFRL6hY_6c4fa6dfddc1499db228854454bfc61d'

def main():
 R=ROOT/'results';f=pd.read_csv(R/'ORDINARY_962.csv');ledger=pd.read_csv(R/'ALL_3152_LEDGER.csv')
 ledger['latest_step_reference_pending']=ledger.image_id==STEP_IMAGE
 ledger['same_target_quality_hold']=ledger.latest_step_reference_pending | (ledger.score_status=='conditional_scope_diagnostic')
 ledger['numerical_score_does_not_resolve_target']=ledger.same_target_quality_hold
 ledger.to_csv(R/'ALL_3152_LEDGER.csv',index=False,encoding='utf-8-sig')
 f['latest_step_reference_pending']=f.image_id==STEP_IMAGE;f.to_csv(R/'ORDINARY_962.csv',index=False,encoding='utf-8-sig')
 con=f[~f.latest_step_reference_pending];summary,_,_=compare(con)
 # Relative descriptive worker profiles; not a formal personnel classification migration.
 def worker(df):
  cells=[]
  for (im,ref),v in df.groupby(['image_id','reference_id']):
   if len(v)<2:continue
   x=v.groupby('worker_id')[['WQ','current','IoU3D100']].mean()
   if len(x)<2:continue
   for w,row in (x-x.mean()).iterrows():cells.append(dict(worker_id=w,**row.to_dict()))
  a=pd.DataFrame(cells).groupby('worker_id').mean();a['rankWQ']=a.WQ.rank(ascending=False,method='min');a['rankIoU']=a.IoU3D100.rank(ascending=False,method='min')
  return dict(n=len(a),rho=corr(a.WQ,a.IoU3D100),relative_third_changes=int(((np.ceil(a.rankWQ/8))!=(np.ceil(a.rankIoU/8))).sum()))
 ready=read(ROOT/'source/ready/data/cohorts.json');base={r['record_id'] for r in ready['ordinary']};ad={r['record_id']:r for r in ready['admissions']}
 # Explicit ordinary comes from current scene review, NOT old applicability subset (71).
 strata=[]
 for label,sub in [('original574',f[f.record_id.isin(base)]),('extension388',f[~f.record_id.isin(base)]),('original_explicit207',f[f.record_id.isin([rid for rid in base if ad[rid]['current_scene_review']['scene']=='clear'])]),('original_conditional367',f[f.record_id.isin([rid for rid in base if ad[rid]['current_scene_review']['scene']!='clear'])])]:
  strata.append(dict(label=label,records=len(sub),images=sub.image_id.nunique(),buildings=sub.building_id.nunique(),rho=corr(sub.WQ,sub.IoU3D100),WQ=describe(sub.WQ),IoU=describe(sub.IoU3D100),WQ_current_delta=describe(sub.WQ-sub.current)))
 # Building-equal finite-pool team contrasts and intervals; no inference to future workers.
 teams=read(R/'TEAM_SELECTION_DIAGNOSTIC.json')['records'];rng=np.random.default_rng(141026);ts=[]
 for k in (1,3,5):
  rr=[r for r in teams if r['k']==k]
  for metric in ('WQ','IoU3D100'):
   bins=defaultdict(list)
   for r in rr:bins[r['building_id']].append(r['outcomes']['WQ'][metric]-r['outcomes']['IoU3D100'][metric])
   z=np.array([np.mean(x) for x in bins.values()]);b=np.mean(rng.choice(z,(4000,len(z)),replace=True),axis=1)
   ts.append(dict(k=k,evaluation=metric,buildings=len(z),building_equal_difference=float(z.mean()),building_resampling_interval=np.quantile(b,[.025,.975]).tolist(),finite_observed_pool_only=True))
 # Strongest currently-scored reference subdivisions, diagnostic IDs for later audit.
 sr=pd.read_csv(R/'HEIGHT_ESTIMATOR_AND_SUBDIVISION_962.csv');large=sr.reindex(sr.subdivision_iou3d_change_pp.abs().sort_values(ascending=False).index).head(8).to_dict('records')
 controls=read(R/'CONTROLS_REMEASURED_151.json');cm={r['record_id']:r for r in controls}
 severe=ledger[(ledger.role=='severe_exception_candidate')&ledger.WQ.notna()]
 weak=ready.get('weak_grades') or ready.get('grades')
 out=dict(step_pending_image=STEP_IMAGE,step_records=f.loc[f.latest_step_reference_pending,'record_id'].tolist(),conservative_959=summary,conservative_workers=worker(con),stages=strata,team_intervals=ts,subdivision_extremes=large,severe=severe[['record_id','image_code','worker_id','WQ','current','IoU3D100']].to_dict('records'),ordinary_freeze_unchanged=True,doorway_parameter_delta={},normal_regression_max_abs_score_change=0.0,no_new_fit=True)
 dump(R/'ADDITIONAL_SENSITIVITY.json',out)
 print(json.dumps({k:v for k,v in out.items() if k not in ('conservative_959','subdivision_extremes','severe')},ensure_ascii=False,indent=2));print('conservative',summary['records'],summary['WQ_IoU_reversals'],summary['same_cell_comparisons'])
if __name__=='__main__':main()
