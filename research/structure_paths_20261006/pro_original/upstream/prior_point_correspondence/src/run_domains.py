from __future__ import annotations
import json,gzip,copy,itertools
from pathlib import Path
import numpy as np
from core import *

HUMAN={
 'rpc':dict(image='rPc6DW4iMge-06',must=[['R02452',2],['R01986',2],['R01557',4]],rejected=['R01557',2],relation='same_corner_pair'),
 '2t7':dict(image='2t7WUuJeko7-06',must=[['R00227',0],['R00539',0],['R01831',0]],relation='same_corner_pair'),
 'unb':dict(image='uNb9QFRL6hY-67',bottom=[['R00144',0],['R00526',0],['R02210',0]],bottom_relation='same_corner_user_tentative',upper_target_labels={'R00144:0':'low_glass_top','R00526:0':'glass_to_ceiling','R02210:0':'glass_to_ceiling'},task_target='undecided')
}

def human_probe(ns,gs,ds,tau,review,metric):
    kk=review.get('must',review.get('bottom'))
    ix=[next(i for i,n in enumerate(ns) if key(n)==tuple(k)) for k in kk]
    ids=[next(j for j,g in enumerate(gs) if i in g) for i in ix]
    union=sorted(set(i for g in set(ids) for i in gs[g]));d=ds[metric]
    coords=np.unravel_index(np.argmax(d[np.ix_(union,union)]),(len(union),len(union)))
    byworker={w:[key(ns[i]) for i in union if ns[i]['worker']==w] for w in set(ns[i]['worker'] for i in union)}
    ans=dict(members=kk,member_groups=[f'corner_{i+1:03d}' for i in ids],supports=[len(gs[i]) for i in ids],
       same_group=len(set(ids))==1,local_diameters_deg={m:float(x[np.ix_(ix,ix)].max()) for m,x in ds.items()},
       local_feasible=bool(d[np.ix_(ix,ix)].max()<=tau),whole_union_diameter=float(d[np.ix_(union,union)].max()),
       whole_union_witness=[key(ns[union[i]]) for i in coords],same_worker_conflicts={w:v for w,v in byworker.items() if len(v)>1})
    if 'rejected' in review:
        old=next(i for i,n in enumerate(ns) if key(n)==tuple(review['rejected'])); oid=next(j for j,g in enumerate(gs) if old in g)
        ans['wrong_triple_same_group']=len(set(ids[:2]+[oid]))==1
    return ans

def apply_blocks(gs,dom,cand):
    out=[g for i,g in enumerate(gs) if i not in dom['group_indices']];out+=cand['blocks'];return out

