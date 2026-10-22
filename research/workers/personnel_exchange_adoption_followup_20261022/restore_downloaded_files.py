#!/usr/bin/env python3
"""Restore separately downloaded named artifacts into their original repo paths.

Default: validate and report only. --install links/copies missing destinations.
Existing different files cause a conflict; they are never silently overwritten.
No network, fusion, scoring or classification is performed.
"""
from pathlib import Path
import argparse,csv,hashlib,json,os,shutil

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--downloads',type=Path,required=True)
 p.add_argument('--repo',type=Path,required=True)
 p.add_argument('--install',action='store_true')
 a=p.parse_args();repo=a.repo.resolve();srcroot=a.downloads.resolve()
 rows=list(csv.DictReader((Path(__file__).parent/'DOWNLOAD_MAP.csv').open(encoding='utf-8-sig')))
 result=[]
 for r in rows:
  src=srcroot/r['download_filename'];dst=repo/r['repo_destination']
  if not dst.resolve().is_relative_to(repo):raise ValueError(r['repo_destination'])
  state='not_downloaded'
  if src.is_file():
   if sha(src)!=r['sha256']:raise ValueError('Download checksum differs: '+str(src))
   if dst.exists():
    if sha(dst)!=r['sha256']:raise FileExistsError('Existing destination differs: '+str(dst))
    state='already_present'
   elif a.install:
    dst.parent.mkdir(parents=True,exist_ok=True)
    try:os.link(src,dst)
    except OSError:shutil.copyfile(src,dst)
    state='restored'
   else:state='ready_to_restore'
  elif dst.is_file() and sha(dst)==r['sha256']:state='already_present'
  result.append({'file':r['download_filename'],'status':state,'destination':str(dst)})
 print(json.dumps({'install':a.install,'files':result},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
