"""Read-only identity/source audit and outcome-free assessment registration."""
from __future__ import annotations
import collections, datetime, gzip, hashlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'interchangeability_20261020/code'))
from design_history_panel import read, write, team_key
from design_blocks import labels_from, counts, allowed_workers, applicable
import design_mixed_challenge as design

OUT = Path(__file__).resolve().parent
SNAPSHOT = ROOT/'restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz'
LABELS = [ROOT/'interchangeability_20261020/forward/worker_labels.csv.gz', ROOT/'interchangeability_20261020/reverse/mixed_fit/worker_labels.csv.gz']
SPLIT = ROOT/'analysis/composition/SPLIT.json'
MANIFESTS = {'discovery':ROOT/'interchangeability_20261020/mixed_challenge/discovery_requests.json.gz', 'assessment':OUT/'assessment_requests.json.gz'}

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def audit(path, phase, pools, maps, split):
    data=read(path); events=data['events']; requests=data['requests']
    assert data['spec']['methods']==design.METHODS and data['spec']['seed']==design.SEED
    assert data['spec']['phase']==phase
    target=set(split['discovery_buildings' if phase=='discovery' else 'validation_buildings'])
    methods={(m['method_id'],m['domain']):m for m in design.METHODS}
    req={q['request_id']:q for q in requests}; assert len(req)==len(requests)
    event_ids=set(); tk=set(); person=set(); blocks=set(); signatures=collections.Counter(); ownsrc=collections.Counter()
    for e in events:
        assert e['event_id'] not in event_ids; event_ids.add(e['event_id'])
        p=pools[e['pool_id']]; method=methods[e['method_id'],e['domain']]; mapping=maps[e['method_id'],e['domain']]
        assert p['meta']['building'] in target and applicable(p,method)
        for key in ['building','image','difficulty','layer','condition','reference_id']: assert e[key]==p['meta'][key]
        ws=set(allowed_workers(p,method)); origins={r['worker_id']:r['origin'] for r in p['records']}
        a,b,c=[set(e[x+'_workers']) for x in 'ABC']; core=set(e['core_workers']); aa=set(e['outgoing_workers']); bb=set(e['within_incoming']); cc=set(e['cross_incoming'])
        n,m=e['n'],e['m']; assert n>=3 and 2<=m<=n
        assert a==core|aa and b==core|bb and c==core|cc
        assert len(core)==n-m and all(len(x)==m for x in [aa,bb,cc])
        assert a&b==a&c==core and aa&bb==aa&cc==set()
        assert all(len(x)==n and x<=ws for x in [a,b,c])
        assert len(a-b)==len(a-c)==m and len(b-c)==e['B_to_C_actual_turnover']>=1
        assert bool(n==m)==e['complete_turnover']
        assert e['context_id']==('whole_team' if n==m else 'partial_mixed_block')
        assert all(w in mapping for w in aa|bb|cc)
        ca,cb,cd=[counts(x,mapping) for x in [a,b,c]]
        assert ca==e['A_counts']==cb==e['B_counts'] and cd==e['C_counts'] and ca!=cd
        assert counts(aa,mapping)==counts(bb,mapping)==e['outgoing_counts'] and counts(cc,mapping)==e['incoming_counts']
        assert len(counts(aa,mapping))>=2 and counts(core,mapping)==e['core_counts']
        assert e['changed_category_slots']==sum(abs(ca.get(cl,0)-cd.get(cl,0)) for cl in set(ca)|set(cd))//2
        assert 1<=e['changed_category_slots']<=e['B_to_C_actual_turnover']<=m
        src=[collections.Counter(origins[w] for w in x) for x in [aa,bb,cc]]
        assert e['actual_source_match']==(src[0]==src[1]==src[2])
        if e['matching']=='source_matched': assert src[0]==src[1]==src[2]
        assert e['outside_background_n']==sum(w not in mapping for w in core)
        person|=a|b|c; blocks|=aa|bb|cc
        ownsrc[(e['method_id'],e['context_id'],e['matching'],e['actual_source_match'])]+=1
        signatures[(e['method_id'],e['domain'],e['pool_id'],n,m,tuple(sorted(ca.items())),tuple(sorted(cd.items())),tuple(sorted(a)),tuple(sorted(b)),tuple(sorted(c)))]+=1
        for arm,s in zip('ABC',[a,b,c]):
            key=team_key(e['pool_id'],list(s)); assert key==e[arm+'_team_key']; q=req[key]
            assert q['pool_id']==e['pool_id'] and q['k']==n and sorted(q['worker_ids'])==sorted(s)
            assert len(q['worker_ids'])==n; tk.add(key)
    assert tk==set(req)
    by=collections.Counter((e['method_id'],e['domain'],e['pool_id']) for e in events)
    for row in data['ledger']:
        assert row['accepted_events']==by[row['method_id'],row['domain'],row['pool_id']]
        assert row['metadata_n_m_source_frame']==row['whole_frame']+row['partial_frame']
        assert row['selected_metadata_contexts']==min(16,row['whole_frame'])+min(16,row['partial_frame'])
        assert row['accepted_events']+sum(row['draw_failures'].values())==row['selected_metadata_contexts']
    return dict(path=str(path.relative_to(ROOT)),sha256=sha(path),events=len(events),unique_teams=len(tk),images=len({e['image'] for e in events}),pools=len({e['pool_id'] for e in events}),buildings=sorted({e['building'] for e in events}),workers=len(person),replacement_workers=len(blocks),whole_team_events=sum(e['complete_turnover'] for e in events),partial_events=sum(not e['complete_turnover'] for e in events),methods=len(methods),method_context_cells=len({(e['method_id'],e['domain'],e['context_id']) for e in events}),n=sorted({e['n'] for e in events}),m=sorted({e['m'] for e in events}),changed_category_slots=sorted({e['changed_category_slots'] for e in events}),B_to_C_actual_turnover=sorted({e['B_to_C_actual_turnover'] for e in events}),metadata_contexts=sum(x['metadata_n_m_source_frame'] for x in data['ledger']),selected_contexts=sum(x['selected_metadata_contexts'] for x in data['ledger']),rejected_draws=sum(sum(x['draw_failures'].values()) for x in data['ledger']),exact_duplicate_events=sum(v-1 for v in signatures.values()),all_identity_reference_source_invariants=True)

