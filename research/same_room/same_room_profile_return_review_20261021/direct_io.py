"""Read ordinary files and complete-record shards; historical gzip inputs remain readable.
No archive reconstruction or extraction is needed. Writers produce plain files.
"""
from pathlib import Path
import gzip, io, json

def plain_path(path):
 p=Path(path)
 return p.with_suffix('') if p.suffix=='.gz' else p

def data_exists(path):
 p=Path(path);q=plain_path(p)
 return p.exists() or q.exists() or q.with_name(q.name+'.parts').is_dir()

def read_bytes(path):
 p=Path(path);q=plain_path(p);folder=q.with_name(q.name+'.parts')
 if q.is_file():return q.read_bytes()
 if folder.is_dir():
  idx=json.loads((folder/'index.json').read_text(encoding='utf-8'))
  if idx['kind']=='csv':
   chunks=[(folder/x['path']).read_bytes() for x in idx['parts']]
   return chunks[0]+b''.join(x.split(b'\n',1)[1] for x in chunks[1:])
  values=[json.loads((folder/x['path']).read_bytes()) for x in idx['parts']]
  if idx['kind']=='dict':
   result={}
   for x in values:
    if result.keys() & x.keys():raise ValueError('Duplicate shard keys')
    result.update(x)
  else:result=[v for x in values for v in x]
  return json.dumps(result,ensure_ascii=False,separators=(',',':')).encode()
 if p.suffix=='.gz':return gzip.decompress(p.read_bytes())
 return p.read_bytes()

def open_data(path,mode='rt',encoding=None,newline=None,**kwargs):
 if any(c in mode for c in 'wax+'):
  q=plain_path(path);q.parent.mkdir(parents=True,exist_ok=True)
  return open(q,mode,**({} if 'b' in mode else {'encoding':encoding or 'utf-8','newline':newline}),**kwargs)
 b=read_bytes(path)
 return io.BytesIO(b) if 'b' in mode else io.StringIO(b.decode(encoding or 'utf-8'),newline=newline)

def read_json(path):
 with open_data(path) as f:return json.load(f)

def read_csv(path,*args,**kwargs):
 import pandas as pd
 if isinstance(path,(str,Path)):
  kwargs.pop('compression',None)
  return pd.read_csv(io.BytesIO(read_bytes(path)),*args,**kwargs)
 return pd.read_csv(path,*args,**kwargs)

def write_csv(frame,path=None,*args,**kwargs):
 kwargs.pop('compression',None)
 if isinstance(path,(str,Path)):
  path=plain_path(path);path.parent.mkdir(parents=True,exist_ok=True)
 return frame.to_csv(path,*args,compression=None,**kwargs)

def write_bytes(path,data):
 p=Path(path);q=plain_path(p);q.parent.mkdir(parents=True,exist_ok=True)
 if p.suffix=='.gz' and data.startswith(b'\x1f\x8b'):data=gzip.decompress(data)
 return q.write_bytes(data)
