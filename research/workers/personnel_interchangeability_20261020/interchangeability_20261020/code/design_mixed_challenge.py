"""Resample genuinely mixed compositions, including complete team turnover.

A and B are disjoint blocks with the same multivariate class-count vector.
C changes s actual members of B, retaining its other members, but is entirely
disjoint from A. Therefore A->B and A->C both replace exactly m members, while
the number of changed class slots may be smaller than m. All use the same core.
This separates member turnover, class-count change and whole-team resampling.
"""
from __future__ import annotations
import argparse,collections,datetime,random,sys
from pathlib import Path
from design_history_panel import read,write,digest,team_key
from design_blocks import labels_from,counts,allowed_workers,applicable
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'analysis/composition'))
from design_compositions import vectors

SEED=2026102017
METHODS=[
    dict(method_id='F20_highQ23_T_qK2',domain='all',pool_filter={'layer':'ordinary_manual'}),
    dict(method_id='F20_new_Scope_qK2',domain='all',allowed_origins=['new'],pool_filter={'layer':'ordinary_manual'}),
    dict(method_id='F20_new_NewNonedit_qK2',domain='all',allowed_origins=['new'],pool_filter={'layer':'ordinary_manual'}),
    dict(method_id='R_directswap_geometry_partition_b2_K2__ordinary_new__mixed_history_v1',domain='ordinary_new',allowed_origins=['new'],pool_filter={'layer':'ordinary_manual'}),
    dict(method_id='R_directswap_continuous_partition_b2_K3__ordinary__mixed_history_v1',domain='ordinary',pool_filter={'layer':'ordinary_manual'}),
    dict(method_id='R_directswap_geometry_partition_b0_K7__ordinary__mixed_history_v1',domain='ordinary',pool_filter={'layer':'ordinary_manual'}),
    dict(method_id='F20_semi_new_QTGEditReport_balanced_K3',domain='semi_new',allowed_origins=['new'],pool_filter={'layer':'ordinary_semi'})]

def sample_same(groups,oc,origins,matching,rng):
    aa=[];bb=[]
    for (cl,workers),amount in zip(groups.items(),oc):
        if not amount:continue
        if matching=='source_matched':
            on=[w for w in workers if origins[w]=='new'];oo=[w for w in workers if origins[w]=='v1']
            possible=[t for t in range(amount+1) if len(on)>=2*t and len(oo)>=2*(amount-t)]
            if not possible:return None
            t=rng.choice(possible)
            for available,k in [(on,t),(oo,amount-t)]:
                z=rng.sample(available,2*k);aa+=z[:k];bb+=z[k:]
        else:
            z=rng.sample(workers,2*amount);aa+=z[:amount];bb+=z[amount:]
    return sorted(aa),sorted(bb)

