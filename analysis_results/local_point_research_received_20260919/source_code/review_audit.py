"""Compare to raw reviewer fields. No automatic 'different detail' => mandatory whole-image split.
The older binary mapping is reproduced ONLY as a sensitivity, never used to tune new radii.
"""
import json
from pathlib import Path
import numpy as np,pandas as pd
import local_points as lp
R=lp.ROOT

def run():
 p=pd.read_csv(R/'results/pairwise.csv');pm={tuple(sorted([x.id_a,x.id_b])):x._asdict() for x in p.itertuples(index=False)}
 c=json.loads((R/'results/cache.json').read_text());rv=json.loads((R/'inputs/user12_review_original.json').read_text())
 mprev=pd.read_csv(R/'inputs/previous_user24_mapping.csv').set_index('key');out=[]
 for key,d in rv['decisions'].items():
  iid,cond,a,b=key.split('|');g=c[iid+'|'+cond];i,j=g['ids'].index(a),g['ids'].index(b);f=pm[tuple(sorted([a,b]))]
  row=dict(key=key,source='user12',**d,**f,previous_interpretation=mprev.loc[key,'category'])
  # Preserve distinct questions; no combined accuracy headline.
  row['similarity_explicit']=bool((d['Range']=='相近'and d['Detail']=='相近'and d['Position']=='接近')or d['Note']=='oos,但是他们标注确实很接近')
  row['different_coverage_reported']=d['Range']=='不同'
  row['detail_difference_reported']=d['Detail']=='有增减或不同表达'
  row['whole_image_split_explicit']=None
  for name,lab in g['labels'].items():row['cluster_'+name]=lab[i]==lab[j]
  out.append(row)
 d=pd.DataFrame(out);d.to_csv(R/'results/user24_multitarget_relations.csv',index=False)
 summ=[]
 for name in g['labels']:
  field='cluster_'+name
  si=d[d.similarity_explicit];di=d[d.previous_interpretation=='different_expression_or_cover'];cov=d[d.different_coverage_reported]
  summ.append(dict(method=name,explicit_near=len(si),near_together=int(si[field].sum()),old_mapping_different=len(di),old_mapping_separate=int((~di[field]).sum()),coverage_different=len(cov),coverage_separate=int((~cov[field]).sum())))
 pd.DataFrame(summ).to_csv(R/'results/user24_summary.csv',index=False)
 prev=pd.read_csv(R/'inputs/previous29_relations.csv');rows,audit=lp.load();idx={(audit.loc[r['canonical_annotation_id'],'code'],r['raw_condition'],r['worker_id']):r['canonical_annotation_id']for r in rows}
 oldout=[]
 for r in prev.to_dict('records'):
  a=idx[r['code'],r['condition'],r['worker_a']];b=idx[r['code'],r['condition'],r['worker_b']];f=pm[tuple(sorted([a,b]))];g=c[f['image_id']+'|'+r['condition']];i,j=g['ids'].index(a),g['ids'].index(b)
  row={**r,**f,'source':'previous_analyst29_not_user_gold'}
  for name,lab in g['labels'].items():row['cluster_'+name]=lab[i]==lab[j]
  oldout.append(row)
 pd.DataFrame(oldout).to_csv(R/'results/previous29_multimethod.csv',index=False)
 print(pd.DataFrame(summ).to_string(index=False))
 cols=['code','worker_a','worker_b','n_a','n_b','ospa1','hausdorff','bottleneck','cluster_OSPA1_6','cluster_Hausdorff_6','cluster_Hausdorff_9','cluster_Hausdorff_12','Note']
 print(d[cols].to_string(index=False))
 print('old29');print(pd.DataFrame(oldout)[['code','worker_a','worker_b','n_a','n_b','ospa1','hausdorff','bottleneck','cluster_OSPA1_6','cluster_Hausdorff_6','cluster_Hausdorff_9','cluster_Hausdorff_12','relation']].to_string(index=False))
if __name__=='__main__':run()
