"""Authored synthetic mechanisms. Writes generation inputs and separate truth.
This script is fixture preparation, NOT an automatic geometry/evidence detector.
"""
from pathlib import Path
import sys,itertools,copy
sys.path.insert(0,str(Path(__file__).parent/'src'))
from finite_paths import dump,assemble,evidence_prediction
ROOT=Path(__file__).parent
A=[[-2.,-2.,1.],[0.,-2.,1.],[2.,-2.,1.],[2.,2.,1.],[0.,2.,1.],[-2.,2.,1.]]
def path(j,k,inside,workers,construction='observed_local_path'):
    nodes=[A[j]]+[[float(x),float(z),float(h)] for x,z,h in inside]+[A[(j+1)%6]]
    return {'id':f'P{j}{k}','nodes_xz_top':nodes,'donors':[{'worker':w,'record':'S_'+w,'source_segment':j,'source_path':f'P{j}{k}'} for w in workers],
            'construction':construction,'semantic_correctness':'not_in_generation_input'}
S=[]
# Two symmetric 0.04h local structures with exactly the same minority count.
S.append({'carrier_index':1,'paths':[path(0,0,[],['W1','W2','W3','W4','W5']),path(0,1,[(-1.1,-2,1),(-1.1,-2.04,1),(-.9,-2.04,1),(-.9,-2,1)],['W6']),path(0,2,[(-1,-2,1)],['W7'])]})
S.append({'carrier_index':1,'paths':[path(1,0,[],['W1','W2','W3','W4','W5','W7']),path(1,1,[(.9,-2,1),(.9,-2.04,1),(1.1,-2.04,1),(1.1,-2,1)],['W6'])]})
S.append({'carrier_index':1,'paths':[path(2,0,[],['W1','W2','W3','W4','W5','W6']),path(2,1,[(2,-.005,1),(2.08,0,1),(2,.005,1)],['W7']),path(2,2,[(3,-1,1),(1,1,1),(3,1,1),(1,-1,1)],[],'proposed_anchor_path_no_donor')]})
S.append({'carrier_index':0,'paths':[path(3,0,[],['W1','W2','W3','W4']),path(3,1,[(1.6,2,1),(1.6,3,1),(.4,3,1),(.4,2,1)],['W5','W6']),path(3,2,[(1.,2.,1.3)],['W7'])]})
S.append({'carrier_index':0,'paths':[path(4,0,[],['W3','W4','W5','W6','W7']),path(4,1,[(-.4,2,1),(-.4,3,1),(-1.6,3,1),(-1.6,2,1)],['W1','W2']),path(4,2,[],[],'proposed_anchor_path_no_donor')]})
S[4]['paths'][2]['nodes_xz_top'][-1]=[-2.2,2,1.] # finite but mismatched given anchor
S.append({'carrier_index':1,'paths':[path(5,0,[],[],'new_anchor_chord_no_exact_path_donor'),path(5,1,[(-2,.3,1),(-1.97,.3,1),(-1.97,-.3,1),(-2,-.3,1)],['W1','W2','W3','W4','W5','W6','W7'])]})
D={'schema':'paired_local_path_domain_v1','anchors_xz_top':A,'segments':S,
   'independent_workers':['W'+str(i) for i in range(1,8)],
   'note':'given synthetic source rings and local paths; unknown relation retained; a per-sector carrier combination is not assumed a valid maximum room',
   'incompatibilities':[
       {'id':'scope_exclusive','assignments':{'3':1,'4':1},'basis':'given experimental relation: the two extended ranges are alternative scope interpretations, not jointly admissible'},
       {'id':'higher_order','assignments':{'0':1,'1':1,'2':1},'basis':'given 3-way structural correspondence conflict; every constituent pair is compatible'}],
   'unknown_compatibilities':[{'id':'unverified_pair','assignments':{'2':1,'5':1},'basis':'given unresolved local-to-local anchor relation'}]}
D['observed_person_assignments']=[]
for worker in D['independent_workers']:
    choices=[]
    for seg in S:
        found=[i for i,p in enumerate(seg['paths']) if worker in [d['worker'] for d in p['donors']]]
        assert len(found)==1,(worker,found)
        choices.append(found[0])
    D['observed_person_assignments'].append({'worker':worker,'record':'S_'+worker,'choices':choices})
