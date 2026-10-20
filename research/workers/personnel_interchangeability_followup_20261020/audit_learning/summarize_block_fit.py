import json,hashlib
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.metrics import adjusted_rand_score
B=Path(__file__).resolve().parent;R=B.parent;O=B/'block_fit';man=json.load(open(O/'METHOD_MANIFEST.json'));folds=pd.read_csv(O/'fold_labels.csv');features=pd.read_csv(R/'unpacked/interchangeability_20261020/forward/features_train.csv.gz').set_index('worker_id');f=pd.read_csv(R/'audit_corner/history_block_metrics/COMMON_ENDPOINT_PAIRS.csv.gz',low_memory=False);f['distance']=.5*(f.bev_mean_pairscale+f.top_mean_pairscale);f.loc[~f.status.eq('unique_cyclic_candidate'),'distance']=np.nan
sens=[];profiles=[];support=[]
for mid,s in man.items():
 lab={w:c for c,ws in s['classes'].items() for w in ws}
 for fi,g in folds[folds.method_id.eq(mid)].groupby('fold'):
  sens.append({'method_id':mid,'fold':fi,'common_people':len(g),'ARI':adjusted_rand_score([lab[w] for w in g.worker_id],g.class_id)})
 for c,ws in s['classes'].items():
  x=features.loc[ws];row={'method_id':mid,'class_id':c,'members':'|'.join(ws),'workers':len(ws)}
  for k in ['q_beta','t_source_origin_effect','pair_count_effect','height_log_effect','bottom_y_effect']:row[k+'_mean']=x[k].mean()
  profiles.append(row)
 # Full-fit in-sample relation descriptions; never held-out performance.
 vectors=lambda col:col.map(lambda x:tuple(sorted(lab.get(w,'unknown') for w in x.split('|'))))
 a,b=vectors(f.left_workers),vectors(f.right_workers);same=a==b
 for vector,idx in a[same].groupby(a[same]).groups.items():
  v=f.loc[idx];support.append({'method_id':mid,'class_count_vector':'|'.join(vector),'description':'full_fit_training_descriptive_only','attempted':len(v),'valid':v.distance.notna().sum(),'images':v.pool_id.nunique(),'buildings':v.building.nunique(),'distance_mean':v.distance.mean(),'distance_p90':v.distance.quantile(.9),'distance_p95':v.distance.quantile(.95),'different_count_rate':v.different_count.mean(),'incomplete_rate':v.noncomplete.mean()})
pd.DataFrame(sens).to_csv(O/'label_sensitivity.csv',index=False);pd.DataFrame(sens).groupby('method_id').ARI.agg(['mean','min','max']).to_csv(O/'label_sensitivity_summary.csv');pd.DataFrame(profiles).to_csv(O/'class_profiles.csv',index=False);pd.DataFrame(support).to_csv(O/'class_vector_support_descriptive.csv',index=False)
freeze={'selection':'no_practical_winner; neither direct_m2 model improves Q or original_Rnew2 on heldout within/gap and structure','no_more_family_search':True,'source':'five heldout historical building folds only','methods':{m:{'classes':v['classes'],'unknown':v['unknown'],'membership_sha256':hashlib.sha256(json.dumps(sorted((w,c) for c,ws in v['classes'].items() for w in ws),separators=(',',':')).encode()).hexdigest()} for m,v in man.items()},'manifest_sha256':hashlib.sha256((O/'METHOD_MANIFEST.json').read_bytes()).hexdigest()}
(O/'FROZEN_NEGATIVE_SELECTION.json').write_text(json.dumps(freeze,indent=2))
cv=pd.read_csv(O/'inner_cv_summary.csv');cmp=pd.read_csv(O/'paired_summary.csv');lines=['# Direct m2 block learning: finite negative experiment','','## Result','','Neither registered candidate is a practical improvement over Q or the original Rnew2. Both slightly beat capacity-matched random labels, but have worse held-out within distance and separation than useful baselines; valid-distance coverage and verified count-change risk also worsen against Rnew2. No winner is nominated, and no additional search is undertaken.','','|Candidate|Within|Between−within|Within valid|Within count-change|Within incomplete|','|---|---:|---:|---:|---:|---:|']
for r in cv.itertuples():lines.append(f'|{r.method_id}|{r.within_distance:.6f}|{r.distance_gap:.6f}|{r.within_allanchors_valid_distance:.3%}|{r.within_allanchors_different_count:.3%}|{r.within_allanchors_incomplete:.3%}|')
lines+=['','|Candidate|Baseline|Δwithin (lower better)|Δgap (higher better)|Δvalid|Δcount-change|','|---|---|---:|---:|---:|---:|']
for r in cmp.itertuples():lines.append(f'|{r.method_id}|{r.baseline}|{r.delta_within_distance:.6f}|{r.delta_distance_gap:.6f}|{r.delta_within_allanchors_valid_distance:.3%}|{r.delta_within_allanchors_different_count:.3%}|')
lines+=['','These are equal-building held-out history estimates on exact common anchors. Conditional distance is .5(BEVmean+topmean)/pairscale; invalid distances never become zero. Structural rates use all-attempt observed common anchors. Random rows average40 fixed capacity permutations, not confidence intervals. Ten buildings limit uncertainty and generalization.','', '## Frozen membership and meaning','']
for mid,s in man.items():
 lines.append('### '+mid)
 for c,ws in s['classes'].items():lines.append('- '+c+': '+', '.join(ws))
lines+=['','All35 new-source workers are known;25 old-source workers remain outside this domain. These unsupported alternative memberships are archived for reproducibility, not recommended replacements for the existing conditional Rnew2 reference. Descriptive Q/T/geometry profiles and full-fit relation tails are separately labeled in-sample, not validation.','', '## Why this is genuinely block-level','', 'The learner compares the two-person class-count vectors of disjoint replacement blocks and uses their actual final-team geometry distance. It never substitutes summed single-person outcomes for a block outcome. Its fixed registered objective, two K values, two starts and30 accepted-move cap completed without outcome-driven amendments. Registration/design/native/metric hashes and full optimizer trace remain available.','', '## Stopping decision','', 'Preserve the negative legacy m1→m2 transfer and this independent history-only m2 result. Use the original conditional Rnew2 plus explicit Q/geometry/source/scope qualifications where its empirical domain supports it. There is no evidence here for a universally strong coarse/fine hierarchy. Additional learning would need a new scientific justification and a genuinely new evaluation plan rather than repeated optimization against the same assessment.']
(O/'BLOCK_LEARNING_REPORT.md').write_text('\n'.join(lines)+'\n')
print(pd.DataFrame(sens).groupby('method_id').ARI.mean().to_string())
