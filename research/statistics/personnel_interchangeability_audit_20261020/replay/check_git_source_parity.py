from pathlib import Path
import subprocess,json,hashlib
B=Path(__file__).resolve().parents[1];repo=B/'source_repo';audit=json.loads((B/'unpacked/interchangeability_20261020/independent/SOURCE_PARITY_AUDIT.json').read_text());head=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD']).decode().strip();commits=['e572eb73bedc4fe9056df838e458bab83c3fa423','445686f8f3cf6039c4ce1f60016cad1d26829044',head];rows=[]
for r in audit['critical_files']:
 p=B/r['local_replay_path'];raw=p.read_bytes();blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest();observed={}
 for c in commits:
  line=subprocess.check_output(['git','-C',str(repo),'ls-tree',c,'--',r['repository_path']]).decode().strip();observed[c]=line.split()[2]if line else None
 rows.append(dict(repository_path=r['repository_path'],restored_blob_sha1=blob,git_tree_blobs=observed,all_match=all(v==blob for v in observed.values())))
result=dict(all_passed=all(r['all_match']for r in rows),current_checked_main=head,rows=rows);(B/'audit_replay/GIT_SOURCE_PARITY_INDEPENDENT.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
