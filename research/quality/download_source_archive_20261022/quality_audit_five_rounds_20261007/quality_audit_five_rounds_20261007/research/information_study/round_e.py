"""Round E: consequence of conditional noncompensatory comparison, NOT a fusion rule.
Frozen experiment: no reference-derived change to saved outputs, eligibility or votes.
Tolerance/weights declared in code before inspecting E results.
"""
from round_d import *
import pandas as pd
from components import sample_polyline,segment_distances
LOSS={'L0':'iou','C':'centroid_distance_normalized','U':'top_mae_deg','D3':'top3d_symmetric_mean_h'}
TOLS={'strict':{'L0':.0001,'C':.0001,'U':.1,'D3':.01},'relaxed':{'L0':.01,'C':.005,'U':.25,'D3':.03}}
POLICIES=['IoU','LC','LCU_fixed','LCUD_fixed','LOBO_scale_sum','guard_angular_strict','guard_full_strict','guard_full_relaxed','guard_spatial_strict','guard_spatial_relaxed']
# Each policy's name identifies checked domain. Spatial-only never certifies upper angular tolerance.
NEEDED={'IoU':['L0'],'LC':['L0','C'],'LCU_fixed':['L0','C','U'],'LCUD_fixed':['L0','C','U','D3'],'LOBO_scale_sum':['L0','C','U','D3'],'guard_angular_strict':['L0','C','U'],'guard_full_strict':['L0','C','U','D3'],'guard_full_relaxed':['L0','C','U','D3'],'guard_spatial_strict':['L0','C','D3'],'guard_spatial_relaxed':['L0','C','D3']}
def finite(x):return x is not None and np.isfinite(x)
def loss(r):return {k:1-float(r.get(v,np.nan)) if k=='L0' else float(r.get(v,np.nan)) for k,v in LOSS.items()}
def choose(pool,anchor,policy,scales):
 req=NEEDED[policy]
 if any(not finite(anchor['loss'][k]) for k in req):return None,'abstain_anchor_metric_NA',0
 valid=[r for r in pool if all(finite(r['loss'][k]) for k in req)]
 if not valid:return None,'abstain_no_metric_complete_candidate',0
 if policy.startswith('guard'):
  tol=TOLS['relaxed' if policy.endswith('relaxed') else 'strict']
  feasible=[r for r in valid if all(r['loss'][k]-anchor['loss'][k]<=tol[k]+1e-12 for k in req)]
  # Require an actual LC improvement to propose a change; tolerance is not free permission to move.
  feasible=[r for r in feasible if r['id']==anchor['id'] or r['loss']['L0']+.5*r['loss']['C']<anchor['loss']['L0']+.5*anchor['loss']['C']-1e-12]
  selected=min(feasible,key=lambda r:(r['loss']['L0']+.5*r['loss']['C'],r['id']!=anchor['id'],r['id']))
  return selected,'propose_change' if selected['id']!=anchor['id'] else 'retain_anchor',len(feasible)
 def score(r):
  e=r['loss'];lc=e['L0']+.5*e.get('C',0)
  if policy=='IoU':return e['L0']
  if policy=='LC':return lc
  if policy=='LCU_fixed':return lc+.1*e['U']/2
  if policy=='LCUD_fixed':return lc+.1*e['U']/2+.1*e['D3']/.15
  return sum(e[k]/scales[k] for k in ['L0','C','U','D3'])
 selected=min(valid,key=lambda r:(score(r),r['id']!=anchor['id'],r['id']))
 return selected,'propose_change' if selected['id']!=anchor['id'] else 'retain_anchor',len(valid)

