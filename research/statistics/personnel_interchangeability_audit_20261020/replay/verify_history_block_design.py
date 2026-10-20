from pathlib import Path
import json,gzip,hashlib,collections
B=Path(__file__).resolve().parents[1]
def read(p):return json.loads(gzip.decompress(p.read_bytes())if p.suffix=='.gz'else p.read_bytes())
def tk(pid,ws):return pid+'__'+hashlib.sha256(json.dumps(sorted(ws),sort_keys=True,separators=(',',':')).encode()).hexdigest()[:20]
p=B/'audit_learning/history_blocks/history_block_requests.json.gz';d=read(p);assert hashlib.sha256(p.read_bytes()).hexdigest()=='9fa849e711bbe71d2b052096aeadb9722cb2b1f22f08b90a7940a61e900e9e00'
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
npairs=0;common_nested={}
for a in d['common_anchors']:
 core=set(a['core_workers']);assert len(core)==a['n']-a['m']and core==set(a['core_prefix_order'][:a['n']-a['m']]);bs=a['blocks'];by={r['worker_id']:r for r in pools[a['pool_id']]['records']}
 for b in bs:
  ws=set(b['workers']);assert len(ws)==a['m']and not ws&core and all(by[w]['origin']=='new'for w in ws);assert req[b['team_key']]==core|ws
 invariant=(a['core_prefix_order'],[(b['block_index'],b['workers'])for b in bs]);g=a['nested_group_id'];assert g not in common_nested or common_nested[g]==invariant;common_nested[g]=invariant
 for i,j in a['disjoint_block_pairs']:
  assert not set(bs[i]['workers'])&set(bs[j]['workers']);assert len(req[bs[i]['team_key']]-req[bs[j]['team_key']])==a['m'];npairs+=1
assert len(req)==7670 and len(d['events'])==0 and len(d['common_anchors'])==160 and npairs==144140
split=read(B/'unpacked/analysis/composition/SPLIT.json');buildings={pools[r['pool_id']]['meta']['building']for r in d['requests']};assert buildings==set(split['history_buildings'])and not buildings&set(split['discovery_buildings']+split['validation_buildings'])
out=dict(history_buildings_only=True,all_ten_history_buildings_covered=True,all_passed=True,request_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),teams=len(req),class_specific_events=len(d['events']),nested_groups=len(nested),common_nested_groups=len(common_nested),common_anchors=len(d['common_anchors']),common_disjoint_block_pairs=npairs,checks=['Exact worker IDs, availability and deterministic team keys','Every exchanged block contains only available new-source workers; no class labels used','Exact turnover m and identical common core','Nested prefix cores and constant exchanged blocks within group','Shared-library blocks disjoint from core; each declared pair disjoint and exact m'],phase='history_block_training');(B/'audit_replay/HISTORY_BLOCK_DESIGN_INDEPENDENT.json').write_text(json.dumps(out,indent=2));print(out)