probes=[{'id':'e0','kind':'occupancy','xz':[-1,-2.02]},
        {'id':'e1','kind':'occupancy','xz':[1,-2.02]},
        {'id':'e2','kind':'occupancy','xz':[2.04,0]},
        {'id':'e3','kind':'occupancy','xz':[1,2.5]},
        {'id':'e4','kind':'wall_top_at_x','segment':3,'x':1.,'height_threshold_h':1.15},
        {'id':'e5','kind':'occupancy','xz':[-1,2.5]},
        {'id':'e6','kind':'occupancy','xz':[-1.985,0]}]
# Truth is separate. No method reads the names or truth choices below.
worlds=[{'id':'W_A','choices':[1,0,1,1,0,0],'description':'minority first detail true; symmetric second detail false; narrow true; right range true'},
        {'id':'W_B','choices':[0,1,1,1,0,0],'description':'same observations and compatibility as A; symmetric first detail false and second true'},
        {'id':'W_C','choices':[0,0,0,0,0,0],'description':'plain true layout; all observed deviations spurious'},
        {'id':'W_D','choices':[1,1,0,2,1,1],'description':'both small details, top-only structure, left range and inset are true'}]
streams=[]
for w in worlds:
    truth=assemble(D,w['choices'])
    clean=[{'id':f'm{i}','probe_id':p['id'],'source_group':f'check_{i}','status':'observed','value':evidence_prediction(truth,p)} for i,p in enumerate(probes)]
    none=copy.deepcopy(clean)
    for e in none:e['status']='missing';e['value']=None
    partial=copy.deepcopy(clean)
    for i,e in enumerate(partial):
        if i not in (0,2):e['status']='missing';e['value']=None
    wrong0=copy.deepcopy(clean);wrong0[0]['value']=not wrong0[0]['value']
    wrong1=copy.deepcopy(clean);wrong1[1]['value']=not wrong1[1]['value']
    conflict=copy.deepcopy(clean);extra=copy.deepcopy(clean[0]);extra.update(id='m0_contradiction',source_group='other_check',value=not extra['value']);conflict.append(extra)
    shared=copy.deepcopy(wrong0);shared.append(dict(wrong0[0],id='same_raw_evidence_repeated'))
    separate=copy.deepcopy(wrong0);separate.append(dict(wrong0[0],id='independent_but_also_wrong',source_group='second_wrong_source'))
    for mode,claims in [('observations_only',none),('sparse_local',partial),('clean_geometric_probes_upper',clean),('misclassified_probe0',wrong0),('misclassified_probe1',wrong1),('conflicting_checks',conflict),('shared_wrong_evidence_twice',shared),('two_wrong_source_groups',separate)]:
        streams.append({'id':w['id']+'__'+mode,'evaluation_world':w['id'],'mode':mode,'claims':claims,
         'interpretation':'authored sensor/verification outcome, not measured automatic visual accuracy; clean stream is a conditional error-free geometric-evidence upper condition'})
policies=[{'id':'budget_005','kind':'budget_compact','budget_h':.05},{'id':'budget_020','kind':'budget_compact','budget_h':.20},{'id':'carrier_pareto','kind':'carrier_pareto'},
          {'id':'evidence_b0','kind':'evidence','max_wrong_source_groups':0},{'id':'evidence_b1','kind':'evidence','max_wrong_source_groups':1}]
dump(ROOT/'inputs/domain.json',D);dump(ROOT/'inputs/probes.json',probes);dump(ROOT/'inputs/evidence_streams.json',streams);dump(ROOT/'inputs/policies.json',policies)
dump(ROOT/'evaluation/synthetic_truth.json',{'worlds':worlds,'feature_events':{'small_left':[0,1],'small_right':[1,1],'narrow':[2,1],'range_right':[3,1],'top_only':[3,2],'range_left':[4,1],'inset':[5,1]},'do_not_use_for_construction':True})
print('Frozen:',len(A),'anchors;',len(list(itertools.product(*[range(len(s['paths'])) for s in S]))),'candidates;',len(streams),'evidence streams')