def main(root:Path,out:Path,resume=False):
    out.mkdir(parents=True,exist_ok=resume)
    cfg=json.loads((root/'config.json').read_text()); summaries=[];checks=[];node_tables={}; baselines=[];probes=[]
    for image,n_exp in cfg['full_rosters'].items():
        rec=json.loads((root/'inputs'/f'{image}.json').read_text())['records'];assert len(rec)==n_exp
        before=copy.deepcopy(rec);ns=nodes_from_records(rec); ds=distances(ns);di=distances(ns,independent=True)
        node_tables[image]=ns
        checks.append(dict(image=image,n_records=len(rec),n_nodes=len(ns),independent_distance_max_error=max(float(np.max(abs(ds[s]-di[s]))) for s in ds)))
        for t in cfg['thresholds_deg']:
            for metric in cfg['metrics']:
                gs,z=partition(ns,ds[metric],t)
                if len(set(sum(gs,[])))!=len(ns): raise AssertionError('observation_loss')
                baseline=dict(image=image,threshold=t,metric=metric,roster_denominator=len(rec),groups=gs,
                   centers=[center(ns,g,ds['pair']) for g in gs],linkage=z.tolist())
                baselines.append(baseline)
                for review in HUMAN.values():
                    if review['image']==image:probes.append(dict(image=image,threshold=t,metric=metric,**human_probe(ns,gs,ds,t,review,metric)))
                doms=candidate_domains(ns,gs,ds[metric],t,cfg['nominated_seeds'][image])
                if not doms:summaries.append(dict(image=image,threshold=t,metric=metric,status='no_cross_group_compatible_domain',domain_id=None))
                for k,dom in enumerate(doms):
                    name=f'{image}_{metric}_{t:g}_d{k}'
                    cached=out/(name+'.json')
                    if resume and cached.exists():
                        obj=json.loads(cached.read_text()); meta=obj['domain'];auto=obj['automatic'];assistance=obj['human_assisted'];detailed=obj['selected_details'];front=obj['pareto_ids']
                        def cachedsame(sel):return [v.get('human_development_probe',{}).get('same_group') for v in detailed if v['local_id'] in (sel or {}).get('selected_ids',[])]
                        summaries.append(dict(image=image,threshold=t,metric=metric,domain_id=name,status=meta['status'],n_nodes=meta['union_nodes'],states=meta['orientation_states'],feasible=meta.get('feasible_count',0),baseline_sizes=list(map(len,dom['blocks'])),automatic=auto,assisted=assistance,automatic_triple_same=cachedsame(auto),assisted_triple_same=cachedsame(assistance),pareto_count=len(front)))
                        continue
                    print('START',name,flush=True)
                    meta,rr=enumerate_two_blocks(ns,ds[metric],t,dom['blocks'],**dict(max_nodes=cfg['limits']['max_union_nodes'],max_states=cfg['limits']['max_orientation_states']))
                    print('ENUMERATED',name,len(rr),flush=True)
                    meta.update(domain_id=name,group_indices=dom['group_indices'],compatible_cross_pairs=dom['compatible_cross_pairs'])
                    auto=choose(rr) if rr else dict(status='budget_exceeded',selected_ids=[])
                    assistance=None
                    # These branches run AFTER complete automatic candidates are computed.
                    if image=='rPc6DW4iMge-06' and rr:
                        rv=HUMAN['rpc'];must=[next(i for i,n in enumerate(ns) if key(n)==tuple(k)) for k in rv['must']]
                        wrong=next(i for i,n in enumerate(ns) if key(n)==tuple(rv['rejected']))
                        # If rejected point is outside local domain, fixed global partition already separates it.
                        cannot=[(must[0],wrong)] if wrong in meta['union'] else []
                        assistance=choose(rr,'human_assisted',must=[must],cannot=cannot)
                    front=frontier(rr) if rr else []
                    selected=set(auto['selected_ids']+(assistance or {}).get('selected_ids',[])+front)
                    detailed=[]
                    for cand in rr:
                        if cand['local_id'] not in selected:continue
                        full=apply_blocks(gs,dom,cand)
                        old_edges={tuple(sorted((a,b))) for g in dom['blocks'] for a,b in itertools.combinations(g,2)}
                        new_edges={tuple(sorted((a,b))) for g in cand['blocks'] for a,b in itertools.combinations(g,2)}
                        ca=dict(cand,diameters_checked_deg=[float(ds[metric][np.ix_(g,g)].max()) for g in cand['blocks']],centers=[center(ns,g,ds['pair']) for g in cand['blocks']],
                           added_coassignments=[list(e) for e in sorted(new_edges-old_edges)],lost_coassignments=[list(e) for e in sorted(old_edges-new_edges)],
                           full_observation_count=len(sum(full,[])),full_unique_observations=len(set(sum(full,[]))),
                           outside_groups_unchanged=all(g in full for j,g in enumerate(gs) if j not in dom['group_indices']),new_same_worker_collisions=sum(len(g)-len({ns[i]['worker'] for i in g}) for g in full),new_diameter_violations=sum(float(ds[metric][np.ix_(g,g)].max())>t+1e-10 for g in full),
                           newly_split_identical_coordinates=[list(e) for e in sorted(old_edges-new_edges) if ds['pair'][e[0],e[1]]<=1e-10],
                           complete_layout_created=False,roster_denominator=len(rec))
                        for case,review in HUMAN.items():
                            if review['image']==image: ca['human_development_probe']=human_probe(ns,full,ds,t,review,metric)
                        detailed.append(ca)
                    with gzip.GzipFile(filename='',mode='wb',fileobj=(out/(name+'.jsonl.gz')).open('wb'),mtime=0) as f:
                        for row in rr:f.write((json.dumps(row,separators=(',',':'),allow_nan=False)+'\n').encode())
                    min_w=min((x['cost'] for x in rr),default=None);base_w=next((x['cost'] for x in rr if x['edit_count']==0),None)
                    obj=dict(minimum_dispersion_ids=[r['local_id'] for r in rr if r['cost']<=min_w+1e-10] if rr else [],
                         baseline_equal_dispersion_ids=[r['local_id'] for r in rr if abs(r['cost']-base_w)<=1e-10] if rr else [],
                         domain=meta,automatic=auto,human_assisted=assistance,pareto_ids=front,selected_details=detailed,
                         all_candidate_ledger=name+'.jsonl.gz',node_lookup_file='node_lookup.json')
                    (out/(name+'.json')).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False))
                    def same_out(sel):
                        vv=[v for v in detailed if v['local_id'] in sel.get('selected_ids',[])]
                        return [v.get('human_development_probe',{}).get('same_group') for v in vv]
                    summaries.append(dict(image=image,threshold=t,metric=metric,domain_id=name,status=meta['status'],n_nodes=meta['union_nodes'],
                        states=meta['orientation_states'],feasible=len(rr),baseline_sizes=list(map(len,dom['blocks'])),
                        automatic=auto,assisted=assistance,automatic_triple_same=same_out(auto),assisted_triple_same=same_out(assistance or {}),pareto_count=len(front)))
        assert rec==before
    for name,obj in [('domains_summary',summaries),('node_lookup',node_tables),('baseline_partitions',baselines),('development_probes',probes),('input_checks',checks)]:
        (out/(name+'.json')).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False))
    print('domains',sum(x['domain_id'] is not None for x in summaries),'feasible',sum(x.get('feasible',0) for x in summaries))
    for row in summaries:
        if row['image'].startswith('rPc') and row['threshold']==5:print(row)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--resume',action='store_true')
    a=p.parse_args();main(a.root,a.out,a.resume)
