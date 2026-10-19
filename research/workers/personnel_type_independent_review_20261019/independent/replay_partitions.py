import sys,pathlib,json,gzip,tempfile,shutil
import numpy as np,pandas as pd
R=pathlib.Path('/workspace/shared/personnel_partA_audit_20261019/extracted/work_personnel_typing_A_20261019');O=R.parents[1]/'independent'
sys.path[:0]=[str(R/'forward'),str(R/'reverse')]
import build_features as b
from multiview_partition import partition_features
from discover_reverse_types import read_geometry_inputs,normalize_events,RelationStore,cluster_labels
sets=json.loads((R/'forward/TRAINING_SETS.json').read_text());ff=pd.read_csv(R/'forward/worker_features_by_training_set.csv.gz');labs=pd.read_csv(R/'forward/candidate_labels_by_training_set.csv.gz');out={}
# All 69 main selected QT-only partitions recomputed from saved training-side features.
errors=[];n=0
for k,f in ff.groupby('train_key'):
 a=partition_features(f,{x:b.DOMAINS[x] for x in ['Q','T']},ks=(4,),method_id='fw_QT_only').labels.set_index('worker_id').class_id
 c=labs[(labs.train_key==k)&(labs.method_id=='fw_QT_only_K4')].set_index('worker_id').class_id
 if not a.equals(c.reindex(a.index)):errors.append(k)
 n+=len(a)
out['forward_partitions']={'training_sets':69,'worker_assignments':n,'mismatch_sets':errors};print('partitions',out,flush=True)
# Fresh feature fit for one full outer heldout and one nested inner, with poisoned excluded rows.
repo=R/'recovered/repo_main_20261019'
with tempfile.TemporaryDirectory(dir=O) as tmp:
 shutil.copyfile(R/'forward/REGISTRATION.json',pathlib.Path(tmp)/'REGISTRATION.json')
 d,q,_,_,_,_=b.NATIVE.load_inputs(repo,pathlib.Path(tmp))
ex=b.extra_frame(json.load(gzip.open(repo/'research/statistics/v2_evidence_audit_20261019/records.json.gz','rt'))['records']);workers=sorted(q.worker_id.unique())
checks=[]
for alias in [x for x in sets['aliases'] if x['fold_id']=='B6ByNegPMKs' and (x['inner_group'] is None or x['inner_group']==0)]:
 key=alias['train_key'];bs=sets['sets'][key];fresh,meta=b._training_features(d,ex,workers,bs);saved=ff[ff.train_key==key].set_index('worker_id');fresh=fresh.set_index('worker_id')
 errors={}
 for c in fresh.select_dtypes(include='number').columns:
  x=fresh[c];y=saved[c];mask=x.notna()&y.notna();err=float(np.max(abs(x[mask]-y[mask]))) if mask.any() else 0
  if err>1e-9 or not x.isna().equals(y.isna()):errors[c]=err
 poison=d.copy();mask=~poison.building_id.isin(bs)
 for c in ['B8L2','D10','source_active_time_seconds','declared_pair_count']:poison.loc[mask,c]=1e8
 ex2=ex.copy();ex2.loc[~ex2.building_id.isin(bs),'scope_out']=1234
 again,_=b._training_features(poison,ex2,workers,bs);again=again.set_index('worker_id')
 pd.testing.assert_frame_equal(fresh,again)
 checks.append({'train_key':key,'inner_group':alias['inner_group'],'training_buildings':len(bs),'fresh_feature_mismatches':errors,'poison_excluded_rows':int(mask.sum()),'poison_parity':True})
 print('features',checks[-1],flush=True)
out['forward_fresh_features']=checks
# Recreate FULL and one outer main reverse partitions from training-only raw local geometry.
rec,pairs=read_geometry_inputs(R/'recovered/work_v2_20261019/clusters/assignments.csv',R/'recovered/work_v2_20261019/clusters/records_geometry.csv')
sp=json.loads((R/'reverse/FROZEN_BUILDING_SPLITS.json').read_text())['folds'];rs=[]
for fold in ['FULL','B6ByNegPMKs']:
 fit=RelationStore(rec,pairs,None).fit(sp[fold]['train_buildings']);ll,_=cluster_labels(fit,'geometry9','average',4,False)
 saved=pd.read_csv(R/f'reverse/results/folds/{fold}/classes.csv.gz');saved=saved[saved.method_id=='reverse_selected'].set_index('worker_id').class_id.to_dict()
 rs.append({'fold':fold,'label_mismatches':[w for w in ll if ll[w]!=saved[w]],'n':len(ll),'training_buildings':len(sp[fold]['train_buildings'])})
out['reverse_partitions']=rs
(O/'independent_partitions.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
