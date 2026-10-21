"""Capacity-directed, result-independent additions to the frozen main design.

F01: all n=12 member sets in its new-source known-label domain.
Pure blocks: an entire single-class block goes to another class; separate
matched ABC and cross-only designs preserve their distinct estimands.
"""
from __future__ import annotations
import collections,itertools,json,math
import pandas as pd
from multin_design import HERE,ROOT,OLD,gs,h,sha,write_csv,existing_scalar_paths
from design_matched_events import label_maps,event,vecstr

def cache_index(include_f01=True):
    cache={}
    for path in existing_scalar_paths():
        x=pd.read_csv(path,usecols=['team_key']);cache.update({k:str(path.relative_to(ROOT)) for k in x.team_key})
    for name in ['DESIGN_TEAMS.csv.gz','LARGE_BLOCK_TEAMS.csv.gz','F01_CAPACITY_TEAMS.csv.gz']:
        if name=='F01_CAPACITY_TEAMS.csv.gz' and not include_f01:continue
        path=HERE/name
        if path.exists():
            x=pd.read_csv(path,usecols=['team_key']);cache.update({k:'registered_v3:'+name for k in x.team_key})
    historical=set(__import__('gzip').open(OLD/'composition/HISTORICAL_TEAM_KEYS.txt.gz','rt').read().splitlines())
    return cache,historical

_POOL_HASHES={}
def team_row(pool,workers,cache,historical):
    meta=pool['meta'];key=gs.team_key(pool['pool_id'],workers)
    if pool['pool_id'] not in _POOL_HASHES:_POOL_HASHES[pool['pool_id']]=gs.digest(pool)
    return dict(team_key=key,pool_id=pool['pool_id'],image=meta['image'],building=meta['building'],condition=meta['condition'],difficulty=meta['difficulty'],layer=meta['layer'],n=len(workers),member_workers='|'.join(sorted(workers)),cached=key in cache,cache_scalar_source=cache.get(key,''),historical_583261_set_overlap=key in historical,pool_input_sha256=_POOL_HASHES[pool['pool_id']])

def batches(teams,prefix):
    t=pd.DataFrame(teams.values()).sort_values(['condition','pool_id','n','team_key']);chunks=[]
    for condition,cg in t.groupby('condition'):
        rows=[];size=0
        for pid,g in cg.groupby('pool_id'):
            if rows and size+len(g)>12000:chunks.append(pd.concat(rows));rows=[];size=0
            rows.append(g);size+=len(g)
        if rows:chunks.append(pd.concat(rows))
    plan=[]
    for i,g in enumerate(chunks,1):
        bid=f'{prefix}_{i:03d}';write_csv(HERE/'batches'/bid/'REQUESTS.csv.gz',g)
        plan.append(dict(batch_id=bid,condition=g.condition.iloc[0],requested=len(g),cached=int(g.cached.sum()),required=int((~g.cached).sum()),pools=g.pool_id.nunique()))
    write_csv(HERE/f'{prefix.upper()}_BATCH_PLAN.csv',pd.DataFrame(plan));return t

