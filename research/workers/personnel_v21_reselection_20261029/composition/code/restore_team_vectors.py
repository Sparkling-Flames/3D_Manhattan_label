"""Expand lossless vector codes into the original per-method table schema.

Code 0 remains missing, not a class. Output values/keys are equivalent to the
original CSV; gzip byte encoding/timestamps need not match the historical file.
"""
from pathlib import Path
import argparse,gzip,os
import pandas as pd

def main():
 p=argparse.ArgumentParser();p.add_argument('--compact',type=Path,required=True)
 p.add_argument('--out',type=Path,required=True);p.add_argument('--methods',default='')
 a=p.parse_args();index=pd.read_csv(a.compact/'TEAM_LINK_INDEX.csv.gz')
 codes=pd.read_csv(a.compact/'METHOD_VECTOR_CODES.csv.gz')
 book=pd.read_csv(a.compact/'VECTOR_CODEBOOK.csv',keep_default_na=False)
 methods=a.methods.split(',') if a.methods else list(codes.columns.drop('team_link_id'))
 assert index.team_link_id.tolist()==codes.team_link_id.tolist()
 for method in methods:
  b=book[book.method.eq(method)].set_index('vector_code').class_counts.to_dict()
  v=codes[method].map(b).fillna('');known=codes[method].gt(0)
  assert v.ne('').equals(known)
  d=pd.DataFrame(dict(panel_id=index.panel_id,team_key=index.team_key,method=method,
   heldout_building=index.building,class_counts=v,known=known,shared_known=index.shared_known))
  out=a.out/'by_method'/method/'TEAM_CLASS_VECTORS.csv.gz';out.parent.mkdir(parents=True,exist_ok=True)
  data=gzip.compress(d.to_csv(index=False).encode('utf-8-sig'),mtime=0)
  tmp=out.with_name(out.name+'.writing')
  with tmp.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  tmp.replace(out)
 print({'methods':len(methods),'links_per_method':len(index),'output':str(a.out)})
if __name__=='__main__':main()
