from round_d import *
import pandas as pd
from round_e import LOSS
p=pd.read_csv(OUT/'E_policy_decisions.csv');base=p[(p.policy=='guard_full_strict')&p.selected_id.notna()][['experiment','image','source_id','reference_version']]
c=p.merge(base,on=['experiment','image','source_id','reference_version'],how='inner')
rows=[]
for (experiment,version,policy),g in c.groupby(['experiment','reference_version','policy']):
 out={'experiment':experiment,'reference_version':version,'policy':policy,'same_anchor_four_metric_domain_pools':len(g),'images':g.image.nunique(),'propose_change':int((g.status=='propose_change').sum()),'selected_four_metric_complete':int((g.all_four_comparable==True).sum())}
 for k in LOSS:
  out['image_equal_delta_'+k]=float(g.groupby('image')['delta_'+k].mean().mean());out['strict_regression_'+k]=int((g['strict_regression_'+k]==True).sum())
 rows.append(out)
csvout('E_common_domain_summary.csv',rows)
# Per-building readout for scale-calibrated sum vs the frozen fixed scalar and guard, same-domain only.
b=[]
for (experiment,version,policy,building),g in c.groupby(['experiment','reference_version','policy','building']):
 out={'experiment':experiment,'reference_version':version,'policy':policy,'building':building,'pools':len(g),'propose_change':int((g.status=='propose_change').sum()),'any_strict_regression':int((g.any_strict_regression==True).sum())}
 for k in LOSS:out['image_equal_delta_'+k]=float(g.groupby('image')['delta_'+k].mean().mean())
 b.append(out)
csvout('E_building_heldout_results.csv',b)
print(pd.DataFrame(rows).query("experiment=='new_continuous_projection' and reference_version=='original'").to_string(index=False))
