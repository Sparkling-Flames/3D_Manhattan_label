"""Freeze n/m/background-matched composition contrasts without endpoints.

Primary panels: 12 deterministic anchors per complete 924-set member panel,
m=2,4,5; search all feasible backgrounds, then hash-select one same-count and
one changed-count endpoint. Fine-within-parent is registered separately.
Supplement: four result-independent anchors at each large-team n; m=8,10,12
and the largest nondegenerate supported m, with maximum feasible class change.
"""
from __future__ import annotations
import collections, itertools, json, math, sys
from pathlib import Path
import numpy as np
import pandas as pd
from multin_design import HERE,ROOT,OLD,CONT,gs,h,write_csv,sha,existing_scalar_paths

NEW=HERE.parent/'taxonomy'
MAIN_METHODS={'M_structure','SP_scale','A2_relation','MV_QTD_manual_new','MV_QTScopeSemi_semi_new','Rnew2','F01'}

def label_maps():
    d=gs.method_rows();d=d[d.method_id.isin(MAIN_METHODS)]
    out={}
    for key,g in d.groupby(['method_id','tier','condition','heldout_building']):
        out[key]=({r.worker_id:r.class_id for r in g.itertuples()},{r.worker_id:r.parent_class for r in g.itertuples()})
    paths=[NEW/'ALL_METHOD_LABELS_LOBO.csv.gz']
    for p in paths:
        if not p.exists():raise FileNotFoundError(p)
        x=pd.read_csv(p,keep_default_na=False);x=x[x.known.astype(str).str.lower().isin(['true','1'])]
        for (method,condition,building),g in x.groupby(['method','condition','heldout_building']):
            if building=='ALL':continue
            for tier in ['coarse','fine']:
                labels={r.worker_id:getattr(r,tier+'_label') for r in g.itertuples() if getattr(r,tier+'_label') not in ['','unknown','unassigned','insufficient_evidence']}
                parents={r.worker_id:r.coarse_label for r in g.itertuples() if r.worker_id in labels}
                out[method,tier,condition,building]=(labels,parents)
    return out,paths

def vec(ws,labels):return collections.Counter(labels[w] for w in ws)
def vecstr(ws,labels):return gs.canonical_counts({c:sum(labels[w]==c for w in ws) for c in sorted(set(labels.values()))})
def turnover(a,b):return sum(abs(a[c]-b[c]) for c in set(a)|set(b))//2

def event(meta,method,tier,labels,parents,A,B,C,*,panel_id,source_domain,anchor_id,design_scope,event_mode):
    A,B,C=tuple(sorted(A)),tuple(sorted(B)),tuple(sorted(C));sa,sb,sc=map(set,(A,B,C));n=len(A)
    bg=sa&sb
    if bg!=sa&sc or len(B)!=n or len(C)!=n:raise ValueError('unmatched_background')
    m=n-len(bg)
    if vec(A,labels)!=vec(B,labels) or vec(A,labels)==vec(C,labels):raise ValueError('invalid_count_contrast')
    teams=[gs.team_key(meta['pool_id'],w) for w in (A,B,C)]
    key=[method,tier,panel_id,design_scope,*teams]
    r={k:meta[k] for k in ['pool_id','image','building','condition','layer','difficulty']}
    r.update(method_id=method,tier=tier,panel_id=panel_id,source_domain=source_domain,anchor_id=anchor_id,
        design_scope=design_scope,event_mode=event_mode,n=n,m_AB=m,m_AC=m,m_BC=n-len(sb&sc),
        event_id=h('event',key)[:24],physical_triple_id=h('physical',sorted(teams))[:24],oriented_triple_id=h('oriented',teams)[:24],
        team_A=teams[0],team_B=teams[1],team_C=teams[2],A_member_workers='|'.join(A),B_member_workers='|'.join(B),C_member_workers='|'.join(C),
        common_background='|'.join(sorted(bg)),outgoing_block_X='|'.join(sorted(sa-bg)),same_count_block_Y='|'.join(sorted(sb-bg)),changed_count_block_Z='|'.join(sorted(sc-bg)),
        A_counts=vecstr(A,labels),B_counts=vecstr(B,labels),C_counts=vecstr(C,labels),
        A_parent_counts=vecstr(A,parents),B_parent_counts=vecstr(B,parents),C_parent_counts=vecstr(C,parents),
        composition_turnover_AC=turnover(vec(A,labels),vec(C,labels)),within_parent_fine_change=(tier=='fine' and vec(A,parents)==vec(C,parents)),
        label_scope='target_building_excluded',selection_uses_target_endpoints=False)
    return r

