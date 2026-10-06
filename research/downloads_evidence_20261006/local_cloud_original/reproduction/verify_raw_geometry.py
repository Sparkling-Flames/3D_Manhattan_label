"""Independent pure-Python checks, without importing delivery code."""
from pathlib import Path
import argparse,json,gzip,itertools,math
parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True,help='Extracted delivery package root');parser.add_argument('--replay',type=Path,required=True,help='Newly reproduced results directory');args=parser.parse_args()
ROOT=args.source;R=args.replay;BASE=R.parent
load=lambda p:json.loads(p.read_text());nodes=load(R/'domains/node_lookup.json');checks=[]
def check(name,observed,expected):checks.append(dict(check=name,observed=observed,expected=expected,passed=observed==expected))
def xyz(pt):
 lon=(pt[0]/1024-.5)*2*math.pi;lat=(.5-pt[1]/512)*math.pi
 return (math.cos(lat)*math.sin(lon),math.sin(lat),-math.cos(lat)*math.cos(lon))
def angle(a,b):
 a,b=xyz(a),xyz(b);cross=(a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
 return math.degrees(math.atan2(math.sqrt(math.fsum(x*x for x in cross)),math.fsum(x*y for x,y in zip(a,b))))
dist={};provenance_errors=[]
for image,ns in nodes.items():
 records={r['id']:r for r in load(ROOT/'inputs'/f'{image}.json')['records']}
 for n in ns:
  r=records[n['id']];i=n['pair_index'];pairs=r['points'][2*i:2*i+2]
  if not (n['worker']==r['worker'] and n['points']==pairs and n['source_pair_index']==r['source_pair_indices'][i] and n['source_point_indices']==r['source_point_indices'][2*i:2*i+2]):provenance_errors.append([image,n['id'],i])
 for metric in ('pair','top','bottom'):
  dd={}
  for i,j in itertools.combinations(range(len(ns)),2):
   ds=[angle(ns[i]['points'][k],ns[j]['points'][k]) for k in (0,1)]
   dd[i,j]=max(ds) if metric=='pair' else ds[0 if metric=='top' else 1]
  dist[image,metric]=dd
check('all_400_lookup_nodes_match_raw_input_provenance',provenance_errors,[])
checks_graph=[];costs=[]
for state in load(R/'domains/domains_summary.json'):
 if not state.get('domain_id'):continue
 name=state['domain_id'];obj=load(R/'domains'/f'{name}.json');meta=obj['domain'];ns=nodes[state['image']];dd=dist[state['image'],state['metric']];t=state['threshold'];u=meta['union']
 forbidden={tuple(p['nodes']) for p in meta['forbidden_pairs']};raw={(i,j) for i,j in itertools.combinations(u,2) if ns[i]['worker']==ns[j]['worker'] or dd[min(i,j),max(i,j)]>t}
 checks_graph.append(dict(domain_id=name,edge_count=len(raw),passed=raw==forbidden))
 if name in {f'rPc6DW4iMge-06_{m}_5_d0' for m in ('pair','top','bottom')}:
  maxdiff=0.;n=0
  with gzip.open(R/'domains'/obj['all_candidate_ledger'],'rt') as f:
   for line in f:
    c=json.loads(line);w=math.fsum(math.fsum((dd[min(i,j),max(i,j)]/t)**2 for i,j in itertools.combinations(g,2))/len(g) for g in c['blocks']);maxdiff=max(maxdiff,abs(w-c['cost']));n+=1
  costs.append(dict(domain_id=name,candidates=n,max_absolute_cost_error=maxdiff,within_1e_10=maxdiff<=1e-10))
check('all_41_forbidden_graphs_equal_independent_unit_vector_geometry',all(x['passed'] for x in checks_graph),True)
check('all_6272_primary_5deg_costs_equal_independent_pair_sum_to_1e_10',all(x['within_1e_10'] for x in costs),True)
result=dict(all_pass=all(x['passed'] for x in checks),checks=checks,graphs=checks_graph,main_cost_checks=costs,method='Pure Python spherical unit-vector atan2 distances, raw record ID/pair lookup, independent pairwise math.fsum cost; no delivery module import')
(BASE/'independent_raw_checks.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
