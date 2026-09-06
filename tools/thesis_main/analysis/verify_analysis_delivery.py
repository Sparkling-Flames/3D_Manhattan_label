"""Seal or verify analysis outputs; optionally verify exact bytes in a Git ref.
Never considers workflow/source-only commits a completed result delivery.
"""
from __future__ import annotations
import argparse,hashlib,json,os,subprocess,zipfile
from pathlib import Path

def digest(data:bytes)->str:
 return hashlib.sha256(data).hexdigest()

def verify(root:Path,manifest:dict,git_ref:str|None=None)->None:
 repository=Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True).strip()) if git_ref else None
 for item in manifest['files']:
  p=root/item['path']
  if not p.is_file():raise FileNotFoundError(p)
  data=p.read_bytes()
  if len(data)!=item['bytes'] or digest(data)!=item['sha256']:raise ValueError(f'Local hash mismatch: {p}')
  if git_ref:
   rel=p.resolve().relative_to(repository.resolve()).as_posix()
   remote=subprocess.check_output(['git','show',f'{git_ref}:{rel}'])
   if digest(remote)!=item['sha256']:raise ValueError(f'Git read-back hash mismatch: {rel}')

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--seal',action='store_true');parser.add_argument('--archive',type=Path);parser.add_argument('--git-ref');parser.add_argument('--minimum-files',type=int,default=1);parser.add_argument('--require',action='append',default=[]);args=parser.parse_args()
 root=args.root.resolve();target=root/'DELIVERY_MANIFEST.json'
 for name in args.require:
  p=root/name
  if not p.is_file() or not p.stat().st_size:raise ValueError(f'Required output missing/empty: {p}')
 if args.seal:
  excluded={target}
  if args.archive:excluded|={args.archive.resolve(),Path(str(args.archive.resolve())+'.sha256')}
  files=[]
  for p in sorted(root.rglob('*')):
   if p.is_file() and p.resolve() not in excluded:
    data=p.read_bytes();files.append(dict(path=p.relative_to(root).as_posix(),bytes=len(data),sha256=digest(data)))
  if len(files)<args.minimum_files:raise ValueError(f'Only {len(files)} outputs, required {args.minimum_files}')
  try:commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
  except (subprocess.CalledProcessError,FileNotFoundError):commit='local_untracked_workspace'
  manifest=dict(status='sealed_and_locally_verified',source_commit=commit,run_id=os.environ.get('GITHUB_RUN_ID'),file_count=len(files),files=files,raw_data_modified=False,archive_excludes_itself_and_sha_sidecar=True)
  target.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 else:manifest=json.loads(target.read_text(encoding='utf-8'))
 verify(root,manifest,args.git_ref)
 if args.archive:
  archive=args.archive.resolve()
  if args.seal:
   with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for item in manifest['files']:z.write(root/item['path'],item['path'])
    z.write(target,target.name)
   Path(str(archive)+'.sha256').write_text(digest(archive.read_bytes())+'  '+archive.name+'\n')
  with zipfile.ZipFile(archive) as z:
   bad=z.testzip()
   if bad:raise ValueError(f'CRC error: {bad}')
   for item in manifest['files']:
    if digest(z.read(item['path']))!=item['sha256']:raise ValueError(f'Archive hash mismatch: {item["path"]}')
   if z.read(target.name)!=target.read_bytes():raise ValueError('Archive manifest differs')
  if args.git_ref:
   repository=Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True).strip())
   for p in [target,archive,Path(str(archive)+'.sha256')]:
    remote=subprocess.check_output(['git','show',f'{args.git_ref}:{p.relative_to(repository.resolve()).as_posix()}'])
    if digest(remote)!=digest(p.read_bytes()):raise ValueError(f'Git publication mismatch: {p}')
 print(json.dumps(dict(verified=True,file_count=manifest['file_count'],archive=str(args.archive) if args.archive else None,git_ref=args.git_ref),indent=2))
if __name__=='__main__':main()
