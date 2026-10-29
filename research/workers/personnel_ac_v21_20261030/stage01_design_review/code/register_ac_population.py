"""Outcome-blind registration of AC, whole-class and coalition studies.

No annotation geometry, target-image score, or time value is read. This program
only reads the frozen, projected capacity inputs. It does not execute fusion.
The native legacy team-key convention is preserved byte for byte.
"""
from pathlib import Path
from itertools import combinations, product
from collections import defaultdict, Counter
import argparse, csv as csvlib, gzip, hashlib, json, math, random, time, tempfile, shutil
import pandas as pd

BASE=Path(__file__).resolve().parents[2]
CAP=BASE/'stage01_capacity'
OUT=Path(__file__).resolve().parents[1]
SEED=202610291901
COMMIT='ec0973ad46fcfa64d3cdbedfeeef1fee180c4cff'
METHODS=['TARGET_DSTRUCT_K3','TARGET_DSTRUCT_K2','V21_DSTRUCT_RAW3_K3',
         'OPPJOINT_K3','OPPJOINT_K4','RFUSE_GEOM_K2','OPPSTRUCT_K3']
CORE=['TARGET_DSTRUCT_K3','V21_DSTRUCT_RAW3_K3','OPPJOINT_K3','OPPJOINT_K4']

def enc(x):return json.dumps(x,sort_keys=True,separators=(',',':'))
def digest(x):return hashlib.sha256(enc(x).encode()).hexdigest()
def team_key(pid,workers):return pid+'__'+digest(sorted(workers))[:20]
def rng(*x):return random.Random(int(digest([SEED,*x])[:16],16))
def save(obj,path):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def csv(rows,path):
    # Explicitly close and atomically promote compressed tables. A dataframe
    # writer returned successfully with an incomplete gzip in this environment.
    fields=list(dict.fromkeys(k for row in rows for k in row))
    tmp=path.with_name(path.name+'.partial')
    opener=gzip.open if path.name.endswith('.gz') else open
    with opener(tmp,'wt',encoding='utf-8-sig',newline='') as stream:
        writer=csvlib.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    tmp.replace(path)
def unpipe(x):return [] if pd.isna(x) or not str(x) else str(x).split('|')

def sample_xz(S,T,m,token,draws,enumerate_limit):
    total=math.comb(len(S),m)*math.comb(len(T),m)
    if total<=max(enumerate_limit,draws):
        return [(list(x),list(z),'enumerated',i) for i,(x,z) in enumerate(product(combinations(S,m),combinations(T,m)))],total
    found=[];seen=set()
    # Two independent batches, de-duplicated; never weight duplicates as repeats.
    for batch in range(2):
        rr_x=rng('XZ_group',token,S,m,batch);rr_z=rng('XZ_group',token,T,m,batch)
        wanted=(draws+1)//2 if batch==0 else draws//2
        if wanted<=0:continue
        for attempt in range(10000):
            x=tuple(sorted(rr_x.sample(S,m)));z=tuple(sorted(rr_z.sample(T,m)));sig=(x,z)
            if sig in seen:continue
            seen.add(sig);found.append((list(x),list(z),f'batch_{batch}',attempt))
            wanted-=1
            if wanted<=0:break
    assert len(found)==min(draws,total)
    return found,total

def fair_class_sequence(groups,token):
    """A monotone proportional quota path; no largest-remainder paradox."""
    sizes={k:len(v) for k,v in groups.items() if v};N=sum(sizes.values())
    used=Counter();seq=[];tie={k:digest([token,k]) for k in sizes}
    for i in range(N):
        k=min((k for k in sizes if used[k]<sizes[k]),key=lambda k:(-(sizes[k]*(i+1)/N-used[k]),tie[k]))
        used[k]+=1;seq.append(k)
    return seq

