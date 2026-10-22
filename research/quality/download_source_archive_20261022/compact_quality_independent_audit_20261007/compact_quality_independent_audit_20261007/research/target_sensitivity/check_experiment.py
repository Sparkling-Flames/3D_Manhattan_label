#!/usr/bin/env python3
"""Focused checks for the extension, beyond the original-pipeline identity checks."""
from pathlib import Path
import argparse, json
import numpy as np
import pandas as pd
from run_experiment import HERE as DEFAULT_OUT, CORE, ORIGINAL_SCALE, INTRINSIC, SCHEMES, TOL, individual, pareto, natural

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--out",type=Path,default=DEFAULT_OUT,help="Existing experiment output directory; CHECKS.json is written here")
parser.add_argument("--source",type=Path,default=None,help="Optional extracted compact root/results directory for source-identity validation")
args=parser.parse_args()
HERE=args.out.resolve()

q=pd.read_csv(HERE/'frozen_eligible_records.csv')
p=pd.read_csv(HERE/'all_pairs_predictions.csv')
p=p[p.supported].copy()
s=pd.read_csv(HERE/'frozen_and_intrinsic_train_scales.csv').set_index('held_building')
checks={}
if args.source is not None:
 source=args.source.resolve();results=source if (source/"manual_scored.csv").is_file() else source/"results"
 raw=pd.read_csv(results/"manual_scored.csv")
 source_q=raw[raw.primary_candidate & raw.reference_version.eq("original")].dropna(subset=ORIGINAL_SCALE)
 assert set(map(tuple,q[["image","id","worker"]].values))==set(map(tuple,source_q[["image","id","worker"]].values))
 checks["optional_source_record_identity"]="passed"
# Unit-level label direction, explicit ties and Pareto incomparability.
a=pd.Series({'L':.2,'C':.2,'U':2.,'B':2.,'T':.2,'F':.2})
b=pd.Series({'L':.1,'C':.1,'U':1.,'B':1.,'T':.1,'F':.1})
assert pareto(a,b,CORE)==('ordered',1)
assert pareto(b,a,CORE)==('ordered',-1)
assert pareto(a,a,CORE)==('tie',0)
c=b.copy();c.U=3.
assert pareto(a,c,CORE)==('incomparable',0)
c=b.copy();c['T']=.3
assert natural(a,c)
assert pareto(a,c,CORE)==('ordered',1)
assert individual(a,c,'T')==('ordered',-1)
assert pareto(a,c,CORE+['T'])==('incomparable',0)
checks['label_units']='passed: orientation, ties, incomparable vectors, original 3D conflict'
# Same workers and held building must have exactly the same prediction on every held image.
max_within=float(p.groupby(['building','a_worker','b_worker'])[SCHEMES].agg(lambda x: x.max()-x.min()).to_numpy().max())
assert max_within==0.
checks['prediction_invariant_across_same_building_images']=max_within
# Independently reconstruct sampled paired means from two separate worker frames.
max_error=0.
for r in p.sample(32,random_state=20261007).itertuples():
 a=q[(q.worker==r.a_worker)&q.building.ne(r.building)]
 b=q[(q.worker==r.b_worker)&q.building.ne(r.building)]
 z=a.merge(b,on=['image','building'],suffixes=('_a','_b'),validate='one_to_one')
 assert len(z)==r.shared_train_images and z.building.nunique()==r.shared_train_buildings
 sc=s.loc[r.building]
 means={k:float((z[k+'_a']-z[k+'_b']).mean()) for k in ORIGINAL_SCALE+INTRINSIC+['LC']}
 lcn=means['L']/sc.L+means['C']/sc.C
 s4=sum(means[k]/sc[k] for k in CORE)
 scores={'S0':means['L'],'S1':means['LC'],'S4':s4,'S5':s4+means['T']/sc['T'],'S5_relative':s4+means['T_relative']/sc.T_relative,
  'LCn':lcn,'LCn_T':lcn+means['T']/sc['T'],'LCn_G':lcn+.5*sum(means[k]/sc[k] for k in INTRINSIC)}
 for k,v in scores.items():max_error=max(max_error,abs(getattr(r,k)-v))
assert max_error<1e-10
checks['independent_32_pair_training_reconstruction_max_error']=max_error
# Every target category partitions the frozen supported panel, and every model shares the denominator.
cov=pd.read_csv(HERE/'target_coverage.csv')
assert np.array_equal(cov[['ordered_pairs','tie_pairs','incomparable_pairs','missing_pairs','outside_stratum_pairs']].sum(axis=1).to_numpy(),cov.total_supported_pairs.to_numpy())
summ=pd.read_csv(HERE/'target_score_summary.csv')
assert summ.groupby(['panel','target'])[['ordered_pairs','images','buildings']].nunique().eq(1).all().all()
checks['coverage_partitions_and_paired_denominators']='passed'
# Original and broad conflict aliases coincide empirically, rather than assumed in code.
targets=pd.read_csv(HERE/'all_pair_targets.csv')
w=targets.pivot(index='pair_id',columns='target',values='expected_sign')
assert np.array_equal(w.original_natural_conflict_core,w.LCUB_T_conflict_core)
checks['original_and_general_conflict_sets_equal']='passed; observed equality, not a universal identity'
checks['status']='passed'
(HERE/'CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(checks,ensure_ascii=False,indent=2))
