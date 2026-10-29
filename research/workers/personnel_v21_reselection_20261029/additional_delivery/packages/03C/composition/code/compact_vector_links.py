"""Lossless compact complete-team class vectors shared by all candidate methods.
Original per-method tables remain unchanged. Code zero means unknown label,
never a middle/neutral class; semantics are resolved in the held-out fold.
"""
from pathlib import Path
import argparse,gzip,json,os,hashlib
import numpy as np,pandas as pd

def save(p,d):
 b=d.to_csv(index=False).encode('utf-8-sig')
 if p.suffix=='.gz':b=gzip.compress(b,compresslevel=6,mtime=0)
 t=p.with_name(p.name+'.writing')
 with t.open('wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 t.replace(p)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--results',type=Path,required=True);ap.add_argument('--inputs',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 receipt=json.loads((a.results/'COMPLETE.json').read_text());methods=receipt['methods']
 links=pd.read_csv(a.inputs/'PANEL_TEAMS.csv.gz');panels=pd.read_csv(a.inputs/'PANELS_USED.csv');index=links[['panel_id','team_key']].copy();assert not index.duplicated().any()
 index=index.merge(panels[['panel_id','pool_id','building','condition','n']],on='panel_id',validate='many_to_one');index.insert(0,'team_link_id',np.arange(len(index),dtype=np.int32))
 pos=pd.MultiIndex.from_frame(index[['panel_id','team_key']]);wide=pd.DataFrame({'team_link_id':index.team_link_id});book=[];shared=None;sources=[]
 for method in methods:
  p=a.results/'by_method'/method/'TEAM_CLASS_VECTORS.csv.gz';x=pd.read_csv(p,keep_default_na=False)
  x=x.set_index(['panel_id','team_key']).reindex(pos);assert x.method.eq(method).all() and x.index.is_unique
  known=x.known.astype(str).str.lower().isin(['true','1','1.0']);vectors=sorted(set(x.loc[known,'class_counts']));mapping={v:i+1 for i,v in enumerate(vectors)}
  codes=x.class_counts.map(mapping).fillna(0).to_numpy(dtype=np.uint16);wide[method]=codes
  assert np.array_equal(codes>0,known.to_numpy())
  inverse={i:v for v,i in mapping.items()};assert all(inverse[int(i)]==v for i,v in zip(codes[known],x.loc[known,'class_counts']))
  this_shared=x.shared_known.astype(str).str.lower().isin(['true','1','1.0']).to_numpy()
  if shared is None:shared=this_shared
  else:assert np.array_equal(shared,this_shared)
  book += [dict(method=method,vector_code=i,class_counts=v) for v,i in mapping.items()]
  sources.append(dict(method=method,file=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),vector_codes=len(vectors)))
 index['shared_known']=shared;assert np.array_equal(wide[methods].gt(0).all(axis=1),shared)
 save(a.out/'TEAM_LINK_INDEX.csv.gz',index);save(a.out/'METHOD_VECTOR_CODES.csv.gz',wide);save(a.out/'VECTOR_CODEBOOK.csv',pd.DataFrame(book))
 result=dict(methods=methods,team_links=len(index),shared_known=int(shared.sum()),code_zero='unknown/not all members have required fold label',
  code_fields='method column + vector_code; class-count semantics require heldout building from link index',source_bytes=sum(s['bytes'] for s in sources),
  compact_bytes=sum((a.out/p).stat().st_size for p in ['TEAM_LINK_INDEX.csv.gz','METHOD_VECTOR_CODES.csv.gz','VECTOR_CODEBOOK.csv']),lossless_roundtrip_checked=True,sources=sources)
 (a.out/'COMPACT_RECEIPT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ['sources','methods']}),flush=True)
if __name__=='__main__':main()
