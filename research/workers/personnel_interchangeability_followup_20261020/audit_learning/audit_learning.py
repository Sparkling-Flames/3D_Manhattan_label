import os
for k in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']: os.environ[k]='1'
import sys,json,hashlib
from pathlib import Path
import pandas as pd,numpy as np
from sklearn.metrics import adjusted_rand_score
ROOT=Path(__file__).resolve().parents[1]; P=ROOT/'unpacked'; S=P/'interchangeability_20261020'; OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(S/'forward'))
import build_candidates as bc
f=pd.read_csv(S/'forward/features_train.csv.gz'); catalog=bc.define_candidates(f)
a=pd.DataFrame(catalog.rows); b=pd.read_csv(S/'forward/worker_labels.csv.gz'); keys=['method_id','worker_id']
a=a.sort_values(keys).reset_index(drop=True); b=b.sort_values(keys).reset_index(drop=True)
cols=['method_id','worker_id','class_id','known','eligible_population','reason','domain','train_key','origin']
checks={c:bool(a[c].equals(b[c])) for c in cols}
assert all(checks.values()),checks
manifest=json.loads((S/'forward/method_manifest.json').read_text())['methods']
assert all(catalog.methods[m]['partition_sha256']==manifest[m]['partition_sha256'] for m in manifest)
re={'feature_shape':list(f.shape),'forward_methods':len(catalog.methods),'forward_label_rows':len(a),'forward_columns_equal':checks,'forward_partitions_exact':True}
# recompute LOBO ARI directly from saved raw labels rather than reported summary
lo=pd.read_csv(S/'forward/HISTORY_LOBO_labels.csv.gz'); fixed=b[b.known].set_index(['method_id','worker_id']); rows=[]
for (mid,held),g in lo.groupby(['method_id','removed_history_building']):
    orig=fixed.loc[mid]; other=g[g.known].set_index('worker_id'); common=sorted(set(orig.index)&set(other.index))
    ari=adjusted_rand_score(orig.loc[common,'class_id'],other.loc[common,'class_id']) if len(common)>=2 else np.nan
    rows.append(dict(method_id=mid,removed_history_building=held,ARI=ari,common_people=len(common),lost_people=len(set(orig.index)-set(other.index)),gained_people=len(set(other.index)-set(orig.index))))
res=pd.DataFrame(rows); reported=pd.read_csv(S/'forward/HISTORY_LOBO_per_fold.csv'); joined=res.merge(reported,on=['method_id','removed_history_building'],suffixes=('_ind','_report'))
assert np.allclose(joined.ARI_ind,joined.ARI_report,equal_nan=True,atol=1e-12)
res.to_csv(OUT/'forward_lobo_recomputed.csv',index=False)
re['forward_lobo_rows_recomputed']=len(res)
# reverse manifest counts/member labels independent checks
reverse={}
for family in ['legacy','mixed']:
    d=S/'reverse'/f'{family}_fit'; man=json.loads((d/'METHOD_MANIFEST.json').read_text()); lab=pd.read_csv(d/'worker_labels.csv.gz',keep_default_na=False)
    mismatches=[]
    for mid,v in man.items():
        expected={w:c for c,ws in v['classes'].items() for w in ws}
        actual=dict(lab[(lab.method_id==mid)&(lab.known==True)][['worker_id','class_id']].itertuples(index=False,name=None))
        if actual!=expected:mismatches.append(mid)
    assert not mismatches
    reverse[family]={'candidates':len(man),'valid_candidates':sum(v['full_history_status']=='ok' for v in man.values()),'label_rows':len(lab),'manifest_label_mismatches':mismatches}
    if family=='mixed':
        mid='R_directswap_geometry_partition_b2_K2__ordinary_new__mixed_history_v1'; v=man[mid]
        lobo=pd.read_csv(S/'reverse/mixed_audit/lobo_label_stability.csv'); z=lobo[lobo.method_id==mid]
        re['R_new2']={'method_id':mid,'class_sizes':v['class_sizes'],'all_new_source':bool(f.set_index('worker_id').loc[[w for ws in v['classes'].values() for w in ws],'person_origin'].eq('new').all()),'lobo_reported_mean_reaggregated':z.ari.mean(),'lobo_min':z.ari.min(),'lobo_values':z[['dropped_building','ari','dropped_worker_support']].to_dict('records'),'training_events':v['training_events']}
        z.to_csv(OUT/'reverse_new2_lobo_source.csv',index=False)
re['reverse']=reverse
split=json.loads((P/'analysis/composition/SPLIT.json').read_text()); re['split']={k:split[k] for k in ['history_buildings','discovery_buildings','validation_buildings']}
assert all(not set(split[a])&set(split[b]) for a,b in [('history_buildings','discovery_buildings'),('history_buildings','validation_buildings'),('discovery_buildings','validation_buildings')])
re['split_disjoint']=True
re['source_sha256']={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [S/'forward/build_candidates.py',S/'forward/audit_and_features.py',S/'reverse/learn_swap_types.py',S/'forward/features_train.csv.gz']}
(OUT/'AUDIT_RECEIPT.json').write_text(json.dumps(re,indent=2))
print(json.dumps(re,indent=2))
