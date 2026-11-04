"""Verify immutable natural inputs; optionally fetch missing files, never overwrite differences."""
from pathlib import Path
import argparse,json,hashlib,urllib.request,concurrent.futures
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[3]
def verify_one(record,download):
 p=ROOT/record['path']
 if not p.exists():
  if not download:return {'path':record['path'],'status':'missing'}
  with urllib.request.urlopen(urllib.request.Request(record['url'],headers={'User-Agent':'HOHONET-reproduction'}),timeout=90) as r:data=r.read()
  assert hashlib.sha256(data).hexdigest()==record['sha256'],record['path']
  p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.download');tmp.write_bytes(data);tmp.replace(p)
 else:data=p.read_bytes()
 if hashlib.sha256(data).hexdigest()!=record['sha256']:return {'path':record['path'],'status':'existing_file_hash_differs_not_overwritten'}
 return {'path':record['path'],'status':'verified'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');ap.add_argument('--download-missing',action='store_true');a=ap.parse_args()
 records=json.loads((OUT/'NATURAL_SOURCE_MANIFEST.json').read_text());results=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
  for x in ex.map(lambda r:verify_one(r,a.download_missing),records):results.append(x)
 bad=[r for r in results if r['status']!='verified'];print(json.dumps({'inputs':len(results),'verified':len(results)-len(bad),'issues':bad},ensure_ascii=False,indent=2))
 if bad:raise SystemExit(1)
if __name__=='__main__':main()
