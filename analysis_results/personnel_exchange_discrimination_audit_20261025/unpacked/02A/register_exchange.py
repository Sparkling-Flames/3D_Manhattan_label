"""Finite target-outcome-free strict ABC search; real member/background ledger."""
import argparse, collections, hashlib, itertools, json, math
import numpy as np
import pandas as pd
from run_native import ROOT,REPO,POP,read,save,csv,team_key
SEED=2026102507
GRID=[(10,7),(12,8),(12,10),(14,9),(16,8),(17,9),(18,7),(20,6),(24,5)]
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def random(v):return np.random.default_rng(int(digest([SEED,v])[:16],16))

def collect_labels():
    frames=[]
    for name in ['NEW_METHOD_LABELS_ALL_LOBO.csv.gz','AXIS_METHOD_LABELS_ALL_LOBO.csv.gz','SCOPE_INCREMENT_LABELS_ALL_LOBO.csv.gz']:
        d=pd.read_csv(ROOT/'classifications'/name);d['candidate_origin']='new_20261025';d['tier']='specified';d['label_source']=name;frames.append(d)
    reverse=ROOT/'reverse/REVERSE_LABELS_ALL_LOBO.csv.gz'
    if reverse.exists():
        d=pd.read_csv(reverse);d['candidate_origin']='new_reverse_fusion_20261025';d['tier']='specified';d['label_source']='reverse/REVERSE_LABELS_ALL_LOBO.csv.gz';frames.append(d)
    old=pd.read_csv(POP/'inputs/ALL_METHOD_LABELS_LOBO.csv.gz')
    for meth in ['V3_BEHAVIOR','V3_JOINT_QT']:
        for tier in ['coarse','fine']:
            d=old[(old.condition=='manual')&(old.method==meth)].copy();d['class_id']=d[tier+'_label'];d['method']=meth+'_'+tier
            d['tier']=tier;d['candidate_origin']='reused_20261021';d['label_source']='population_inputs/ALL_METHOD_LABELS_LOBO.csv.gz';frames.append(d)
    cross=pd.read_csv(REPO/'research/workers/personnel_effective_exchange_conditions_20261022/cross_condition_taxonomy/CROSS_LABELS_LOBO.csv')
    for meth in ['XCOND_GEOM','XCOND_GEOM_QT','XCOND_PAIRED']:
        d=cross[(cross.condition=='manual')&(cross.method==meth)].copy();d['class_id']=d.coarse_label;d['method']=meth+'_coarse';d['tier']='coarse';d['candidate_origin']='reused_20261022';d['label_source']='cross_condition_taxonomy/CROSS_LABELS_LOBO.csv';frames.append(d)
    fields=['worker_id','heldout_building','method','class_id','known','condition','tier','candidate_origin','label_source']
    labels=pd.concat(frames,ignore_index=True)[fields].drop_duplicates()
    assert not labels.duplicated(['worker_id','heldout_building','method','condition']).any()
    return labels

def partition(pools):
    ps=[p for p in pools if p['meta']['layer']=='ordinary_manual'];bs=sorted({p['meta']['building'] for p in ps},key=lambda b:digest(['split',b]))
    discovery=set(bs[:12]);selected=set()
    for b in discovery:
        for difficulty in ['简单','中等','困难']:
            own=[p for p in ps if p['meta']['building']==b and p['meta']['difficulty']==difficulty]
            own.sort(key=lambda p:digest(['screen_image',p['pool_id']]))
            selected.update(p['pool_id'] for p in own[:2])
    rows=[]
    for p in pools:
        ordinary=p['meta']['layer']=='ordinary_manual';b=p['meta']['building']
        phase='screen' if p['pool_id'] in selected else 'within_building_extension' if ordinary and b in discovery else 'selection_heldout_building' if ordinary else 'not_primary'
        rows.append(dict(p['meta'],phase=phase,selection_building_group='discovery' if b in discovery else 'heldout',split_seed=SEED))
    return pd.DataFrame(rows)

def vector_count(cap,n):
    poly=[1]
    for sz in cap.values():
        new=[0]*(len(poly)+sz)
        for i,v in enumerate(poly):
            for j in range(sz+1):new[i+j]+=v
        poly=new
    return poly[n]

