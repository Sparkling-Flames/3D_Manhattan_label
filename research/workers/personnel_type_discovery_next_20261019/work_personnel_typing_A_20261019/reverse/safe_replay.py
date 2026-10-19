#!/usr/bin/env python3
"""Publication-safe wrapper around the unchanged scientific entry points.

Example:
  python reverse/safe_replay.py --program discover --fast --stage discover \
      --events events/common_events.csv.gz

Every path-based CSV export is fully read back before publication. This wrapper
changes I/O only; optional --fast is the previously crosschecked aggregation.
"""
from pathlib import Path
import argparse,hashlib,importlib,json,os,sys,time,uuid
import pandas as pd

HERE=Path(__file__).resolve().parent
ORIGINAL_TO_CSV=pd.DataFrame.to_csv
RECEIPTS=[]


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while b:=f.read(1<<20):h.update(b)
    return h.hexdigest()


def safe_to_csv(frame,path_or_buf=None,*args,**kwargs):
    if not isinstance(path_or_buf,(str,os.PathLike)):
        return ORIGINAL_TO_CSV(frame,path_or_buf,*args,**kwargs)
    path=Path(path_or_buf);path.parent.mkdir(parents=True,exist_ok=True)
    if kwargs.get('mode','w')!='w':raise ValueError('Safe wrapper requires a single whole-file writer')
    if kwargs.get('index',True):raise ValueError('Scientific exports are expected to specify index=False')
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.writing')
    kw=dict(kwargs);compression='gzip' if path.name.endswith('.gz') else None
    kw['compression']=compression
    ORIGINAL_TO_CSV(frame,tmp,*args,**kw)
    with tmp.open('rb') as f:os.fsync(f.fileno())
    n=0
    for chunk in pd.read_csv(tmp,compression=compression,chunksize=50000):
        assert list(chunk.columns)==list(frame.columns),(str(path),'columns')
        n+=len(chunk)
    assert n==len(frame),(str(path),n,len(frame))
    digest=sha(tmp);os.replace(tmp,path)
    fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    RECEIPTS.append({'path':str(path),'rows':n,'sha256':digest,'bytes':path.stat().st_size,'full_csv_crc_pass':True})
    return None


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--program',choices=['discover','explain','diagnostics'],default='discover')
    ap.add_argument('--fast',action='store_true')
    options,remaining=ap.parse_known_args()
    module={'discover':'discover_reverse_types','explain':'explain_reverse_types','diagnostics':'analyze_partition_stability'}[options.program]
    target=importlib.import_module(module);start=time.time();fast_sha=None
    if options.fast:
        if options.program!='discover':raise ValueError('--fast applies only to discovery')
        sys.path.insert(0,str(HERE.parent/'forward'))
        fast=importlib.import_module('selection_fast')
        parity=json.loads((HERE/'FAST_SELECTION_PARITY.json').read_text())
        fast_sha=sha(HERE.parent/'forward/selection_fast.py')
        assert parity['passed'] and parity['fast_sidecar_sha256']==fast_sha
        target.fit_calibrator=fast.fit_calibrator
        target.predict_calibrator=fast.predict_calibrator
        target.building_brier=fast.building_brier
    pd.DataFrame.to_csv=safe_to_csv
    sys.argv=[module]+remaining
    target.main()
    pd.DataFrame.to_csv=ORIGINAL_TO_CSV
    receipt={'program':options.program,'arguments':remaining,'scientific_source_sha256':sha(target.__file__),
             'fast_sidecar_sha256':fast_sha,'safe_wrapper_sha256':sha(__file__),'seconds':time.time()-start,'exports':RECEIPTS,
             'method_change':False,'writer':'UUID temporary, close/fsync, full CSV/CRC/row check, rename, directory fsync'}
    out=HERE/'safe_io_receipts';out.mkdir(exist_ok=True)
    (out/(options.program+'_'+uuid.uuid4().hex+'.json')).write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'verified_exports':len(RECEIPTS),'seconds':receipt['seconds']}),flush=True)


if __name__=='__main__':main()
