"""Frozen v2 descriptive balanced-person x view sums-of-squares decomposition.

Uses original declarations and observed full common-worker panels. It is a
sample composition, not a causal decomposition or prediction accuracy. No
new same-room edge is inferred: every pair in each reported comparable panel
is explicitly checked against the original relation registry.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'source';OUT=ROOT/'stage02_same_room/prediction'
original=json.loads((SRC/'research/same_room/relation_adoption_20261016/original_groups.json').read_text());rels=json.loads((SRC/'research/same_room/relation_adoption_20261016/relations.json').read_text());rm={tuple(sorted([r['image_a'],r['image_b']])):r for r in rels}
import itertools
old=pd.read_csv(OUT/'V2_FORMAL_RECORDS.csv.gz');current=pd.read_csv(OUT/'CURRENT_FORMAL_RECORDS.csv.gz');oldids=set(old.object_id)
scenarios={'v2_frozen':old,'v21_on_v2_records':current[current.object_id.isin(oldids)],'v21_all':current}
summaries=[];allparts=[];indices=[];matrices=[]
for scenario,d in scenarios.items():
    for og in original:
        images=og['image_ids'];gid=og['review_code']
        for condition in ['manual','semi']:
            for layer in ['ordinary','doorway']:
                x=d[d.image_id.isin(images)&d.condition.eq(condition)&d.layer.eq(layer)]
                if x.image_id.nunique()<2:continue
                present=sorted(x.image_id.unique());rr=[rm.get(tuple(sorted(pair)),{}) for pair in itertools.combinations(present,2)]
                scope=all(r.get('scope_comparable',False) for r in rr);direct=all(r.get('physical_adopted',False) for r in rr);conflict=any(r.get('substantive_conflict',False) for r in rr);pending=any(r.get('oos_pending',False) for r in rr)
                for metric in ['B8L2','D10']:
                    p=x.pivot(index='worker_id',columns='image_id',values=metric).dropna();meta=dict(scenario=scenario,group=gid,condition=condition,layer=layer,metric=metric,building=x.building_id.iloc[0],n_declared=len(images),n_observed=len(present),n_common=len(p),scope_comparable=scope,direct_complete=direct,substantive_conflict=conflict,relation_oos_pending=pending,images='|'.join(present))
                    indices.append(meta)
                    if len(p)<3 or p.shape[1]<2:continue
                    q=p.to_numpy();gm=q.mean();we=q.mean(1)-gm;ve=q.mean(0)-gm;interaction=q-gm-we[:,None]-ve[None,:];sst=np.square(q-gm).sum();ssw=q.shape[1]*np.square(we).sum();ssv=q.shape[0]*np.square(ve).sum();ssi=np.square(interaction).sum();assert abs(ssw+ssv+ssi-sst)<1e-8*max(1,sst)
                    row={**meta,'n_views':p.shape[1],'mean':gm,'view_mean_range':np.ptp(q.mean(0)),'worker_share':ssw/sst if sst else np.nan,'view_share':ssv/sst if sst else np.nan,'interaction_share':ssi/sst if sst else np.nan,'interaction_rms':np.sqrt(np.mean(interaction**2)),'total_ss':sst,'worker_ss':ssw,'view_ss':ssv,'interaction_ss':ssi};allparts.append(row)
                    x=x.set_index(['worker_id','image_id'],drop=False)
                    for wi,w in enumerate(p.index):
                        for vi,im in enumerate(p.columns):
                            rr=x.loc[w,im];matrices.append(dict(scenario=scenario,group=gid,condition=condition,layer=layer,metric=metric,building=rr.building_id,worker_id=w,image_id=im,image_code=rr.image_code,object_id=rr.object_id,reference_id=rr.reference_id,reference_version=rr.reference_version,Q=q[wi,vi],view_mean=q[:,vi].mean(),worker_effect=we[wi],view_effect=ve[vi],interaction=interaction[wi,vi]))
                    x=x.reset_index(drop=True)
part=pd.DataFrame(allparts);index=pd.DataFrame(indices);matrix=pd.DataFrame(matrices)
for (scenario,metric),d in part.groupby(['scenario','metric']):
    d=d[d.condition.eq('manual')&d.layer.eq('ordinary')&d.scope_comparable&d.direct_complete&~d.substantive_conflict]
    for scope in ['legacy_combined','ordinary_no_relation_oos_pending','relation_oos_pending']:
        z=d if scope=='legacy_combined' else d[d.relation_oos_pending.eq(scope=='relation_oos_pending')]
        mm=matrix[matrix.scenario.eq(scenario)&matrix.metric.eq(metric)&matrix.condition.eq('manual')&matrix.layer.eq('ordinary')&matrix.group.isin(z.group)]
        fields=['worker_share','view_share','interaction_share','interaction_rms','view_mean_range'];b=z.groupby('building')[fields].mean();summaries.append(dict(scenario=scenario,scope=scope,metric=metric,groups=len(z),buildings=len(b),images=mm.image_id.nunique(),people=mm.worker_id.nunique(),unique_answers=mm.object_id.nunique(),matrix_cells=len(mm),**{'building_equal_'+c:b[c].mean() for c in fields}))
for obj,name in [(part,'DECLARATION_VARIATION_PARTITION.csv'),(index,'DECLARATION_VARIATION_SUPPORT.csv'),(pd.DataFrame(summaries),'DECLARATION_VARIATION_SUMMARY.csv')]:obj.to_csv(OUT/name,index=False)
matrix.to_csv(OUT/'DECLARATION_COMMON_MATRIX.csv.gz',index=False,compression={'method':'gzip','compresslevel':3,'mtime':0})
print(pd.DataFrame(summaries).query("metric=='B8L2' and scope=='ordinary_no_relation_oos_pending'").to_string(index=False))
