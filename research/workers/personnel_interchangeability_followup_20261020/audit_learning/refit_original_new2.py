import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import sys,json,time,hashlib
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.metrics import adjusted_rand_score
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;S=ROOT/'unpacked/interchangeability_20261020';sys.path.insert(0,str(S/'reverse'))
from learn_swap_types import load_history,domain_mask,pair_building_table,make_graph,fit_labels,make_inner_folds,SEED

def run():
 t=time.perf_counter();frame,split,receipt=load_history(BASE/'reverse_input_root',BASE/'native_history_events_rebuilt.csv.gz');d=frame[frame.panel_id.isin(['Pro_exact_fixed_background_v1','H20_metadata_allentrant_v1'])];d=d[domain_mask(d,'ordinary_new')];pb=pair_building_table(d);full=make_graph(d,pb);mid='R_directswap_geometry_partition_b2_K2__ordinary_new__mixed_history_v1';m=json.load(open(S/'reverse/mixed_fit/METHOD_MANIFEST.json'))[mid];ref={w:c for c,ws in m['classes'].items() for w in ws};reg=json.load(open(S/'reverse/mixed_fit/REGISTRATION.json'));gate=reg['opportunity'].get('each_class_known_pair_fraction_min',0)
 lab,status=fit_labels(full,'geometry','partition_b2',2,SEED+2,gate);ari=adjusted_rand_score([ref[w] for w in full['workers']],lab);assert status=='ok' and ari==1,(status,ari)
 rows=[];foldlabels=[]
 for b in split['history_buildings']:
  tr=d[~d.building.eq(b)];g=make_graph(tr,pb[~pb.building.eq(b)]);l,st=fit_labels(g,'geometry','partition_b2',2,SEED+2,gate);r={'dropped_building':b,'status':st,'workers':len(g['workers']),'ari':adjusted_rand_score([ref[w] for w in g['workers']],l) if l is not None else None};rows.append(r)
  print(json.dumps(r),flush=True)
 for fi,held in enumerate(make_inner_folds(split['history_buildings'])):
  tr=d[~d.building.isin(held)];g=make_graph(tr,pb[~pb.building.isin(held)]);l,st=fit_labels(g,'geometry','partition_b2',2,SEED+fi*1000+2,gate)
  if l is not None:
   for w,c in zip(g['workers'],l):foldlabels.append({'fold':fi,'worker_id':w,'class_id':int(c)})
 pd.DataFrame(rows).to_csv(BASE/'original_Rnew2_lobo_refit.csv',index=False);pd.DataFrame(foldlabels).to_csv(BASE/'original_Rnew2_inner_fold_labels.csv',index=False)
 reported=pd.read_csv(S/'reverse/mixed_audit/lobo_label_stability.csv');reported=reported[reported.method_id.eq(mid)];merged=pd.DataFrame(rows).merge(reported,on='dropped_building',suffixes=('_new','_old'));assert np.allclose(merged.ari_new,merged.ari_old,atol=1e-12)
 out={'full_refit_ARI':ari,'all_ten_lobo_ARIs_match':True,'lobo_mean':pd.DataFrame(rows).ari.mean(),'training_events':len(d),'source_total_history_loaded':len(frame),'elapsed_seconds':time.perf_counter()-t,'no_new_labels_tuned':True};(BASE/'ORIGINAL_RNEW2_FULL_REFIT_RECEIPT.json').write_text(json.dumps(out,indent=2));print(json.dumps(out),flush=True)
if __name__=='__main__':run()