def panels():
    maps,paths=label_maps();pp=pd.read_csv(HERE/'PANELS.csv',keep_default_na=False);events=[];opportunities=[]
    for panel in pp.to_dict('records'):
        meta={k:panel[k] for k in ['pool_id','image','building','condition','layer','difficulty']};variable=panel['variable_workers'].split('|');bg=panel['background_workers'].split('|');pid=panel['panel_id']
        all_ss=list(itertools.combinations(variable,6));anchors=sorted(all_ss,key=lambda x:h('anchor',pid,x))[:12]
        for (method,tier,cond,building),(labels,parents) in maps.items():
            if (cond,building)!=(panel['condition'],panel['building']):continue
            unknown=set(variable+bg)-labels.keys()
            scopes=['all_composition_changes']+(['within_parent_fine_change'] if tier=='fine' else [])
            for scope in scopes:
                for m in [2,4,5]:
                    opportunity=dict(method_id=method,tier=tier,condition=cond,building=building,panel_id=pid,pool_id=panel['pool_id'],image=panel['image'],difficulty=panel['difficulty'],source_domain=panel['source_domain'],n=panel['n'],m=m,scope=scope,anchor_population=924,anchors_attempted=12,unselected_anchors=912,backgrounds_per_anchor=math.comb(6,6-m),backgrounds_examined=0,eligible_backgrounds=0,candidate_same_alternatives=0,candidate_cross_alternatives=0,candidate_ABC_triples_for_selected_anchors=0,unknown_workers='|'.join(sorted(unknown)),anchors_with_same_count=0,anchors_with_cross_count=0,matched_events=0)
                    if unknown:
                        opportunity['status']='unknown_label_in_panel';opportunities.append(opportunity);continue
                    for ai,X6 in enumerate(anchors):
                        outside=sorted(set(variable)-set(X6));options=[];same_exists=False;cross_exists=False
                        for common in itertools.combinations(X6,6-m):
                            opportunity['backgrounds_examined']+=1
                            removed=set(X6)-set(common);target=vec(removed,labels);target_parent=vec(removed,parents)
                            yy=[];zz=[]
                            for alt in itertools.combinations(outside,m):
                                if vec(alt,labels)==target:yy.append(alt)
                                elif scope=='all_composition_changes' or vec(alt,parents)==target_parent:zz.append(alt)
                            same_exists|=bool(yy);cross_exists|=bool(zz)
                            opportunity['candidate_same_alternatives']+=len(yy);opportunity['candidate_cross_alternatives']+=len(zz)
                            if yy and zz:
                                options.append((common,yy,zz));opportunity['eligible_backgrounds']+=1;opportunity['candidate_ABC_triples_for_selected_anchors']+=len(yy)*len(zz)
                        opportunity['anchors_with_same_count']+=same_exists;opportunity['anchors_with_cross_count']+=cross_exists
                        if not options:continue
                        common,yy,zz=min(options,key=lambda z:h('common',pid,method,tier,scope,ai,m,z[0]))
                        B=min(yy,key=lambda z:h('same',pid,method,tier,scope,ai,m,z));C=min(zz,key=lambda z:h('changed',pid,method,tier,scope,ai,m,z))
                        A=bg+list(X6);B=bg+list(common)+list(B);C=bg+list(common)+list(C)
                        ev=event(meta,method,tier,labels,parents,A,B,C,panel_id=pid,source_domain=panel['source_domain'],anchor_id=str(ai),design_scope=scope,event_mode='complete_panel_same_background')
                        ev.update(candidate_backgrounds_for_anchor=math.comb(6,6-m),eligible_backgrounds_for_anchor=len(options),same_candidates_for_selected_background=len(yy),cross_candidates_for_selected_background=len(zz),candidate_ABC_triples_for_anchor=sum(len(z[1])*len(z[2]) for z in options))
                        events.append(ev)
                        opportunity['matched_events']+=1
                    opportunity['status']='available' if opportunity['matched_events'] else 'no_matched_opportunity';opportunities.append(opportunity)
    e=pd.DataFrame(events).drop_duplicates('event_id');write_csv(HERE/'matched/PANEL_MATCHED_EVENTS.csv.gz',e);write_csv(HERE/'matched/PANEL_OPPORTUNITIES.csv.gz',pd.DataFrame(opportunities))
    r=dict(events=len(e),distinct_endpoints=len(set(e.team_A)|set(e.team_B)|set(e.team_C)),panels=e.panel_id.nunique(),pools=e.pool_id.nunique(),buildings=e.building.nunique(),maximum_m=5,requested_m=[2,4,5],anchor_count_per_panel=12,all_backgrounds_searched_before_one_hash_selected=True,no_score_filter=True,no_native_calls=True,source_sha256={str(p.relative_to(ROOT)):sha(p) for p in paths},events_sha256=sha(HERE/'matched/PANEL_MATCHED_EVENTS.csv.gz'))
    gs.save(HERE/'matched/PANEL_MATCHED_FREEZE.json',r);print(json.dumps(r,ensure_ascii=False),flush=True)

