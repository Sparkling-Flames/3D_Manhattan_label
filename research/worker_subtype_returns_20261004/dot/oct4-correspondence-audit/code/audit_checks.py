"""Focused independent audit. Known failing original checks are retained, not hidden.

Run from any directory with NumPy/SciPy/Shapely available. No remote writes.
The cost-table probes verify combinatorics only, not physical realizability.
"""
from pathlib import Path
import sys, json, copy, hashlib, itertools, contextlib, unittest, importlib.util
from unittest.mock import patch
import numpy as np
from shapely.geometry import Point
BASE=Path(__file__).resolve().parents[1]
SOURCE=BASE/'fixtures/reference_tests'
sys.path.insert(0,str(BASE/'fixtures'));sys.path.insert(0,str(BASE/'patched'))
import consensus_lab_original as lab
import consensus_lab_guarded as fixed
out={'scope':'frozen Pro source; isolated fail-closed guard; not latest repository baseline',
     'source_sha256':hashlib.sha256((BASE/'fixtures/consensus_lab_original.py').read_bytes()).hexdigest(),
     'checks':[]}
def save(name,value):
    (BASE/'results'/name).write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False))
def check(name,passed,detail):
    out['checks'].append({'name':name,'passed':bool(passed),'detail':detail})

def oracle(c,tolerance):
    m,n=c.shape;found={}
    for js_order in (tuple(range(n)),tuple(range(n-1,-1,-1))):
        for sh in range(n):
            seq=js_order[sh:]+js_order[:sh]
            for k in range(min(m,n)+1):
                for ia in itertools.combinations(range(m),k):
                    for positions in itertools.combinations(range(n),k):
                        p=tuple(zip(ia,[seq[j] for j in positions]))
                        if all(c[i,j]<=tolerance+1e-10 for i,j in p):
                            found[p]=(k,float(sum(c[i,j] for i,j in p)),p)
    return sorted(found.values(),key=lambda v:(-v[0],v[1],v[2]))

def partial_for_table(c,tau=5):
    with patch.object(lab,'costs',lambda *args,**kw:c):
        return lab.partial_alignment(np.zeros((len(c),2,2)),np.zeros((c.shape[1],2,2)),tau)

rng=np.random.default_rng(103704)
probe=[]
for m,n in [(3,3),(3,4),(4,3),(3,5),(4,4)]:
    for _ in range(3):
        c=rng.choice([0.,1.,3.,5.,5.01,11.],(m,n));z=oracle(c,5);g=partial_for_table(c)
        runner=z[1] if len(z)>1 and z[1][0]==z[0][0] else None
        good=(g['matched']==z[0][0] and abs(g['sum_angle']-z[0][1])<1e-10 and g['mapping']==[list(v) for v in z[0][2]] and g['runner_up_mapping']==([list(v) for v in runner[2]] if runner else None))
        probe.append({'shape':[m,n],'cost_table':c.tolist(),'passed':good,'returned':g})
check('independent_partial_oracle_15_cost_tables',all(v['passed'] for v in probe),{'cases':len(probe)})
save('partial_oracle_cases.json',probe)

c=np.zeros((3,4));z=oracle(c,5);g=partial_for_table(c)
ties=sum(v[:2]==z[0][:2] for v in z)
check('partial_ties_are_flagged_but_not_all_enumerated',g['ambiguous'] and ties==24,{'exact_tie_count':ties,'returned_mapping_count':2,'returned':g,'classification':'disclosed two-best interface limitation, not a DP optimality bug'})
c=np.array([[0,4.9,99],[99,0,4.9],[4.9,99,99.]])
z=oracle(c,5);g=partial_for_table(c)
check('maximum_cardinality_precedes_error',g['matched']==3 and abs(g['sum_angle']-14.7)<1e-9,{'returned':g,'best_lower_cardinality':{'matched':next(v[0] for v in z if v[0]<3),'sum_angle':next(v[1] for v in z if v[0]<3)},'classification':'declared objective; no lower-cardinality alternative exported; not physical layout example'})

