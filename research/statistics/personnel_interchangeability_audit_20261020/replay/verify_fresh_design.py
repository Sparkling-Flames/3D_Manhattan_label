from pathlib import Path
import json,gzip,hashlib,collections
B=Path(__file__).resolve().parents[1]
def read(p):return json.loads(gzip.decompress(p.read_bytes())if p.suffix=='.gz'else p.read_bytes())
def tk(pid,ws):return pid+'__'+hashlib.sha256(json.dumps(sorted(ws),sort_keys=True,separators=(',',':')).encode()).hexdigest()[:20]
p=B/'audit_learning/fresh_blocks/fresh_block_requests.json.gz';d=read(p);assert hashlib.sha256(p.read_bytes()).hexdigest()=='2324bf001fbc0b5387632758b817645fe5cd6965e391850a6ccc4e0c89167600'
snap=read(B/'restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz');pools={p['pool_id']:p for p in snap['images']};req={};nested={}
for r in d['requests']:
 ws=r['worker_ids'];pool=pools[r['pool_id']];by={r['worker_id']:r for r in pool['records']};assert len(ws)==len(set(ws))==r['k'];assert set(ws)<=by.keys();key=tk(r['pool_id'],ws);assert key==r['request_id']and key not in req;req[key]=set(ws)
for e in d['events']:
 sets={a:set(e[a+'_workers'])for a in 'ABC'};core=set(e['core_workers']);assert len(core)==e['n']-e['m'];assert core==set(e['core_prefix_order'][:e['n']-e['m']]);labels=d['label_maps'][e['method_id']];by={r['worker_id']:r for r in pools[e['pool_id']]['records']}
 for a in 'ABC':
  assert req[e[a+'_team_key']]==sets[a]and len(sets[a])==e['n'];counts=dict(collections.Counter(labels.get(w,'outside_group')for w in sets[a]));assert counts==e[a+'_counts'];assert all(by[w]['origin']=='new'for w in sets[a]-core)
 assert sets['A']&sets['B']==sets['A']&sets['C']==core
 assert len(sets['A']-sets['B'])==len(sets['A']-sets['C'])==e['m'];assert e['A_counts']==e['B_counts']and e['A_counts']!=e['C_counts']
 invariant=(e['core_prefix_order'],sorted(sets['A']-core),sorted(sets['B']-core),sorted(sets['C']-core));g=e['nested_group_id'];assert g not in nested or nested[g]==invariant;nested[g]=invariant
npairs=0
for a in d['common_anchors']:
 core=set(a['core_workers']);assert len(core)==a['n']-a['m']and core==set(a['core_prefix_order'][:a['n']-a['m']]);bs=a['blocks'];by={r['worker_id']:r for r in pools[a['pool_id']]['records']}
 for b in bs:
  ws=set(b['workers']);assert len(ws)==a['m']and not ws&core and all(by[w]['origin']=='new'for w in ws);assert req[b['team_key']]==core|ws
 for i,j in a['disjoint_block_pairs']:
  assert not set(bs[i]['workers'])&set(bs[j]['workers']);assert len(req[bs[i]['team_key']]-req[bs[j]['team_key']])==a['m'];npairs+=1
assert len(req)==12229 and len(d['events'])==2552 and len(d['common_anchors'])==152 and npairs==63476
out=dict(all_passed=True,request_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),teams=len(req),class_specific_events=len(d['events']),nested_groups=len(nested),common_anchors=len(d['common_anchors']),common_disjoint_block_pairs=npairs,checks=['Exact worker IDs, availability and deterministic team keys','Exact A/B/C class vectors and source-matched new-worker exchanged blocks','Exact turnover m and identical common core','Nested prefix cores and constant exchanged blocks within group','Shared-library blocks disjoint from core; each declared pair disjoint and exact m'],phase=d['spec']['assessment_status']);(B/'audit_replay/FRESH_DESIGN_INDEPENDENT.json').write_text(json.dumps(out,indent=2));print(out)