def main():
 raw=pd.read_csv(OUT/'D_full_panel_metrics.csv');original=raw[(raw.gate=='main_candidate')&(raw.reference_version=='original')].copy()
 for k,v in LOSS.items():original[k]=1-original[v] if k=='L0' else original[v]
 scales={};scale_rows=[]
 for building in raw.building.unique():
  train=original[original.building!=building];perim=train.groupby('image')[list(LOSS)].median()
  s={k:max(float(perim[k].median()),1e-8) for k in LOSS};scales[building]=s
  scale_rows.append({'heldout_building':building,'training_buildings':train.building.nunique(),'training_images':train.image.nunique(),'calibration_method':'median of image medians; original references; no test building; no labels',**s})
 csvout('E_lobo_calibration_scales.csv',scale_rows)
 cm=pd.read_csv(SRC/'results/correction_metrics.csv');met=pd.read_csv(SRC/'results/metrics.csv')
 pools=[];attempts=[]
 for (im,sid),g in cm.groupby(['image','source_id'],sort=False):
  first=g.iloc[0];entry={'experiment':'projection','image':im,'source_id':sid,'panel':first.panel,'building':first.building,'source_eligible':bool(first.source_eligible),'attempt_status':first.status}
  attempts.append(entry)
  if first.status!='ok' or not first.source_eligible:continue
  for version,vgroup in g.groupby('version'):
   first=vgroup.iloc[0];anchor={'id':sid,'role':'original_anchor','loss':{k:(1-first['before_'+v] if k=='L0' else first['before_'+v]) for k,v in LOSS.items()},'alpha':0}
   pool=[anchor]
   for _,r in vgroup.iterrows():pool.append({'id':r.derived_id,'role':'projection','alpha':r.alpha,'loss':{k:(1-r['after_'+v] if k=='L0' else r['after_'+v]) for k,v in LOSS.items()}})
   pools.append({'experiment':'projection','image':im,'building':first.building,'source_id':sid,'panel':first.panel,'reference_version':version,'pool':pool,'anchor':anchor})
 # Sequential follow-on: apply unchanged policies to the newly tested continuous-boundary fit from C.
 c_path=DENSITY/'round_c_reference_comparisons.csv'
 if not c_path.exists():raise FileNotFoundError('Round C results required for sequential E: '+str(c_path))
 cmet=pd.read_csv(c_path);cstatus=pd.read_csv(DENSITY/'round_c_fit_status.csv')
 for _,r in cstatus[cstatus.method=='continuous_boundary'].iterrows():
  attempts.append({'experiment':'new_continuous_projection','image':r.image,'source_id':r.expression_id,'panel':r.source_panel,'building':r.building,'attempt_status':r.status})
 for _,r in cmet[cmet.method=='continuous_boundary'].iterrows():
  anchor={'id':r.expression_id,'role':'original_anchor','loss':{k:(1-r['before_'+v] if k=='L0' else r['before_'+v]) for k,v in LOSS.items()},'alpha':0}
  alternate={'id':r.expression_id+'__continuous_boundary','role':'continuous_projection','loss':{k:(1-r['after_'+v] if k=='L0' else r['after_'+v]) for k,v in LOSS.items()},'alpha':1}
  pools.append({'experiment':'new_continuous_projection','image':r.image,'building':r.building,'source_id':r.expression_id,'panel':r.source_panel,'reference_version':r.reference_version,'pool':[anchor,alternate],'anchor':anchor})
 # Five frozen full candidates and a deterministic original anchor. No GT enters anchor choice.
 states=json.loads((SRC/'inputs/candidates.json').read_text())['states']
 for state in states:attempts.append({'experiment':'fusion','image':state['image'],'route':state['route'],'attempt_status':state['result'].get('status'),'has_complete_points':bool((state['result'].get('candidate') or {}).get('points'))})
 panel=json.loads((SRC/'inputs/panel.json').read_text())['images'];ims={im['code']:im for im in panel}
 for image in sorted(set(s['image'] for s in states)):
  im=ims[image];answers=sorted([a for a in im['annotations'] if eligible(a)],key=lambda r:r['id'])
  if not answers:continue
  sid=answers[0]['id'];g=met[met.image==image]
  for version,vgroup in g.groupby('reference_version'):
   ar=vgroup[vgroup.id==sid]
   if len(ar)!=1:continue
   r=ar.iloc[0];anchor={'id':sid,'role':'original_anchor','loss':loss(r),'alpha':0};pool=[anchor]
   for _,r in vgroup[vgroup.kind=='fusion'].iterrows():pool.append({'id':r.id,'role':'fusion','route':r.route,'loss':loss(r)})
   pools.append({'experiment':'fusion','image':image,'building':im['building'],'source_id':sid,'panel':r.panel,'reference_version':version,'pool':pool,'anchor':anchor})
   paired_anchor=next((x for x in pool if x.get('route')=='paired'),None)
   if paired_anchor is not None:
    pools.append({'experiment':'fusion_paired_anchor','image':image,'building':im['building'],'source_id':paired_anchor['id'],'panel':r.panel,'reference_version':version,'pool':pool,'anchor':paired_anchor})
 # Named observations: no semantic truth is inferred from the path itself.
 specs=json.loads((SRC/'results/local_paths.json').read_text());objects=json.loads((SRC/'results/objects.json').read_text());lookup={o['id']:o['record'] for o in objects}
 localrows=[]
 for spec in specs:
  im=ims[spec['image']];anchorrec=lookup[spec['source']];at,ab=paired_wall_proxy(anchorrec);path=at[spec['indices']];q,_,_,L=sample_polyline(path,2048,closed=False)
  records=[anchorrec]+[lookup[x] for x in spec['compare'] if x in lookup and '__paired' not in x]+[lookup[x] for x in lookup if x.startswith(im['code']+'__')]
  for ref in im['references']:
   pool=[]
   for a in records:
    m=compare(a,ref);top,_=paired_wall_proxy(a);local=float(segment_distances(q,top).mean())
    c={'id':a['id'],'role':'named_observation_or_frozen_candidate','loss':loss(m),'local_observed_path_mean_h':local};pool.append(c)
    localrows.append({'image':im['code'],'reference_version':ref['version'],'id':a['id'],'observation_source':spec['source'],'observation_description':spec['target'],'local_path_is_GT':False,'required_structure_status':'not_inferred','local_observed_path_mean_h':local,**{k:v for k,v in c['loss'].items()}})
   anchor=next(r for r in pool if r['id']==spec['source'])
   pools.append({'experiment':'local_observation','image':im['code'],'building':im['building'],'source_id':spec['source'],'panel':'named_local_witness','reference_version':ref['version'],'pool':pool,'anchor':anchor})
 csvout('E_attempt_denominators.csv',attempts);csvout('E_named_local_comparisons.csv',localrows)
 decisions=[]
 for p in pools:
  anchor=p['anchor']
  for policy in POLICIES:
   selected,status,n=choose(p['pool'],anchor,policy,scales[p['building']]);row={k:p[k] for k in ['experiment','image','building','source_id','panel','reference_version']}
   row.update(policy=policy,status=status,all_alternatives=len(p['pool'])-1,eligible_policy_candidates=n,selected_id=None if selected is None else selected['id'],selected_alpha=None if selected is None else selected.get('alpha'),target_compatibility='known_accepted_alternative_targets_no_common_quality_order' if p['experiment']=='local_observation' and p['image']=='X7HyMhZNoso-19' else 'unknown_not_certified',semantic_quality_label=None)
   for k in LOSS:
    row['anchor_'+k]=anchor['loss'][k]
    row['selected_'+k]=np.nan if selected is None else selected['loss'][k]
    row['delta_'+k]=np.nan if selected is None else selected['loss'][k]-anchor['loss'][k]
    row['strict_regression_'+k]=None if selected is None or not finite(row['delta_'+k]) else bool(row['delta_'+k]>TOLS['strict'][k]+1e-12)
   if selected is not None:
    row['selected_local_observed_path_mean_h']=selected.get('local_observed_path_mean_h')
    row['all_four_comparable']=all(finite(row['delta_'+k]) for k in LOSS)
    row['any_strict_regression']=any(row['strict_regression_'+k] is True for k in LOSS) if row['all_four_comparable'] else None
   decisions.append(row)
 dec=pd.DataFrame(decisions);dec.to_csv(OUT/'E_policy_decisions.csv',index=False,encoding='utf-8-sig')
 summaries=[]
 subsets={'all':np.ones(len(dec),dtype=bool),'broad':dec.panel=='broad'}
 for subset,mask in subsets.items():
  for (exp,version,policy),g in dec[mask].groupby(['experiment','reference_version','policy']):
   decided=g[g.selected_id.notna()];changed=decided[decided.status=='propose_change'];full=changed[changed.all_four_comparable==True]
   out={'subset':subset,'experiment':exp,'reference_version':version,'policy':policy,'pools':len(g),'images':g.image.nunique(),'buildings':g.building.nunique(),'decided':len(decided),'abstain_metric_NA':len(g)-len(decided),'propose_change':len(changed),'retain_anchor':int((decided.status=='retain_anchor').sum()),'changed_all_four_comparable':len(full),'changed_any_strict_regression':int((full.any_strict_regression==True).sum())}
   for k in LOSS:
    out['changed_'+k+'_measurable']=int(changed['delta_'+k].notna().sum());out['changed_'+k+'_strict_regressions']=int((changed['strict_regression_'+k]==True).sum())
    # Image-equal delta among decisions, including unchanged anchors.
    out['image_equal_delta_'+k]=float(decided.groupby('image')['delta_'+k].mean().mean()) if decided['delta_'+k].notna().any() else np.nan
   summaries.append(out)
 csvout('E_policy_summary.csv',summaries)
 # Paired-reference decisions, no best-reference substitution.
 pair=dec[dec.reference_version=='original'].merge(dec[dec.reference_version=='manual_revision'],on=['experiment','image','source_id','policy'],suffixes=('_original','_revision'))
 pair['both_decided']=pair.selected_id_original.notna()&pair.selected_id_revision.notna();pair['decision_changed']=pair.both_decided&(pair.selected_id_original!=pair.selected_id_revision)
 pair.to_csv(OUT/'E_reference_policy_reversals.csv',index=False,encoding='utf-8-sig')
 rev=pair.groupby(['experiment','policy']).agg(paired_pools=('image','size'),both_decided=('both_decided','sum'),decision_changed=('decision_changed','sum')).reset_index();rev.to_csv(OUT/'E_reference_reversal_summary.csv',index=False,encoding='utf-8-sig')
 # Extra effect of 3D guard versus already including angular guard: exact same anchor and tolerance.
 ga=dec[dec.policy=='guard_angular_strict'];gf=dec[dec.policy=='guard_full_strict'];ab=ga.merge(gf,on=['experiment','image','source_id','reference_version'],suffixes=('_angular','_full'))
 ab['threeD_changes_choice']=ab.selected_id_angular.notna()&ab.selected_id_full.notna()&(ab.selected_id_angular!=ab.selected_id_full)
 ab.to_csv(OUT/'E_incremental_3d_guard.csv',index=False,encoding='utf-8-sig')
 # Absolute four-component Pareto frontier is a diagnostic, not an output-producing fusion.
 fronts=[]
 for p in pools:
  valid=[r for r in p['pool'] if all(finite(r['loss'][k]) for k in LOSS)]
  nondom=[]
  for r in valid:
   dominated=any(all(s['loss'][k]<=r['loss'][k]+1e-10 for k in LOSS) and any(s['loss'][k]<r['loss'][k]-1e-10 for k in LOSS) for s in valid)
   if not dominated:nondom.append(r['id'])
  fronts.append({k:p[k] for k in ['experiment','image','source_id','reference_version']}|{'pool_size':len(p['pool']),'four_metric_complete':len(valid),'pareto_size':len(nondom),'pareto_distinct_loss_vectors':len({tuple(round(r['loss'][k],10) for k in LOSS) for r in valid if r['id'] in nondom}),'pareto_ids':'|'.join(nondom)})
 csvout('E_pareto_fronts.csv',fronts)
 frozen={'question':'What tradeoffs do scalar losses conceal when choosing among already fixed complete proposals, and what does a four-component noncompensatory guard add?','stopping_condition':'Evaluate all listed fixed policies and two stated tolerance settings, preserve all attempt/NA denominators and both reference versions; do not search new thresholds or weights after results.','not_deployment':'No selected result replaces source annotations or saved fusion; unknown target compatibility cannot become semantic acceptance.','fusion_anchor_definition':'Primary: lexicographically first eligible original ID, a deliberately arbitrary diagnostic anchor, not a user-endorsed operational baseline. Sensitivity: fixed paired-route candidate, same alternative pool. Neither selects the actual fusion output.','fixed_scalar_weights':{'centroid':.5,'upper_mae_per_degree':.05,'top3d_per_h':.1/.15},'tolerances':TOLS,'calibration':'Original-reference main-candidate manual records from D; each held-out building excluded; per-image medians then median across training images; no outcome labels or test optimization.','required_local_structure':'Observed named paths are not GT; necessary/optional semantic status is not inferred; path drift is descriptive.','policies':POLICIES}
 dump('E_experiment_definition.json',frozen)
 stats={'projection_attempts':sum(a['experiment']=='projection' for a in attempts),'projection_eligible_attempts':sum(a['experiment']=='projection' and a['source_eligible'] for a in attempts),'projection_success_eligible':sum(a['experiment']=='projection' and a['source_eligible'] and a['attempt_status']=='ok' for a in attempts),'frozen_fusion_attempts':sum(a['experiment']=='fusion' for a in attempts),'frozen_fusion_complete':sum(a['experiment']=='fusion' and a['has_complete_points'] for a in attempts),'projection_original_pools':sum(p['experiment']=='projection' and p['reference_version']=='original' for p in pools),'fusion_original_pools':sum(p['experiment']=='fusion' and p['reference_version']=='original' for p in pools),'new_continuous_attempts':sum(a['experiment']=='new_continuous_projection' for a in attempts),'new_continuous_success_pools':sum(p['experiment']=='new_continuous_projection' and p['reference_version']=='original' for p in pools),'full_guard_different_from_angular_guard':ab[ab.threeD_changes_choice].groupby(['experiment','reference_version']).size().to_dict()}
 stats['full_guard_different_from_angular_guard']={str(k):int(v) for k,v in stats['full_guard_different_from_angular_guard'].items()};dump('E_summary.json',stats);print(json.dumps(stats,ensure_ascii=False,indent=2))
 print(pd.DataFrame(summaries).query("subset=='broad' and experiment=='projection' and reference_version=='original'")[['policy','pools','decided','abstain_metric_NA','propose_change','changed_all_four_comparable','changed_any_strict_regression','changed_U_strict_regressions','changed_D3_strict_regressions']].to_string(index=False))
 print('LOCAL',dec[dec.experiment=='local_observation'][['image','reference_version','policy','status','selected_id','selected_local_observed_path_mean_h']].to_string(index=False))
if __name__=='__main__':main()
