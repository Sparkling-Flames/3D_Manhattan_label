"""Read exact raw scope choices and retain protocol-specific adjudication.

The old, explicit task gold is not promoted wholesale to today's whole-space
policy. New batches and legitimate target alternatives do not acquire a binary
correctness label from geometry or from an accepted layout alone.
"""
import json,sys
from pathlib import Path
from functools import lru_cache
import pandas as pd
from paths import ROOT,REPO,OUT,STUDY
from tools.thesis_main.analysis.prescreen_scope_adjudication import _worker_scope

def save(name,x):
 if isinstance(x,pd.DataFrame):
  for c in x:
   if x[c].map(lambda v:isinstance(v,(dict,list))).any():x[c]=x[c].map(lambda v:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v)
  x.to_csv(OUT/name,index=False,encoding='utf-8-sig')
 else:(OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')

@lru_cache(None)
def raw_tasks(path):
 return {int(t['id']):t for t in json.loads((REPO/path.replace('\\','/')).read_text(encoding='utf-8-sig'))}

def outcome(gold,answer):
 if gold not in {'in_scope','oos'}:return 'task_judgement_unknown'
 if answer not in {'in_scope','oos'}:return 'response_unknown'
 return ('false_rejection' if gold=='in_scope' else 'false_acceptance') if gold!=answer else ('correct_acceptance' if gold=='in_scope' else 'correct_rejection')

def main():
 objects=json.loads((OUT/'validated_annotations.json').read_text())
 ledger=pd.read_csv(OUT/'reliability_object_ledger.csv').set_index('object_id').to_dict('index')
 old=pd.read_csv(REPO/'research/workers/worker_four_axis_update_20261015/scope_records.csv').fillna('')
 oldmap=old.set_index('object_id').to_dict('index')
 goldpath='analysis_results/prescreen_closeout_final_gold_v2_20260701/final_gold_records_v2_p1_closeout_corrected.jsonl'
 gold={r['base_task_id']:r for r in map(json.loads,(REPO/goldpath).read_text().splitlines())}
 expertpath='analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/prescreen_synthetic_expert_review.csv'
 expert=pd.read_csv(REPO/expertpath).fillna('').set_index('base_image_key').to_dict('index')
 diff={r['image_id']:r for r in json.loads((REPO/'research/quality/quality_b8l2_d10_20261017/difficulty_records.json').read_text())}
 laterholds={r['image_id']:r['later_hold'] for r in old.to_dict('records') if r['later_hold']}
 rows=[]
 for o in objects:
  s=o['source'];l=ledger[o['object_id']];d=diff[o['image_id']]
  path=s.get('selected_snapshot_path') or s['path']
  errors=[];raw='';answer='unknown';geom=None;taskdata={};rawchoices=[]
  try:
   task=raw_tasks(path)[int(s['task'])]; found=[a for a in task.get('annotations',[]) if int(a['id'])==int(s['annotation'])]
   assert len(found)==1,'annotation_identity_not_unique'
   a=found[0]; assert int(a['completed_by'])==int(s.get('source_account_id',o['worker_id'][1:])),'worker_identity_mismatch'
   taskdata=task.get('data',{})
   taskimage=taskdata.get('base_task_id') or taskdata.get('image_id')
   if taskimage:assert str(taskimage)==o['image_id'],'image_identity_mismatch'
   raw,answer,geom=_worker_scope(a)
   rawchoices=[r['value'].get('choices',[]) for r in a.get('result',[]) if r.get('type')=='choices' and r.get('from_name') in {'scope','worker_scope_response'}]
   explicit_new=[r['value'].get('choices',[]) for r in a.get('result',[]) if r.get('type')=='choices' and r.get('from_name')=='worker_scope_response']
   if explicit_new:
    vals=[v for x in explicit_new for v in x];raw=';'.join(vals)
    categories={'in_scope' if v in {'normal','in_scope'} else 'oos' if v=='out_of_scope' or v.startswith('oos') else 'unknown' for v in vals}
    answer=next(iter(categories)) if len(categories)==1 else 'ambiguous_multiple_scope_choices'
   if o.get('worker_scope_response') is not None:assert [v for x in rawchoices for v in x]==o['worker_scope_response'],'batch_scope_raw_mismatch'
  except Exception as ex:errors=[type(ex).__name__+':'+str(ex)];answer='source_binding_failed'
  r={k:o[k] for k in ['object_id','worker_id','image_id','image_code','building_id','condition','cleaning_disposition','independent_vote_eligible']}
  r.update(data_release='v1',raw_source_path=path,raw_project=s['project'],raw_task=s['task'],raw_annotation=s['annotation'],
   raw_binding_verified=not errors,raw_binding_errors=errors,raw_scope=raw,raw_scope_choices=rawchoices,worker_scope=answer,raw_geometry_present=geom,
   original_holdout=l['current_original_holdout'],source_verdict=l['source_verdict'],source_individually_reviewed=l['individually_reviewed_flag'],
   scene=d['scene'],oos_subtype=d['oos_subtype'],doorway_status=d['doorway_status'],current_difficulty=d['current_class'],
   current_gt_error_excluded=d.get('gt_error_excluded',False),current_scope_semantics=d.get('scope_semantics','unknown'),
   existing_scope_axis_1013=o['object_id'] in oldmap,raw_scope_recorded=bool(rawchoices),
   historical_task_gold='unknown',historical_gold_alias='',historical_gold_source='',historical_gold_ready=False,
   historical_later_hold=laterholds.get(o['image_id'],''))
  is_p1=s['project'] in {28,29,30,39,40,41}
  if is_p1:
   g=gold.get(o['image_id']);e=expert.get(o['image_id'])
   if e and int(s['task']) in {int(e['runtime_task_id']),int(e['mirror_task_id'])}:
    assert e['scope_gold_ready']
    r.update(historical_task_gold=e['expert_final_scope'],historical_gold_alias=e['expert_final_scope'],historical_gold_source=expertpath,historical_gold_ready=True)
   elif g and g.get('scope_gold_ready'):
    # Require a matching task contract, not merely a same-image lookup.
    assert str(taskdata.get('task_id'))==str(g['task_id']), (o['object_id'],'gold_task_contract_mismatch',taskdata.get('task_id'),g['task_id'])
    r.update(historical_task_gold=g['final_scope_binary'],historical_gold_alias=g['final_scope_alias'],historical_gold_source=goldpath,historical_gold_ready=True)
  if o['object_id'] in oldmap:
   oldr=oldmap[o['object_id']]
   assert answer==oldr['worker_scope'] and r['historical_task_gold']==oldr['final_scope'],(o['object_id'],'published_scope_disagreement')
  r['historical_eligible']=bool(r['historical_gold_ready'] and not r['historical_later_hold'])
  r['historical_outcome']=outcome(r['historical_task_gold'] if r['historical_eligible'] else 'unknown',answer)
  compatible_clear=(r['historical_eligible'] and r['historical_task_gold']=='in_scope' and d['scene']=='clear' and d['oos_subtype']=='not_oos')
  strict_oos=(r['historical_eligible'] and r['historical_task_gold']=='oos' and r['historical_gold_alias'] in {'oos_geometry','oos_split_level'} and d['scene']=='oos')
  r['current_clear_in_scope_adjudicated']=bool(compatible_clear)
  r['historical_representation_oos_narrow']=bool(strict_oos)
  r['current_compatible_target']='in_scope' if compatible_clear else 'unknown'
  r['current_compatible_outcome']=outcome(r['current_compatible_target'],answer)
  r['narrow_historical_representation_outcome']=outcome('oos' if strict_oos else 'unknown',answer)
  r['current_task_judgement_unknown']=not compatible_clear
  r['scope_context_key']=json.dumps([o['image_id'],o['condition'],'scope'],separators=(',',':'))
  rows.append(r)
 f=pd.DataFrame(rows)
 assert f.raw_binding_verified.all(),f.loc[~f.raw_binding_verified,['object_id','raw_binding_errors']].to_dict('records')
 assert f.existing_scope_axis_1013.sum()==1013
 save('scope_object_ledger.csv',f)
 wr=[]
 for w,g in f.groupby('worker_id'):
  p=dict(worker_id=w,n_inventory=len(g),n_raw_bound=int(g.raw_binding_verified.sum()),n_scope_choice_recorded=int(g.raw_scope_recorded.sum()),n_scope_response_unknown=int((~g.worker_scope.isin(['in_scope','oos'])).sum()),
   n_scope_no_task_gold=int((~g.historical_gold_ready).sum()),n_scope_later_hold=int(g.historical_later_hold.ne('').sum()),n_current_task_unknown=int(g.current_task_judgement_unknown.sum()))
  for name,subset,col in [('historical_manual_oos',g[g.condition.isin(['manual','oos'])&g.historical_eligible],'historical_outcome'),('historical_semi',g[g.condition.eq('semi')&g.historical_eligible],'historical_outcome'),('current_clear_manual',g[g.condition.eq('manual')&g.current_clear_in_scope_adjudicated],'current_compatible_outcome'),('current_clear_semi',g[g.condition.eq('semi')&g.current_clear_in_scope_adjudicated],'current_compatible_outcome'),('narrow_historical_representation_oos',g[g.historical_representation_oos_narrow],'narrow_historical_representation_outcome')]:
   p[name+'_opportunities']=len(subset);p[name+'_images']=subset.image_id.nunique();p[name+'_buildings']=subset.building_id.nunique()
   for v in ['false_rejection','false_acceptance','correct_acceptance','correct_rejection','response_unknown']:p[name+'_'+v]=int(subset[col].eq(v).sum())
   known=subset[col].isin(['false_rejection','false_acceptance','correct_acceptance','correct_rejection']);p[name+'_judged_responses']=int(known.sum())
  wr.append(p)
 save('worker_scope_summary.csv',pd.DataFrame(wr))
 scopes=f[f.historical_gold_ready].groupby(['image_id','condition']).first().reset_index()
 save('scope_task_adjudications.csv',scopes[['image_id','image_code','building_id','condition','historical_task_gold','historical_gold_alias','historical_gold_source','historical_later_hold','scene','oos_subtype','doorway_status','current_scope_semantics','current_clear_in_scope_adjudicated','historical_representation_oos_narrow']])
 receipt=dict(data_release='v1',inventory=len(f),raw_bound=int(f.raw_binding_verified.sum()),raw_scope_choices=int(f.raw_scope_recorded.sum()),raw_scope_answer=f.worker_scope.value_counts().to_dict(),old_1013_reproduced=True,
  historical_gold_rows=int(f.historical_gold_ready.sum()),historical_held=int(f.historical_later_hold.ne('').sum()),historical_eligible=int(f.historical_eligible.sum()),
  historical_outcomes=f.loc[f.historical_eligible,'historical_outcome'].value_counts().to_dict(),
  historical_by_condition={c:g.loc[g.historical_eligible,'historical_outcome'].value_counts().to_dict() for c,g in f.groupby('condition')},
  current_clear_in_scope_rows=int(f.current_clear_in_scope_adjudicated.sum()),current_clear_by_condition={c:g.loc[g.current_clear_in_scope_adjudicated,'current_compatible_outcome'].value_counts().to_dict() for c,g in f.groupby('condition')},
  narrow_representation_oos_rows=int(f.historical_representation_oos_narrow.sum()),narrow_representation_oos_outcomes=f.loc[f.historical_representation_oos_narrow,'narrow_historical_representation_outcome'].value_counts().to_dict(),
  limits=['Historical binary gold is original protocol-specific task adjudication, not a newly established current-policy label.','Only historical in-scope tasks compatible with current clear scene are current-compatible rejection opportunities.','Geometry/split-level OOS is a narrowly sourced historical diagnostic; open-boundary, insufficiency and policy ambiguity remain separate.','Legitimate multi-space choice is not an OOS error. New batch source scope choices do not receive gold labels from their geometry.','Inventory denominators retain historical exclusions and empty layouts; no vote eligibility changes.'])
 save('scope_recovery_receipt.json',receipt);print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