def sample_counts(pool,labels,counts,seed):
    selected=[]
    for c,k in sorted(counts.items()):
        ww=[w for w in pool if labels[w]==c]
        if len(ww)<k:return None
        selected.extend(sorted(ww,key=lambda w:h('member-choice',seed,c,w))[:k])
    return sorted(selected)

def farthest_counts(pool,labels,target,parents=None,target_parent=None):
    cap=vec(pool,labels);m=sum(target.values());candidates=[]
    if parents is None:
        for preferred in cap:
            order=sorted(cap,key=lambda c:(c!=preferred,target[c]/max(cap[c],1),h('class-priority',c)))
            left=m;co=collections.Counter()
            for c in order:co[c]=min(left,cap[c]);left-=co[c]
            if left==0:candidates.append(co)
    else:
        parent_of={labels[w]:parents[w] for w in pool}
        # Vary each sibling allocation towards each candidate preferred child;
        # other parent totals are fixed throughout.
        for preferred in cap:
            co=collections.Counter();good=True
            for pa,k in target_parent.items():
                cs=[c for c in cap if parent_of[c]==pa]
                order=sorted(cs,key=lambda c:(c!=preferred,target[c]/max(cap[c],1),h('class-priority',c)))
                left=k
                for c in order:co[c]=min(left,cap[c]);left-=co[c]
                if left:good=False;break
            if good:candidates.append(co)
    if not candidates:return None
    return max(candidates,key=lambda co:(turnover(co,target),h('count-tie',sorted(co.items()))))

