#!/usr/bin/env python3
"""Document actual baseline-vs-new history eligibility; no refit or rescoring."""
import json, hashlib
from pathlib import Path
import pandas as pd
W=Path(__file__).resolve().parents[2]
R=W.parent/'HOHONET_v21_20261029'
basepath=R/'research/data/releases/v2.1/condition_classification/RAW_CONDITION_RESPONSE_RECORDS.csv.gz'
newpath=W/'classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz'
b=pd.read_csv(basepath,low_memory=False); n=pd.read_csv(newpath,low_memory=False)
b['layer']=b['pool_layer'];b['scope']='primary'
rows=[]
for name,d in [('official_baseline20_common_history',b),('new_target_aware_forward13',n)]:
 g=d.groupby(['scope','condition','layer','history_eligible'],dropna=False).agg(records=('object_id','size'),images=('image_id','nunique'),buildings=('building','nunique'),workers=('worker_id','nunique')).reset_index()
 g.insert(0,'history_family',name);rows.append(g)
pd.concat(rows,ignore_index=True).to_csv(W/'stage02/BASELINE_NEW_HISTORY_SCOPE_COMPARISON.csv',index=False,encoding='utf-8-sig')
bids=set(b.loc[b.history_eligible,'object_id']);nids=set(n.loc[n.history_eligible,'object_id'])
bo=b[b.object_id.isin(bids-nids)].copy();bo.to_csv(W/'stage02/BASELINE_ONLY_SPECIAL_HISTORY_RECORDS.csv',index=False,encoding='utf-8-sig')
srcs=[basepath,newpath,R/'tools/thesis_main/analysis/refit_v21_condition_classes_20261028.py',R/'tools/thesis_main/analysis/refit_v21_scope_axes_20261028.py']
receipt={'baseline_eligible':len(bids),'new_eligible':len(nids),'shared_ordinary':len(bids&nids),'baseline_only_special':len(bids-nids),'new_only_admitted_other':len(nids-bids),'baseline_only_condition_counts':bo.groupby('condition').size().to_dict(),'baseline_only_images':bo.image_code.unique().tolist(),'baseline_rule':'non_doorway AND formal difficulty in easy/medium/hard; includes special_range auxiliary history','new_rule':'ordinary_manual/ordinary_semi legal target records; other target ungraded contributes general/opportunity only','scope_axes_note':'Official baseline scope and axis controls use the same condition-classification history, with scope domain separately appended','classification_unchanged':True,'pool_eligibility_unchanged':True,'source_files':[{'file':str(p.relative_to(R)) if R in p.parents else str(p.relative_to(W)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in srcs]}
(W/'stage02/BASELINE_NEW_HISTORY_SCOPE_CHECK.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False))
print(json.dumps(receipt,ensure_ascii=False))
