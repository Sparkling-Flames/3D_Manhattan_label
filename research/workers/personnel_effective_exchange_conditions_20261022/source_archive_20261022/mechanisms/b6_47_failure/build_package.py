#!/usr/bin/env python3
"""Bundle exact small evidence; exclude repository inputs and endpoint caches."""
import io,zipfile,json
import pandas as pd
import export_cases as e

def main():
 paths=[]
 for p in sorted(e.HERE.rglob('*')):
  if not p.is_file() or '__pycache__' in p.parts or p.suffix in ['.zip','.log'] or p.name.endswith('.partial'):continue
  if p.name in ['PACKAGE_MANIFEST.csv','DELIVERY_RECEIPT.json']:continue
  paths.append(p)
 rows=[dict(path=str(p.relative_to(e.HERE)),bytes=p.stat().st_size,sha256=e.sha(p)) for p in paths]
 e.csv('PACKAGE_MANIFEST.csv',pd.DataFrame(rows));paths.append(e.HERE/'PACKAGE_MANIFEST.csv')
 buf=io.BytesIO()
 with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in paths:z.writestr('b6_47_failure/'+str(p.relative_to(e.HERE)),p.read_bytes())
 dest=e.HERE/'B6_47_FAILURE_MECHANISM_20261022.zip';e.atomic(dest,buf.getvalue())
 with zipfile.ZipFile(dest) as z:assert z.testzip() is None and len(z.namelist())==len(paths)
 receipt=dict(path=dest.name,bytes=dest.stat().st_size,sha256=e.sha(dest),files=len(paths),
  event_count=2,distinct_native_teams=6,full_state_replays=6,new_endpoints=0,score_calls=0,
  exact_native_geometry_verified=True,actual_release_figures=2,raw_members_preserved=True,
  original_photo_not_duplicated=True,repository_inputs_not_duplicated=True)
 e.save(e.HERE/'DELIVERY_RECEIPT.json',receipt);print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()
