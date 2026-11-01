#!/usr/bin/env python3
"""Read every compressed result to EOF and check marker counts and source hashes."""
import argparse,csv,gzip,hashlib,json,sys
from pathlib import Path
import pandas as pd
import analyze_response as ar

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['manual','doorway'],required=True);ap.add_argument('--invalidate-bad',action='store_true');args=ap.parse_args()
 root=Path(__file__).resolve().parents[1];base=root/'stage03_response'/args.mode
 index=pd.read_csv(root/'stage02_normalized'/args.mode/'POOL_INDEX.csv');rows=[];bad=[]
 expected_code=hashlib.sha256(Path(ar.__file__).read_bytes()).hexdigest()
 expected_config=hashlib.sha256(json.dumps(ar.CONFIG,sort_keys=True).encode()).hexdigest()
 for i,idx in enumerate(index.to_dict('records')):
  p=base/'by_pool'/idx['pool_id']/'COMPLETION.json';issues=[];checked=0
  if not p.exists():issues.append('missing marker');marker={}
  else:
   marker=json.loads(p.read_text())
   if marker['code_sha256']!=expected_code:issues.append('code hash mismatch')
   if marker['config_sha256']!=expected_config:issues.append('config hash mismatch')
   sf=ar.input_file(idx,root)
   if hashlib.sha256(sf.read_bytes()).hexdigest()!=marker['source_sha256']:issues.append('source hash mismatch')
   for name,expected_n in marker['output_rows'].items():
    f=p.parent/name
    try:
     with gzip.open(f,'rt',encoding='utf-8-sig',newline='') as h:
      reader=csv.reader(h);header=next(reader,[]);n=0
      for row in reader:
       if len(row)!=len(header):raise ValueError(f'row {n+1} width {len(row)} != header {len(header)}')
       n+=1
     if n!=expected_n:issues.append(f'{name}: row count {n} != {expected_n}')
     checked+=1
    except Exception as e:issues.append(f'{name}: {type(e).__name__}: {e}')
  if issues:
   bad.append(idx['pool_id'])
   if args.invalidate_bad and p.exists():p.rename(p.with_name('COMPLETION.invalidated.json'))
  rows.append({'pool_id':idx['pool_id'],'files_read_to_EOF':checked,'ok':not issues,'issues':issues})
  if (i+1)%25==0:print(json.dumps({'checked_pools':i+1,'total':len(index),'bad_so_far':len(bad)}),flush=True)
 result={'mode':args.mode,'pools':len(index),'bad_pools':bad,'files_read_to_EOF':sum(r['files_read_to_EOF'] for r in rows),'rows':rows}
 out=base/'CHECKPOINT_READBACK.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