def make_event(pool,method,mapping,n,m,matching,phase,rank):
    ws=allowed_workers(pool,method);origin={r['worker_id']:r['origin'] for r in pool['records']}
    classes=sorted(set(mapping.values()));groups={c:[w for w in ws if mapping.get(w)==c] for c in classes}
    caps=tuple(len(v)//2 for v in groups.values())
    choices=[v for v in vectors(caps,m) if sum(x>0 for x in v)>=2]
    if not choices:return None,'no_mixed_count_vector'
    key=[SEED,phase,method['method_id'],method['domain'],pool['pool_id'],n,m,matching,rank]
    rng=random.Random(int(digest(key)[:16],16));reasons=collections.Counter()
    for attempt in range(16):
        oc=rng.choice(choices);blocks=sample_same(groups,oc,origin,matching,rng)
        if blocks is None:reasons['source_capacity_for_chosen_vector']+=1;continue
        aa,bb=blocks;spare=[w for w in ws if w in mapping and w not in set(aa+bb)]
        max_s=min(m,len(spare),len(ws)-n-m)
        if max_s<1:reasons['no_spare_known_member_or_core_capacity']+=1;continue
        s=rng.randint(1,max_s);removed=rng.sample(bb,s)
        if matching=='source_matched':
            added=[]
            for src in ['new','v1']:
                need=sum(origin[w]==src for w in removed);av=[w for w in spare if origin[w]==src]
                if len(av)<need:break
                added+=rng.sample(av,need)
            if len(added)!=s:reasons['cross_source_capacity']+=1;continue
        else:added=rng.sample(spare,s)
        cc=sorted(set(bb)-set(removed)|set(added));ocount=counts(aa,mapping);icount=counts(cc,mapping)
        if ocount==icount:reasons['draw_did_not_change_composition']+=1;continue
        remain=[w for w in ws if w not in set(aa+bb+cc)]
        core=sorted(rng.sample(remain,n-m))
        arms=[sorted(core+b) for b in [aa,bb,cc]];ca,cb,cd=[counts(t,mapping) for t in arms]
        assert ca==cb and ca!=cd
        assert all(len(t)==len(set(t))==n for t in arms)
        assert set(arms[0])&set(arms[1])==set(arms[0])&set(arms[2])==set(core)
        assert len(set(arms[0])-set(arms[1]))==len(set(arms[0])-set(arms[2]))==m
        src=[collections.Counter(origin[w] for w in b) for b in [aa,bb,cc]]
        if matching=='source_matched':assert src[0]==src[1]==src[2]
        slots=sum(abs(ocount.get(c,0)-icount.get(c,0)) for c in classes)//2
        event=dict(event_id='MC20_'+digest(key)[:22],phase=phase,method_id=method['method_id'],domain=method['domain'],
            family='mixed_composition_challenge',context_id='whole_team' if n==m else 'partial_mixed_block',
            pool_id=pool['pool_id'],building=pool['meta']['building'],image=pool['meta']['image'],difficulty=pool['meta']['difficulty'],
            layer=pool['meta']['layer'],condition=pool['meta']['condition'],reference_id=pool['meta']['reference_id'],n=n,k=n,m=m,
            outgoing_class='mixed_vector',incoming_class='changed_mixed_vector',
            outgoing_counts=ocount,incoming_counts=icount,background_policy='random',matching=matching,
            actual_source_match=src[0]==src[1]==src[2],core_workers=core,outgoing_workers=aa,within_incoming=bb,cross_incoming=cc,
            A_counts=ca,B_counts=cb,C_counts=cd,core_counts=counts(core,mapping),changed_category_slots=slots,
            pattern='multi_class_block',outside_background_n=sum(w not in mapping for w in core),complete_turnover=n==m,
            direction=json_vector(ocount)+'>'+json_vector(icount),B_to_C_actual_turnover=s,
            allowed_origins=method.get('allowed_origins',['new','v1']),available_population_n=len(ws),replicate=rank,
            draw_attempts=attempt+1,preceding_draw_failures=dict(reasons))
        for arm,workers in zip('ABC',arms):event[arm+'_workers']=workers;event[arm+'_team_key']=team_key(pool['pool_id'],workers)
        return event,None
    return None,'sixteen_outcome_free_draws_failed:'+str(dict(reasons))

def json_vector(value):return '|'.join(c+':'+str(n) for c,n in sorted(value.items()))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--snapshot',type=Path,required=True);ap.add_argument('--split',type=Path,required=True)
    ap.add_argument('--labels',type=Path,action='append',required=True);ap.add_argument('--phase',choices=['discovery','assessment'],required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();maps=labels_from(a.labels);split=read(a.split);phase=a.phase
    bs=set(split['discovery_buildings' if phase=='discovery' else 'validation_buildings'])
    events=[];requests={};ledger=[]
    for method in METHODS:
        mapping=maps[method['method_id'],method['domain']]
        for pool in read(a.snapshot)['images']:
            if pool['meta']['building'] not in bs or not applicable(pool,method):continue
            ws=allowed_workers(pool,method);known=sum(w in mapping for w in ws)
            classes=collections.Counter(mapping[w] for w in ws if w in mapping)
            max_m=min(sum(v//2 for v in classes.values()),(known-1)//2)
            whole=[];partial=[]
            for m in range(2,max_m+1):
                for n in range(max(3,m),len(ws)-m):
                    for matching in ['source_matched','unrestricted']:
                        (whole if n==m else partial).append((n,m,matching))
            rng=random.Random(int(digest([SEED,phase,method['method_id'],pool['pool_id']])[:16],16))
            rng.shuffle(whole);rng.shuffle(partial)
            selected=whole[:16]+partial[:16];fail=collections.Counter();accepted=[]
            for rank,(n,m,matching) in enumerate(selected):
                event,reason=make_event(pool,method,mapping,n,m,matching,phase,rank)
                if reason:fail[reason]+=1;continue
                events.append(event);accepted.append(event)
                for arm in 'ABC':
                    tk=event[arm+'_team_key'];requests.setdefault(tk,dict(request_id=tk,pool_id=pool['pool_id'],k=n,worker_ids=event[arm+'_workers']))
            ledger.append(dict(method_id=method['method_id'],domain=method['domain'],pool_id=pool['pool_id'],known_workers=known,
                class_capacities=dict(classes),metadata_n_m_source_frame=len(whole)+len(partial),whole_frame=len(whole),partial_frame=len(partial),
                selected_metadata_contexts=len(selected),accepted_events=len(accepted),draw_failures=dict(fail),
                interpretation='n/m/source frame enumerated; at most16 whole+16 partial contexts sampled. Feasible out count vectors enumerated per draw, one sampled; concrete members and net changed slots sampled. Draw failure is not exhaustive impossibility.'))
    spec=dict(schema='multi_class_and_whole_team_challenge_v1',phase=phase,seed=SEED,methods=METHODS,
        registered_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        selection='Seven user-priority/history-risk-supported routes chosen before this challenge outcomes, not from target success ranking.',
        estimands='Same mixed composition with disjoint replacement blocks; same actual m against changed class counts. Complete turnover n=m separately; B/C may overlap, their actual turnover and changed category slots retained.',
        qualification='n>=3, existing frozen pool/reference/native qualification; no altered fusion or metric.')
    write(a.out,dict(spec=spec,events=events,requests=list(requests.values()),ledger=ledger))
    print(dict(events=len(events),unique_teams=len(requests),whole_team_events=sum(e['n']==e['m'] for e in events),
        pools=len({e['pool_id'] for e in events}),buildings=len({e['building'] for e in events}),
        n=sorted({e['n'] for e in events}),m=sorted({e['m'] for e in events}),changed_slots=sorted({e['changed_category_slots'] for e in events})))

if __name__=='__main__':main()
