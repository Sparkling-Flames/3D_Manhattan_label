from pathlib import Path
import json,gzip,hashlib,collections
B=Path(__file__).resolve().parents[1]
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz'else p.read_bytes())
rp=B/'audit_learning/fresh_blocks/fresh_block_requests.json.gz';req=read(rp);run=read(B/'audit_replay/fresh_corner_blocks/RUN_fresh_block_requests.json');expected={(r['pool_id'],tuple(sorted(r['worker_ids']))):r for r in req['requests']};observed={};statuses=collections.Counter();hashes={}
snapshot=read(B/'restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz');pools={p['pool_id']:p for p in snapshot['images']}
for p in sorted((B/'audit_replay/fresh_corner_blocks/pools').glob('*.json.gz')):
 d=read(p);assert d['context']['science_commit']=='82c6164b0d4630de5316199c92aa405930973168' and d['context']['fusion_gap']==7.5
 hashes[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
 pool=pools[p.name[:-8]];by={r['worker_id']:r for r in pool['records']};assert d['context']['pool_digest']==hashlib.sha256(json.dumps(pool,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 for t in d['teams']:
  k=(t['pool_id'],tuple(t['member_workers']));assert k not in observed and k in expected and t['k']==len(k[1]);assert t['member_object_ids']==[by[w]['object_id']for w in t['member_workers']]
  assert all(t[f]==pool['meta'][f]for f in ['reference_id','reference_version','image_id','building'])
  observed[k]=t;statuses[t['score_status']]+=1
assert set(expected)==set(observed)and run['new_fusions']==len(observed)==12229
out=dict(all_passed=True,unique_native_fusions=len(observed),pools=len(hashes),images=len({t['image_id']for t in observed.values()}),buildings=len({t['building']for t in observed.values()}),workers=len({w for t in observed.values()for w in t['member_workers']}),score_status_counts=dict(statuses),request_sha256=hashlib.sha256(rp.read_bytes()).hexdigest(),exact_members_checked_all=True,exact_snapshot_context_and_reference_checked_all=True,pool_sha256=hashes,seconds=run['seconds'],scope='Fresh native evaluation of frozen discovery-nominated class-specific and category-independent block probe.12 reused internal assessment images; not an independent holdout. No post-result label/threshold/member tuning.')
(B/'audit_replay/FRESH_NATIVE_INDEPENDENT.json').write_text(json.dumps(out,indent=2));print({k:v for k,v in out.items()if k!='pool_sha256'})
