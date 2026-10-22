"""Enumerate exact matched ABC triples within each registered n20 panel.

This module deliberately never opens scores, endpoint geometry, or outcomes.
Coarse views reuse each family's identical registered fine-panel member sets.
"""
from __future__ import annotations
import argparse, collections, csv, gzip, hashlib, json, os, time
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
STUDY=HERE.parents[1]
DESIGN=HERE.parent/'next_stage/candidate_n20'
LABELS=STUDY/'composition/FROZEN_LABELS.csv'

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:24]

def read_csv(p):
    op=gzip.open if str(p).endswith('.gz') else open
    with op(p,'rt',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def save_json(p,d):
    p=Path(p);t=p.with_name(p.name+'.pending')
    with t.open('w',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(t,p)

def save_csv(p,rows,fields=None,key=None):
    p=Path(p);rows=list(rows)
    if fields is None:fields=list(rows[0])
    t=p.with_name(p.name+'.pending');op=gzip.open if str(p).endswith('.gz') else open
    with op(t,'wt',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
    with op(t,'rt',encoding='utf-8-sig',newline='') as f:
        r=csv.reader(f);assert next(r)==fields
        n=0;keys=[]
        for row in r:
            assert len(row)==len(fields);n+=1
            if key:keys.append(row[fields.index(key)])
    assert n==len(rows)
    if key:assert keys==[str(x[key]) for x in rows] and len(keys)==len(set(keys))
    os.replace(t,p)
    return dict(path=str(p.relative_to(HERE)),rows=n,columns=len(fields),bytes=p.stat().st_size,sha256=sha(p))

def counts(ws,mapping):
    c=collections.Counter(mapping[w] for w in ws)
    return '|'.join(f'{k}:{v}' for k,v in sorted(c.items()))

def discover(condition):
    started=time.monotonic()
    membership=read_csv(DESIGN/'CONFIG_MEMBERSHIP.csv.gz')
    with gzip.open(DESIGN/'ENDPOINT_REQUESTS.json.gz','rt') as f:requests=json.load(f)['requests']
    request={r['team_key']:r for r in requests}
    labels=read_csv(LABELS)
    maps=collections.defaultdict(dict)
    parents=collections.defaultdict(dict)
    for r in labels:
        maps[(r['method_id'],r['tier'],r['condition'],r['heldout_building'])][r['worker_id']]=r['class_id']
        if r['tier']=='fine':parents[(r['method_id'],r['condition'],r['heldout_building'])][r['class_id']]=r['parent_class']
    grouped=collections.defaultdict(dict)
    for r in membership:
        if r['condition']==condition:grouped[(r['method_id'],r['tier'],r['pool_id'])][r['team_key']]=r
    out=[];ledgers=[];mrows=[];physical=set();old_oriented=set()
    # Old event IDs are not used for selection. They only mark repeats after
    # metadata enumeration has fixed the full candidate set.
    meta_fields=['pool_id','image','image_id','building','condition','layer','difficulty','reference_id','reference_version','method_id','formal_pool_n','labelled_pool_n']
    for gi,((method,input_tier,pid),group) in enumerate(sorted(grouped.items())):
        gs=sorted(group.values(),key=lambda x:x['team_key']);first=gs[0]
        teamkeys=[r['team_key'] for r in gs]
        workers=[request[k]['member_workers'] for k in teamkeys]
        universe=sorted(set().union(*(set(w) for w in workers)));assert len(universe)<=64
        bit={w:1<<i for i,w in enumerate(universe)}
        masks=np.array([sum(bit[w] for w in ws) for ws in workers],dtype=np.uint64)
        assert len(set(masks.tolist()))==len(gs)
        tiers=['single'] if input_tier=='single' else ['coarse','fine']
        for tier in tiers:
            mapping=maps[(method,tier,condition,first['building'])]
            assert all(set(ws)<=mapping.keys() for ws in workers)
            comp=[counts(ws,mapping) for ws in workers]
            comp_names=sorted(set(comp));comp_i=np.array([comp_names.index(c) for c in comp],int)
            if tier=='fine':
                pm=maps[(method,'coarse',condition,first['building'])]
                par=[counts(ws,pm) for ws in workers]
            else:par=comp
            registered=0;raw=0;skipped=0;same_pairs=0;no_c=0;by_m=collections.defaultdict(collections.Counter)
            active_anchors=set();active_backgrounds=set()
            for ai,am0 in enumerate(masks):
                am=int(am0);inter=masks&am0
                # At most 1287 registered sets per input family/pool. Group by
                # the exact background mask, not by overlap cardinality.
                unique,inverse,ns=np.unique(inter,return_inverse=True,return_counts=True)
                for ui,s0 in enumerate(unique):
                    s=int(s0);m=20-s.bit_count()
                    if m<4:continue
                    ix=np.flatnonzero(inverse==ui)
                    bs=ix[comp_i[ix]==comp_i[ai]]
                    if len(bs)==0:continue
                    assert ai not in bs
                    cs=ix[comp_i[ix]!=comp_i[ai]]
                    same_pairs+=len(bs);by_m[m]['eligible_oriented_AB_pairs']+=len(bs)
                    if len(cs)==0:
                        no_c+=len(bs);by_m[m]['AB_pairs_without_same_S_cross_C']+=len(bs);continue
                    raw+=len(bs)*len(cs);by_m[m]['raw_valid_anchor_triples']+=len(bs)*len(cs)
                    for bi0 in bs:
                        bi=int(bi0);bm=int(masks[bi])
                        for ci0 in cs:
                            ci=int(ci0);cm=int(masks[ci])
                            # B can also anchor this same physical triple iff
                            # B∩C is the exact same S. Retain the smaller legal
                            # A/B team key only, otherwise keep the sole valid A.
                            if bi<ai and (bm&cm)==s:
                                skipped+=1;by_m[m]['duplicate_valid_anchor_removed']+=1;continue
                            registered+=1;by_m[m]['unique_matched_triples']+=1
                            parent_same=(par[ai]==par[ci]) if tier=='fine' else False
                            if parent_same:by_m[m]['within_parent_fine_triples']+=1
                            keys=[teamkeys[j] for j in (ai,bi,ci)]
                            eid=digest(['n20_registered_panel_exact_abc_v1',method,tier,pid,*keys])
                            wsA,wsB,wsC=[set(workers[j]) for j in (ai,bi,ci)]
                            S=wsA&wsB;assert S==wsA&wsC and len(wsA-wsB)==len(wsA-wsC)==m
                            row={k:first[k] for k in meta_fields}
                            row.update(event_id=eid,tier=tier,input_panel_tier=input_tier,event_mode='cross_composition',
                              within_parent_fine_change=parent_same,n=20,m_AB=m,m_AC=m,m_BC=len(wsB-wsC),
                              overlap_AB=len(S),overlap_AC=len(S),overlap_BC=len(wsB&wsC),
                              team_A=keys[0],team_B=keys[1],team_C=keys[2],composition_A=comp[ai],composition_B=comp[bi],composition_C=comp[ci],
                              parent_composition_A=par[ai],parent_composition_C=par[ci],
                              common_background='|'.join(sorted(S)),outgoing_block_X='|'.join(sorted(wsA-S)),same_count_block_Y='|'.join(sorted(wsB-S)),changed_count_block_Z='|'.join(sorted(wsC-S)),
                              A_member_workers='|'.join(sorted(wsA)),B_member_workers='|'.join(sorted(wsB)),C_member_workers='|'.join(sorted(wsC)),
                              physical_triple_id=digest([pid,*sorted(keys)]),oriented_triple_id=digest([pid,*keys]),
                              registration_stage='n20_all_registered_panel_exact_matched_triples_v1',
                              selection_contract='all feasible m>=4 triples within own registered panel; canonical legal anchor; no outcomes read')
                            out.append(row);physical.add(row['physical_triple_id']);active_anchors.add(ai);active_backgrounds.add(s)
            ledger={k:first[k] for k in meta_fields}
            ledger.update(tier=tier,input_panel_tier=input_tier,n=20,registered_member_sets=len(gs),registered_vectors=len(comp_names),
              eligible_oriented_AB_pairs=same_pairs,AB_pairs_without_same_S_cross_C=no_c,raw_valid_anchor_triples=raw,
              duplicate_valid_anchor_removed=skipped,unique_matched_triples=registered,anchors_with_events=len(active_anchors),distinct_backgrounds=len(active_backgrounds),
              within_parent_fine_triples=sum(c['within_parent_fine_triples'] for c in by_m.values()))
            assert raw-skipped==registered
            ledgers.append(ledger)
            for m,c in sorted(by_m.items()):mrows.append({k:ledger[k] for k in meta_fields+['tier','n']}|{'m':m}|{f:c[f] for f in ['eligible_oriented_AB_pairs','AB_pairs_without_same_S_cross_C','raw_valid_anchor_triples','duplicate_valid_anchor_removed','unique_matched_triples','within_parent_fine_triples']})
        if (gi+1)%20==0:print(json.dumps({'condition':condition,'groups_done':gi+1,'groups_total':len(grouped),'unique_events_so_far':len(out),'seconds':time.monotonic()-started}),flush=True)
    assert len(out)==len({r['event_id'] for r in out})
    # This comparison accesses old membership metadata only, never old scores.
    for r in read_csv(STUDY/'composition/ABC_EVENTS.csv.gz'):
        old_oriented.add((r['method_id'],r['tier'],r['pool_id'],r['team_A'],r['team_B'],r['team_C']))
    for r in out:
        r['previously_registered_same_oriented_triple']=(r['method_id'],r['tier'],r['pool_id'],r['team_A'],r['team_B'],r['team_C']) in old_oriented
    folder=HERE/('design_'+condition);folder.mkdir(parents=True,exist_ok=True)
    if out:
        event_result=save_csv(folder/'MATCHED_ABC_EVENTS.csv.gz',out,key='event_id')
    else:event_result={'path':None,'rows':0}
    results=[event_result,save_csv(folder/'MATCHED_ABC_POOL_SCALE.csv',ledgers)]
    if mrows:results.append(save_csv(folder/'MATCHED_ABC_M_SCALE.csv',mrows))
    receipt={'condition':condition,'n':20,'minimum_actual_m':4,'registered_family_pool_groups':len(grouped),
      'registered_method_tier_pool_groups':len(ledgers),'events':len(out),'unique_physical_triples_across_methods':len(physical),
      'same_oriented_triples_in_previous_ABC':sum(r['previously_registered_same_oriented_triple'] for r in out),
      'all_matched_triples_in_declared_registered_panel_enumerated':True,
      'all_possible_membersets_enumerated':False,'all_methods_union_membersets_relabelled':False,
      'outcomes_accessed_for_design':False,'labels_target_building_excluded':True,
      'source_sha256':{str(p.relative_to(STUDY)):sha(p) for p in [DESIGN/'CONFIG_MEMBERSHIP.csv.gz',DESIGN/'ENDPOINT_REQUESTS.json.gz',LABELS]},
      'code_sha256':sha(Path(__file__)),'seconds':time.monotonic()-started,'outputs':results}
    save_json(folder/'DESIGN_RECEIPT.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--condition',choices=['manual','semi'],required=True);a=p.parse_args();discover(a.condition)
