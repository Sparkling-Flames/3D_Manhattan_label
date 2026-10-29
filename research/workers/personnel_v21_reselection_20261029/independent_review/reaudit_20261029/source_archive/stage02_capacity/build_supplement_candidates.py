"""Input-only exact m7/m8 opportunities and prior execution coverage.

No saved target Q is read in selecting the opportunity list.
"""
from pathlib import Path
import collections, itertools, json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT / 'repo'
BASE = REPO / 'research/workers/personnel_v21_reselection_20261029'
OUT = ROOT / 'audit_capacity/results'
NEW = ROOT / 'audit_classification/results'

def main():
    pools = [p for f in ['pools/INPUT_SNAPSHOT.json','admitted_space_extension/pools/INPUT_SNAPSHOT.json']
             for p in json.loads((REPO/'research/data/releases/v2.1'/f).read_text())['images']
             if p['meta']['layer']=='ordinary_manual']
    old = pd.read_csv(BASE/'classification/MAIN45_LABELS_ALL_LOBO.csv.gz',low_memory=False)
    new = pd.read_csv(NEW/'NEW_LABELS_ALL_LOBO.csv.gz')
    labels = pd.concat([old,new],ignore_index=True)
    labels = labels[(labels.heldout_building!='ALL') & labels.known.eq(True)]
    oldroles = pd.read_csv(BASE/'classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz')
    newroles = pd.read_csv(NEW/'CLASS_CENTERS_ALL_LOBO.csv.gz')
    for dest, src in [('challenge_turn_rank_asc','m_challenge_turn_n'),('hard_turn_rank_asc','m_hard_turn_n'),('q_rank_asc','m_all_B8L2')]:
        newroles[dest] = newroles.groupby(['method','heldout_building'])[src].rank(method='dense')
    cols=['method','heldout_building','class_id','k','workers','challenge_turn_rank_asc','hard_turn_rank_asc','q_rank_asc','m_all_turn_n','m_hard_turn_n','m_challenge_turn_n','m_all_B8L2']
    roles=pd.concat([oldroles[cols],newroles[cols]],ignore_index=True).set_index(['method','heldout_building','class_id'])
    design_paths=[BASE/'additional_delivery/packages/05A/experiment/global_screen_design/EVENTS_EXACT.csv.gz']+sorted((BASE/'experiment').glob('*_design/EVENTS_EXACT.csv.gz'))
    use={'method','pool_id','source_class','target_class','n','m','B_team_key','event_id'}
    events=pd.concat([pd.read_csv(p,usecols=lambda c:c in use).assign(stage=p.parent.name) for p in design_paths],ignore_index=True)
    events=events[events.B_team_key.notna()]
    existing=events.groupby(['method','pool_id','source_class','target_class','n','m'],dropna=False).agg(prior_events=('event_id','nunique'),prior_stages=('stage',lambda x:'|'.join(sorted(set(x))))).to_dict('index')
    candidates=[]
    chosen=['DSTRUCT_K3','TARGET_DSTRUCT_K2','TARGET_DSTRUCT_K3','TARGET_DSTRUCT_K4','OPPSTRUCT_K3','OPPJOINT_K3','OPPJOINT_K4','RFUSE_GEOM_K3',
            'V21_DSTRUCT_RAW3_K2','V21_DSTRUCT_RAW3_K3','V21_DSTRUCT_RAW3_K4','V21_DSTRUCT_FULL_K3','V21_DSTRUCT_COND_K3']
    for (method,b),g in labels[labels.method.isin(chosen)].groupby(['method','heldout_building']):
        lm=g.set_index('worker_id').class_id.to_dict()
        for p in pools:
            meta=p['meta']
            if meta['building']!=b:continue
            groups=collections.defaultdict(list)
            for r in p['records']:groups[lm.get(r['worker_id'],'unknown')].append(r['worker_id'])
            N=len(p['records'])
            for sc,tc in itertools.permutations(sorted(c for c in groups if c!='unknown'),2):
                S,T=len(groups[sc]),len(groups[tc])
                sr,tr=roles.loc[(method,b,sc)],roles.loc[(method,b,tc)]
                for n,m in [(10,7),(12,7),(14,7),(18,7),(20,7),(12,8),(14,8),(16,8),(18,8)]:
                    if not (N>=n+2*m and S>=2*m and T>=m):continue
                    e=existing.get((method,p['pool_id'],sc,tc,n,m),{})
                    candidates.append(dict(method=method,pool_id=p['pool_id'],image=meta['image'],building=b,
                        condition='manual',layer='ordinary_manual',scope='other' if meta.get('analysis_scope')=='other_admitted_target' else 'primary',
                        n=n,m=m,pool_n=N,source_class=sc,target_class=tc,source_capacity=S,target_capacity=T,
                        source_challenge_rank=int(sr.challenge_turn_rank_asc),target_challenge_rank=int(tr.challenge_turn_rank_asc),
                        source_hard_rank=int(sr.hard_turn_rank_asc),target_hard_rank=int(tr.hard_turn_rank_asc),
                        source_Q_rank=int(sr.q_rank_asc),target_Q_rank=int(tr.q_rank_asc),
                        source_historical_challenge_turn=float(sr.m_challenge_turn_n),target_historical_challenge_turn=float(tr.m_challenge_turn_n),
                        source_historical_Q=float(sr.m_all_B8L2),target_historical_Q=float(tr.m_all_B8L2),
                        source_members='|'.join(sorted(groups[sc])),target_members='|'.join(sorted(groups[tc])),
                        unknown_background_members='|'.join(sorted(groups.get('unknown',[]))),
                        prior_events=e.get('prior_events',0),prior_stages=e.get('prior_stages','')))
    df=pd.DataFrame(candidates)
    df.to_csv(OUT/'M7_M8_EXACT_SUPPLEMENT_CANDIDATES.csv',index=False,encoding='utf-8-sig')
    df[df.prior_events.eq(0)].to_csv(OUT/'M7_M8_CAPACITY_PRESENT_NOT_REGISTERED.csv',index=False,encoding='utf-8-sig')
    summary=df.groupby(['method','n','m','source_challenge_rank','target_challenge_rank']).agg(
        feasible_pools=('pool_id','nunique'),feasible_images=('image','nunique'),feasible_buildings=('building','nunique'),
        previously_registered_pools=('prior_events',lambda x:int(x.gt(0).sum())),not_registered_pools=('prior_events',lambda x:int(x.eq(0).sum())))
    summary.to_csv(OUT/'M7_M8_DIRECTION_CAPACITY_AND_DESIGN_GAPS.csv',encoding='utf-8-sig')
    common=[]
    for n,m in [(14,7),(16,8),(12,8),(20,7)]:
        for a,b in itertools.combinations(chosen,2):
            aa=df[(df.method==a)&df.n.eq(n)&df.m.eq(m)]
            bb=df[(df.method==b)&df.n.eq(n)&df.m.eq(m)]
            both=aa[aa.pool_id.isin(bb.pool_id)]
            common.append(dict(method_A=a,method_B=b,n=n,m=m,common_capacity_pools=both.pool_id.nunique(),common_capacity_images=both.image.nunique(),common_capacity_buildings=both.building.nunique()))
    pd.DataFrame(common).to_csv(OUT/'PAIRWISE_COMMON_M7_M8_CAPACITY.csv',index=False,encoding='utf-8-sig')
    receipt=dict(label_sources=['classification/MAIN45_LABELS_ALL_LOBO.csv.gz',str(NEW/'NEW_LABELS_ALL_LOBO.csv.gz')],
                 candidate_rows=len(df),not_registered_rows=int(df.prior_events.eq(0).sum()),
                 target_fusion_outcomes_used_for_selection=False,
                 role_basis='Fold historical challenge-turn rank; Q history included for later interpretation, not capacity selection.',
                 scope='Ordinary Manual, pure same-source X/Y and pure distinct target Z, D/X/Y/Z disjoint.')
    (OUT/'SUPPLEMENT_OPPORTUNITY_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(summary.to_string())

if __name__=='__main__':main()