def background_paths(remaining,lookup,s,t,token):
    groups=defaultdict(list)
    for w in remaining:groups[lookup.get(w,'unknown')].append(w)
    order={}
    for rep in [0,1]:
        by={k:sorted(v) for k,v in groups.items()}
        for k,v in by.items():rng('D_members',token,k,rep).shuffle(v)
        seq=fair_class_sequence(groups,['D_quota',token])
        ix=Counter();path=[]
        for k in seq:path.append(by[k][ix[k]]);ix[k]+=1
        order[f'neutral_members_{rep}']=path
        if rep==0:
            for key,name in [(s,'source_enriched'),(t,'target_enriched')]:
                focus=by.get(key,[])
                other={k:v for k,v in groups.items() if k!=key}
                tailseq=fair_class_sequence(other,['D_enriched_quota',token,key]);ix=Counter();tail=[]
                for k in tailseq:tail.append(by[k][ix[k]]);ix[k]+=1
                order[name]=focus+tail
    for v in order.values():assert len(v)==len(set(v))==len(remaining) and set(v)==set(remaining)
    return order

class Registry:
    def __init__(self,pools,pm,roles):
        self.pools=pools;self.pm=pm;self.roles=roles;self.events={};self.link_n=0;self.teams=set();self.cells=[]
        self.counts=Counter();self.seq=0;self.anchors={};self.physical_methods=defaultdict(set)
        self.method_counts=Counter();self.scope_counts=Counter();self.event_pools=set()
        self.temp=Path(tempfile.mkdtemp(prefix='hohonet_ac_registration_'))
        self.streams={k:gzip.open(self.temp/(k+'.jsonl.gz'),'wt',encoding='utf-8',compresslevel=2) for k in ['events','links','requests','omissions']}
        self.fields={k:set() for k in self.streams}
    def write(self,kind,row):
        self.fields[kind].update(row)
        self.streams[kind].write(json.dumps(row,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
    def finish(self,out):
        for stream in self.streams.values():stream.close()
        for kind,name in [('events','AC_EVENTS.csv.gz'),('links','DESIGN_LINKS.csv.gz'),('requests','TEAM_REQUESTS.csv.gz'),('omissions','NONEXECUTED_SMALL_TEAM_CONTRASTS.csv.gz')]:
            fields=sorted(self.fields[kind])
            if kind=='events':fields+=['design_family']
            temporary=out/(name+'.partial')
            with gzip.open(self.temp/(kind+'.jsonl.gz'),'rt',encoding='utf-8') as src,gzip.open(temporary,'wt',encoding='utf-8-sig',newline='',compresslevel=5) as dst:
                writer=csvlib.DictWriter(dst,fieldnames=fields);writer.writeheader()
                for line in src:
                    row=json.loads(line)
                    if kind=='events':row['design_family']='|'.join(sorted(self.events[row['event_id']]))
                    writer.writerow(row)
            temporary.replace(out/name)
        shutil.rmtree(self.temp)
    def event(self,pool,method,groups,A,C,family,**link):
        A=sorted(A);C=sorted(C)
        assert len(A)==len(set(A)) and len(C)==len(set(C))
        if len(A)<3 or len(C)<3:
            self.write('omissions',dict(pool_id=pool['pool_id'],method=method,design_family=family,n_A=len(A),n_C=len(C),
                A_workers='|'.join(A),C_workers='|'.join(C),A_team_key=team_key(pool['pool_id'],A),C_team_key=team_key(pool['pool_id'],C),
                reason='team_n_below_3',link_metadata=enc(link)))
            return None
        if A==C:return None
        D=sorted(set(A)&set(C));X=sorted(set(A)-set(C));Z=sorted(set(C)-set(A))
        assert set(D).isdisjoint(X) and set(D).isdisjoint(Z) and set(X).isdisjoint(Z)
        lookup={w:cl for cl,ws in groups.items() for w in ws}
        ax=sorted({lookup.get(w,'unknown') for w in X});cz=sorted({lookup.get(w,'unknown') for w in Z})
        assert 'unknown' not in ax+cz, (family,pool['pool_id'])
        ak=team_key(pool['pool_id'],A);ck=team_key(pool['pool_id'],C)
        # One method row per physical pair. Pure class directions follow frozen
        # training roles; all other comparisons use a deterministic entity order.
        # Each design link retains the input orientation for exact decompositions.
        pure=len(ax)==len(cz)==1 and ax!=cz
        def role_key(c):
            value=self.roles.get((method,pool['meta']['building'],c),{}).get('primary_role_rank','')
            return (float(value) if value!='' else 999,c)
        swap=role_key(ax[0])>role_key(cz[0]) if pure else ak>ck
        input_sign=-1 if swap else 1
        if swap:A,C=C,A;X,Z=Z,X;ax,cz=cz,ax;ak,ck=ck,ak
        physical=digest([pool['pool_id'],sorted([ak,ck])])[:24]
        eid=digest([pool['pool_id'],method,physical])[:24]
        def counts(ws):return dict(sorted(Counter(lookup.get(w,'unknown') for w in ws).items()))
        if eid not in self.events:
            meta=pool['meta'];same=len(A)==len(C)
            source=ax[0] if len(ax)==1 else '|'.join(ax);target=cz[0] if len(cz)==1 else '|'.join(cz)
            source_all=groups.get(source,[]);target_all=groups.get(target,[])
            sr=self.roles.get((method,meta['building'],source),{});tr=self.roles.get((method,meta['building'],target),{})
            event=dict(event_id=eid,physical_pair_id=physical,pool_id=pool['pool_id'],method=method,
                image=meta['image'],building=meta['building'],heldout_building=meta['building'],condition=meta['condition'],
                layer=meta['layer'],scope=pool['scope'],reference_id=meta.get('reference_id',''),reference_version=meta.get('reference_version',''),
                source_class=source,target_class=target,D_workers='|'.join(D),X_workers='|'.join(X),Z_workers='|'.join(Z),
                role_axis=sr.get('primary_role_axis',tr.get('primary_role_axis','')),source_role_rank=sr.get('primary_role_rank'),target_role_rank=tr.get('primary_role_rank'),
                source_parent_class=sr.get('parent_class',''),target_parent_class=tr.get('parent_class',''),
                A_workers='|'.join(A),C_workers='|'.join(C),A_team_key=ak,C_team_key=ck,n_A=len(A),n_C=len(C),
                n=len(A) if same else None,m=len(X) if same else None,m_X=len(X),m_Z=len(Z),D_n=len(D),delta_n=len(C)-len(A),
                equal_team_size=same,pure_cross_class_blocks=len(ax)==len(cz)==1 and ax!=cz,
                source_class_available_n=len(source_all) if len(ax)==1 else None,target_class_available_n=len(target_all) if len(cz)==1 else None,
                whole_source=bool(X) and len(ax)==1 and set(X)==set(source_all),whole_target=bool(Z) and len(cz)==1 and set(Z)==set(target_all),
                A_class_counts=enc(counts(A)),C_class_counts=enc(counts(C)),D_class_counts=enc(counts(D)),
                mv50_threshold_A=math.ceil(len(A)/2),mv50_threshold_C=math.ceil(len(C)/2),
                X_can_independently_reach_MV50=len(X)>=math.ceil(len(A)/2),Z_can_independently_reach_MV50=len(Z)>=math.ceil(len(C)/2),
                source_commit=COMMIT)
            self.events[eid]=set();self.write('events',event)
            self.physical_methods[physical].add(method);self.method_counts[method]+=1;self.scope_counts[pool['scope']]+=1;self.event_pools.add(pool['pool_id'])
            if method in CORE and pool['scope']=='primary' and event['n']==20 and event['m'] in [9,10,12] and event['pure_cross_class_blocks']:
                anchor_key=(pool['pool_id'],method,source,target,event['m'])
                if anchor_key not in self.anchors or eid<self.anchors[anchor_key]['event_id']:self.anchors[anchor_key]=event
            membermap={m['worker_id']:str(m['object_id']) for m in pool['members']}
            for k,ws in [(ak,A),(ck,C)]:
                if k not in self.teams:
                    self.teams.add(k)
                    self.write('requests',dict(team_key=k,pool_id=pool['pool_id'],member_workers='|'.join(ws),n=len(ws),
                        member_object_ids='|'.join(membermap[w] for w in ws),reference_id=meta.get('reference_id',''),reference_version=meta.get('reference_version','')))
        self.events[eid].add(family)
        self.seq+=1
        self.write('links',dict(link_id=self.seq,event_id=eid,physical_pair_id=physical,design_family=family,method=method,pool_id=pool['pool_id'],input_orientation_sign=input_sign,**link));self.link_n+=1
        self.counts[family]+=1
        return eid

def main(args):
    started=time.monotonic();out=OUT/args.name;out.mkdir(exist_ok=False)
    source_paths=[CAP/'SCORE_BLIND_POOL_INPUTS.json',CAP/'POOL_METHOD_CAPACITY.csv.gz',CAP/'ALL_CLASS_ALLIANCE_TEAMS.csv.gz',CAP/'ALL_CLASS_ALLIANCE_CONTRASTS.csv.gz',CAP/'FROZEN_LABELS_USED_ALL_LOBO.csv.gz',CAP/'FROZEN_ROLE_PARENT_MAP_ALL_LOBO.csv']
    source=json.loads(source_paths[0].read_text());assert source['commit']==COMMIT
    pools={p['pool_id']:p for p in source['pools']}
    pm=pd.read_csv(source_paths[1],low_memory=False)
    role_df=pd.read_csv(CAP/'FROZEN_ROLE_PARENT_MAP_ALL_LOBO.csv').fillna('')
    roles={(r['method'],r['heldout_building'],r['class_id']):r for r in role_df.to_dict('records')}
    reg=Registry(pools,pm,roles)
    def class_order(method,building,c):
        rank=roles.get((method,building,c),{}).get('primary_role_rank','')
        return (float(rank) if rank!='' else 999,c)
    # A. Fixed block / nested background series. Class pairs are oriented once.
    for i,row in enumerate(pm.to_dict('records')):
        pool=pools[row['pool_id']];method=row['method'];N=row['pool_n'];groups=json.loads(row['class_members_json'])
        lookup={w:c for c,ws in groups.items() for w in ws};classes=sorted([c for c in groups if groups[c]],key=lambda c:class_order(method,pool['meta']['building'],c))
        for s,t in combinations(classes,2):
            S=groups[s];T=groups[t];maxm=min(len(S),len(T))
            if method=='RFUSE_GEOM_K2':ms=[m for m in [3,4] if m<=maxm]
            elif row['scope']=='other_admitted':ms=[m for m in [3,4] if m<=maxm]
            else:ms=[m for m in [7,8,9,10,12] if m<=maxm]
            # Per-pool whole-class equal replacement adds its actual legal block size.
            whole_m=min(len(S),len(T))
            for m in sorted(set(ms+[whole_m])):
                token=[pool['pool_id'],sorted([S,T])]
                draws=args.block_draws if m in ms else args.whole_draws
                blocks,totalxz=sample_xz(S,T,m,token,draws,args.enumerate_limit)
                if m in ms:
                    ns={m,math.ceil(1.5*m),2*m,2*m+2,20,N-m}
                else:
                    ns={m,math.ceil(1.5*m),2*m,20,N-m}
                ns=sorted(n for n in ns if n>=3 and m<=n<=N-m)
                background_anchor=20 if 20 in ns else (min(ns,key=lambda n:(abs(n-2*m),n)) if ns else None)
                for n in ns:
                    tags=[]
                    if m in ms:tags.append('A_equal_AC')
                    if m==whole_m:tags.append('B_equal_whole_class')
                    cellid=digest([method,pool['pool_id'],s,t,n,m])[:24]
                    cell_before=reg.link_n
                    for bi,(x,z,batch,attempt) in enumerate(blocks):
                        remain=sorted(set(pool['workers'])-set(x)-set(z))
                        paths=background_paths(remain,lookup,s,t,[pool['pool_id'],x,z])
                        seenD=set()
                        for di,(profile,path) in enumerate(paths.items()):
                            if n!=background_anchor and profile!='neutral_members_0':continue
                            if args.background_profiles==2 and profile in ['source_enriched','target_enriched']:continue
                            d=sorted(path[:n-m]);ds=tuple(d)
                            if ds in seenD:continue
                            seenD.add(ds)
                            blockid=digest([pool['pool_id'],x,z])[:24]
                            dpath=digest([pool['pool_id'],x,z,profile])[:24]
                            for family in tags:
                                reg.event(pool,method,groups,d+x,d+z,family,cell_id=cellid,n=n,m=m,block_id=blockid,
                                    background_id=digest([pool['pool_id'],d])[:24],background_profile=profile,member_rep=bi,background_rep=di,
                                    sample_batch=batch,sample_attempt=attempt,possible_XZ_blocks=str(totalxz),sampled_XZ_blocks=len(blocks),
                                    XZ_enumerated=totalxz<=args.enumerate_limit,possible_D_per_XZ=str(math.comb(N-2*m,n-m)),
                                    nested_background_path_id=dpath,at_pool_frontier=n==N-m,zero_background=n==m)
                    reg.cells.append(dict(pool_id=pool['pool_id'],method=method,source_class=s,target_class=t,n=n,m=m,
                        design_families='|'.join(tags),cell_id=cellid,possible_XZ_blocks=str(totalxz),registered_XZ_blocks=len(blocks),
                        possible_D_per_XZ=str(math.comb(N-2*m,n-m)),registration_links=reg.link_n-cell_before,at_pool_frontier=n==N-m,
                        intensive_background_anchor=n==background_anchor))
                # B. Entire unequal classes under the identical outside-class D.
                # Equal-size middle team permits an exact telescoping scalar contrast.
                if m==whole_m and len(S)!=len(T):
                    small,large=(S,T) if len(S)<len(T) else (T,S)
                    sc,tc=(s,t) if len(S)<len(T) else (t,s)
                    other=sorted(set(pool['workers'])-set(S)-set(T));R=len(other)
                    dlevels=sorted({0,R//2,R})
                    paths=background_paths(other,lookup,sc,tc,[pool['pool_id'],small,large,'whole_unequal'])
                    smallblocks,total=sample_xz(small,large,len(small),[pool['pool_id'],sorted([small,large])],args.whole_draws,args.enumerate_limit)
                    seen=set()
                    for dn in dlevels:
                        for rep,profile in enumerate(['neutral_members_0','neutral_members_1']):
                            d=sorted(paths[profile][:dn]);sig=tuple(d)
                            if sig in seen:continue
                            seen.add(sig)
                            if min(len(d)+len(small),len(d)+len(large))<3:continue
                            parent=digest([pool['pool_id'],method,d,small,large,'unequal'])[:24]
                            reg.event(pool,method,groups,d+small,d+large,'B_unequal_whole_classes',parent_contrast_id=parent,
                                background_id=digest([pool['pool_id'],d])[:24],background_profile='outside_swapped_classes_'+profile,
                                background_rep=rep,background_n=dn,all_other_classes_in_D=dn==R)
                            for bi,(x,z,batch,attempt) in enumerate(smallblocks):
                                mid=d+z
                                reg.event(pool,method,groups,d+small,mid,'B_unequal_equal_size_anchor',parent_contrast_id=parent,
                                    decomposition_leg='equal_size_class_replacement',member_rep=bi,sample_batch=batch,
                                    background_id=digest([pool['pool_id'],d])[:24],background_profile='outside_swapped_classes_'+profile)
                                reg.event(pool,method,groups,mid,d+large,'B_unequal_additional_same_target_members',parent_contrast_id=parent,
                                    decomposition_leg='add_remaining_target_class_members',member_rep=bi,sample_batch=batch,
                                    background_id=digest([pool['pool_id'],d])[:24],background_profile='outside_swapped_classes_'+profile)
        if i%200==0:print(json.dumps({'phase':'A_B','pool_method_rows':i,'method_events':len(reg.events),'unique_teams':len(reg.teams)},ensure_ascii=False),flush=True)
    # C. Complete, finite class-alliance census, including a separate unknown-D view.
    alliances=pd.read_csv(CAP/'ALL_CLASS_ALLIANCE_TEAMS.csv.gz').fillna('')
    alliance_lookup={(r['method'],r['pool_id'],r['member_identity_key']):unpipe(r['members']) for r in alliances.to_dict('records')}
    method_lookup={(r['method'],r['pool_id']):json.loads(r['class_members_json']) for r in pm.to_dict('records')}
    edges=pd.read_csv(CAP/'ALL_CLASS_ALLIANCE_CONTRASTS.csv.gz').fillna('')
    for e in edges.to_dict('records'):
        groups=method_lookup[e['method'],e['pool_id']];pool=pools[e['pool_id']]
        A=alliance_lookup[e['method'],e['pool_id'],e['A_identity_key']];C=alliance_lookup[e['method'],e['pool_id'],e['C_identity_key']]
        reg.event(pool,e['method'],groups,A,C,'C_complete_class_alliances',A_alliance=e['A_alliance'],C_alliance=e['C_alliance'],
            unknown_background_included=e['unknown_background_included'],coalition_comparison_type=e['comparison_type'],complete_coalition_census=True)
    # D. Fixed original A, nested m increase. An explicitly different family.
    for row in pm.to_dict('records'):
        method=row['method'];pool=pools[row['pool_id']];groups=json.loads(row['class_members_json']);N=row['pool_n']
        classes=sorted([c for c in groups if groups[c]],key=lambda c:class_order(method,pool['meta']['building'],c));lookup={w:c for c,ws in groups.items() for w in ws}
        for s,t in combinations(classes,2):
            S=groups[s];T=groups[t]
            maxm=min(len(S),len(T))
            key_m=[1,2,3,4,5,6] if row['scope']=='other_admitted' else ([3,4] if method=='RFUSE_GEOM_K2' else [7,8,9,10,12])
            ms=sorted({m for m in key_m+[maxm] if 1<=m<=maxm})
            if len(ms)<2:continue
            for n in sorted({20,N-maxm}):
                if n<max(3,maxm) or n>N-maxm:continue
                pairs,total=sample_xz(S,T,maxm,[pool['pool_id'],sorted([S,T]),'fixed_A',n],args.path_reps,0)
                for rep,(xmax,zmax,batch,attempt) in enumerate(pairs):
                    rest=sorted(set(pool['workers'])-set(xmax)-set(zmax))
                    paths=background_paths(rest,lookup,s,t,[pool['pool_id'],xmax,zmax,'fixed_A',n])
                    xx=xmax.copy();zz=zmax.copy();rng('nested_X_order',pool['pool_id'],n,rep,xx).shuffle(xx);rng('nested_Z_order',pool['pool_id'],n,rep,zz).shuffle(zz)
                    seen_d=set()
                    for di,dp in enumerate(['neutral_members_0','neutral_members_1']):
                        d=sorted(paths[dp][:n-maxm]);A=sorted(d+xmax)
                        if tuple(d) in seen_d:continue
                        seen_d.add(tuple(d));pathid=digest([pool['pool_id'],method,A,xx,zz])[:24]
                        for m in ms:
                            C=sorted(set(A)-set(xx[:m])|set(zz[:m]))
                            reg.event(pool,method,groups,A,C,'D_fixed_A_expand_replacement',anchor_A_path_id=pathid,n=n,m=m,
                                member_rep=rep,background_rep=di,sample_batch=batch,max_m_on_path=maxm,source_prefix_order='|'.join(xx),target_prefix_order='|'.join(zz))
    # E. Exact fixed D, class-count-preserving member sensitivity at the main n20 anchor.
    anchors=reg.anchors.copy()
    for k,e in sorted(anchors.items()):
        pool=pools[e['pool_id']];groups=method_lookup[e['method'],e['pool_id']];d=unpipe(e['D_workers']);m=e['m']
        S=sorted(set(groups[e['source_class']])-set(d));T=sorted(set(groups[e['target_class']])-set(d))
        blocks,total=sample_xz(S,T,m,[pool['pool_id'],S,T,'fixed_D',d],args.deep_member_draws,args.enumerate_limit)
        for bi,(x,z,batch,attempt) in enumerate(blocks):
            reg.event(pool,e['method'],groups,d+x,d+z,'E_fixed_D_member_sensitivity',fixed_D_panel_id=digest([k,d])[:24],
                n=20,m=m,member_rep=bi,sample_batch=batch,possible_XZ_given_D=str(total),exact_fixed_D=True)
    # Final files and precise coverage are frozen before any endpoint output is read.
    reg.finish(out)
    csv(reg.cells,out/'REGISTERED_AC_CELLS.csv.gz')
    overlap=reg.physical_methods
    csv([dict(physical_pair_id=k,methods='|'.join(sorted(v)),method_count=len(v)) for k,v in overlap.items()],out/'PHYSICAL_PAIR_METHOD_OVERLAP.csv.gz')
    receipt=dict(source_commit=COMMIT,seed=SEED,design_status='registered_before_outcomes_not_executed',methods=METHODS,
        method_events=len(reg.events),physical_pairs=len(overlap),unique_teams=len(reg.teams),design_links=reg.link_n,registered_A_B_cells=len(reg.cells),
        pools=len(reg.event_pools),by_scope=dict(reg.scope_counts),
        by_method=dict(reg.method_counts),family_links=dict(reg.counts),
        block_draws=args.block_draws,whole_draws=args.whole_draws,enumeration_limit=args.enumerate_limit,
        background_profiles=args.background_profiles,deep_member_draws=args.deep_member_draws,path_reps=args.path_reps,
        intensive_background_policy='four profiles only at n20 if legal, otherwise nearest legal anchor to 2m; neutral_members_0 path retained at every n',
        registry_memory_policy='stream payloads to compressed temporary JSONL, retain only identity sets, family tags, and small fixed-D anchors; atomic final gzip CSV writes',
        independent_random_batches=2,identities_and_disjointness_checked=True,no_B_or_strict_ABC_registered=True,
        all_requests_use_legacy_native_team_key=True,target_image_quality_time_and_geometry_read=False,
        reverse_orientations_not_independent_replicates=True,all_coalitions_enumerated=True,
        small_team_policy='n<3 held out of new execution and listed separately',
        outcome_blind_inputs=[dict(path=str(p.relative_to(BASE)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in source_paths],
        elapsed_seconds=time.monotonic()-started)
    save(receipt,out/'DESIGN_REGISTRATION_RECEIPT.json')
    save({'requested_outputs':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in out.iterdir() if p.is_file()}},out/'FROZEN_DESIGN_FILES.json')
    print(json.dumps(receipt,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--name',default='registered_v2');ap.add_argument('--block-draws',type=int,default=8)
    ap.add_argument('--whole-draws',type=int,default=4);ap.add_argument('--enumerate-limit',type=int,default=16)
    ap.add_argument('--background-profiles',type=int,choices=[2,4],default=4);ap.add_argument('--path-reps',type=int,default=4)
    ap.add_argument('--deep-member-draws',type=int,default=8);main(ap.parse_args())
