import copy,itertools,json,sys
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from core import *
from diagnostics import unb_split
from run_domains import HUMAN,apply_blocks,human_probe

def records(code='rPc6DW4iMge-06'):
    return json.loads((ROOT/'inputs'/f'{code}.json').read_text())['records']

def brute(ns,d,t,b):
    u=sorted(sum(b,[]));n=len(u);w=[ns[i]['worker'] for i in u]
    bad=[(i,j) for i in range(n) for j in range(i+1,n) if w[i]==w[j] or d[u[i],u[j]]>t]
    rr=[]
    for start in range(1,2**(n-1),4096):
        k=np.arange(start,min(2**(n-1),start+4096),dtype=np.uint64)
        lab=np.zeros((len(k),n),dtype=np.int8)
        lab[:,1:]=((k[:,None]>>np.arange(n-2,-1,-1,dtype=np.uint64))&1).astype(np.int8)
        good=np.ones(len(k),bool)
        for i,j in bad:good&=(lab[:,i]!=lab[:,j])
        for row in lab[good]:rr.append(normalize_blocks([[u[i] for i in np.flatnonzero(row==c)] for c in (0,1)]))
    return set(rr)

@pytest.mark.parametrize('code,n,pairs_n',[('2t7WUuJeko7-06',3,12),('7y3sRwLe3Va-04',24,96),('rPc6DW4iMge-06',24,224),('uNb9QFRL6hY-67',15,68)])
def test_full_inputs_and_angular_independent(code,n,pairs_n):
    r=records(code);before=copy.deepcopy(r);ns=nodes_from_records(r)
    assert len(r)==n and len(ns)==pairs_n
    da=distances(ns);db=distances(ns,True)
    assert max(np.max(abs(da[k]-db[k])) for k in da)<1e-10
    assert r==before

def test_rpc_report_reproduction():
    ns=nodes_from_records(records());d=distances(ns)
    for m,expected in [('pair',[10,8,8]),('top',[10,10,5]),('bottom',[11,9,9])]:
        gs,_=partition(ns,d[m],5);pr=human_probe(ns,gs,d,5,HUMAN['rpc'],m)
        assert pr['supports']==expected
    assert pr['local_diameters_deg']['pair']==pytest.approx(4.326333840176633,abs=1e-11)

def test_rpc_exhaustive_complement_coloring_matches_direct_subsets():
    ns=nodes_from_records(records());d=distances(ns)['pair'];gs,_=partition(ns,d,5)
    dom=candidate_domains(ns,gs,d,5,['R02452',2])[0]
    meta,rr=enumerate_two_blocks(ns,d,5,dom['blocks'])
    assert meta['feasible_count']==4096
    assert {normalize_blocks(r['blocks']) for r in rr}==brute(ns,d,5,dom['blocks'])

def test_rpc_minimal_auto_negative_and_assisted_positive():
    ns=nodes_from_records(records());ds=distances(ns);gs,_=partition(ns,ds['pair'],5)
    dom=candidate_domains(ns,gs,ds['pair'],5,['R02452',2])[0];_,rr=enumerate_two_blocks(ns,ds['pair'],5,dom['blocks'])
    must=[next(i for i,n in enumerate(ns) if key(n)==tuple(k)) for k in HUMAN['rpc']['must']]
    assert choose(rr)['status']=='unchanged'
    h=choose(rr,'human_assisted',must=[must]);assert h['edit_count']==1
    alt=rr[h['selected_ids'][0]];assert alt['supports']==[9,9]
    moved=alt['moved_nodes_alternative_alignments'][0];assert [key(ns[i]) for i in moved]==[('R02452',2)]
    full=apply_blocks(gs,dom,alt);assert sorted(sum(full,[]))==list(range(224))

def test_disabling_same_worker_alone_does_not_repair_this_real_case():
    ns=nodes_from_records(records());d=distances(ns)['top'];gs,_=partition(ns,d,5)
    ix=[next(i for i,n in enumerate(ns) if key(n)==('R01557',j)) for j in (2,4)]
    assert not any(set(ix)<=set(g) for g in gs)
    relaxed,_=partition(ns,d,5,False);assert normalize_blocks(relaxed)==normalize_blocks(gs)
    assert not any(set(ix)<=set(g) for g in relaxed)

def test_unb_labels_do_not_propagate():
    ns=nodes_from_records(records('uNb9QFRL6hY-67'));ds=distances(ns);gs,_=partition(ns,ds['bottom'],5)
    r=unb_split(ns,ds,gs,5)
    assert r['bottom_support']==9
    assert sorted(g['geometric_support'] for g in r['geometric_top_subgroups'])==[2,3,4]
    x={t['target']:t for t in r['targets']}
    assert x['low_glass_top']['top_support']==1 and x['glass_to_ceiling']['top_support']==2
    assert x['unknown']['top_support']==6 and x['unknown']['center_of_own_sources'] is None
    assert not r['single_upper_target_selected'] and not r['complete_layout_created']

def test_same_person_points_preserved_not_double_vote():
    ns=[dict(id=str(i),pair_index=0,worker='A' if i in [0,2] else str(i),points=[[512.,128.],[512.,384.]]) for i in range(4)]
    m,r=enumerate_two_blocks(ns,np.zeros((4,4)),5,[[0,1],[2,3]])
    assert len(r)==4
    for x in r:
        assert sorted(sum(x['blocks'],[]))==[0,1,2,3]
        assert all(len(set(ns[i]['worker'] for i in g))==len(g) for g in x['blocks'])