def generate(a):
    pools=read(POP/'inputs/INPUT_SNAPSHOT.json.gz')['images'];by={p['pool_id']:p for p in pools};part=partition(pools);labels=collect_labels();out=ROOT/'design'/a.stage;out.mkdir(parents=True,exist_ok=True)
    csv(out/'FROZEN_LABELS.csv.gz',labels);csv(out/'IMAGE_PHASE_ASSIGNMENT.csv',part)
    if a.stage.endswith('screen'):eligible=set(part.loc[part.phase=='screen','pool_id'])
    elif a.stage.endswith('confirm'):eligible=set(part.loc[part.phase.isin(['selection_heldout_building','within_building_extension']),'pool_id'])
    else:eligible=set(part.loc[part.layer=='ordinary_manual','pool_id'])
    plan=read(a.plan) if a.plan else None
    chosen=set(plan) if plan else None if not a.methods else set(a.methods.split(','));grid=GRID if not a.grid else [tuple(map(int,x.split(':'))) for x in a.grid.split(',')]
    history=pd.read_csv(ROOT/'features/HISTORY_FEATURES_ALL_LOBO.csv.gz');hs={b:g.set_index('worker_id') for b,g in history.groupby('heldout_building')}
    events=[];requests={};capacity=[];centers=[]
    for (method,b),gg in labels[(labels.heldout_building!='ALL') & labels.known & (labels.condition=='manual')].groupby(['method','heldout_building'],sort=True):
        if chosen and method not in chosen:continue
        lm=dict(zip(gg.worker_id,gg.class_id));hf=hs[b];cent={}
        for cl,cg in gg.groupby('class_id'):
            xx=hf.reindex(cg.worker_id);vals={x:float(xx[x].mean()) for x in ['m_all_B8L2','m_hard_B8L2','m_all_log_time','m_hard_turn_n','m_hard_matched_bottom_bias_deg','m_hard_matched_top_bias_deg']}
            cent[cl]=vals;centers.append(dict(method=method,heldout_building=b,class_id=cl,members='|'.join(cg.worker_id),**vals))
        for pid in sorted(eligible):
            p=by[pid];meta=p['meta']
            if meta['building']!=b:continue
            ws=sorted(r['worker_id'] for r in p['records']);N=len(ws);groups=collections.defaultdict(list)
            for w in ws:groups[lm.get(w,'unknown')].append(w)
            for source,target in itertools.permutations(sorted(set(groups)-{'unknown'}),2):
                S,T=len(groups[source]),len(groups[target])
                for n,m in (plan[method] if plan else grid):
                    d=n-m;possible=S>=2*m and T>=m and N>=n+2*m
                    row=dict(pool_id=pid,method=method,source_class=source,target_class=target,n=n,m=m,pool_n=N,source_capacity=S,target_capacity=T,feasible=possible,building=b,image=meta['image'],difficulty=meta['difficulty'],phase=str(part.loc[part.pool_id==pid,'phase'].iloc[0]))
                    if not possible:capacity.append(row);continue
                    remainder=N-3*m;lo=max(0,d-(remainder-(T-m)));hi=min(d,T-m)
                    levels=sorted(set([lo,(lo+hi)//2,hi]));nxyz=math.comb(S,m)*math.comb(S-m,m)*math.comb(T,m)//2
                    cap={c:len(v)-(2*m if c==source else m if c==target else 0) for c,v in groups.items()}
                    row.update(background_target_min=lo,background_target_max=hi,feasible_background_class_vectors=vector_count(cap,d),feasible_xyz_unordered=str(nxyz),feasible_member_events=str(nxyz*math.comb(remainder,d)),planned_xyz_blocks=a.blocks,planned_target_background_levels='|'.join(map(str,levels)))
                    before=len(events);seenblocks=set()
                    # EVENT_GENERATION
                    build_events(a,pid,method,source,target,n,m,groups,ws,lm,cent,row,gg,levels,events,requests,seenblocks)
                    row['events_generated']=len(events)-before;row['distinct_xyz_blocks']=len(seenblocks);capacity.append(row)
    ev=pd.DataFrame(events).drop_duplicates('event_id');capframe=pd.DataFrame(capacity)
    counts=ev.groupby(['pool_id','method','source_class','target_class','n','m']).size().rename('distinct_registered_events').reset_index()
    capframe=capframe.merge(counts,how='left',on=['pool_id','method','source_class','target_class','n','m']);capframe['distinct_registered_events']=capframe.distinct_registered_events.fillna(0).astype(int)
    csv(out/'EVENTS_EXACT.csv.gz',ev);csv(out/'CAPACITY_AND_ATTEMPTS.csv.gz',capframe);csv(out/'FOLD_ROLE_CENTERS.csv.gz',pd.DataFrame(centers));save(out/'REQUESTS.json.gz',list(requests.values()))
    status=dict(stage=a.stage,seed=SEED,grid=grid,method_count=labels.method.nunique() if not chosen else len(chosen),available_pool_count=len(eligible),attempted_configurations=len(capacity),feasible_configurations=sum(r['feasible'] for r in capacity),events=len(ev),unique_endpoints=len(requests),images=ev.pool_id.nunique(),buildings=ev.building.nunique(),blocks_per_cell=a.blocks,backgrounds_per_level=a.backgrounds,sampling='All prespecified method/direction/n/m cells in fixed image frame; low/middle/high target-class D counts; seeded disjoint XYZ and background sampling. Full member space counts recorded, not claimed exhaustive.',score_selection_status='No target fusion outcomes read in registration',underlying_data='v2')
    if plan:status['method_specific_grid']=plan
    save(out/'DESIGN.json',status);print(json.dumps(status,ensure_ascii=False),flush=True)

def build_events(a,pid,method,source,target,n,m,groups,ws,lm,cent,row,gg,levels,events,requests,seenblocks):
    for rep in range(a.blocks):
        rng=random([a.stage,pid,method,source,target,n,m,rep])
        sx=rng.choice(groups[source],2*m,replace=False).tolist();x=sorted(sx[:m]);y=sorted(sx[m:]);z=sorted(rng.choice(groups[target],m,replace=False).tolist())
        canonical_xy=sorted([tuple(x),tuple(y)]);block_sig=(canonical_xy[0],canonical_xy[1],tuple(z))
        if block_sig in seenblocks:continue
        seenblocks.add(block_sig);remaining=sorted(set(ws)-set(x+y+z));rt=[w for w in remaining if lm.get(w)==target];ro=[w for w in remaining if lm.get(w)!=target]
        for target_n in levels:
            for bg_rep in range(a.backgrounds):
                bg=sorted(rng.choice(rt,target_n,replace=False).tolist()+rng.choice(ro,n-m-target_n,replace=False).tolist())
                teams={arm:sorted(bg+block) for arm,block in [('A',x),('B',y),('C',z)]}
                assert len(set(bg+x+y+z))==n+2*m
                eid=digest([pid,method,source,target,n,m,bg,x,y,z])[:24]
                source_history=cent[source];target_history=cent[target]
                e=dict(row,event_id=eid,design='strict_disjoint_ABC',stage=a.stage,block_replicate=rep,background_replicate=bg_rep,background_target_n=target_n,background_source_n=sum(lm.get(w)==source for w in bg),background_unknown_n=sum(w not in lm for w in bg),background_id=digest([pid,bg])[:20],block_id=digest([pid,x,y,z])[:20],
                    D='|'.join(bg),X='|'.join(x),Y='|'.join(y),Z='|'.join(z),replacement_fraction=m/n,source_block_fraction=m/len(groups[source]),actual_m_AB=m,actual_m_AC=m,actual_m_BC=m,seat_net_change_l1=2*m,
                    candidate_origin=gg.candidate_origin.iloc[0],tier=gg.tier.iloc[0])
                for field in source_history:e['history_target_minus_source_'+field]=target_history[field]-source_history[field]
                e['historical_turn_direction']='more_turns' if e['history_target_minus_source_m_hard_turn_n']>0 else 'fewer_turns';e['historical_q_direction']='higher_Q' if e['history_target_minus_source_m_all_B8L2']>0 else 'lower_Q'
                for arm,members in teams.items():
                    key=team_key(pid,members);e[arm+'_team_key']=key;e[arm+'_members']='|'.join(members);e[arm+'_class_vector']='|'.join(f'{c}:{sum(lm.get(w,"unknown")==c for w in members)}' for c in sorted(groups));requests[key]=dict(pool_id=pid,worker_ids=members,team_key=key)
                assert e['A_class_vector']==e['B_class_vector']
                events.append(e)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',default='screen');p.add_argument('--methods');p.add_argument('--grid');p.add_argument('--plan');p.add_argument('--blocks',type=int,default=2);p.add_argument('--backgrounds',type=int,default=1);generate(p.parse_args())
