#!/usr/bin/env python3
"""B8->D10 re-profile/re-partition sensitivity, fixed algorithm and candidate K."""
from pathlib import Path
import json
import pandas as pd
from explain_and_audit import pair_metrics
from atomic_exports import csv_verified

H=Path(__file__).resolve().parent
a=pd.read_csv(H/'candidate_classes_by_fold.csv.gz');b=pd.read_csv(H/'candidate_classes_by_fold_D10.csv.gz')
keys=['fold_id','method_id','difficulty','worker_id']
m=a.merge(b,on=keys,validate='one_to_one',suffixes=('_B8','_D10'))
assert len(m)==len(a)==len(b)
rows=[]
for (fold,method,diff),g in m.groupby(['fold_id','method_id','difficulty']):
    valid=g[g.class_id_B8.ne('unknown')&g.class_id_D10.ne('unknown')]
    rows.append({'fold_id':fold,'method_id':method,'difficulty':diff,'n_workers':len(g),'n_unknown_either':len(g)-len(valid),
                 **pair_metrics(valid.class_id_B8,valid.class_id_D10)})
csv_verified(pd.DataFrame(rows),H/'metric_partition_sensitivity.csv')
(H/'METRIC_SENSITIVITY_RECEIPT.json').write_text(json.dumps({'rows':len(rows),'worker_label_pairs':len(m),
    'fixed':['input records','reference','fusion','support gates','domain definitions','linkage','K range'],
    'changed':'B8 Q and difficulty effects/distribution -> D10, same metric-source evidence and no model selection by this sensitivity',
    'comparison':'pair coassignment/ARI, not literal fold class IDs','new_fusion':False},indent=2)+'\n')
print(len(rows))
