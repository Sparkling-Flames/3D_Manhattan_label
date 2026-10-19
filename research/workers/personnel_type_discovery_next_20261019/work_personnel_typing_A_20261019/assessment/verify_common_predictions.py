#!/usr/bin/env python3
"""Compare independent original-calibrator replay with every published alias.

Reads every compressed source stream to its end; only selected aliases are
compared numerically. All 92 candidates remain available in discovery outputs.
"""
from pathlib import Path
import json,sys,hashlib
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(HERE))
from evaluate_common import savej

def main():
    root=pd.read_csv(HERE/'EVENT_PREDICTIONS_WIDE.csv.gz').set_index('event_id')
    sources=[('forward',ROOT/'forward/event_predictions.csv.gz','predicted_relation')]+[('reverse',p,'relation') for p in sorted((ROOT/'reverse/results/folds').glob('*/predictions.csv.gz'))]
    rows=[];by_method={};maxdiff=0.
    for source,path,relationcol in sources:
        nr=0;nc=0;err=0.
        for chunk in pd.read_csv(path,usecols=['event_id','method_id','probability',relationcol],chunksize=100000):
            nr+=len(chunk)
            for m,g in chunk.groupby('method_id'):
                if 'p__'+m not in root:continue
                a=root.reindex(g.event_id);assert a.index.notna().all() and a['p__'+m].notna().all()
                diff=float(np.abs(a['p__'+m].to_numpy()-g.probability.to_numpy()).max())
                assert diff<1e-12,(source,path,m,diff)
                assert np.array_equal(a['rel__'+m].to_numpy(),g[relationcol].to_numpy())
                nc+=len(g);err=max(err,diff);by_method[m]=by_method.get(m,0)+len(g)
        rows.append(dict(source=source,file=str(path.relative_to(ROOT)),stream_rows=nr,compared_alias_rows=nc,max_probability_difference=err,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),crc_end_of_stream_passed=True));maxdiff=max(maxdiff,err)
        print(source,path.parent.name,nr,nc,err,flush=True)
    assert all(n==len(root) for n in by_method.values()),by_method
    savej(HERE/'INDEPENDENT_ALIAS_PREDICTION_PARITY.json',{'status':'PASS','events':len(root),'alias_methods':len(by_method),'compared_alias_rows':sum(by_method.values()),'max_probability_difference':maxdiff,'per_method_rows':by_method,'sources':rows,'not_claimed':'No independent full data collection or complete Dot replay.'})
if __name__=='__main__':main()