def actual_maps_and_errors(dec,records):
    cand=dec['single_candidate'];m=len(lab.pairs(cand))
    maps={r['id']:[dict(a['mapping'])[i] for i in range(m)] for r in records for a in cand['alignments'] if a['id']==r['id']}
    errors=[{'a':ra['id'],'b':rb['id'],'max_bound_angle_deg':float(lab.costs(lab.pairs(ra),lab.pairs(rb))[maps[ra['id']],maps[rb['id']]].max())} for ra,rb in itertools.combinations(records,2)]
    fixed_residual=[{'id':r['id'],'max_bound_angle_deg':float(lab.costs(lab.pairs(cand),lab.pairs(r))[np.arange(m),maps[r['id']]].max())} for r in records]
    return {'maps':maps,'induced_pair_errors':errors,'fixed_mapping_residuals':fixed_residual}

for name,file in [('known_two_record','known_certification_objective_mismatch.json'),('new_three_record','three_record_actual_mapping_diameter_counterexample.json')]:
    fixture=json.loads((BASE/'fixtures'/file).read_text());records=fixture['records']
    before=lab.conditional_decision(records,tolerance=5);after=fixed.conditional_decision(records,tolerance=5)
    details=actual_maps_and_errors(before,records)
    payload={'attribution':'Two-record fixture and original defect already documented in repository ad12d64 REVIEW section 5. New three-record extension is independent audit evidence of induced >5-degree diameter, not a prevalence estimate.',
        'source_records':records,'input_polygon_valid':[lab.polygon(r).is_valid for r in records],
        'input_contains_camera':[lab.polygon(r).contains(Point(0,0)) for r in records],
        'selected_candidate_contains_camera':lab.polygon(before['single_candidate']).contains(Point(0,0)),
        'before':before,'actual_candidate_identity':details,'after':after}
    save(name+'_before_after.json',payload)
    check(name+'_original_rejects_mismatched_certificate',before['status']!='single_candidate_conditional_on_method_tolerance',{'status':before['status'],'actual_pair_errors':details['induced_pair_errors'],'expected':'unresolved mapping; KNOWN ORIGINAL FAILURE retained'})
    check(name+'_guard_rejects_mismatched_certificate',after['status']=='unresolved_actual_mapping_certificate_mismatch',{'status':after['status'],'scope':'conservative abstention only; no joint solver integration'})

# New (not author) three-record fixture: the separate solver can diagnose it,
# but the guard deliberately does not select or publish this numerical winner.
records=json.loads((BASE/'fixtures/three_record_actual_mapping_diameter_counterexample.json').read_text())['records']
joint=lab.joint_ring_alignment(records,5)
for c in joint['candidates']:
    c['fixed_mapping_candidate_residual_deg']=[float(lab.costs(lab.pairs(c),lab.pairs(obs))[np.arange(3),pm['indices']].max()) for obs,pm in zip(records,c['source_pair_maps'])]
save('new_three_record_joint_diagnostic.json',joint)
check('new_three_record_joint_diagnostic_remains_separate',joint['states_enumerated']==36 and joint['feasible_count']==2 and joint['optimal_count']==1,
      {'states':joint['states_enumerated'],'feasible':joint['feasible_count'],'optima':joint['optimal_count'],'induced_pair_errors':joint['candidates'][0]['induced_pair_errors_deg'],'interpretation':'a computational alternative exists; no semantic winner declared'})

