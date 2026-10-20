from pathlib import Path
import json,gzip,hashlib,collections
B=Path(__file__).resolve().parents[1]
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz'else p.read_bytes())
rp=B/'unpacked/interchangeability_20261020/history_panel/history_requests.json.gz';req=read(rp);run=read(B/'audit_replay/history_native/RUN_history_requests.json');expected={(r['pool_id'],tuple(sorted(r['worker_ids']))):r for r in req['requests']};observed={};statuses=collections.Counter();hashes={}
for p in sorted((B/'audit_replay/history_native/pools').glob('*.json.gz')):
 d=read(p);assert d['context']['science_commit']=='82c6164b0d4630de5316199c92aa405930973168' and d['context']['fusion_gap']==7.5
 hashes[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
 for t in d['teams']:
  k=(t['pool_id'],tuple(t['member_workers']));assert k not in observed and k in expected and t['k']==len(k[1]);observed[k]=t;statuses[t['score_status']]+=1
assert set(expected)==set(observed)and run['new_fusions']==len(observed)==31539
out=dict(all_passed=True,unique_native_fusions=len(observed),pools=len(hashes),images=len({t['image_id']for t in observed.values()}),buildings=len({t['building']for t in observed.values()}),workers=len({w for t in observed.values()for w in t['member_workers']}),score_status_counts=dict(statuses),request_sha256=hashlib.sha256(rp.read_bytes()).hexdigest(),exact_members_checked_all=True,pool_sha256=hashes,seconds=run['seconds'],scope='Fresh native reconstruction of frozen H20 history requests for history-only classification and corner-distance diagnostics. No target outcome used here; this is not a new independent validation sample.')
(B/'audit_replay/HISTORY_NATIVE_INDEPENDENT.json').write_text(json.dumps(out,indent=2));print({k:v for k,v in out.items()if k!='pool_sha256'})
