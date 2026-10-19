"""Single-writer atomic CSV exports with explicit end-of-stream read-back."""
from __future__ import annotations
import hashlib,os,uuid
from pathlib import Path
import pandas as pd


def csv_verified(frame,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+"."+uuid.uuid4().hex+".writing")
    compression="gzip" if path.name.endswith(".gz") else None
    frame.to_csv(tmp,index=False,compression=compression)
    with tmp.open("rb")as f:os.fsync(f.fileno())
    n=0
    for chunk in pd.read_csv(tmp,compression=compression,chunksize=100000):
        assert list(chunk.columns)==list(frame.columns),f"column mismatch exporting {path}"
        n+=len(chunk)
    assert n==len(frame),f"row mismatch exporting {path}: {n}/{len(frame)}"
    digest=hashlib.sha256(tmp.read_bytes()).hexdigest()
    os.replace(tmp,path)
    return {"file":str(path),"rows":n,"bytes":path.stat().st_size,"sha256":digest,"full_readback_passed":True}