def f01():
    maps,paths=label_maps();pools=gs.pool_lookup();panels=pd.read_csv(HERE/'PANELS.csv',keep_default_na=False)
    source=panels[panels.source_domain.eq('new_only')&panels.condition.eq('manual')].drop_duplicates('pool_id')
    cache,historical=cache_index(False);rows=[];membership=[];teams={};opportunity=[]
    for r in source.to_dict('records'):
        key=('F01','coarse','manual',r['building'])
        if key not in maps:
            opportunity.append(dict(pool_id=r['pool_id'],building=r['building'],image=r['image'],status='outside_F01_frozen_target_building_support'));continue
        labels,parents=maps[key];known=sorted(w for w in r['domain_workers'].split('|') if w in labels);U=len(known)
        meta={k:r[k] for k in ['pool_id','image','building','condition','difficulty','layer','eligible_pool_n']}
        op=dict(meta,source_domain_n=r['domain_pool_n'],known_F01_n=U,n=12,possible_member_sets=math.comb(U,12) if U>=12 else 0)
        if U<12:opportunity.append(dict(op,status='insufficient_known_F01_people_for_n12'));continue
        pid=r['pool_id']+'__F01_knownnew__n12';size=math.comb(U,12)
        rows.append(dict(meta,panel_id=pid,n=12,source_domain='new_only_F01_labelled',domain_pool_n=U,domain_workers='|'.join(known),variable_n=U,selected_variable_n=12,background_n=0,background_workers='',variable_workers='|'.join(known),possible_member_sets=size,exhaustive_conditional_members=True,member_variation_estimable=size>1,source_domain_member_sets=math.comb(int(r['domain_pool_n']),12),classification_scope='frozen_F01_known_new_source_population',label_scope='target_building_excluded'))
        for selected in itertools.combinations(known,12):
            tr=team_row(pools[r['pool_id']],selected,cache,historical);teams[tr['team_key']]=tr
            membership.append(dict(panel_id=pid,pool_id=r['pool_id'],team_key=tr['team_key'],n=12,selected_variable_workers='|'.join(selected),F01_counts=vecstr(selected,labels)))
        opportunity.append(dict(op,status='full_known_domain_member_census',registered_member_sets=size,member_variation_estimable=size>1))
    t=batches(teams,'f01');write_csv(HERE/'F01_CAPACITY_TEAMS.csv.gz',t);write_csv(HERE/'F01_PANELS.csv',pd.DataFrame(rows));write_csv(HERE/'F01_PANEL_MEMBERSHIP.csv.gz',pd.DataFrame(membership));write_csv(HERE/'F01_CAPACITY_OPPORTUNITIES.csv',pd.DataFrame(opportunity))
    frozen=gs.method_rows();frozen=frozen[frozen.method_id.eq('F01')].copy();frozen['label_source']=str((OLD/'composition/legacy_composition_labels.csv').relative_to(ROOT));write_csv(HERE/'F01_FROZEN_LABELS_LOBO.csv.gz',frozen)
    receipt=dict(status='frozen_without_target_outcomes',panels=len(rows),pools=len(rows),buildings=len(set(r['building'] for r in rows)),registered_unique_teams=len(t),cached=int(t.cached.sum()),new_native_required=int((~t.cached).sum()),n=12,member_population='all C(U,12) sets of known F01 labels in the registered new-source domain',U_min=min(r['domain_pool_n'] for r in rows),U_max=max(r['domain_pool_n'] for r in rows),single_set_panels=sum(r['possible_member_sets']==1 for r in rows),single_set_variation_is_evidence=False,maximum_possible_actual_m=max(r['domain_pool_n']-12 for r in rows),labels_sha256=sha(paths[0]),requests_sha256=sha(HERE/'F01_CAPACITY_TEAMS.csv.gz'))
    receipt['labels_sha256']=sha(HERE/'F01_FROZEN_LABELS_LOBO.csv.gz');receipt['label_sources']=sorted(frozen.label_source.unique());gs.save(HERE/'F01_CAPACITY_FREEZE.json',receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)

def count_backgrounds(cap,allowed,b):
    d=[0]*(b+1);d[0]=1
    for c,N in sorted(cap.items()):
        nxt=[0]*(b+1)
        for j,v in enumerate(d):
            if v:
                for k in range(min(allowed[c],b-j)+1):nxt[j+k]+=v*math.comb(N,k)
        d=nxt
    return d[b]

def backgrounds(workers,labels,allowed,b,seed):
    picked=[];used=collections.Counter()
    for w in sorted(workers,key=lambda w:h('pure-background',seed,w)):
        c=labels[w]
        if used[c]<allowed[c]:picked.append(w);used[c]+=1
        if len(picked)==b:break
    if len(picked)!=b:raise ValueError('infeasible registered background')
    first=tuple(sorted(picked));out=[first]
    # Any second feasible fixed-size set is reachable by one legal member
    # exchange in this partition-capacity family, so no failed random retry.
    alternatives=[]
    for a in first:
        for z in set(workers)-set(first):
            cc=used.copy();cc[labels[a]]-=1;cc[labels[z]]+=1
            if all(cc[c]<=allowed[c] for c in cc):alternatives.append(tuple(sorted((set(first)-{a})|{z})))
    if alternatives:out.append(min(set(alternatives),key=lambda q:h('pure-second-background',seed,q)))
    return out

