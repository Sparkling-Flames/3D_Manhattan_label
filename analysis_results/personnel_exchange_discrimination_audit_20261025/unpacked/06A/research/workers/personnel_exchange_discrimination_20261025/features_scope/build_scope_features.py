#!/usr/bin/env python3
"""LOBO scope-response propensities from frozen real-v2 evidence.
Restores 286 unambiguous historical 'oos' answers as an auxiliary feature bridge.
Does not modify source records, eligibility, references, Q or fusion.
"""
from pathlib import Path
import argparse,hashlib,json,sys
import numpy as np
import pandas as pd

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def summarize(q,col='response_image_condition_source_residual',min_n=8,min_b=3):
 z=q.loc[q[col].notna()]
 n=z.image_id.nunique();b=z.building_id.nunique();supported=n>=min_n and b>=min_b
 return len(z),n,b,supported,(z[col].mean() if supported else np.nan)
def main():
 here=Path(__file__).resolve().parent
 sys.path.insert(0,str(here.parent));from run_native import ROOT,REPO,POP
 ap=argparse.ArgumentParser();ap.add_argument('--root');ap.add_argument('--repo');ap.add_argument('--output');ap.add_argument('--population-inputs');a=ap.parse_args()
 root=Path(a.root) if a.root else ROOT
 repo=Path(a.repo) if a.repo else (root/'HOHONET_exchange_latest' if a.root else REPO)
 out=Path(a.output) if a.output else (root/'exchange_research_20261025/features_scope' if a.root else here);out.mkdir(parents=True,exist_ok=True)
 pop=Path(a.population_inputs) if a.population_inputs else (root/'exchange_research_20261025/recovery/prior_population/research/workers/personnel_population_curves_v2_20261023/inputs' if a.root else POP/'inputs')
 ledger=repo/'research/workers/personnel_type_discovery_next_20261019/work_personnel_typing_A_20261019/input/RECORD_EVIDENCE_LEDGER.csv.gz'
 oldp=repo/'research/workers/worker_b8l2_d10_20261017/scope_response_evidence.csv'
 dp=pop/'IMAGE_DIFFICULTY_OPPORTUNITIES.csv';wp=pop/'RAW_POOL_MEMBER_FEATURES.csv.gz'
 d=pd.read_csv(ledger);old=pd.read_csv(oldp);meta=pd.read_csv(dp)
 assert not d.object_id.duplicated().any()
 assert not old.duplicated(['worker_id','image_id']).any()
 old=old.rename(columns={'object_id':'historical_scope_object_id','source':'historical_scope_source','building_id':'historical_scope_building_id'})
 d=d.merge(old[['worker_id','image_id','historical_scope_object_id','historical_scope_source','historical_scope_building_id','worker_scope']],on=['worker_id','image_id'],how='left',validate='many_to_one')
 d['scope_response_v2_original']=d.scope_response
 d['scope_response_historical_normalized']=d.worker_scope.replace({'oos':'out_of_scope','normal':'in_scope'})
 both=d.scope_response.notna()&d.scope_response_historical_normalized.notna()
 assert (d.loc[both,'scope_response']==d.loc[both,'scope_response_historical_normalized']).all()
 rec=d.scope_response.isna() & d.scope_response_historical_normalized.isin(['in_scope','out_of_scope'])
 assert d.loc[rec,'historical_scope_object_id'].nunique()==int(rec.sum())
 d['scope_feature_response']=d.scope_response.fillna(d.scope_response_historical_normalized)
 d['scope_feature_provenance']=np.where(rec,'historical_exact_worker_image_oos_normalized','v2_record_evidence_ledger')
 d['scope_restored_from_historical_oos']=rec
 d.loc[rec,['object_id','worker_id','image_id','image_code','building_id','condition','origin','scope_response_v2_original','historical_scope_object_id','historical_scope_source','worker_scope','scope_feature_response','scope_feature_provenance']].to_csv(out/'SCOPE_RESTORED_HISTORICAL_286.csv',index=False)
 d=d.merge(meta[['image_id','is_oos','is_doorway','difficulty_main_eligible','difficulty_coarse','scope_semantics','reference_status']],on='image_id',how='left',validate='many_to_one')
 d['scope_stratum']=np.select([d.is_oos.eq(True),d.is_doorway.eq(True),d.difficulty_main_eligible.eq(True)],['current_oos','current_doorway','current_ordinary'],default='current_special_or_unknown')
 d['recorded_rejection']=d.scope_feature_response.map({'in_scope':0.0,'out_of_scope':1.0})
 cols=['object_id','worker_id','image_id','image_code','building_id','condition','origin','quality_usable','quality_use','cleaning_disposition','scope_response_v2_original','scope_feature_response','scope_feature_provenance','scope_restored_from_historical_oos','historical_scope_object_id','historical_scope_source','worker_scope','scope_gold_opportunity','scope_correct','is_oos','is_doorway','difficulty_main_eligible','difficulty_coarse','scope_stratum','scope_semantics','reference_status','recorded_rejection']
 d[cols].to_csv(out/'SCOPE_RECORDS_WITH_OPPORTUNITIES.csv.gz',index=False,compression='gzip')
 # Same person-image-condition duplicate objects repeat the same answer: one behavioural opportunity.
 conflict=d.groupby(['worker_id','image_id','condition']).recorded_rejection.nunique().gt(1)
 assert not conflict.any()
 dedup=d.sort_values('object_id').groupby(['worker_id','image_id','condition'],as_index=False).agg(
  building_id=('building_id','first'),origin=('origin','first'),recorded_rejection=('recorded_rejection','mean'),
  scope_stratum=('scope_stratum','first'),difficulty_coarse=('difficulty_coarse','first'),
  raw_records=('object_id','size'),object_ids=('object_id',lambda v:'|'.join(v)),
  scope_restored_from_historical_oos=('scope_restored_from_historical_oos','max'),
  current_formal_any=('quality_usable','max'))
 workers=sorted(d.worker_id.unique());folds=['ALL']+sorted(d.building_id.dropna().unique())
 rows=[]
 for held in folds:
  tr=dedup if held=='ALL' else dedup.loc[dedup.building_id.ne(held)].copy()
  tr=tr.copy();ctx=['image_id','condition','origin'];gg=tr.groupby(ctx).recorded_rejection
  n=gg.transform('count');mu=gg.transform('mean')
  tr['scope_context_response_n']=n
  tr['response_image_condition_source_residual']=(tr.recorded_rejection-mu).where(n.ge(3))
  for w in workers:
   q=tr.loc[tr.worker_id.eq(w)];row={'worker_id':w,'heldout_building':held,'scope_origin':'|'.join(sorted(q.origin.dropna().unique())),'scope_opportunities':len(q),'scope_recorded_opportunities':int(q.recorded_rejection.notna().sum()),'scope_buildings':q.loc[q.recorded_rejection.notna()].building_id.nunique(),'scope_restored_historical_n':int(q.scope_restored_from_historical_oos.sum())}
   ordq=q.loc[q.scope_stratum.eq('current_ordinary') & q.condition.isin(['manual','semi'])]
   # Main scope domain: same image/condition/source residual, equal weight to supported Manual and Semi means.
   conditioned=[]
   for name,z,minn,minb in [
     ('manual',ordq.loc[ordq.condition.eq('manual')],8,3),
     ('semi',ordq.loc[ordq.condition.eq('semi')],8,3),
     ('ordinary',ordq,8,3),
     ('hard',ordq.loc[ordq.difficulty_coarse.eq('困难')],5,3),
     ('easy',ordq.loc[ordq.difficulty_coarse.eq('简单')],8,3),
     ('doorway',q.loc[q.scope_stratum.eq('current_doorway')],3,2),
     ('oos',q.loc[q.scope_stratum.eq('current_oos')],3,2),
     ('special',q.loc[q.scope_stratum.eq('current_special_or_unknown')],3,2)]:
    nn,ii,bb,sup,value=summarize(z,min_n=minn,min_b=minb)
    row['scope_'+name+'_records']=nn;row['scope_'+name+'_images']=ii;row['scope_'+name+'_buildings']=bb;row['scope_'+name+'_supported']=sup;row['scope_'+name+'_residual']=value
    row['scope_'+name+'_reject_rate']=z.loc[z.recorded_rejection.notna(),'recorded_rejection'].mean() if sup else np.nan
    if name in ['manual','semi'] and sup:conditioned.append(value)
   row['scope_supported']=bool(conditioned)
   row['scope_centered_rejection']=np.mean(conditioned) if conditioned else np.nan
   row['scope_manual_minus_semi']=row['scope_manual_residual']-row['scope_semi_residual']
   row['scope_hard_minus_easy']=row['scope_hard_residual']-row['scope_easy_residual']
   row['scope_missing_reason']='' if conditioned else ('no_recorded_scope_history' if not q.recorded_rejection.notna().any() else 'ordinary_image_condition_source_comparison_support_below_8_images_3_buildings')
   rows.append(row)
 features=pd.DataFrame(rows);features.to_csv(out/'SCOPE_FEATURES_ALL_LOBO.csv.gz',index=False,compression='gzip');features.query("heldout_building == 'ALL'").to_csv(out/'SCOPE_FEATURES_ALL.csv',index=False)
 source=d.groupby(['origin','condition'],dropna=False).agg(records=('object_id','size'),workers=('worker_id','nunique'),images=('image_id','nunique'),recorded_v2=('scope_response_v2_original',lambda v:v.notna().sum()),recorded_feature=('scope_feature_response',lambda v:v.notna().sum()),restored=('scope_restored_from_historical_oos','sum'),reject_rate=('recorded_rejection','mean')).reset_index();source.to_csv(out/'SCOPE_SOURCE_SUPPORT.csv',index=False)
 coverage=features.groupby('heldout_building').agg(workers=('worker_id','size'),supported=('scope_supported','sum'),manual_supported=('scope_manual_supported','sum'),semi_supported=('scope_semi_supported','sum'),hard_supported=('scope_hard_supported','sum')).reset_index();coverage.to_csv(out/'SCOPE_FOLD_COVERAGE.csv',index=False)
 evidence={'actual_commit':'972857b2b3f548316be215400e42d6ef6e639250','data_version':'v2','sources':[{'path':str(p.relative_to(root)) if p.is_relative_to(root) else str(p),'sha256':sha(p)} for p in [ledger,oldp,dp,wp]],'input_records':len(d),'scope_response_v2_n':int(d.scope_response_v2_original.notna().sum()),'recovered_historical_oos':int(rec.sum()),'scope_feature_response_n':int(d.scope_feature_response.notna().sum()),'deduplicated_opportunities':len(dedup),'scope_worker_n':d.worker_id.nunique(),'folds':len(folds),'rules':{'scope_response_not_correctness':True,'scope_recovery':'286 old oos strings have exact unique worker-image match and original questionnaire source; no conflict with an existing ledger response; derived auxiliary features only','centering':'train-side image×condition×origin mean; at least three observed responders; heldout building removed first','main_domain':'mean of supported ordinary Manual and Semi residual means; each needs eight images and three buildings','target_building_exclusion':'all supplied conditions removed before any fitting','missing':'unknown stays missing, not response zero','scope_gold':'93 opportunities and correctness remain source values, not used as general correctness classification','frozen_contract_unchanged':True}}
 (out/'PROVENANCE.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
 print(json.dumps({'input':len(d),'v2_scope':int(d.scope_response_v2_original.notna().sum()),'restored':int(rec.sum()),'total_scope':int(d.scope_feature_response.notna().sum()),'duplicate_opportunities_removed':len(d)-len(dedup),'all_supported':int(features.query("heldout_building == 'ALL'").scope_supported.sum())}))
if __name__=='__main__':main()
