"""Review/apply the HOHONET v2.1 document overlay without overwriting parallel work.

Default is read-only validation. --apply writes only after every document guard,
payload conflict check, and git-apply check passes. --study imports the actual
research delivery into a new independent archive directory. No push/commit occurs.
"""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys

HERE=Path(__file__).resolve().parent
META=json.loads((HERE/'UPDATED_FILES.json').read_text(encoding='utf-8'))
RECEIPT=json.loads((HERE/'UPDATE_RECEIPT.json').read_text(encoding='utf-8'))
WORKER=META['worker_path']
REQUIRED=[
    'REPORT_ZH.md','REPORT_ZH.html','DELIVERY_README.md',
    'stage01_half_team/README.md','stage01_half_team/MAIN_CHECKED_SUMMARY.csv',
    'stage02_same_room/README.md','stage02_same_room/EVIDENCE_COMPLETION_CHECKS.json',
    'stage03_speed_difficulty/README.md','stage03_speed_difficulty/REPORT_VALIDATION.json',
    'stage05_selection_stop/REPORT_ZH.md','stage05_selection_stop/validation/NUMERIC_RECONSTRUCTION_CHECKS.json',
    'stage06_synthesis/V2_TO_V21_CROSSWALK.csv','stage06_synthesis/GAP_REGISTER.csv',
    'source/research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json',
    'scripts/selection_stop_prepare.py',
]

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def git(repo,*args):return subprocess.run(['git','-C',str(repo),*args],capture_output=True,text=True)
def fail(message,detail=None):
    print(json.dumps({'ok':False,'reason':message,'detail':detail},ensure_ascii=False,indent=2),file=sys.stderr)
    raise SystemExit(2)

def plain_destination(repo,dest):
    try:parts=dest.relative_to(repo).parts
    except ValueError:fail('Destination escapes the repository',str(dest))
    current=repo
    for part in parts:
        current=current/part
        if current.is_symlink():fail('Destination has a symlink ancestor; review before any write',str(current))

