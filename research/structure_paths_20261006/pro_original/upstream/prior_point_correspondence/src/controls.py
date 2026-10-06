from __future__ import annotations
import copy,json,itertools,random
from pathlib import Path
import numpy as np
from core import *
from run_domains import HUMAN,apply_blocks

def p_signature(ns,gs):
    return tuple(sorted(tuple(sorted(key(ns[i]) for i in g)) for g in gs))
def pair_set(ns,gs):
    return {tuple(sorted((key(ns[i]),key(ns[j])))) for g in gs for i,j in itertools.combinations(g,2)}
def run_state(records,metric,tau,seed_key):
    ns=nodes_from_records(records);ds=distances(ns);gs,z=partition(ns,ds[metric],tau)
    domains=candidate_domains(ns,gs,ds[metric],tau,seed_key)
    auto=[];assisted=[];feasible_sets={}
    rv=HUMAN.get('rpc') if records[0].get('image','').startswith('rPc') else None
    for dom in domains:
        meta,rr=enumerate_two_blocks(ns,ds[metric],tau,dom['blocks'])
        choice=choose(rr);auto.extend(p_signature(ns,apply_blocks(gs,dom,rr[i])) for i in choice['selected_ids'])
        if rv:
            must=[next(i for i,n in enumerate(ns) if key(n)==tuple(k)) for k in rv['must']]
            old=next(i for i,n in enumerate(ns) if key(n)==tuple(rv['rejected']))
            aa=choose(rr,'human_assisted',must=[must],cannot=[(must[0],old)] if old in meta['union'] else [])
            assisted.extend(p_signature(ns,apply_blocks(gs,dom,rr[i])) for i in aa['selected_ids'])
    if not auto:auto=[p_signature(ns,gs)]
    return dict(ns=ns,ds=ds,groups=gs,baseline=p_signature(ns,gs),auto=sorted(set(auto)),assisted=sorted(set(assisted)))

def has_relation(sig,kk):return any(set(tuple(k) for k in kk)<=set(g) for g in sig)

