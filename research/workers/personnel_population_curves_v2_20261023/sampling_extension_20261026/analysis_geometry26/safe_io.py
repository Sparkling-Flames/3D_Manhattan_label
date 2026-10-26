"""Complete-body CSV writes with atomic replacement and actual readback.

This changes delivery I/O only. Numerical calculations are unchanged. The
explicit installer preserves pandas' normal in-memory/file-like behavior and
wraps writes to local paths used by these research scripts.
"""
from __future__ import annotations
import gzip
import os
from pathlib import Path
import uuid


def atomic_bytes(path, body):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.writing')
    try:
        with temp.open('wb') as f:
            written=f.write(body)
            if written!=len(body):raise IOError('Short write: '+str(path))
            f.flush();os.fsync(f.fileno())
        if temp.read_bytes()!=body:raise IOError('Temporary readback differs: '+str(path))
        temp.replace(path)
        if path.read_bytes()!=body:raise IOError('Final readback differs: '+str(path))
    finally:
        if temp.exists():temp.unlink()


def install_safe_csv_writer():
    import pandas as pd
    if getattr(pd.DataFrame.to_csv,'_hohonet_complete_body',False):return
    original=pd.DataFrame.to_csv
    def writer(self,path_or_buf=None,*args,**kwargs):
        if not isinstance(path_or_buf,(str,os.PathLike)):
            return original(self,path_or_buf,*args,**kwargs)
        path=Path(path_or_buf)
        mode=kwargs.get('mode','w')
        if mode not in ('w','wt'):
            raise ValueError('The research safe writer supports complete CSV replacement only')
        options=dict(kwargs)
        compression=options.pop('compression','infer')
        encoding=options.pop('encoding',None) or 'utf-8'
        options.pop('mode',None)
        if compression=='infer':compression='gzip' if str(path).endswith('.gz') else None
        method=compression.get('method') if isinstance(compression,dict) else compression
        if method not in (None,'gzip'):
            raise ValueError('Unsupported CSV compression in safe research writer: '+str(method))
        text=original(self,None,*args,compression=None,**options)
        raw=text.encode(encoding)
        if method=='gzip':
            level=compression.get('compresslevel',6) if isinstance(compression,dict) else 6
            body=gzip.compress(raw,compresslevel=level,mtime=0)
            if gzip.decompress(body)!=raw:raise IOError('In-memory gzip validation failed')
        else:body=raw
        atomic_bytes(path,body)
        saved=path.read_bytes()
        if method=='gzip' and gzip.decompress(saved)!=raw:
            raise IOError('Saved gzip decompression differs: '+str(path))
        return None
    writer._hohonet_complete_body=True
    pd.DataFrame.to_csv=writer