# Independent neutral square verifies one contribution per independent record,
# even with exactly duplicate coordinate arrays. Coordinate deduplication is prohibited.
square=lab.from_floor([[-2,-2],[2,-2],[2,2],[-2,2]],worker='P0')
rs=[dict(copy.deepcopy(square),id=f'P{i}',worker=f'P{i}',synthetic=False,independent=True,consensus_eligible=True) for i in range(3)]
en=lab.derive_candidates(rs,5);cand=en['candidates'][0]
check('identical_coordinates_distinct_workers_are_three_votes',cand['point_support_counts']==[3]*4 and all(len(v)==3 for v in cand['direct_edge_witnesses']) and len(cand['complete_ring_mapping_witnesses'])==3,{'point_counts':cand['point_support_counts'],'direct_counts':[len(v) for v in cand['direct_edge_witnesses']],'whole_count':len(cand['complete_ring_mapping_witnesses'])})
sub=lab.insert_subdivision(square,worker='P1');en=lab.derive_candidates([square,sub]);cand=next(v for v in en['candidates'] if v['anchor']=='P0')
check('subdivision_path_is_not_direct_or_whole_ring_vote',len(cand['direct_edge_witnesses'][0])==1 and len(cand['endpoint_connection_with_intermediate_pairs'][0])==1 and len(cand['complete_ring_mapping_witnesses'])==1,{'direct_counts':[len(v) for v in cand['direct_edge_witnesses']],'paths':cand['endpoint_connection_with_intermediate_pairs'],'whole_count':len(cand['complete_ring_mapping_witnesses']),'limitation':'path payload has endpoints only; intermediate indices/direction/geometry must be recovered from source'})

# Explicit null provenance: already reported by ad12d64, independently reproduced.
nullable=copy.deepcopy(rs[:2]);nullable[0]['source_point_indices']=None;nullable[0]['source_point_labels']=None
for mod,label in [(lab,'original'),(fixed,'guarded')]:
    try: mod.derive_candidates(nullable);ok=True;message='returned normally; no invented provenance'
    except Exception as exc:ok=False;message=f'{type(exc).__name__}: {exc}'
    check(label+'_null_provenance_does_not_crash',ok,{'result':message,'attribution':'known ad12d64 interface defect'})

mixed=[rs[0],dict(copy.deepcopy(square),id='SYN',worker='SYN')]
en=lab.derive_candidates(mixed);d=lab.conditional_decision(mixed,en)
check('mixed_populations_are_detectably_counted_together',en['candidates'][0]['point_support_counts']==[2]*4,{'populations':en['evidence_populations'],'point_counts':en['candidates'][0]['point_support_counts'],'status':d['status'],'classification':'missing separation guard; controlled API probe, not evidence current real run contaminated'})

# Budget boundary with a new two-record rectangle control: 8 states required.
z=lab.joint_ring_alignment(rs[:2],5,max_states=7);y=lab.joint_ring_alignment(rs[:2],5,max_states=8)
check('joint_budget_boundary_is_exact_and_nontruncating',z['status']=='budget_exceeded_no_exact_result' and z['states_required']==8 and y['states_enumerated']==8,{'below_boundary':z,'at_boundary':{k:y[k] for k in ['status','states_enumerated','feasible_count','optimal_count']}})
# We do not replay the author's 6x64-state joint experiment; another worker owns it.
check('conditional_does_not_call_joint_solver','joint_ring_alignment(' not in __import__('inspect').getsource(lab.conditional_decision),{'classification':'integration gap; exact solver remains separate, not proof of a wrong numerical solver'})

# The parent explicitly requested the original 25 tests on the isolated guard.
sys.modules['consensus_lab']=fixed
spec=importlib.util.spec_from_file_location('original_tests_on_guard',SOURCE/'tests/test_lab.py');tm=importlib.util.module_from_spec(spec);spec.loader.exec_module(tm)
with (BASE/'results/patched_original_25_tests.log').open('w') as stream:
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tm))
check('guarded_copy_original_25_tests',result.wasSuccessful() and result.testsRun==25,{'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)})
out['total_checks']=len(out['checks']);out['passed_checks']=sum(v['passed'] for v in out['checks']);out['original_failures_retained']=[v['name'] for v in out['checks'] if not v['passed']]
save('audit_summary.json',out)
print(json.dumps(out,indent=2,ensure_ascii=False))
