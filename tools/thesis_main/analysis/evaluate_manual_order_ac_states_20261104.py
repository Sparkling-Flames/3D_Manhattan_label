"""Exact AC output-state count patch, with physical/team denominators kept separate."""
from pathlib import Path
from types import SimpleNamespace
import sys
import pandas as pd
from .evaluate_manual_order_ac_20261104 import AC,OUT,save,jsave,compare,align,read_json
from .evaluate_manual_order_ac_sensitivity_20261104 import subset

SOURCE=AC/'stage05_funnel_bridge'


def state_tuple(r,arm,m):
    return (m.status(r[arm+'_output_state']),m.status(r[arm+'_score_status']),*[m.truth(r[arm+'_'+f]) for f in m.FLAGS])


def physical_key(meta,a,c,m):
    return (meta['condition'],meta['layer'],meta['scope'],a[0],c[0],a[1],c[1],*a[2:],*c[2:],m.pattern(a,c))


def sets_for(frame,m):
    sets={};examples={};seen=set()
    for r in frame.to_dict('records'):
        pid=r['physical_pair_id']
        if pid in seen:continue
        seen.add(pid);a,c=state_tuple(r,'A',m),state_tuple(r,'C',m)
        lo,hi=sorted([r['A_team_key'],r['C_team_key']])
        if lo!=r['A_team_key']:a,c=c,a
        k=physical_key(r,a,c,m)
        sets.setdefault(k,set()).add(r['building'])
        examples.setdefault(k,(pid,lo,hi))
    return sets,examples