def all_control(root,out):
    out.mkdir(exist_ok=False,parents=True);cfg=json.loads((root/'config.json').read_text());rng=np.random.default_rng(cfg['controls']['seed']);rows=[]
    for image in cfg['full_rosters']:
        records=json.loads((root/'inputs'/f'{image}.json').read_text())['records'];before=copy.deepcopy(records)
        for m in cfg['metrics']:
            t=cfg['controls']['perturb_threshold_deg'];seed=cfg['nominated_seeds'][image];base=run_state(records,m,t,seed)
            for mode,reps in [('shuffle',cfg['controls']['shuffle_repeats']),('rename',cfg['controls']['rename_repeats']),('jitter',cfg['controls']['perturb_repeats']),('seam',1)]:
                for k in range(reps):
                    rec=copy.deepcopy(records)
                    if mode=='shuffle':rng.shuffle(rec)
                    elif mode=='rename':
                        ww=sorted(r['worker'] for r in rec); perm=rng.permutation(len(ww));wm={w:f'ANON_{i:03d}' for w,i in zip(ww,perm)}
                        for r in rec:r['worker']=wm[r['worker']]
                    elif mode=='jitter':
                        for r in rec:
                            p=np.array(r['points']).reshape(-1,2,2);dx=rng.uniform(-.05,.05,len(p));dy=rng.uniform(-.05,.05,(len(p),2))
                            p[:,:,0]=(p[:,:,0]+dx[:,None])%1024;p[:,:,1]+=dy;r['points']=p.reshape(-1,2).tolist()
                    else:
                        for r in rec:r['points']=[[(x+cfg['controls']['seam_shift_px'])%1024,y] for x,y in r['points']]
                    q=run_state(rec,m,t,seed)
                    aa=pair_set(base['ns'],base['groups']);bb=pair_set(q['ns'],q['groups'])
                    data=dict(image=image,metric=m,mode=mode,replicate=k,baseline_partition_changed=q['baseline']!=base['baseline'],
                        changed_pair_relations=len(aa^bb),automatic_alternative_set_changed=q['auto']!=base['auto'],assisted_alternative_set_changed=q['assisted']!=base['assisted'],
                        baseline_groups=len(q['groups']),auto_alternatives=len(q['auto']),assisted_alternatives=len(q['assisted']))
                    if image.startswith('rPc'):
                        data.update(automatic_correct_triple_any=any(has_relation(sig,HUMAN['rpc']['must']) for sig in q['auto']),
                           automatic_correct_triple_all=all(has_relation(sig,HUMAN['rpc']['must']) for sig in q['auto']),
                           assisted_correct_triple_all=bool(q['assisted']) and all(has_relation(sig,HUMAN['rpc']['must']) for sig in q['assisted']))
                    rows.append(data)
            assert records==before
            print('CONTROL',image,m,flush=True)
    # Required targeted mechanisms; truth labels not used by enumeration or cost.
    def nd(i,x,y=128.,w=None):return dict(id=f'S{i}',worker=w or f'W{i}',pair_index=0,points=[[512+x*1024/360,y],[512+x*1024/360,384.]])
    # Finite locality can be insufficient: must-link a0,b0 has a 3-edge incompatibility path in union.
    ns=[nd(i,x) for i,x in enumerate([0,.9,-.3,-1.01,.3,-.6])];ds=distances(ns);t=.70
    old=[[0,1],[2,3],[4,5]];meta,rr=enumerate_two_blocks(ns,ds['pair'],t,old[:2]);loc=choose(rr,'human_assisted',must=[[0,2]])
    global_alt=[[0,2],[1,4],[3,5]]
    global_ok=all(ds['pair'][np.ix_(g,g)].max()<=t for g in global_alt)
    # Equal costs and non-unique compatible correspondences; not hidden by one partition's labels.
    # Pure metric graph fixture; these d values are not claimed as another human panorama.
    ns2=[nd(i,0) for i in range(4)];d=np.array([[0,1,1,1.414],[1,0,1.414,1],[1,1.414,0,1],[1.414,1,1,0.]])
    mm,ties=enumerate_two_blocks(ns2,d,1.01,[[0,1],[2,3]])
    # Same-person collision forbids pooling different nodes even at zero distances.
    sc=copy.deepcopy(ns2);sc[0]['worker']=sc[2]['worker']='same_person'
    sm,same=enumerate_two_blocks(sc,np.zeros((4,4)),5.,[[0,1],[2,3]])
    # Geometrically identical endpoints can be distinct upper targets. Labels exist only in evaluation.
    conflict=dict(observations=[nd(0,0),nd(1,0)],known_upper_targets=['low_object_top','ceiling_boundary'],
                  metric_top_angle_deg=0.,automatic_semantic_identifiability=False,
                  alternative_world_same_observations=['same_target','same_target'])
    # Fixed-domain input permutations preserve the full feasible set (not necessarily upstream clustering).
    rpc=json.loads((root/'inputs/rPc6DW4iMge-06.json').read_text())['records'];orig=run_state(rpc,'pair',5,cfg['nominated_seeds']['rPc6DW4iMge-06'])
    ns0=orig['ns'];ds0=orig['ds'];dom=candidate_domains(ns0,orig['groups'],ds0['pair'],5,cfg['nominated_seeds']['rPc6DW4iMge-06'])[0]
    _,r0=enumerate_two_blocks(ns0,ds0['pair'],5,dom['blocks']);s0={p_signature(ns0,r['blocks']) for r in r0};invars=[]
    for k in range(8):
        perm=rng.permutation(len(ns0));inv=np.argsort(perm);nsp=[ns0[i] for i in perm];dp=ds0['pair'][np.ix_(perm,perm)]
        b=[[int(inv[i]) for i in g] for g in dom['blocks']];_,rrp=enumerate_two_blocks(nsp,dp,5,b)
        invars.append({p_signature(nsp,r['blocks']) for r in rrp}==s0)
    targeted=dict(local_scope_counterexample=dict(nodes=ns,threshold=t,original_partition=old,local_result=loc,
                        local_feasible_count=len(rr),global_alternative=global_alt,global_alternative_valid=bool(global_ok),incompatibilities=meta['forbidden_pairs'],
                        interpretation='A local two-block impossibility is not a global impossibility; no data or threshold changes.'),
        symmetric_tie=dict(metric_graph_not_real_panorama=True,candidates=ties,distinct_partitions=len(ties),all_costs_equal=max(r['cost'] for r in ties)-min(r['cost'] for r in ties)<1e-10),
        same_worker=dict(feasible_count=len(same),all_unique_workers=all(all(len({sc[i]['worker'] for i in g})==len(g) for g in r['blocks']) for r in same),forbidden_pairs=sm['forbidden_pairs']),
        unidentifiable_upper_semantics=conflict,fixed_domain_permutation=dict(repeats=8,all_feasible_sets_equal=all(invars),states=len(s0)),
        control_labels='synthetic or transformed copies; not new independent human records; original inputs unchanged')
    (out/'robustness_rows.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    (out/'targeted_controls.json').write_text(json.dumps(targeted,ensure_ascii=False,indent=2))
    summ=[]
    for image,m,mode in itertools.product(cfg['full_rosters'],cfg['metrics'],['shuffle','rename','jitter','seam']):
        a=[r for r in rows if r['image']==image and r['metric']==m and r['mode']==mode]
        summ.append(dict(image=image,metric=m,mode=mode,n=len(a),baseline_changed=sum(r['baseline_partition_changed'] for r in a),auto_set_changed=sum(r['automatic_alternative_set_changed'] for r in a),
             assisted_set_changed=sum(r['assisted_alternative_set_changed'] for r in a),max_changed_relations=max(r['changed_pair_relations'] for r in a),
             automatic_correct_triple_any=sum(r.get('automatic_correct_triple_any',False) for r in a)))
    (out/'robustness_summary.json').write_text(json.dumps(summ,ensure_ascii=False,indent=2))
    print('CONTROL COMPLETE',len(rows),targeted,flush=True)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();all_control(a.root,a.out)
