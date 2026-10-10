"""Finite extensions of unchanged Pro componentwise staged-alpha function."""
import copy,importlib.util,sys,itertools
from pathlib import Path
from collections import defaultdict,Counter
from common import read,save,csvwrite
from penalty_enumeration import root,THRESHOLDS
ROOT=Path(__file__).resolve().parents[1]
def main():
 config=read(ROOT/'frozen/Pro_selected_original/experiments/preregistered_candidates.json')
 spec=importlib.util.spec_from_file_location('frozen_pro_scalar',ROOT/'frozen/Pro_selected_original/experiments/run_quality.py');pro=importlib.util.module_from_spec(spec);spec.loader.exec_module(pro)
 import csv
 policy={r['record_id']:r for r in csv.DictReader(open(ROOT/'results/Pro_policy_membership_current.csv',encoding='utf-8-sig'))}
 alignment={r['record_id']:r for r in read(ROOT/'results/target_alignment_ledger.json')}
 rows=[r for r in read(ROOT/'results/current_components.json') if r['current_Q_status']=='available'];groups=defaultdict(list)
 for i,r in enumerate(rows):groups[r['image_code']].append(i)
 pairs=[(i,j) for ids in groups.values() for i,j in itertools.combinations(ids,2)]
 scores=[];bands=[];roots=[];flips=[];summaries=[]
 for start,end in itertools.product([1,1.5,2],[3,4]):
  family=f'Pro_componentwise_stage_start{start}_end{end}';coeffs=[]
  for r in rows:
   m={'iou':r['iou_2d'],'S_top_deg':r['S_top_deg'],'S_bottom_deg':r['S_bottom_deg'],'dir':r['dir'],'flat':r['flat'],'Hstar':r['Hstar']}
   def value(gamma):
    conf=copy.deepcopy(config);conf['variants']=[{'name':'probe','type':'componentwise_continuous_alpha','alpha_min':.15,'alpha_max':.15+gamma,'start_loss_units':start,'end_loss_units':end}];return pro.variant_scores(m,conf)['probe']
   intercept=value(0);slope=(intercept-value(.6))/.6;assert abs(intercept-r['Q'])<1e-9;coeffs.append((intercept,slope))
   for threshold in THRESHOLDS:bands.append({'family':family,'record_id':r['record_id'],'image_code':r['image_code'],'worker_id':r['worker_id'],'threshold':threshold,'threshold_kind':'historical' if threshold in [95,85,50] else 'unapproved_explanatory',**root(intercept,slope,threshold,0,.6)})
   for gamma in [.15,.3,.45,.6]:
    candidate=intercept-gamma*slope;direct=value(gamma);assert abs(candidate-direct)<1e-9
    scores.append({'family':family,'start_loss_units':start,'end_loss_units':end,'gamma':gamma,'alpha_max':.15+gamma,'record_id':r['record_id'],'image_code':r['image_code'],'worker_id':r['worker_id'],'Q_candidate':candidate,'Q_v11':r['Q'],'delta':candidate-r['Q'],'original_Pro_variant':'Q_stage13' if start==1 and end==3 and gamma==.3 else 'Q_stage24' if start==2 and end==4 and gamma==.3 else 'finite_unapproved_extension'})
  for i,j in pairs:
   a,b=rows[i],rows[j];ai,as_=coeffs[i];bi,bs=coeffs[j];rt=root(ai-bi,as_-bs,0,0,.6)
   record={'family':family,'image_code':a['image_code'],'record_1':a['record_id'],'record_2':b['record_id'],'worker_1':a['worker_id'],'worker_2':b['worker_id'],'Pro_target_1725_pair':all(policy[x['record_id']]['target_aligned_quality_candidate']=='True' for x in [a,b]),'strict_1059_pair':all(alignment[x['record_id']]['target_unconfounded_conservative'] for x in [a,b]),**rt};roots.append(record)
   for gamma in [.15,.3,.45,.6]:
    if (a['Q']-b['Q'])*((ai-gamma*as_)-(bi-gamma*bs)) < -1e-12:flips.append({**record,'gamma':gamma,'alpha_max':.15+gamma,'Q1':ai-gamma*as_,'Q2':bi-gamma*bs})
  for gamma in [.15,.3,.45,.6]:
   selected=[r for r in scores if r['family']==family and r['gamma']==gamma]
   for population in ['math3021','reference_quality2003','Manhattan_diagnostic1980','Pro_target_quality1725','Pro_target_primary1724','conservative_target1059']:
    def accept(r):
     p=policy[r['record_id']]
     return True if population=='math3021' else p['conservative_fixed_gt_quality_candidate']=='True' if population=='reference_quality2003' else alignment[r['record_id']]['main_Manhattan_comparison'] if population=='Manhattan_diagnostic1980' else p['target_aligned_quality_candidate']=='True' if population=='Pro_target_quality1725' else p['target_aligned_primary_candidate']=='True' if population=='Pro_target_primary1724' else alignment[r['record_id']]['target_unconfounded_conservative']
    for severity in ['all','mild_Dle5_Fle2','severe_Dge10','other']:
     lookup={r['record_id']:r for r in rows}
     def sev(r):
      g=lookup[r['record_id']];return 'mild_Dle5_Fle2' if g['dir']<=5 and g['flat']<=2 else 'severe_Dge10' if g['dir']>=10 else 'other'
     selectedpop=[r for r in selected if accept(r) and (severity=='all' or sev(r)==severity)];changed=[r for r in selectedpop if abs(r['delta'])>1e-10];ids={r['record_id'] for r in selectedpop};fs=[r for r in flips if r['family']==family and r['gamma']==gamma and r['record_1'] in ids and r['record_2'] in ids]
     summaries.append({'family':family,'alpha_max':.15+gamma,'gamma':gamma,'population':population,'severity_group':severity,'n_records':len(selectedpop),'n_changed_records':len(changed),'n_changed_images':len({r['image_code'] for r in changed}),'n_changed_workers':len({r['worker_id'] for r in changed}),'mean_delta':sum(r['delta'] for r in selectedpop)/len(selectedpop) if selectedpop else None,'threshold_crossings':{str(t):sum((r['Q_v11']>=t)!=(r['Q_candidate']>=t) for r in selectedpop) for t in THRESHOLDS},'n_pair_flips':len(fs),'n_flip_images':len({r['image_code'] for r in fs}),'n_flip_workers':len({r[k] for r in fs for k in ['worker_1','worker_2']})})
 csvwrite(ROOT/'results/Pro_stage_finite_scores.csv',scores);csvwrite(ROOT/'results/Pro_stage_band_roots.csv',bands);csvwrite(ROOT/'results/Pro_stage_same_image_pair_roots.csv',roots);csvwrite(ROOT/'results/Pro_stage_rank_flips.csv',flips);csvwrite(ROOT/'results/Pro_stage_group_summaries.csv',summaries)
 result={'finite_stage_candidates':24,'original_stage13_stage24_preserved':True,'additional_extra_beta_grid_kept_separate':True,'scores':len(scores),'band_roots':len(bands),'pair_roots':len(roots),'rank_flip_rows':len(flips),'all_math_records':len(rows),'no_final_parameter_or_band_selected':True,'analytic_roots_and_frozen_function_checks_passed':True};save(ROOT/'results/Pro_stage_enumeration_summary.json',result);print(result)
if __name__=='__main__':main()