def payload_plan(study,repo):
    target=repo/WORKER;out=[];ignored=[]
    if study==target:fail('--study must be the external complete delivery root, not the installed archive itself')
    for p in sorted(study.iterdir()):
        if p.name.startswith('.') or p.name=='repository_update':ignored.append(p.name);continue
        if p.is_dir():
            if p.name not in ['scripts','source'] and not p.name.startswith('stage'):
                ignored.append(p.name);continue
            choices=sorted(q for q in p.rglob('*') if q.is_file())
        else:
            if p.name.lower().endswith(('.zip','.tar','.tar.gz','.tgz','.7z')):
                ignored.append(p.name);continue
            choices=[p]
        for src in choices:
            rel=src.relative_to(study)
            if src.is_symlink():fail('Payload symlink requires manual review',str(rel))
            if any(x in ['__pycache__','.git'] for x in rel.parts) or src.name.endswith(('.pyc','.tmp','.part')):continue
            name='DELIVERY_README.md' if rel.as_posix()=='README.md' else rel.as_posix()
            dst=target/name
            plain_destination(repo,dst)
            h=digest(src)
            if dst.is_symlink():fail('Existing payload symlink requires manual review',str(dst))
            if dst.exists() and (not dst.is_file() or digest(dst)!=h):fail('Existing research archive file differs; refusing to overwrite parallel work',str(dst))
            out.append(dict(source=str(src),target=name,sha256=h,bytes=src.stat().st_size,already_present=dst.exists()))
    names={x['target'] for x in out}
    missing=[name for name in REQUIRED if name not in names and not (target/name).is_file()]
    if missing:fail('Complete research payload is required before document publication',missing)
    return out,ignored

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo',required=True,type=Path)
    ap.add_argument('--study',type=Path,help='Complete extracted delivery; imported only with --apply')
    ap.add_argument('--apply',action='store_true',help='Actually import data and apply the validated document patch')
    ap.add_argument('--receipt',type=Path,help='Optional write path for an application receipt (not used in default check mode)')
    args=ap.parse_args();repo=args.repo.resolve()
    if not repo.is_dir():fail('Repository directory does not exist',str(repo))
    top=git(repo,'rev-parse','--show-toplevel')
    if top.returncode or Path(top.stdout.strip()).resolve()!=repo:fail('--repo must be the actual Git worktree root',top.stderr.strip())
    patch=HERE/'UPDATE.patch'
    if digest(patch)!=RECEIPT['patch_sha256']:fail('Patch SHA256 does not match the frozen update receipt')
    checks=[];conflicts=[]
    for row in META['files']:
        dest=repo/row['path'];plain_destination(repo,dest);actual=None
        if dest.is_symlink():conflicts.append(dict(path=row['path'],reason='symlink'));continue
        if dest.exists():
            if not dest.is_file():conflicts.append(dict(path=row['path'],reason='not_regular_file'));continue
            actual=digest(dest)
        expected=row['base_sha256']
        state='base' if actual==expected else ('updated' if actual==row['updated_sha256'] else 'conflict')
        checks.append(dict(path=row['path'],state=state,base_sha256=expected,actual_sha256=actual))
        if state=='conflict':conflicts.append(checks[-1])
        if digest(HERE/'overlay'/row['path'])!=row['updated_sha256']:fail('Overlay SHA256 mismatch',row['path'])
    if conflicts:fail('Document SHA256 guard blocked differing files. Preserve the parallel version and review/rebase the dated addition; no files were changed.',conflicts)
    states={x['state'] for x in checks}
    if len(states)>1:fail('Only some document updates are present. No automatic partial overwrite; review the listed states.',checks)
    already=states=={'updated'}
    if not already:
        check=git(repo,'apply','--check',str(patch))
        if check.returncode:fail('git apply --check rejected the patch; no files were changed',check.stderr.strip())
    payload=[];ignored=[]
    if args.study:
        study=args.study.resolve()
        if not study.is_dir():fail('--study directory does not exist',str(study))
        payload,ignored=payload_plan(study,repo)
    else:
        missing=[name for name in REQUIRED if not (repo/WORKER/name).is_file()]
        if args.apply and missing:fail('Research files are not yet installed. Supply --study <complete delivery> before publishing document links.',missing)
    head=git(repo,'rev-parse','--verify','HEAD')
    receipt_path=args.receipt.resolve() if args.receipt else repo/WORKER/'REPOSITORY_APPLICATION_RECEIPT.json'
    if args.apply and receipt_path.exists():fail('Application receipt already exists; choose a new --receipt path. No files were changed.',str(receipt_path))
    result=dict(ok=True,mode='apply' if args.apply else 'read_only_check',base_commit=META['base_commit'],target_head=head.stdout.strip() if head.returncode==0 else None,document_checks=checks,documents_already_updated=already,git_apply_check=True,payload_files_checked=len(payload),payload_new_files=sum(not p['already_present'] for p in payload),payload_bytes=sum(p['bytes'] for p in payload),ignored_top_level=ignored,payload_import_performed=False,documents_applied=False,remote_pushed=False,repository=str(repo))
    if not args.apply:
        if not args.study:result['payload_note']='Document-only check; full payload or --study is required for --apply.'
        print(json.dumps(result,ensure_ascii=False,indent=2));return
    # All guards above pass before the first mutation. Exclusive creation prevents overwrites.
    installed=[]
    for row in payload:
        src=Path(row['source']);dst=repo/WORKER/row['target']
        if digest(src)!=row['sha256']:fail('Payload source changed after preflight; stopped without overwriting any existing file',row['source'])
        if row['already_present']:continue
        dst.parent.mkdir(parents=True,exist_ok=True)
        try:
            with src.open('rb') as inp,dst.open('xb') as out:shutil.copyfileobj(inp,out,1<<20)
        except FileExistsError:fail('Payload destination appeared concurrently; stopped without overwrite',str(dst))
        if digest(dst)!=row['sha256']:fail('New payload copy failed SHA256 verification',str(dst))
        installed.append(row['target'])
    if not already:
        # Check the document bytes again immediately before application.
        for row in META['files']:
            dest=repo/row['path'];actual=digest(dest) if dest.is_file() else None
            if actual!=row['base_sha256']:fail('Document changed during payload import; no document was overwritten',row['path'])
        applied=git(repo,'apply',str(patch))
        if applied.returncode:fail('Git rejected application after preflight. Imported research files are preserved; inspect the error.',applied.stderr.strip())
        result['documents_applied']=True
    for row in META['files']:
        if digest(repo/row['path'])!=row['updated_sha256']:fail('Post-apply document SHA256 mismatch',row['path'])
    result.update(payload_import_performed=bool(payload),payload_new_files_installed=len(installed),all_updated_document_sha256_verified=True,all_new_payload_sha256_verified=True)
    receipt_path.parent.mkdir(parents=True,exist_ok=True)
    with receipt_path.open('x',encoding='utf-8') as receipt_file:receipt_file.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
