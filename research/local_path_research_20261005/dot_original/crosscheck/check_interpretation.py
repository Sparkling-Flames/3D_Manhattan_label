#!/usr/bin/env python3
"""Independent third-pass combinatorial checker. Stdlib only, no research code imports.
Derives the frozen seven-bit model from explicit segment choices, then verifies
it against direct rational point-in-polygon / top interpolation from input paths.
Does not claim to be a general geometry validator or an independent full replay.
"""
import itertools as it,json,collections as co
from pathlib import Path
from fractions import Fraction as F
R=Path(__file__).resolve().parent
S=R.parent/'source/local_path_research_20261005'
D=json.loads((S/'inputs/domain.json').read_text()); P=json.loads((S/'inputs/probes.json').read_text())
def point_in_polygon(point,ring):
 x,y=map(lambda z:F(str(z)),point); count=0
 for p,q in zip(ring,ring[1:]+ring[:1]):
  ax,ay=map(lambda z:F(str(z)),p[:2]);bx,by=map(lambda z:F(str(z)),q[:2])
  cross=(x-ax)*(by-ay)-(y-ay)*(bx-ax)
  if cross==0 and min(ax,bx)<=x<=max(ax,bx) and min(ay,by)<=y<=max(ay,by):return True
  if (ay>y)!=(by>y): count+= (ax+(y-ay)*(bx-ax)/(by-ay)>x)
 return bool(count%2)
def direct_code(q):
 paths=[s['paths'][v]['nodes_xz_top'] for s,v in zip(D['segments'],q)]
 ring=[p for path in paths for p in path[:-1]]; out=[]
 for probe in P:
  if probe['kind']=='occupancy':out.append(point_in_polygon(probe['xz'],ring));continue
  vals=[]; x=F(str(probe['x']))
  for a,b in zip(paths[probe['segment']],paths[probe['segment']][1:]):
   ax,az,ah=map(lambda z:F(str(z)),a);bx,bz,bh=map(lambda z:F(str(z)),b)
   if bx==ax:continue
   t=(x-ax)/(bx-ax)
   if 0<=t<=1: vals.append(ah+t*(bh-ah))
  out.append(max(vals)>F(str(probe['height_threshold_h'])))
 return tuple(out)
# In this fixture: q0=2 is the same straight path as q0=0;
# q2=2 is self-crossing; q4=2 violates the terminal anchor. The remaining
# canonical path combinations are six direct choices, minus two given exclusions.
C=[]
for q in it.product((0,1),(0,1),(0,1),(0,1,2),(0,1),(0,1)):
 if q[3]==1 and q[4]==1:continue
 if q[0]==q[1]==q[2]==1:continue
 code=(bool(q[0]),bool(q[1]),bool(q[2]),q[3]==1,q[3]==2,bool(q[4]),not q[5])
 assert code==direct_code(q),(q,code,direct_code(q))
 C.append({'id':'C'+''.join(map(str,q)),'q':q,'code':code,'events':code[:6]+(not code[6],),'unresolved':q[2]==q[5]==1})
assert len(C)==70
# Check that the explicit canonical choices are exactly the delivered H after
# removing only its redundant q0=2 representation.
A=json.loads((S/'results/final/finite/all_candidates.json').read_text())
assert {c['id'] for c in C}=={a['id'] for a in A if a['admissible'] and a['choices'][0]!=2}
rows=[];examples={};metric=[]
for errors in (0,1,2):
 ctr=co.Counter(); bystatus=co.defaultdict(co.Counter)
 for t in C:
  for flips in it.combinations(range(7),errors):
   y=tuple((not v) if k in flips else v for k,v in enumerate(t['code']))
   chosen=[c for c in C if sum(a!=b for a,b in zip(c['code'],y))<=1]
   status=('no_feasible_candidate' if not chosen else 'multiple_candidates' if len(chosen)>1 else 'compatibility_unresolved' if chosen[0]['unresolved'] else 'single_geometry_conditional')
   fix=[]
   for k in range(7):
    values={c['events'][k] for c in chosen}
    fix.append(next(iter(values)) if len(values)==1 else None)
   wrong=[k for k,v in enumerate(fix) if v is not None and v!=t['events'][k]]
   row={'truth':t['id'],'truth_code':''.join(str(int(v)) for v in t['code']),'flip_probes':flips,'observed':''.join(str(int(v)) for v in y),'selected':[c['id'] for c in chosen],'status':status,'fixed_events':fix,'wrong_event_indices':wrong}
   ctr.update(cases=1,truth_covered=any(c['id']==t['id'] for c in chosen),unique_geometries=len(chosen)==1,empty=not chosen,wrong_fixed_events=len(wrong),cases_with_wrong_fixed_event=bool(wrong),fixed_events=sum(v is not None for v in fix))
   ctr[status]+=1;bystatus[status].update(cases=1,wrong_fixed_events=len(wrong),cases_with_wrong_fixed_event=bool(wrong))
   if wrong:examples.setdefault((errors,status),row)
   if row['observed']=='0001111' and t['id'] in ('C000210','C000010'):rows.append(row)
 metric.append({'flipped_distinct_probes':errors,**dict(ctr),'by_status':{k:dict(v) for k,v in bystatus.items()}})
