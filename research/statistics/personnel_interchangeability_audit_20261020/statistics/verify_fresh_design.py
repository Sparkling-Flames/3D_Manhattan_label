from pathlib import Path
from collections import Counter,defaultdict
import gzip,json,hashlib,itertools
B=Path('/workspace/shared/interchangeability_audit_20261020');P=B/'audit_learning/fresh_blocks/fresh_block_requests.json.gz';d=json.load(gzip.open(P,'rt'));s=json.load(gzip.open(B/'restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz','rt'));pools={p['pool_id']:p for p in s['images']};req={r['request_id']:r for r in d['requests']};assert len(req)==len(d['requests'])
def sha(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
for r in req.values():
 assert len(r['worker_ids'])==len(set(r['worker_ids']))==r['k'];assert r['request_id']==r['pool_id']+'__'+sha(sorted(r['worker_ids']))[:20]
 assert set(r['worker_ids'])<=set(x['worker_id'] for x in pools[r['pool_id']]['records'])
nested=defaultdict(list)
for e in d['events']:
 pid=e['pool_id'];orig={r['worker_id']:r['origin'] for r in pools[pid]['records']};mp=d['label_maps'][e['method_id']];core=set(e['core_workers']);arms={a:set(e[a+'_workers']) for a in 'ABC'};blocks=[set(e[x]) for x in ['outgoing_workers','within_incoming','cross_incoming']]
 assert len(core)==e['n']-e['m'];assert all(len(z)==e['m'] for z in blocks);assert all(not(x&y) for x,y in itertools.combinations(blocks,2));assert all(not(z&core) for z in blocks)
 assert all(orig[w]=='new' for z in blocks for w in z);assert set(e['core_prefix_order'][:e['n']-e['m']])==core
 for a,bl in zip('ABC',blocks):
  assert arms[a]==core|bl and len(arms[a])==e['n'];assert Counter(mp.get(w,'outside_group') for w in arms[a])==Counter(e[a+'_counts']);assert set(req[e[a+'_team_key']]['worker_ids'])==arms[a]
 assert e['A_counts']==e['B_counts'] and e['A_counts']!=e['C_counts']
 for a,b in itertools.combinations('ABC',2):assert arms[a]&arms[b]==core and len(arms[a]-arms[b])==e['m']
 nested[e['nested_group_id']].append(e)
for g in nested.values():
 g.sort(key=lambda e:e['n']);assert [e['n'] for e in g]==list(range(5,max(e['n'] for e in g)+1))
 for a,b in zip(g,g[1:]):
  for arm in 'ABC':assert len(set(b[arm+'_workers'])-set(a[arm+'_workers']))==1 and set(a[arm+'_workers'])<set(b[arm+'_workers'])
pair_count=0
for a in d['common_anchors']:
 core=set(a['core_workers']);reservoir=set(a['entrant_reservoir']);orig={r['worker_id']:r['origin'] for r in pools[a['pool_id']]['records']};assert not core&reservoir;assert all(orig[w]=='new' for w in reservoir)
 blocks=[set(b['workers']) for b in a['blocks']];assert len({tuple(sorted(x)) for x in blocks})==len(blocks)
 for block,b in zip(blocks,a['blocks']):
  assert len(block)==a['m'] and block<=reservoir;assert set(req[b['team_key']]['worker_ids'])==core|block;assert len(core|block)==a['n']
 expected={p for p in itertools.combinations(range(len(blocks)),2) if not blocks[p[0]]&blocks[p[1]]};assert expected==set(map(tuple,a['disjoint_block_pairs']));pair_count+=len(expected)
 assert set(a['core_prefix_order'][:a['n']-a['m']])==core
# Independently reconstruct metadata-only image selection.
for selection in d['spec']['image_selection']:
 candidates=[p['pool_id'] for p in pools.values() if p['meta']['building']==selection['building'] and p['meta']['layer']=='ordinary_manual' and sum(r['origin']=='new' for r in p['records'])>=6]
 ordered=sorted(candidates,key=lambda pid:sha([2026102029,'images',pid]));assert ordered==selection['eligible_pool_ids'];assert ordered[:2]==selection['selected_pool_ids']
r=dict(request_sha256=hashlib.sha256(P.read_bytes()).hexdigest(),unique_teams=len(req),events=len(d['events']),nested_paths=len(nested),all_exact_turnovers_and_actual_class_counts_pass=True,all_nested_core_prefixes_pass=True,all_exchange_blocks_new_source=True,common_anchors=len(d['common_anchors']),common_disjoint_pairs=pair_count,complete_disjoint_pair_enumeration_pass=True,image_selection_sha_order_pass=True,selected_images=sum(len(x['selected_pool_ids']) for x in d['spec']['image_selection']),buildings=len(d['spec']['image_selection']),capacity_statuses=dict(Counter(x['status'] for x in d['ledger'])),scope='New exploratory reuse of assessment images, nominated after discovery; not external confirmation and no cross-method ranking of unequal class-specific ABCs.')
(B/'audit_statistics/FRESH_DESIGN_RECEIPT.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