def test_two_label_alignment_ties_both_retained():
    ns=[dict(id=str(i),pair_index=0,worker=str(i),points=[[512.,128.],[512.,384.]]) for i in range(4)]
    d=np.array([[0,1,1,2],[1,0,2,1],[1,2,0,1],[2,1,1,0.]])
    _,r=enumerate_two_blocks(ns,d,1.1,[[0,1],[2,3]])
    assert len(r)==2;assert r[1]['block_label_alignments']==[0,1]
    assert r[0]['cost']==r[1]['cost']

def test_scope_counterexample_not_global_impossibility():
    def nd(i,x):return dict(id=str(i),worker=str(i),pair_index=0,points=[[512+x*1024/360,128.],[512+x*1024/360,384.]])
    ns=[nd(i,x) for i,x in enumerate([0,.9,-.3,-1.01,.3,-.6])];ds=distances(ns)['pair']
    _,r=enumerate_two_blocks(ns,ds,.7,[[0,1],[2,3]])
    assert choose(r,'human_assisted',must=[[0,2]])['status']=='infeasible_constraints'
    assert all(ds[np.ix_(g,g)].max()<.7 for g in [[0,2],[1,4],[3,5]])

def test_budget_is_recorded_no_truncation():
    ns=[dict(id=str(i),worker=str(i),pair_index=0,points=[[512.,128.],[512.,384.]]) for i in range(6)]
    m,r=enumerate_two_blocks(ns,np.zeros((6,6)),5,[[0,1,2],[3,4,5]],max_states=2)
    assert m['status']=='budget_exceeded' and not m['exhaustive_within_declared_domain'] and r==[]

def test_human_constraint_outside_domain_is_not_discarded():
    ns=[dict(id=str(i),worker=str(i),pair_index=0,points=[[512.,128.],[512.,384.]]) for i in range(4)]
    _,r=enumerate_two_blocks(ns,np.zeros((4,4)),5,[[0,1],[2,3]])
    assert choose(r,'human_assisted',must=[[0,7]])['status']=='constraints_outside_local_domain'

def test_contradictory_human_links_return_empty():
    ns=[dict(id=str(i),worker=str(i),pair_index=0,points=[[512.,128.],[512.,384.]]) for i in range(4)]
    _,r=enumerate_two_blocks(ns,np.zeros((4,4)),5,[[0,1],[2,3]])
    assert choose(r,'human_assisted',must=[[0,1]],cannot=[(0,1)])['status']=='infeasible_constraints'

@pytest.mark.parametrize('change', ['duplicate_worker','ineligible','missing_points','nonshared_x','out_of_bounds','mixed_population'])
def test_no_silent_input_repair(change):
    r=copy.deepcopy(records('2t7WUuJeko7-06'))
    if change=='duplicate_worker':r[1]['worker']=r[0]['worker']
    elif change=='ineligible':r[1]['independent']=False
    elif change=='missing_points':r[1]['points']=None
    elif change=='nonshared_x':r[1]['points'][0][0]+=3
    elif change=='out_of_bounds':r[1]['points'][0][1]=513
    else:r[1]['evidence_kind']='synthetic'
    with pytest.raises(ValueError):nodes_from_records(r)

def test_seam_angle_and_center():
    r=records('2t7WUuJeko7-06');ns=nodes_from_records(r);ds=distances(ns)
    r2=copy.deepcopy(r)
    for x in r2:x['points']=[[(u+723.5)%1024,v] for u,v in x['points']]
    nn=nodes_from_records(r2);dd=distances(nn);lookup={key(n):i for i,n in enumerate(nn)};ix=[lookup[key(n)] for n in ns]
    assert np.max(abs(ds['pair']-dd['pair'][np.ix_(ix,ix)]))<1e-10

def test_no_references_needed_to_compute_automatic():
    ns=nodes_from_records(records());d=distances(ns)['pair'];g,_=partition(ns,d,5)
    dom=candidate_domains(ns,g,d,5,['R02452',2])[0];_,a=enumerate_two_blocks(ns,d,5,dom['blocks'])
    before=choose(a)
    # Arbitrary semantic labels are external to the constructor and objective.
    labels={'R02452': 'anything','R01557':'opposite'};labels.clear()
    assert choose(a)==before


def test_merge_trace_current_cluster_union_not_only_three_targets():
    from diagnostics import merge_history
    ns=nodes_from_records(records());ds=distances(ns)
    target=[next(i for i,n in enumerate(ns) if key(n)==tuple(k)) for k in HUMAN['rpc']['must']]
    constrained=merge_history(ns,ds['top'],5,target,True)['first_irreversible_obstruction']
    relaxed=merge_history(ns,ds['top'],5,target,False)['first_irreversible_obstruction']
    assert constrained['step']==149 and any(x['same_worker'] for x in constrained['obstructions'])
    assert relaxed['step']==168 and any(x['distance_exceeds'] for x in relaxed['obstructions'])
    requested={tuple(x) for x in HUMAN['rpc']['must']}
    assert any(not (set(map(tuple,b['nodes'])) & requested) for b in relaxed['obstructions'])

def test_human_source_bindings_agree_with_explicit_assisted_configuration():
    source=json.loads((ROOT/'inputs/human_review.json').read_text())
    by={r['case_id']:r for r in source['reviews']}
    for case,name in [('rpc_lower','rpc'),('2t7_corner','2t7')]:
        r=by[case]
        assert [list(k) for k in zip(r['record_ids'],r['processed_pair_indices'])]==HUMAN[name]['must']
    assert by['rpc_lower']['rejected_previous_purple_processed_pair_index']==HUMAN['rpc']['rejected'][1]
    assert by['unb_upper']['bottom_relation']==HUMAN['unb']['bottom_relation']