def main():
    pools={p['pool_id']:p for p in read(SNAPSHOT)['images']}; maps=labels_from(LABELS); split=read(SPLIT)
    results={phase:audit(path,phase,pools,maps,split) for phase,path in MANIFESTS.items()}
    assert not (set(results['discovery']['buildings'])&set(results['assessment']['buildings']))
    sources=[Path(__file__),Path(design.__file__),ROOT/'interchangeability_20261020/code/design_blocks.py',ROOT/'interchangeability_20261020/code/design_history_panel.py',ROOT/'analysis/composition/design_compositions.py',SNAPSHOT,SPLIT,*LABELS,ROOT/'interchangeability_20261020/independent/METRIC_CONTRACT.json',ROOT/'interchangeability_20261020/independent/pair_diagnostics.py']
    result=dict(schema='mixed_challenge_independent_design_audit_v1',registered_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scientific_outcomes_read_for_this_audit=False,rules_unchanged=True,phases=results,sources={str(p.relative_to(ROOT)):sha(p) for p in sources},analysis_plan={'main':'Original joint strict/main/wide, parallel noQ and new shape; no changed thresholds. Whole-team and partial blocks separate. Event means within image/pool then equal buildings; finite-score denominator and failures separate. Deduplicate actual A/B pair for within composition, and unique A/B endpoint teams for level/tail estimates.','detailed_tables':['method/context','exact n/m','changed category slots and B/C actual turnover','exact A/B and C composition counts including outside_group','difficulty and actual source matching','per-image/per-building','finite Q tail, actual-team failure, bottom-y and reference geometry diagnostics'],'validation':'All seven routes fixed before discovery challenge outcomes. This assessment reuses v2 six other buildings with fixed rules; it is not external blind testing. Specific vector/case winners found later are descriptive unless their rule is frozen before assessment inspection.'},coverage_limit='Integer n/m/source candidate frame enumerated, at most 16 whole plus 16 partial metadata contexts sampled per method/pool. One feasible outgoing count vector per accepted event, sampled concrete members and changed class slots; 16 failed draws are not mathematical infeasibility. Core may contain explicitly outside_group members. B/C overlap is retained and B->C differs from matched-m A->B versus A->C contrast.')
    write(OUT/'ASSESSMENT_DESIGN_FREEZE.json',result)
    print(json.dumps(results,ensure_ascii=False))

if __name__=='__main__':main()
