import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import sys,json,gzip,importlib.util
from pathlib import Path
import pandas as pd,numpy as np
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;P=ROOT/'unpacked';S=P/'interchangeability_20261020';stage=BASE/'full_forward_rebuild/portable_input'
sys.path.insert(0,str(S/'reverse'));from learn_swap_types import make_inner_folds
spec=importlib.util.spec_from_file_location('old',P/'analysis/forward/build_forward.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
_,fn=old.upstream_functions(stage/'repo');split=json.load(open(P/'analysis/composition/SPLIT.json'));hist=split['history_buildings'];allrec=json.load(gzip.open(stage/'repo'/old.RECORD_SOURCE,'rt'))['records'];rec=[r for r in allrec if r['building_id'] in hist];roster=pd.read_csv(S/'forward/features_train.csv.gz').worker_id.tolist();rows=[]
for fi,held in enumerate(make_inner_folds(hist)):
 train=[b for b in hist if b not in held];rr=[r for r in rec if r['building_id'] in train];d=old.flatten(rr);ex=fn['extra_frame'](rr);f,meta=fn['_training_features'](d,ex,roster,train)
 cols=['worker_id','q_beta','core_supported','t_source_origin_effect','t_supported','person_origin'];f=f[cols].copy();f.insert(0,'fold',fi);rows.append(f);print('fold',fi,flush=True)
out=pd.concat(rows,ignore_index=True);out.to_csv(BASE/'eight_building_QT_features.csv',index=False)
expected=pd.read_csv(S/'reverse/inner_q_baselines/eight_building_Q_features.csv.gz');m=expected.merge(out,on=['fold','worker_id'],suffixes=('_old','_new'));assert np.allclose(m.q_beta_old,m.q_beta_new,atol=1e-9,equal_nan=True)
(BASE/'FOLD_QT_REBUILD_RECEIPT.json').write_text(json.dumps({'folds':5,'rows':len(out),'Q_matches_packaged_eight_building_values':True,'T_independently_rebuilt_on_training_fold_only':True},indent=2))