def main():
    sys.path.insert(0,str(SOURCE/'code'));import analyze_status_transitions as m
    out=OUT/'states';out.mkdir(exist_ok=True)
    pids=sorted(p.name[:-7] for p in (OUT/'metric_shards').glob('*.csv.gz'))
    original,assisted=[],[]
    for pid in pids:
        original.append(pd.read_csv(AC/'stage04_metrics/metric_shards'/(pid+'.csv.gz'),low_memory=False))
        assisted.append(pd.read_csv(OUT/'metric_shards'/(pid+'.csv.gz'),low_memory=False))
    a,b=pd.concat(original,ignore_index=True),pd.concat(assisted,ignore_index=True)
    for label,folder,frame in [('automatic',AC/'stage04_metrics',a),('assisted',OUT,b)]:
        base=out/(label+'_inputs');dest=out/label
        save(frame[['event_id','pool_id']],base/'stage01_registered/AC_EVENTS.csv.gz')
        link=base/'stage01_registered/DESIGN_LINKS.csv.gz'
        if not link.exists():link.symlink_to(AC/'stage01_registered/DESIGN_LINKS.csv.gz')
        target=base/'stage04_metrics/metric_shards';target.mkdir(parents=True,exist_ok=True)
        for pid in pids:
            p=target/(pid+'.csv.gz')
            if not p.exists():p.symlink_to(folder/'metric_shards'/(pid+'.csv.gz'))
        m.BASE=base;m.OUT=dest
        if not (dest/'OUTPUT_STATE_TRANSITION_RECEIPT.json').exists():m.main(SimpleNamespace(output_subdir=None,partial=False))
    parity=[];counts={}
    for fn,ncol in [('OUTPUT_STATE_TRANSITIONS_BY_POOL_METHOD_NM.csv.gz','method_events'),
                    ('OUTPUT_STATE_TRANSITIONS_BY_DESIGN_FAMILY_INPUT_DIRECTION.csv.gz','distinct_method_event_orientation_occurrences')]:
        old=pd.read_csv(SOURCE/fn,low_memory=False)
        oldlocal=pd.read_csv(out/'automatic'/fn,low_memory=False);newlocal=pd.read_csv(out/'assisted'/fn,low_memory=False)
        keys=[c for c in oldlocal if c not in [ncol,'example_event_id','orientation','A_output_state_label_zh','C_output_state_label_zh',
            'both_Q_missing_despite_zero_Q_missing_risk_change','both_observed_fusion_failures','image','building','scope','condition','layer']]
        parity.extend(compare(old[old.pool_id.isin(pids)],oldlocal,keys,'original_state_count:'+fn))
        patched=pd.concat([old[~old.pool_id.isin(pids)],newlocal],ignore_index=True)
        assert patched[ncol].sum()==old[ncol].sum();save(patched,out/fn);counts[fn]=len(patched)
    # Team and physical-pair domains have disjoint pool identities. Exact count
    # and pool-support updates follow by subtracting old nine-pool cells and
    # adding their assisted versions; building support needs set witnesses.
    gfile='GLOBAL_DEDUPLICATED_PHYSICAL_PAIR_OUTPUT_STATES.csv'
    old=pd.read_csv(SOURCE/gfile);l0=pd.read_csv(out/'automatic'/gfile);l1=pd.read_csv(out/'assisted'/gfile)
    keys=['condition','layer','scope','low_key_output_state','high_key_output_state','low_key_score_status','high_key_score_status',
          *['low_key_'+f for f in m.FLAGS],*['high_key_'+f for f in m.FLAGS],'missing_Q_transition_pattern_in_key_order']
    def lookup(d):return {tuple(r[k] for k in keys):r for r in d.to_dict('records')}
    base,local0,local1=lookup(old),lookup(l0),lookup(l1)
    s0,e0=sets_for(a,m);s1,e1=sets_for(b,m)
    candidate_rows=pd.read_csv(SOURCE/'OUTPUT_STATE_TRANSITIONS_BY_POOL_METHOD_NM.csv.gz',low_memory=False)
    candidate_rows=candidate_rows[~candidate_rows.pool_id.isin(pids)]
    # Every published cell carries an actual example event; its frozen team
    # keys determine lexicographic orientation without any geometry operation.
    example_ids=set(candidate_rows.example_event_id)
    examples={}
    for chunk in pd.read_csv(AC/'stage01_registered/AC_EVENTS.csv.gz',usecols=['event_id','physical_pair_id','A_team_key','C_team_key'],chunksize=50000,low_memory=False):
        examples.update({r['event_id']:r for r in chunk[chunk.event_id.isin(example_ids)].to_dict('records')})
    witnesses={};possible={}
    for r in candidate_rows.to_dict('records'):
        aa,cc=state_tuple(r,'A',m),state_tuple(r,'C',m)
        for x,y in [(aa,cc),(cc,aa)]:possible.setdefault((physical_key(r,x,y,m),r['building']),set()).add(r['pool_id'])
        er=examples.get(r['example_event_id'])
        if er is None:continue
        lo,hi=sorted([er['A_team_key'],er['C_team_key']])
        if lo!=er['A_team_key']:aa,cc=cc,aa
        k=physical_key(r,aa,cc,m)
        witnesses[k,r['building']]=(er['physical_pair_id'],lo,hi)
    rows=[];ambiguous=[]
    affected_physical=set(pd.read_csv(OUT/'AFFECTED_EVENT_METRICS_AUTOMATIC.csv.gz',usecols=['physical_pair_id']).physical_pair_id)
    for k in set(base)|set(local1):
        r=dict(base.get(k,local1.get(k)))
        r['unique_physical_pairs']=base.get(k,{}).get('unique_physical_pairs',0)-local0.get(k,{}).get('unique_physical_pairs',0)+local1.get(k,{}).get('unique_physical_pairs',0)
        if r['unique_physical_pairs']==0:continue
        r['target_pools']=base.get(k,{}).get('target_pools',0)-local0.get(k,{}).get('target_pools',0)+local1.get(k,{}).get('target_pools',0)
        building_n=base.get(k,{}).get('buildings',0)
        for building in s0.get(k,set())^s1.get(k,set()):
            other_present=(k,building) in witnesses
            other_possible=(k,building) in possible
            if not other_present and other_possible:
                ambiguous.append(dict(state_key=list(k),building=building,candidate_pools=sorted(possible[k,building])))
                continue
            if not other_present:building_n += 1 if building in s1.get(k,set()) else -1
        r['buildings']=building_n
        if k in e1:example=e1[k]
        elif r.get('example_physical_pair_id') not in affected_physical:example=(r['example_physical_pair_id'],r['example_low_team_key'],r['example_high_team_key'])
        else:
            found=[v for (sk,_),v in witnesses.items() if sk==k]
            if not found:raise AssertionError(('missing_global_state_example',k))
            example=found[0]
        r['example_physical_pair_id'],r['example_low_team_key'],r['example_high_team_key']=example
        rows.append(r)
    jsave(out/'BUILDING_SUPPORT_AMBIGUITIES.json',ambiguous)
    assert not ambiguous,('Need exact saved status from these pools',ambiguous)
    final=pd.DataFrame(rows)[old.columns];assert final.unique_physical_pairs.sum()==old.unique_physical_pairs.sum()
    save(final,out/gfile)
    teamfile='UNIQUE_REQUESTED_TEAM_OUTPUT_STATE_COUNTS.csv'
    oldteam=pd.read_csv(SOURCE/teamfile);t0=pd.read_csv(out/'automatic'/teamfile);t1=pd.read_csv(out/'assisted'/teamfile)
    tk=['condition','layer','scope','output_state','score_status',*m.FLAGS]
    lookup=lambda d:{tuple(r[c] for c in tk):r for r in d.to_dict('records')}
    t,ta,tb=lookup(oldteam),lookup(t0),lookup(t1);tr=[]
    for k in set(t)|set(tb):
        r=dict(t.get(k,tb.get(k)))
        for col in ['unique_requested_teams','target_pools']:r[col]=t.get(k,{}).get(col,0)-ta.get(k,{}).get(col,0)+tb.get(k,{}).get(col,0)
        if r['unique_requested_teams']<=0:continue
        if k in tb:r['example_team_key']=tb[k]['example_team_key']
        tr.append(r)
    save(pd.DataFrame(tr)[oldteam.columns],out/teamfile)
    domains=[]
    for key,g in final.groupby(['condition','layer','scope']):
        rr=dict(zip(['condition','layer','scope'],key));rr['physical_pairs']=int(g.unique_physical_pairs.sum())
        masks={'both_present':~g.low_key_Q_missing&~g.high_key_Q_missing,'one_missing':g.low_key_Q_missing^g.high_key_Q_missing,
               'both_missing':g.low_key_Q_missing&g.high_key_Q_missing,'both_missing_different':g.low_key_Q_missing&g.high_key_Q_missing&g.low_key_output_state.ne(g.high_key_output_state),
               'observed_failure':g.low_key_fusion_failure_observed|g.high_key_fusion_failure_observed}
        for c,mask in masks.items():rr[c+'_pairs']=int(g.loc[mask,'unique_physical_pairs'].sum())
        domains.append(rr)
    save(pd.DataFrame(domains),out/'STATE_DOMAIN_DENOMINATOR_SUMMARY.csv')
    save(pd.DataFrame(parity),out/'PARITY.csv')
    jsave(out/'STATE_IMPACT_RECEIPT.json',dict(affected_pools=9,physical_pairs=int(final.unique_physical_pairs.sum()),
        unique_teams=int(sum(r['unique_requested_teams'] for r in tr)),building_support_exact=True,
        building_support_witnesses='frozen state-cell example events + frozen registration team identities',
        capacity_and_registration_unchanged=True,new_fusions=0,new_scores=0,missing_Q_imputed=False))
    print('AC states complete',len(final),flush=True)


if __name__=='__main__':main()
