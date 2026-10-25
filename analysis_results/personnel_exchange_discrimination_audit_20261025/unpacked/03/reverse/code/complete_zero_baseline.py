#!/usr/bin/env python3
"""Fill the actual inner-building zero-response baseline, keeping labels fixed."""
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
from learn_natural_fusion_roles import Study,OUTPUTS,FAMILIES,OUTPUT_DOMAINS
from prepare_natural_training import save_csv,save_json,sha

def main(a):
 p=Path(a.output);before=sha(p/'REVERSE_LABELS_ALL_LOBO.csv.gz');study=Study(p/'inputs/NATURAL_TRAINING_ENDPOINTS.csv.gz')
 checks=pd.read_csv(p/'INNER_BUILDING_RESPONSE_ERRORS.csv.gz');cache={}
 for key,g in checks.groupby(['heldout_building','inner_building','stratum']):
  outer,inner,stratum=key;excluded={inner} if outer=='ALL' else {outer,inner}
  y2=[v[2] for (s,b),v in study.stats.items() if s==stratum and b not in excluded]
  train=np.mean(y2,axis=0);test=study.stats[(stratum,inner)][2];cache[key]=test/np.maximum(train,1e-10)
 checks['zero_response_normalized_mse']=[float(cache[(r.heldout_building,r.inner_building,r.stratum)][OUTPUTS.index(r.output)]) for r in checks.itertuples()]
 save_csv(checks,p/'INNER_BUILDING_RESPONSE_ERRORS.csv.gz');reg=pd.read_csv(p/'NESTED_LAMBDA_SELECTION.csv')
 for i,r in reg.iterrows():
  z=checks[checks.heldout_building.eq(r.heldout_building)&checks.alpha.eq(r.alpha)];v=[]
  for domain in FAMILIES[r.family]:
   d=z[z.output.isin(OUTPUT_DOMAINS[domain])]
   v.append(d.groupby(['stratum','output']).zero_response_normalized_mse.mean().groupby('stratum').mean().mean())
  reg.loc[i,'zero_response_reference_nmse']=float(np.mean(v));reg.loc[i,'relative_mse_to_zero']=r.inner_normalized_mse/float(np.mean(v))
 save_csv(reg,p/'NESTED_LAMBDA_SELECTION.csv')
 rec=json.loads((p/'REVERSE_BUILD_RECEIPT.json').read_text());rec['validation_baseline']='The zero-response baseline is measured on each held-out inner building with its training-scale denominator; it is not assumed equal to 1 across buildings.';rec['labels_unchanged_baseline_completion']=True;save_json(rec,p/'REVERSE_BUILD_RECEIPT.json');assert before==sha(p/'REVERSE_LABELS_ALL_LOBO.csv.gz')
 print(reg[reg.heldout_building.eq('ALL')][['family','alpha','inner_normalized_mse','zero_response_reference_nmse','relative_mse_to_zero','selected']].to_string(index=False))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);main(p.parse_args())
