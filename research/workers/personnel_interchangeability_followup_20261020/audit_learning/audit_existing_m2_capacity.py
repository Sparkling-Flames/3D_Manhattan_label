"""Metadata-only inventory of exact m2 comparisons already cached in H20."""
import json,gzip,itertools,collections,time
from pathlib import Path
import pandas as pd
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;S=ROOT/'unpacked/interchangeability_20261020'
t=time.perf_counter();q=json.load(gzip.open(S/'history_panel/history_requests.json.gz','rt'));feat=pd.read_csv(S/'forward/features_train.csv.gz');orig=feat.set_index('worker_id').person_origin.to_dict();by=collections.defaultdict(dict)
for r in q['requests']:by[(r['pool_id'],r['k'])][tuple(sorted(r['worker_ids']))]=r['request_id']
rows=[];eligible=[]
for (pid,n),teams in sorted(by.items()):
 cores=collections.defaultdict(list)
 for ws,tk in teams.items():
  for block in itertools.combinations([w for w in ws if orig[w]=='new'],2):
   core=tuple(w for w in ws if w not in block);cores[core].append((block,tk))
 count=0;maxblocks=0;events=0;people=set();validcores=0
 for core,blocks in cores.items():
  if len(blocks)<2:continue
  pairs=[(i,j) for i,j in itertools.combinations(range(len(blocks)),2) if not set(blocks[i][0])&set(blocks[j][0])]
  if not pairs:continue
  count+=1;events+=len(pairs);maxblocks=max(maxblocks,len(blocks))
  for i,j in pairs:people.update(blocks[i][0]);people.update(blocks[j][0])
  if len(blocks)>=4 and len(pairs)>=2:
   validcores+=1;eligible.append({'pool_id':pid,'building':pid.split('-',1)[0],'n':n,'core_workers':list(core),'blocks':[{'workers':list(b),'team_key':tk} for b,tk in blocks],'disjoint_block_pairs':pairs})
 rows.append({'pool_id':pid,'building':pid.split('-',1)[0],'n':n,'existing_unique_teams':len(teams),'exact_m2_cores':count,'cores_ge4blocks_ge2pairs':validcores,'exact_m2_pairs':events,'max_blocks':maxblocks,'entrant_people':len(people)})
r=pd.DataFrame(rows);r.to_csv(BASE/'EXISTING_H20_M2_CAPACITY.csv',index=False);data={'metadata_only_no_geometry_read':True,'no_new_fusion':True,'eligible_core_definition':'>=4 distinct endpoint blocks and >=2 exact disjoint m2 pairs; this is opportunity, not classification/metric efficacy','rows':len(r),'m2_pairs':int(r.exact_m2_pairs.sum()),'m2_cores':int(r.exact_m2_cores.sum()),'eligible_cores':len(eligible),'eligible_pools':len(set(e['pool_id'] for e in eligible)),'eligible_buildings':len(set(e['building'] for e in eligible)),'n_support':r.groupby('n')[['exact_m2_pairs','cores_ge4blocks_ge2pairs']].sum().to_dict('index'),'elapsed_seconds':time.perf_counter()-t};(BASE/'EXISTING_H20_M2_CAPACITY_RECEIPT.json').write_text(json.dumps(data,indent=2));(BASE/'existing_h20_m2_metadata.json.gz').write_bytes(gzip.compress(json.dumps({'anchors':eligible}).encode(),mtime=0));print(json.dumps(data,indent=2))
