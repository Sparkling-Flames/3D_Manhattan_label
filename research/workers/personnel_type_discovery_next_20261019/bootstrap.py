#!/usr/bin/env python3
"""Restore all original Part A ZIP members with SHA256 verification. No numerical run/network."""
import argparse,gzip,hashlib,json,pathlib,subprocess,tarfile,tempfile
HERE=pathlib.Path(__file__).resolve().parent

def safe(root,rel):
 p=(root/rel).resolve()
 if not p.is_relative_to(root.resolve()):raise ValueError('Unsafe path: '+rel)
 return p

def checked(data,row):
 if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Content mismatch: '+row['path'])
 return data

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--output',type=pathlib.Path,required=True,help='New empty directory; existing files never overwritten')
 ap.add_argument('--repository',type=pathlib.Path,help='Repository clone, inferred from this script otherwise')
 ap.add_argument('--previous-archive',type=pathlib.Path,help='Optional location of prior curated archive')
 args=ap.parse_args(); repo=(args.repository or HERE.parents[2]).resolve()
 old=(args.previous_archive or repo/'research/workers/pro_personnel_v2_archive_20261019').resolve()
 out=args.output.resolve()
 if out.exists() and any(out.iterdir()):raise SystemExit('Output must be new or empty: '+str(out))
 rows=json.loads((HERE/'ARCHIVE_FILE_MAP.json').read_text()); out.mkdir(parents=True,exist_ok=True)
 total=0
 mapping={r['path']:r for r in rows}
 for bundle in json.loads((HERE/'PAYLOAD_BUNDLES.json').read_text()):
  with tempfile.TemporaryFile()as packed:
   for part in bundle['parts']:
    data=safe(HERE,part['path']).read_bytes();checked(data,part);packed.write(data)
   packed.seek(0)
   with tarfile.open(fileobj=packed,mode='r:gz')as tar:
    seen=set()
    for member in tar:
     if not member.isfile() or member.name not in mapping:raise ValueError('Unexpected tar entry '+member.name)
     r=mapping[member.name]
     if r.get('bundle')!=bundle['id']or member.name in seen:raise ValueError('Unexpected/duplicate bundle entry')
     data=tar.extractfile(member).read();checked(data,r)
     dest=safe(out,r['path']);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);seen.add(member.name)
    if len(seen)!=bundle['files']:raise ValueError('Bundle file count mismatch')
 for r in rows:
  mode=r['disposition']
  if mode=='retained_in_bundle':
   data=safe(out,r['path']).read_bytes()
  elif mode=='reuse_repository_source':
   p=safe(repo,r['source_path']);data=p.read_bytes()if p.is_file()else b''
   if hashlib.sha256(data).hexdigest()!=r['sha256']:
    result=subprocess.run(['git','-C',str(repo),'show',r['source_commit']+':'+r['source_path']],capture_output=True)
    if result.returncode:raise RuntimeError('Missing pinned source; fetch full history/commit first: '+r['source_path'])
    data=result.stdout
  elif mode=='reuse_previous_archive':
   ent=r['previous_entry'];parts=ent.get('stored_parts')or[ent['stored_path']]
   data=b''.join(safe(old,p).read_bytes()for p in parts)
   if ent.get('encoding')=='gzip':data=gzip.decompress(data)
  else:
   blocks=[]
   for part in r['parts']:
    b=safe(HERE,part['path']).read_bytes();checked(b,part);blocks.append(b)
   data=b''.join(blocks)
   if r['encoding']=='gzip':data=gzip.decompress(data)
  checked(data,r);dest=safe(out,r['path']);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);total+=len(data)
 receipt=dict(files_verified=len(rows),bytes_verified=total,repository=str(repo),previous_archive=str(old),output=str(out),scientific_runs_executed=False)
 (out/'RESTORATION_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
