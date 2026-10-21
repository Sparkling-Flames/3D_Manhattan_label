"""Rebuild the original 13 member manifests, without recomputing fusion.

The original generators run unchanged. Every generated gzip must have exactly
the previously audited SHA256; only the resulting sorted set-key index is kept
in the compact study. Large rebuilt request files live in scratch. This is a
set-coverage recovery, not a claim that excluded historical geometries exist.
"""
from __future__ import annotations
import gzip,hashlib,importlib.metadata,json,os,subprocess,sys,time
from pathlib import Path
from global_study import ROOT,OUT,FUSION,save,read

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    package=ROOT/'research/workers/personnel_composition_study_20261019'
    sys.path.insert(0,str(package/'analysis/independent'))
    import audit_reproduce_requests as audit
    previous=read(package/'analysis/independent/REPRODUCTION_AUDIT.json')
    checked=[]
    for logical,expected in previous['source_sha256'].items():
        p=FUSION/'INPUT_SNAPSHOT.json.gz' if logical.startswith('restored/') else package/logical
        actual=sha(p)
        if actual!=expected:raise ValueError(f'Historical source changed: {logical}')
        checked.append(dict(logical=logical,path=str(p.relative_to(ROOT)),sha256=actual))
    audit.SNAPSHOT=FUSION/'INPUT_SNAPSHOT.json.gz'
    rebuilt=OUT/'runtime/historical_requests';rebuilt.mkdir(parents=True,exist_ok=True)
    keys=set();receipts=[];start=time.monotonic();nrequests=0
    for name,cmd in audit.commands(rebuilt):
        p=rebuilt/name;t=time.monotonic();cached=p.exists() and sha(p)==audit.EXPECTED[name]
        if not cached:subprocess.run(cmd,cwd=package,check=True,capture_output=True,text=True)
        actual=sha(p)
        if actual!=audit.EXPECTED[name]:raise ValueError(f'Historical manifest SHA mismatch: {name}')
        payload=read(p)
        for row in payload['requests']:
            if audit.exact_team_key(row['pool_id'],row['worker_ids'])!=row['team_key']:raise ValueError('team key mismatch')
            keys.add(row['team_key'])
        nrequests+=len(payload['requests'])
        receipt=dict(manifest=name,requests=len(payload['requests']),sha256=actual,byte_identical=True,seconds=time.monotonic()-t,reused_manifest=cached)
        receipts.append(receipt);print(json.dumps(receipt),flush=True)
        del payload
    if len(keys)!=583261 or nrequests!=589990:raise ValueError(('historical coverage mismatch',len(keys),nrequests))
    out=OUT/'HISTORICAL_TEAM_KEYS.txt.gz'
    out.write_bytes(gzip.compress(('\n'.join(sorted(keys))+'\n').encode(),compresslevel=5,mtime=0))
    save(OUT/'HISTORICAL_RECOVERY_RECEIPT.json',dict(source_sha256=checked,manifests=receipts,unique_actual_teams=len(keys),request_rows=nrequests,
       key_index_sha256=sha(out),fusion_recomputed=False,geometries_recovered=False,seconds=time.monotonic()-start,
       packages={x:importlib.metadata.version(x) for x in ('numpy','pandas','scipy')},
       scope='Only unchanged pure request generators; exact byte hashes verified against the prior independent audit. Native fusion or scoring is not invoked.'))
    print(json.dumps(dict(unique_actual_teams=len(keys),requests=nrequests,seconds=time.monotonic()-start)),flush=True)

if __name__=='__main__':main()
