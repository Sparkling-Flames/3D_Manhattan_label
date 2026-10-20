import json,gzip,hashlib,pathlib
B=pathlib.Path(__file__).resolve().parents[1];P=B/'unpacked';R=B/'restored';O=B/'audit_replay'
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
audit=read(P/'interchangeability_20261020/independent/SOURCE_PARITY_AUDIT.json');rows=[]
for r in audit['critical_files']:
 p=R/pathlib.Path(r['local_replay_path']).relative_to('restored');got=sha(p)if p.exists()else None;rows.append(dict(path=str(p.relative_to(R)),expected_sha256=r['sha256'],actual_sha256=got,passed=got==r['sha256'],is_lfs_pointer=p.read_bytes().startswith(b'version https://git-lfs.github.com/spec/v1')if p.exists()else None))
snap=R/'work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz';s=read(snap);pools={p['pool_id']:p for p in s['images']};cases=[]
for p in sorted((P/'interchangeability_20261020/cases').glob('S*.json')):
 c=read(p);e=c['embedded_pool'];original=pools[c['pool_id']];by={x['worker_id']:x for x in original['records']};cases.append(dict(case=p.stem,reference_exact=e['reference']==original['reference'],meta_exact=e['meta']==original['meta'],records_exact=all(x==by[x['worker_id']] for x in e['records']),members=len(e['records'])))
out=dict(source_files=rows,all_source_files_exact=all(r['passed']for r in rows),snapshot_sha256=sha(snap),snapshot_N1_applied=s['N1_applied'],snapshot_fusion_gap=s['fusion_gap'],snapshot_commit=s['git_commit'],snapshot_pools=len(pools),embedded_cases=cases,all_embedded_inputs_exact=all(c['reference_exact']and c['meta_exact']and c['records_exact']for c in cases))
(O/'FROZEN_INPUTS_INDEPENDENT.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
