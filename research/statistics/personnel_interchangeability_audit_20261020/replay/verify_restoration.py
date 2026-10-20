from pathlib import Path
import json,hashlib,datetime
B=Path(__file__).resolve().parents[1];m=B/'source_repo/research/workers/personnel_type_discovery_next_20261019/ARCHIVE_FILE_MAP.json';rs=json.loads(m.read_text());bad=[];total=0
for r in rs:
 p=B/'restored'/r['path'];ok=p.exists()and p.stat().st_size==r['bytes']and hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
 if not ok:bad.append(r['path'])
 else:total+=r['bytes']
out=dict(all_passed=not bad,files_verified=len(rs)-len(bad),manifest_files=len(rs),bytes_verified=total,failures=bad,manifest_sha256=hashlib.sha256(m.read_bytes()).hexdigest(),checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),method='Original archive bundles extracted with per-file SHA checks; frozen repository sources recovered via original Git objects or direct raw.githubusercontent.com pinned-commit reads. This receipt independently checks every resulting byte against the original ARCHIVE_FILE_MAP. No original content changed.');(B/'audit_replay/RESTORATION_INDEPENDENT.json').write_text(json.dumps(out,indent=2));print(out)
