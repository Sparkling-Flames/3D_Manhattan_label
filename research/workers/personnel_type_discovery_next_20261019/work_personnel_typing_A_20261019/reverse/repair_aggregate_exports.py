#!/usr/bin/env python3
"""Rebuild two truncated aggregate exports; never refit classes or select models."""
from pathlib import Path
import gzip,hashlib,json,sys
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'forward'))
from atomic_exports import csv_verified


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def prefix_parity(old,frame):
    n=0;failed=False
    try:
        for a in pd.read_csv(old,chunksize=10000):
            b=frame.iloc[n:n+len(a)].reset_index(drop=True)
            a=a.reset_index(drop=True)
            pd.testing.assert_frame_equal(a,b,check_dtype=False,check_exact=False,rtol=0,atol=1e-12)
            n+=len(a)
    except EOFError:failed=True
    assert failed
    return n


def main():
    p=HERE/'results';out=[]
    target=p/'all_class_diagnostics.csv.gz';frames=[]
    for d in sorted((p/'folds').glob('*/COMPLETE.json')):
        z=pd.read_csv(d.parent/'class_diagnostics.csv.gz');z['outer_fold']=d.parent.name;frames.append(z)
    frame=pd.concat(frames,ignore_index=True)
    before=digest(target);prefix=prefix_parity(target,frame)
    out.append({'file':str(target),'initial_sha256':before,'original_prefix_rows_compared':prefix,
                'reconstruction':'concatenate unchanged 23 per-fold class_diagnostics with outer_fold; exact original aggregation',
                **csv_verified(frame,target)})
    target=p/'geometry_person_pair_relations.csv.gz';before=digest(target)
    with gzip.open(target,'rt') as f:columns=f.readline().strip().split(',')
    geometry=pd.read_csv(p/'all_pair_relations.csv.gz')
    order=json.loads((HERE/'FROZEN_BUILDING_SPLITS.json').read_text())['folds']
    geometry=pd.concat([geometry[geometry.fold_id.eq(f)] for f in order],ignore_index=True)
    # Original geometry-only stage had no swap event input. All geometry fields
    # are the same frozen historical fits; restore its explicit empty context.
    geometry['swap_stability_observed']=np.nan
    geometry['swap_stability_posterior']=.5
    geometry['swap_training_prior']=.5
    geometry['n_swap_images']=0;geometry['n_swap_buildings']=0;geometry['swap_pair_supported']=False
    geometry=geometry[columns]
    prefix=prefix_parity(target,geometry)
    out.append({'file':str(target),'initial_sha256':before,'original_prefix_rows_compared':prefix,
                'reconstruction':'same per-fold geometry columns; restore original no-swap-input missing/zero-support/prior=.5 stage fields',
                **csv_verified(geometry,target)})
    (HERE/'AGGREGATE_EXPORT_REPAIR_RECEIPT.json').write_text(json.dumps({'new_relation_fits':0,'new_partition_fits':0,
        'new_selection':0,'original_readable_prefixes_match_atol':1e-12,'exports':out},indent=2)+'\n')
    print(json.dumps(out,indent=2),flush=True)


if __name__=='__main__':main()