def pure_blocks():
    maps,paths=label_maps();pools=gs.pool_lookup();pp=pd.read_csv(HERE/'PANELS.csv',keep_default_na=False)
    cache,historical=cache_index();events=[];cross=[];opportunities=[];teams={};seen_domains=set()
    for domain in pp.drop_duplicates(['pool_id','source_domain']).to_dict('records'):
        base=domain['domain_workers'].split('|');pool=pools[domain['pool_id']];meta=pool['meta']
        for (method,tier,condition,building),(labels,parents) in sorted(maps.items()):
            if (condition,building)!=(domain['condition'],domain['building']):continue
            workers=sorted(w for w in base if w in labels);unknown=sorted(set(base)-set(workers));N=len(workers)
            did=(domain['pool_id'],method,tier,tuple(workers))
            if did in seen_domains:continue
            seen_domains.add(did);source_domain=domain['source_domain']+('_labelled' if unknown else '')
            cap=collections.Counter(labels[w] for w in workers);class_parent={labels[w]:parents[w] for w in workers}
            if len(cap)<2:
                opportunities.append(dict(pool_id=domain['pool_id'],image=domain['image'],building=building,condition=condition,method_id=method,tier=tier,source_domain=source_domain,known_domain_n=N,unknown_workers='|'.join(unknown),status='fewer_than_two_known_classes'));continue
            for source,target in itertools.permutations(sorted(cap),2):
                max_matched=min(cap[source]//2,cap[target],N//3,(N-10)//2)
                max_cross=min(cap[source],cap[target],N-10)
                for mode,m in [('matched',max_matched),('cross_only',max_cross)]:
                    # A larger cross-only block answers an additional capacity
                    # question; when equally sized matched comparison exists,
                    # the cross-only pair would just repeat the same purpose.
                    if mode=='cross_only' and max_cross<=max_matched:continue
                    baseop=dict(pool_id=domain['pool_id'],image=domain['image'],building=building,condition=condition,difficulty=domain['difficulty'],method_id=method,tier=tier,source_domain=source_domain,known_domain_n=N,unknown_workers='|'.join(unknown),source_class=source,target_class=target,source_capacity=cap[source],target_capacity=cap[target],mode=mode,max_matched_m=max_matched,max_cross_m=max_cross,m=m)
                    if m<4:
                        opportunities.append(dict(baseop,status='class_block_below_four_at_n_at_least_ten'));continue
                    nmax=N-(2*m if mode=='matched' else m)
                    nmin=max(10,m+2)
                    if nmin>nmax:nmin=max(10,m)
                    ns=sorted({nmin,min(20,nmax)})
                    ns=[n for n in ns if nmin<=n<=nmax]
                    for n in ns:
                        allowed=dict(cap);allowed[source]-=m*(2 if mode=='matched' else 1);allowed[target]-=m
                        b=n-m;number=count_backgrounds(cap,allowed,b);seed=[domain['pool_id'],source_domain,method,tier,source,target,mode,n,m]
                        selected_bgs=backgrounds(workers,labels,allowed,b,seed) if b else [tuple()]
                        if len(selected_bgs)!=min(2,number):raise ValueError('background capacity mismatch')
                        generated=0
                        for bi,bg in enumerate(selected_bgs):
                            remain=set(workers)-set(bg)
                            ss=sorted([w for w in remain if labels[w]==source],key=lambda w:h('pure-block',seed,bi,'source',w))
                            tt=sorted([w for w in remain if labels[w]==target],key=lambda w:h('pure-block',seed,bi,'target',w))
                            X=ss[:m];Z=tt[:m];A=sorted(list(bg)+X);C=sorted(list(bg)+Z)
                            panel_id=domain['pool_id']+f'__pure__{source_domain}__{method}__{tier}__{source}_to_{target}__n{n}__m{m}'
                            common=dict(direction_source_class=source,direction_target_class=target,source_class_capacity=cap[source],target_class_capacity=cap[target],labelled_domain_workers='|'.join(workers),unknown_domain_workers='|'.join(unknown),known_domain_n=N,potential_common_backgrounds=str(number),registered_backgrounds=len(selected_bgs),class_seat_transfer=m,original_source_domain=domain['source_domain'],selection_uses_target_outcomes=False)
                            if mode=='matched':
                                Y=ss[m:2*m];B=sorted(list(bg)+Y)
                                scopes=['all_composition_changes']+(['within_parent_fine_change'] if tier=='fine' and class_parent[source]==class_parent[target] else [])
                                for scope in scopes:
                                    r=event(meta,method,tier,labels,parents,A,B,C,panel_id=panel_id,source_domain=source_domain,anchor_id=str(bi),design_scope=scope,event_mode='pure_class_block_matched')
                                    if r['composition_turnover_AC']!=m:raise ValueError('not an entire class transfer')
                                    r.update(common);events.append(r)
                                arms=[A,B,C]
                            else:
                                ka,kc=gs.team_key(domain['pool_id'],A),gs.team_key(domain['pool_id'],C)
                                r={k:meta[k] for k in ['pool_id','image','building','condition','layer','difficulty']}
                                r.update(common,method_id=method,tier=tier,panel_id=panel_id,source_domain=source_domain,anchor_id=str(bi),n=n,m_AC=m,event_id=h('pure-cross-only',panel_id,ka,kc)[:24],event_mode='pure_class_block_cross_only',team_A=ka,team_C=kc,A_member_workers='|'.join(A),C_member_workers='|'.join(C),common_background='|'.join(bg),outgoing_block_X='|'.join(X),changed_count_block_Z='|'.join(Z),A_counts=vecstr(A,labels),C_counts=vecstr(C,labels),A_parent_counts=vecstr(A,parents),C_parent_counts=vecstr(C,parents),within_parent_fine_change=tier=='fine' and class_parent[source]==class_parent[target],composition_turnover_AC=m,matched_same_class_comparison_available_at_this_m=False,label_scope='target_building_excluded')
                                cross.append(r);arms=[A,C]
                            for members in arms:
                                tr=team_row(pool,members,cache,historical);teams[tr['team_key']]=tr
                            generated+=1
                        opportunities.append(dict(baseop,n=n,potential_common_backgrounds=str(number),registered_distinct_backgrounds=len(selected_bgs),registered_physical_contrasts=generated,status='registered_matched' if mode=='matched' else 'registered_cross_only'))
    e_all=pd.DataFrame(events).drop_duplicates('event_id');c_all=pd.DataFrame(cross).drop_duplicates('event_id')
    # The full class-pair capacity screen is larger than the small supplement.
    # Use its largest actual class-seat transfer per image/method/source domain;
    # fine tiers test only genuine sibling changes inside the same parent.
    # Tie-breaking is a fixed hash, never a target quality/geometry result.
    keys=['pool_id','method_id','tier','source_domain'];chosen_keys=set()
    def choose(frame,mode):
        if mode=='matched':valid=frame[(frame.tier.ne('fine')&frame.design_scope.eq('all_composition_changes'))|(frame.tier.eq('fine')&frame.design_scope.eq('within_parent_fine_change'))].copy()
        else:valid=frame[frame.tier.ne('fine')|frame.within_parent_fine_change].copy()
        rows=[]
        for key,g in valid.groupby(keys,sort=True):
            directions=g[['direction_source_class','direction_target_class','class_seat_transfer']].drop_duplicates().to_dict('records')
            choice=min(directions,key=lambda d:(-d['class_seat_transfer'],h('largest-pure-direction',key,mode,d['direction_source_class'],d['direction_target_class'])))
            keep=g[g.direction_source_class.eq(choice['direction_source_class'])&g.direction_target_class.eq(choice['direction_target_class'])]
            rows.append(keep);chosen_keys.add((*key,mode,choice['direction_source_class'],choice['direction_target_class']))
        return pd.concat(rows,ignore_index=True) if rows else valid.iloc[:0]
    e=choose(e_all,'matched');c=choose(c_all,'cross_only');used=set(e.team_A)|set(e.team_B)|set(e.team_C)|set(c.team_A)|set(c.team_C)
    original_team_count=len(teams);teams={k:v for k,v in teams.items() if k in used};t=batches(teams,'pure')
    for op in opportunities:
        key=tuple(op.get(k) for k in keys)+(op.get('mode'),op.get('source_class'),op.get('target_class'))
        op['selected_for_execution']=key in chosen_keys and op.get('status','').startswith('registered_')
        op['capacity_screen_status']=op['status']
        if op.get('status','').startswith('registered_') and not op['selected_for_execution']:
            op['status']='capacity_available_not_selected_maximum_block_rule'
    write_csv(HERE/'matched/PURE_BLOCK_MATCHED_EVENTS.csv.gz',e);write_csv(HERE/'matched/PURE_BLOCK_CROSS_ONLY_EVENTS.csv.gz',c);write_csv(HERE/'matched/PURE_BLOCK_OPPORTUNITIES.csv.gz',pd.DataFrame(opportunities));write_csv(HERE/'PURE_BLOCK_TEAMS.csv.gz',t)
    receipt=dict(status='frozen_without_target_outcomes',matched_events=len(e),cross_only_events=len(c),unique_endpoint_teams=len(t),cached=int(t.cached.sum()),new_native_required=int((~t.cached).sum()),matched_m_min=int(e.m_AC.min()),matched_m_max=int(e.m_AC.max()),cross_only_m_min=int(c.m_AC.min()),cross_only_m_max=int(c.m_AC.max()),n_min=int(t.n.min()),n_max=int(t.n.max()),pools=t.pool_id.nunique(),images=t.image.nunique(),buildings=t.building.nunique(),known_label_subdomains_explicit=True,all_class_seat_transfers_equal_actual_m=True,source_sha256=sha(paths[0]),target_endpoint_scores_never_read=True,matched_events_sha256=sha(HERE/'matched/PURE_BLOCK_MATCHED_EVENTS.csv.gz'),cross_only_events_sha256=sha(HERE/'matched/PURE_BLOCK_CROSS_ONLY_EVENTS.csv.gz'))
    receipt.update(full_capacity_screen_matched_events=len(e_all),full_capacity_screen_cross_only_events=len(c_all),full_capacity_screen_unique_endpoint_teams=original_team_count,execution_selection='Largest feasible class-seat transfer per pool/method/tier/source-domain/mode; fixed hash among tied directional pairs. Fine tiers retain only within-parent changes. Up to two n and two distinct common backgrounds per chosen pair. Selection never reads target endpoint outcomes.')
    gs.save(HERE/'PURE_BLOCK_FREEZE.json',receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('action',choices=['f01','pure']);a=p.parse_args();f01() if a.action=='f01' else pure_blocks()
