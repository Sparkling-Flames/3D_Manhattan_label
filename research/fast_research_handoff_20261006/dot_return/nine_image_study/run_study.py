"""Nine-image paired-only bounded comparison; no evaluation-reference import."""
from pathlib import Path
import sys,os,json,copy,hashlib,time,gzip,io,itertools,argparse
from collections import Counter
import numpy as np

HERE=Path(__file__).resolve().parent
os.environ['STRUCTURE_SOURCE']=str(HERE/'vendor')
# event_search expects STRUCTURE_SOURCE/src; already loaded modules below resolve
# its imports without altering the upstream files.
sys.path.insert(0,str(HERE/'vendor/prototype'))
from baseline import nodes_from_records,distances,partition,key,center
import structure
from structure import PathBank,filter_partition,report_groups,partition_changes,ring_diagnostics
from analysis import context_state,known_relations,group_relation
sys.path.insert(0,str(HERE/'vendor/event'))
from event_search import EventBank,CONFIG,POLICY as EVENT_POLICY
from source_adapter import source_distances,source_center

POLICIES=['raw','fixed_strict','fixed_three_state','event_strict','event_three_state']
def dump(p,x):
    p=Path(p);p.parent.mkdir(exist_ok=True,parents=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write_ledger(p,rows):
    with p.open('wb') as f:
        with gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0) as g:
            with io.TextIOWrapper(g,encoding='utf-8') as z:
                for row in rows:z.write(json.dumps(row,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')

def verify_raw(inputs,baselines,out):
    report=[]
    for im in inputs['images']:
        nodes=nodes_from_records(im['records']);Dp=distances(nodes);Ds=source_distances(nodes)
        for t in [5,9,12]:
            expect=next(s['result']['identity_groups'] for s in baselines['states']
                        if s['image']==im['image'] and s['route']=='paired' and s['threshold_deg']==t)
            expected={tuple(sorted((m['id'],m['pair_index']) for m in g['members'])):g['center'] for g in expect}
            row={'image':im['image'],'threshold_deg':t,'source_nodes':len(nodes)}
            for name,D,cf in [('original_prototype',Dp,center),('source_adapter',Ds,source_center)]:
                groups,_=partition(nodes,D['pair'],t)
                got={tuple(sorted(key(nodes[i]) for i in g)):cf(nodes,g,D['pair'])['points'] for g in groups}
                errs=[float(np.max(np.abs(np.array(v)-expected[k]))) for k,v in got.items()
                      if k in expected and v is not None and expected[k] is not None]
                status={'membership_equal':got.keys()==expected.keys(),
                        'centers_exact_equal':got==expected,'max_center_error_px':max(errs,default=0),
                        'groups':len(got)}
                row[name]=status
                if not status['membership_equal'] or status['max_center_error_px']>1e-9:
                    dump(out/'baseline_parity_failure.json',row);raise AssertionError('raw baseline mismatch')
                # Preserve/report tiny cross-version floating drift rather than
                # call it a structural mismatch; current execution is exact.
            report.append(row)
    dump(out/'raw_parity.json',report)

def three_state(nodes,D,t,rows,records):
    classes={tuple(x['nodes']):context_state(x,nodes,records) for x in rows}
    M=D['pair'].copy()
    for (i,j),label in classes.items():
        if label=='all_proposed_two_sided_paths_disagree':M[i,j]=M[j,i]=181.
    return partition(nodes,M,t)[0],classes

def relation_sources(nodes,pairs):
    return [{'node_indices':p,'sources':[list(key(nodes[i])) for i in p]} for p in pairs]

def run(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    inputs=json.loads((HERE/'inputs/inputs.json').read_text());before=copy.deepcopy(inputs)
    baselines=json.loads((HERE/'inputs/paired_baseline_compact.json').read_text())
    policy={'images':[x['image'] for x in inputs['images']], 'records':sum(len(i['records']) for i in inputs['images']),
            'thresholds_deg':[5,9,12],'metric':'pair','policies':POLICIES,
            'same_focal_and_outer_anchor_gate_as_raw':True,'fixed_path_config':CONFIG,
            'event_source_policy_snapshot_historical_scope_not_current_study':EVENT_POLICY,
            'event_applied_rule':EVENT_POLICY['search_domain'],
            'event_domain_replaces_fixed_domain_not_general_superset':True,
            'complete_pools_unchanged':True,'vote_threshold':'ceil(n/2)',
            'center':'authoritative_source_first_medoid_coordinate_medians_for_every_policy',
            'no_forced_four_or_min8':True,'no_GT_read_or_tuning':True,
            'human_review':'read only after saving all automatic candidates; exposed development cases',
            'not_run':['new focal gate expansion','single-endpoint structure policies','new human-assisted selection'],
            'scope_note':'five targeted hard cases plus four exposed/ordinary cases; not random/blind test',
            'stopping_condition':'all nine images x three fixed gates x five policies plus posthoc relation accounting'}
    dump(out/'frozen_policy.json',policy)
    dump(out/'input_manifest.json',[{'path':str(p.relative_to(HERE)),'sha256':digest(p)} for p in sorted((HERE/'inputs').glob('*.json')) if p.name!='baselines.json'])
    verify_raw(inputs,baselines,out)
    structure.center=source_center # explicit adapter only; no source file edits
    summary=[]
    for im in inputs['images']:
        code=im['image'];records=im['records'];rs={r['id']:r for r in records}
        nodes=nodes_from_records(records);D=source_distances(nodes);folder=out/code;folder.mkdir()
        fixed=PathBank(records,nodes,CONFIG);event=EventBank(records,nodes,CONFIG)
        dump(folder/'nodes.json',nodes)
        print('IMAGE',code,len(records),len(nodes),flush=True)
        for t in [5,9,12]:
            tick=time.monotonic();base,_=partition(nodes,D['pair'],t)
            tested=[(i,j) for i in range(len(nodes)) for j in range(i+1,len(nodes))
                    if nodes[i]['worker']!=nodes[j]['worker'] and D['pair'][i,j]<=t+1e-10]
            groups={'raw':base};ledger={};contexts={};evidence={}
            for name,bank in [('fixed',fixed),('event',event)]:
                rows=[bank.witness(i,j,'pair',t,D) for i,j in tested]
                ledger[name]=rows
                groups[name+'_strict']=filter_partition(nodes,D,'pair',t,rows)
                groups[name+'_three_state'],contexts[name]=three_state(nodes,D,t,rows,rs)
                evidence[name]={'tested_pairs':len(rows),'statuses':dict(Counter(r['status'] for r in rows)),
                                'contexts':dict(Counter(contexts[name].values())),
                                'leg_statuses':dict(Counter(l['status'] for r in rows for l in r['legs']))}
                write_ledger(folder/f'{name}_{t}_evidence.jsonl.gz',rows)
            state={'image':code,'threshold_deg':t,'metric':'pair','vote_denominator':len(records),
                   'minimum_support':int(np.ceil(len(records)/2)), 'evidence':evidence,'policies':{}}
            for name,gg in groups.items():
                reports,lut=report_groups(nodes,gg,D,len(records));ring=ring_diagnostics(records,nodes,reports,lut)
                changes=partition_changes(nodes,base,gg)
                for field in ['lost_comemberships','new_comemberships']:
                    changes[field+'_sources']=relation_sources(nodes,changes[field])
                state['policies'][name]={'groups':reports,'ring':ring,'changes_from_raw':changes}
                row={'image':code,'threshold_deg':t,'policy':name,'n':len(records),'observations':len(nodes),
                     'selected_pairs':ring['selected_pair_count'],'below_four':ring['selected_pair_count']<4,
                     'groups':len(gg),'covered_observations':sum(g['support'] for g in reports if g['selected']),
                     'lost_relations':len(changes['lost_comemberships']),
                     'new_relations':len(changes['new_comemberships']),
                     'affected_observations':len(changes['affected_nodes']),
                     'new_edges_without_direct_source':sum(e['new_edge_without_direct_source'] for e in ring['x_diagnostic_edges']),
                     'geometry_valid':ring['x_diagnostic']['geometry_valid'],
                     'unconfirmed_area_h2':ring['x_diagnostic']['area_h2'],
                     'primary_ring_available':ring['primary_ring_available']}
                summary.append(row)
            status_transitions=Counter((a['status'],b['status']) for a,b in zip(ledger['fixed'],ledger['event']))
            state['domain_change']={'status_transitions':[{'fixed':a,'event':b,'count':n} for (a,b),n in status_transitions.items()],
                'changed_focal_pairs':[{'nodes':a['nodes'],'sources':[list(key(nodes[k])) for k in a['nodes']],
                                       'fixed':a['status'],'event':b['status']}
                                       for a,b in zip(ledger['fixed'],ledger['event']) if a['status']!=b['status']]}
            dump(folder/f'pair_{t}.json',state)
            print(code,t,{name:state['policies'][name]['ring']['selected_pair_count'] for name in POLICIES},
                  evidence,'seconds',round(time.monotonic()-tick,2),flush=True)
        write_ledger(folder/'fixed_source_paths.jsonl.gz',fixed.public_paths())
        write_ledger(folder/'event_source_paths.jsonl.gz',event.public_paths())
        dump(folder/'event_maps.json',[{'record':rid,'metric':m,**emap} for (rid,m),emap in event.event_maps.items()])
        dump(folder/'compute_counts.json',{'fixed':dict(fixed.calls),'event':dict(event.calls)})
    assert inputs==before
    dump(out/'summary.json',summary)
    frozen=[{'path':str(p.relative_to(out)),'sha256':digest(p)} for p in sorted(out.rglob('*')) if p.is_file()]
    dump(out/'automatic_candidates_frozen_before_human_review.json',frozen)
    human=json.loads((HERE/'inputs/human_review.json').read_text())
    known=[];change_audit=[]
    for im in inputs['images']:
        nodes=json.loads((out/im['image']/'nodes.json').read_text());D=source_distances(nodes)
        rels=known_relations(human,im['image'],'pair',nodes)
        relset={tuple(sorted((i,j))):same for i,j,same,_ in rels}
        for t in [5,9,12]:
            state=json.loads((out/im['image']/f'pair_{t}.json').read_text())
            for i,j,same,case in rels:
                row={'image':im['image'],'threshold_deg':t,'case':case,'sources':[key(nodes[i]),key(nodes[j])],
                     'expected_same':same,'pair_distance_deg':float(D['pair'][i,j]),
                     'focal_gate_eligible':bool(D['pair'][i,j]<=t+1e-10),'policies':{}}
                for name,p in state['policies'].items():
                    together=group_relation([g['node_indices'] for g in p['groups']],i,j)
                    row['policies'][name]={'same_group':together,'false_split':same and not together,
                                           'false_merge':not same and together}
                known.append(row)
            for name,p in state['policies'].items():
                counts={}
                for field in ['lost_comemberships','new_comemberships']:
                    pairs=p['changes_from_raw'][field]
                    counts[field]={'total':len(pairs),'known_same':sum(relset.get(tuple(pair)) is True for pair in pairs),
                        'known_different':sum(relset.get(tuple(pair)) is False for pair in pairs),
                        'unknown':sum(tuple(pair) not in relset for pair in pairs)}
                change_audit.append({'image':im['image'],'threshold_deg':t,'policy':name,**counts})
    dump(out/'known_human_relations.json',known);dump(out/'known_unknown_changes.json',change_audit)
    assert all(digest(out/x['path'])==x['sha256'] for x in frozen)
    dump(out/'verification.json',{'source_records_unchanged':True,'automatic_artifacts_unchanged_after_review':True,
          'images':len(inputs['images']),'states':27,'policy_results':len(summary),
          'known_relation_gate_observations':len(known),'construction_reference_reads':0,
          'no_reference_evaluation_performed_here':True})
    return summary

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True)
    run(ap.parse_args().out)
