"""Post-selection diagnostics. Conflict cores use no truth. Off-domain control
is separately labelled evaluation and never used to change candidates/policies.
"""
from pathlib import Path
import itertools,json,copy
import numpy as np
from shapely.geometry import Polygon
from finite_paths import dump,assemble,evidence_prediction,policy_select
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(Path(p).read_text())

def run(out):
    out=Path(out);C=load(out/'all_candidates.json');valid=[c for c in C if c['admissible']]
    streams=load(ROOT/'inputs/evidence_streams.json');D=load(ROOT/'inputs/domain.json');probes={p['id']:p for p in load(ROOT/'inputs/probes.json')}
    cores=[]
    for s in streams:
        observed=[e for e in s['claims'] if e['status']=='observed']; groups=sorted({e['source_group'] for e in observed})
        bad=[{e['source_group'] for e in observed if c['probe_predictions'][e['probe_id']]!=e['value']} for c in valid]
        if any(not b for b in bad):continue
        local=[]
        for k in range(1,len(groups)+1):
            for g in itertools.combinations(groups,k):
                gs=set(g)
                if any(set(core)<=gs for core in local):continue
                if not any(not (b&gs) for b in bad):local.append(list(g))
        cores.append({'stream':s['id'],'minimal_inconsistent_source_group_sets':local,
                      'interpretation':'cannot all be satisfied in the given candidate/compatibility domain; not proof that any named checker alone is wrong'})
    dump(out/'minimal_conflict_cores.json',cores)
    signatures={str(c['geometry_key']):[c['probe_predictions'][p] for p in probes] for c in valid}
    keys=list(signatures);arr=np.array([signatures[k] for k in keys],int)
    d=(arr[:,None,:]!=arr[None,:,:]).sum(2);np.fill_diagonal(d,999)
    checks=0
    for truth_i,code in enumerate(arr):
        for flip in [None]+list(range(arr.shape[1])):
            obs=code.copy()
            if flip is not None:obs[flip]=1-obs[flip]
            feasible=(arr!=obs).sum(1)<=1
            assert feasible[truth_i];checks+=1
    dump(out/'evidence_identifiability.json',{'geometry_classes':len(keys),'probe_count':arr.shape[1],'minimum_hamming_distance':int(d.min()),
             'exhaustive_one_error_coverage_checks':checks,'all_passed':True,
             'unique_decoding_with_b_errors_requires_distance_above_2b':'not met for b=1; applies to all vectors, not necessarily every particular observation',
             'probe_locations_given_not_automatically_selected_from_RGB':True})
    # A geometrically different world with identical available measurements.
    truth=assemble(D,[1,0,1,1,0,0]);outside=copy.deepcopy(truth)
    for p in outside['nodes_xz_top']:
        if p[1]<-2.03 and p[0]<0:p[1]= -2.06
    def predictions(c):return {k:evidence_prediction(c,p) for k,p in probes.items()}
    assert predictions(truth)==predictions(outside)
    claims=[dict(id='off_'+k,probe_id=k,source_group=k,status='observed',value=v) for k,v in predictions(outside).items()]
    dec=policy_select(C,D,{'id':'evidence_b0','kind':'evidence','max_wrong_source_groups':0},claims,probes)
    assert dec['geometry_count']==1
    selected=next(c for c in C if c['id'] in dec['candidate_ids']);F=Polygon(np.array(selected['nodes_xz_top'])[:,:2]);G=Polygon(np.array(outside['nodes_xz_top'])[:,:2])
    dump(out/'outside_candidate_domain_control.json',{'role':'separate evaluation-only domain completeness control','all_probes_correct':True,'same_probe_vector_as_W_A':True,
          'selected_status':dec['status'],'selected_ids':dec['candidate_ids'],'true_nodes_xz_top':outside['nodes_xz_top'],
          'lost_area_h2':G.difference(F).area,'added_area_h2':F.difference(G).area,'iou':F.intersection(G).area/F.union(G).area,
          'interpretation':'uniqueness inside an incomplete finite domain is not proof of true geometry; no candidate or policy adjusted'})
    # Geometric compatibility is independent of source counts.
    triple=assemble(D,[1,1,1,0,0,0]);pairs=[]
    for idx in itertools.combinations(range(3),2):
        v=[0]*6
        for i in idx:v[i]=1
        c=assemble(D,v);pairs.append({'active_slots':idx,'admissible':c['admissible'],'geometry_valid':c['geometry_valid']})
    dump(out/'higher_order_compatibility_control.json',{'pairs':pairs,'all_three':{'id':triple['id'],'geometry_valid':triple['geometry_valid'],'admissible':triple['admissible'],'violations':triple['violated_constraints']},'relation_is_given_synthetic_condition':True})
    # Actual seven observed source rings, not seven extra candidate votes.
    sources=[]
    for r in D['observed_person_assignments']:
        c=assemble(D,r['choices']);c.update(record=r['record'],worker=r['worker'],voting_role='synthetic_observed_person_not_real_human');sources.append(c)
    dump(out/'synthetic_source_rings.json',sources)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)
