"""Losslessly pivot repeated long predictions to one row per actual swap.

Actual values and all model predictions are retained. Squared/absolute errors
are deterministic from them. The original long files are runtime intermediates
and may be omitted from a delivery that includes the wide file and receipt.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent

def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument('--expand-to',type=Path);args=ap.parse_args()
    out=HERE/'swap_transfer';r=json.loads((out/'RECEIPT.json').read_text());target=out/'heldout_predictions_wide.csv.gz';tmp=target.with_suffix('.gz.tmp')
    metadata=['event_key','pool_id','image_id','image_code','building_id','difficulty','k','background_id','entrant_a','entrant_b']
    if args.expand_to:
        args.expand_to.mkdir(parents=True,exist_ok=True);wide=pd.read_csv(target,float_precision='round_trip')
        for building,g in wide.groupby('building_id'):
            frames=[]
            for c in sorted(x for x in g if x.startswith('prediction__')):
                _,outcome,model=c.split('__');valid=g[c].notna();z=g.loc[valid,metadata].copy()
                z['outcome']=outcome;z['actual']=g.loc[valid,'actual__'+outcome];z['model']=model;z['prediction']=g.loc[valid,c]
                z['squared_error']=(z.prediction-z.actual)**2;z['absolute_error']=abs(z.prediction-z.actual)
                z['information']='prospective_historical_features' if model in ['known_task','Q','QT','QTD'] else 'target_annotation_oracle';frames.append(z)
            path=args.expand_to/(building+'_predictions.csv.gz')
            with gzip.open(path,'wt',encoding='utf-8',newline='') as f:pd.concat(frames,ignore_index=True).to_csv(f,index=False)
        print(json.dumps(dict(expanded_buildings=wide.building_id.nunique(),target_directory=str(args.expand_to)),indent=2));return
    sources=[];rows=0;longn=0;header=False;plain=out/'heldout_predictions_wide.csv.tmp'
    with plain.open('wt',encoding='utf-8',newline='') as f:
        for name in r['predictions']:
            path=out/name;d=pd.read_csv(path,float_precision='round_trip')
            assert not d.duplicated(['event_key','model','outcome']).any()
            assert d.groupby(['event_key','outcome']).actual.nunique().le(1).all()
            actual=d.groupby(['event_key','outcome']).actual.first().unstack('outcome');actual.columns=['actual__'+x for x in actual.columns]
            pred=d.pivot(index='event_key',columns=['outcome','model'],values='prediction');pred.columns=['prediction__'+a+'__'+b for a,b in pred.columns]
            meta=d[metadata].drop_duplicates('event_key').set_index('event_key');wide=meta.join(actual,validate='one_to_one').join(pred,validate='one_to_one').reset_index()
            wide=wide.reindex(sorted(wide.columns),axis=1)
            if not header:columns=list(wide.columns)
            else:assert list(wide.columns)==columns
            wide.to_csv(f,index=False,header=not header);header=True;rows+=len(wide);longn+=len(d)
            sources.append(dict(file=name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),long_rows=len(d),wide_rows=len(wide)))
    # Materialize a complete gzip byte stream before writing. This avoids
    # depending on incremental gzip trailer flushing in the workspace.
    content=plain.read_bytes();encoded=gzip.compress(content,compresslevel=6,mtime=0)
    assert gzip.decompress(encoded)==content
    tmp.write_bytes(encoded)
    with gzip.open(tmp,'rb') as f:
        while f.read(1024*1024):pass
    tmp.replace(target)
    plain.unlink()
    # Read back numerical predictions and actuals by the original exact keys.
    read=pd.read_csv(target,float_precision='round_trip');checked=0;maxerror=0.
    for src in sources:
        d=pd.read_csv(out/src['file'],float_precision='round_trip');w=read[read.building_id.eq(d.building_id.iloc[0])].set_index('event_key')
        for (outcome,model),g in d.groupby(['outcome','model']):
            p=w.loc[g.event_key,'prediction__'+outcome+'__'+model].to_numpy();a=w.loc[g.event_key,'actual__'+outcome].to_numpy()
            assert np.array_equal(p,g.prediction.to_numpy()) and np.array_equal(a,g.actual.to_numpy())
            checked+=len(g)
    receipt=dict(encoding='one actual swap per row; actual__outcome and prediction__outcome__model columns',
        outcomes=['abs_B8L2_change','floor_jaccard_difference','joint_geometric_stable'],wide_rows=rows,long_prediction_rows=longn,
        exact_float64_readback_comparisons=checked,numerical_roundtrip_difference=0.,missing_kept_as_empty_not_zero=True,
        target=target.name,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),sources=sources,
        long_files_optional_for_packaging=True,reconstruct_errors='squared_error=(prediction-actual)^2;absolute_error=abs(prediction-actual)',
        train_test_information='Q/QT/QTD/known_task are historical prospective; actual_cluster_* and raw_pair_geometry are target-annotation oracle')
    (out/'WIDE_PREDICTIONS_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k!='sources'},indent=2))

if __name__=='__main__':main()