def large_blocks():
    maps,paths=label_maps();pools=gs.pool_lookup();pp=pd.read_csv(HERE/'PANELS.csv',keep_default_na=False);domain_rows=pp.drop_duplicates(['pool_id','source_domain']);events=[];opportunities=[];teams={}
    cached={}
    for p in existing_scalar_paths():
        d=pd.read_csv(p,usecols=['team_key']);cached.update({k:str(p.relative_to(ROOT)) for k in d.team_key})
    d=pd.read_csv(HERE/'DESIGN_TEAMS.csv.gz',usecols=['team_key']);cached.update({k:'registered_v3_conditional_panels' for k in d.team_key})
    historical=set(__import__('gzip').open(OLD/'composition/HISTORICAL_TEAM_KEYS.txt.gz','rt').read().splitlines())
    for domain in domain_rows.to_dict('records'):
        ws=domain['domain_workers'].split('|');N=len(ws);pool=pools[domain['pool_id']];meta=pool['meta'];poolhash=gs.digest(pool)
        ns=sorted({N//2,min(20,N-8)})
        for (method,tier,cond,building),(labels,parents) in maps.items():
            if (cond,building)!=(meta['condition'],meta['building']):continue
            unknown=set(ws)-labels.keys()
            for n in ns:
                if n<10:continue
                ms=sorted({m for m in [8,10,12,min(n,N-n)-2] if 8<=m<=min(n,N-n)})
                for m in ms:
                    for scope in ['all_composition_changes']+(['within_parent_fine_change'] if tier=='fine' else []):
                        op=dict(pool_id=pool['pool_id'],image=meta['image'],building=building,condition=cond,difficulty=meta['difficulty'],method_id=method,tier=tier,source_domain=domain['source_domain'],n=n,m=m,scope=scope,anchors_attempted=4,unknown_workers='|'.join(sorted(unknown)),same_count_capacity=0,cross_count_capacity=0,matched_events=0)
                        if unknown:op['status']='unknown_label_in_domain';opportunities.append(op);continue
                        for ai in range(4):
                            anchor_seed=[pool['pool_id'],domain['source_domain'],n,ai]
                            anchor_type='uniform_hash' if ai<2 else 'label_capacity_constructed'
                            if ai<2:
                                A=sorted(sorted(ws,key=lambda w:h('large-anchor',anchor_seed,w))[:n])
                                X=sorted(sorted(A,key=lambda w:h('large-removed',anchor_seed,m,w))[:m]);bg=sorted(set(A)-set(X));outside=sorted(set(ws)-set(A));tx=vec(X,labels)
                                same=sample_counts(outside,labels,tx,[anchor_seed,m,method,tier,'same'])
                            else:
                                pairlist=[]
                                for cl in sorted(set(labels[w] for w in ws)):
                                    group=sorted([w for w in ws if labels[w]==cl],key=lambda w:h('paired-member',anchor_seed,m,method,tier,w))
                                    pairlist.extend((group[j],group[j+1]) for j in range(0,len(group)-1,2))
                                if len(pairlist)<m:continue
                                pairs=sorted(pairlist,key=lambda z:h('paired-block',anchor_seed,m,method,tier,z))[:m]
                                X=sorted(a for a,b in pairs);same=sorted(b for a,b in pairs)
                                remain=sorted(set(ws)-set(X)-set(same));bg=sorted(sorted(remain,key=lambda w:h('paired-background',anchor_seed,m,method,tier,w))[:n-m])
                                A=sorted(bg+X);outside=sorted(set(ws)-set(A));tx=vec(X,labels)
                            op['same_count_capacity']+=same is not None
                            changed=farthest_counts(outside,labels,tx,parents if scope=='within_parent_fine_change' else None,vec(X,parents) if scope=='within_parent_fine_change' else None)
                            has_changed=changed is not None and turnover(changed,tx)>0;op['cross_count_capacity']+=has_changed
                            if same is None or not has_changed:continue
                            different=sample_counts(outside,labels,changed,[anchor_seed,m,method,tier,'cross']);assert different is not None
                            B=bg+same;C=bg+different;pid=pool['pool_id']+f'__large__{domain["source_domain"]}__n{n}'
                            row=event(meta,method,tier,labels,parents,A,B,C,panel_id=pid,source_domain=domain['source_domain'],anchor_id=str(ai),design_scope=scope,event_mode='large_block_same_background');row['anchor_type']=anchor_type;events.append(row);op['matched_events']+=1
                            for w in (A,B,C):
                                key=gs.team_key(pool['pool_id'],w)
                                if key not in teams:teams[key]=dict(team_key=key,pool_id=pool['pool_id'],image=meta['image'],building=building,condition=cond,difficulty=meta['difficulty'],layer=meta['layer'],n=n,member_workers='|'.join(sorted(w)),cached=key in cached,cache_scalar_source=cached.get(key,''),historical_583261_set_overlap=key in historical,pool_input_sha256=poolhash)
                        op['status']='available' if op['matched_events'] else 'no_matched_capacity';opportunities.append(op)
    e=pd.DataFrame(events).drop_duplicates('event_id');t=pd.DataFrame(teams.values()).sort_values(['condition','pool_id','n','team_key']);write_csv(HERE/'matched/LARGE_BLOCK_EVENTS.csv.gz',e);write_csv(HERE/'matched/LARGE_BLOCK_OPPORTUNITIES.csv.gz',pd.DataFrame(opportunities));write_csv(HERE/'LARGE_BLOCK_TEAMS.csv.gz',t)
    chunks=[]
    for condition,g0 in t.groupby('condition',sort=True):
        current=[];size=0
        for pid,g in g0.groupby('pool_id'):
            if current and size+len(g)>22000:chunks.append(pd.concat(current));current=[];size=0
            current.append(g);size+=len(g)
        if current:chunks.append(pd.concat(current))
    plan=[]
    for i,g in enumerate(chunks,1):
        bid=f'large_{i:03d}';write_csv(HERE/'batches'/bid/'REQUESTS.csv.gz',g);plan.append(dict(batch_id=bid,condition=g.condition.iloc[0],requested=len(g),cached=int(g.cached.sum()),required=int((~g.cached).sum()),pools=g.pool_id.nunique()))
    write_csv(HERE/'LARGE_BLOCK_BATCH_PLAN.csv',pd.DataFrame(plan))
    r=dict(events=len(e),unique_teams=len(t),cached=int(t.cached.sum()),new_native=int((~t.cached).sum()),pools=e.pool_id.nunique(),images=e.image.nunique(),buildings=e.building.nunique(),m_min=int(e.m_AB.min()),m_max=int(e.m_AB.max()),n_min=int(e.n.min()),n_max=int(e.n.max()),status='frozen_without_target_outcomes',label_sources={str(p.relative_to(ROOT)):sha(p) for p in paths},selection='2 uniform hash anchors and 2 label-capacity constructed anchors per source-domain,n,m. Constructed anchors choose m disjoint within-class worker pairs, then common background. Changed vector maximizes L1 over documented greedy class-priority extremes, not exhaustive all count vectors; separate fixed-parent scope. No target endpoint data accessed.',cross_method_events_not_independent=True,all_attempted_capacity_cells_retained=True,event_sha256=sha(HERE/'matched/LARGE_BLOCK_EVENTS.csv.gz'))
    gs.save(HERE/'matched/LARGE_BLOCK_FREEZE.json',r);print(json.dumps(r,ensure_ascii=False),flush=True)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('action',choices=['panels','large']);a=p.parse_args();panels() if a.action=='panels' else large_blocks()