assert metric[0]['cases']==70 and metric[1]['cases']==490 and metric[2]['cases']==1470
assert metric[2]['unique_geometries']==92 and metric[2]['wrong_fixed_events']==554 and metric[2]['empty']==30
assert metric[1]['unique_geometries']==14 and metric[1]['single_geometry_conditional']==11 and metric[1]['compatibility_unresolved']==3
assert metric[2]['single_geometry_conditional']==73 and metric[2]['compatibility_unresolved']==19
# Directly check the source's double-source stream uses the same erroneous probe.
streams=json.loads((S/'inputs/evidence_streams.json').read_text())
stream_controls=[]
for stream in streams:
 if 'two' not in stream['mode']:continue
 world=stream['evaluation_world']; truth=json.loads((S/'evaluation/synthetic_truth.json').read_text())['worlds']
 tq=next(w['choices'] for w in truth if w['id']==world); tc=direct_code(tq); bad=[e for e in stream['claims'] if e['status']=='observed' and e['value']!=tc[int(e['probe_id'][1:])]]
 stream_controls.append({'world':world,'mode':stream['mode'],'bad_probe_ids':sorted({e['probe_id'] for e in bad}),'bad_source_groups':sorted({e['source_group'] for e in bad}),'bad_claims':len(bad)})
out={'scope':'Independent direct-choice Boolean crosscheck; exact rational input-path probe verification; delivered canonical admissibility set compared, not independently general-geometry validated','canonical_geometries':len(C),'direct_probe_checks':70*7,'metrics':metric,'same_observation_counterexample':rows,'additional_wrong_witnesses':list(examples.values()),'source_double_group_controls':stream_controls}
(R/'crosscheck_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False,indent=2))
# Narrow independent rechecks of the two implementation-report qualifications.
base=S/'results/final'; reproduced=R/'reproduced'
comparison=[]
for src in sorted(base.rglob('*')):
 if not src.is_file():continue
 dst=reproduced/src.relative_to(base)
 same=src.read_bytes()==dst.read_bytes()
 comparison.append({'path':str(src.relative_to(base)),'byte_identical':same,'semantic_identical':same or (src.suffix=='.json' and json.loads(src.read_text())==json.loads(dst.read_text()))})
assert len(comparison)==19 and sum(x['byte_identical'] for x in comparison)==18 and all(x['semantic_identical'] for x in comparison)
old=json.loads((base/'finite/construction_summary.json').read_text());new=json.loads((reproduced/'finite/construction_summary.json').read_text())
assert old==new and list(old['inputs_sha256'])!=list(new['inputs_sha256'])
ledger=[]
for policy in json.loads((base/'finite/policy_outputs_before_truth.json').read_text()):
 if policy['policy']['kind']!='budget_compact':continue
 admissible=[c for c in A if c['admissible']]; budget=policy['policy']['budget_h']
 eligible=[c for c in admissible if max(c['carrier_loss_vector_h'])<=budget+1e-10];best=min(c['extra_knots'] for c in eligible)
 chosen={c['id'] for c in eligible if c['extra_knots']==best}
 assert chosen==set(policy['candidate_ids'])
 missing=[c for c in admissible if c['id'] not in chosen and c['id'] not in policy['excluded']]
 assert all(c in eligible and c['extra_knots']>best for c in missing)
 ledger.append({'policy':policy['policy']['id'],'missing_exclusion_reasons':len(missing),'all_candidates_retained_in_full_ledger':True,'selection_correct':True,'witness':{'id':missing[0]['id'],'max_carrier_loss_h':max(missing[0]['carrier_loss_vector_h']),'extra_knots':missing[0]['extra_knots'],'selected_ids':sorted(chosen),'minimum_extra_knots':best}})
assert [x['missing_exclusion_reasons'] for x in ledger]==[9,21]
out['artifact_check']=comparison;out['budget_reason_check']=ledger
(R/'crosscheck_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print('Additional artifact and budget qualifications independently confirmed.')
