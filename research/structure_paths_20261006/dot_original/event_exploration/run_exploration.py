"""One bounded execution, no GT, no regrouping, no source modifications."""
from __future__ import annotations
import argparse,copy,hashlib,json,sys,time
from pathlib import Path
import numpy as np
from event_search import *


def dump(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def banks(records):
    ns=nodes_from_records(records);D=distances(ns);ix={key(n):i for i,n in enumerate(ns)}
    return PathBank(records,ns,CONFIG),EventBank(records,ns,CONFIG),D,ix


def run(out):
    out=Path(out);out.mkdir(exist_ok=False,parents=True)
    dump(out/'frozen_policy.json',POLICY)
    source_files=sorted((SOURCE/'inputs').glob('*.json'))+sorted((SOURCE/'src').glob('*.py'))+[SOURCE/'config.json',SOURCE/'REPORT_ZH.md',SOURCE/'README.md']
    before={str(p.relative_to(SOURCE)):sha(p) for p in source_files}
    dump(out/'source_manifest_before.json',before)
    # Reproduce exactly the delivered sparse-versus-dense counterexample first.
    saved=json.loads((SOURCE/'results/controls/fixed_hop_subdivision_counterexample.json').read_text())
    records=saved['records'];old,event,D,ix=banks(records)
    oldrow=old.witness(ix[('A',0)],ix[('B',0)],'pair',5,D)
    newrow=event.witness(ix[('A',0)],ix[('B',0)],'pair',5,D)
    assert oldrow==saved['result'], 'original_counterexample_reproduction_mismatch'
    dump(out/'original_counterexample_reproduced.json',{'exact_result_match':True,'records':records,
        'fixed_hop_result':oldrow,'event_result':newrow,'event_paths':event.public_paths()})
    print('ORIGINAL_COUNTEREXAMPLE',oldrow['status'],'->',newrow['status'],flush=True)
    baseA=copy.deepcopy(records[0]);baseB=copy.deepcopy(baseA);baseB.update(id='B',worker='B')
    windows=[{'name':'synthetic_square','image':'synthetic_control','focals':[['A',0],['B',0]],
              'records':[baseA,baseB],'full_source_pool_size':None}]
    input_cache={}
    for spec in POLICY['real_windows']:
        image=spec['image']
        if image not in input_cache:
            raw=json.loads((SOURCE/'inputs'/f'{image}.json').read_text());input_cache[image]=raw
            # Complete source roster retained, not just the two records in each query.
            (out/'inputs').mkdir(exist_ok=True)
            (out/'inputs'/f'{image}.json').write_bytes((SOURCE/'inputs'/f'{image}.json').read_bytes())
        raw=input_cache[image];lookup={r['id']:r for r in raw['records']}
        windows.append({**spec,'records':[lookup[f[0]] for f in spec['focals']], 'full_source_pool_size':len(raw['records'])})
    variants=[(1,1)]+[(1,k) for k in POLICY['subdivision_factors']]+[(k,k) for k in POLICY['subdivision_factors']]
    summaries=[];comparisons=[];all_validations=[];event_issues=[]
    for window in windows:
        references={};wb=copy.deepcopy(window['records'])
        for factors in variants:
            rs=[];validations=[]
            for r,k in zip(window['records'],factors):
                rr,v=subdivide(r,k);rs.append(rr);validations.append({'record':r['id'],**v})
            all_validations.append({'window':window['name'],'factors':factors,'validations':validations})
            old,event,D,ix=banks(rs)
            focal=[ix[(rid,idx*f)] for (rid,idx),f in zip(window['focals'],factors)]
            tag=f"{window['name']}_{factors[0]}x{factors[1]}"
            dump(out/'probe_records'/f'{tag}.json',{'role':'same_record_metamorphic_probe_no_new_voters','records':rs,'validation':validations})
            detailed=[]
            for metric in ('pair','bottom','top'):
                for gate in POLICY['thresholds_deg']:
                    original=old.witness(*focal,metric,gate,D); result=event.witness(*focal,metric,gate,D)
                    sig=event_signature(event,result);kt=metric,gate
                    if factors==(1,1):references[kt]=sig
                    eq=sig==references[kt]
                    comparisons.append({'window':window['name'],'factors':factors,'metric':metric,'gate_deg':gate,
                                        'full_candidate_and_witness_signature_equal_to_original':eq,
                                        'source_status':references[kt]['status'],'probe_status':sig['status']})
                    row={'window':window['name'],'image':window['image'],'factors':factors,'metric':metric,'gate_deg':gate,
                         'focals_original_indices':window['focals'],'full_source_pool_size_unchanged':window['full_source_pool_size'],
                         'fixed_hop':summary(old,original),'event_domain':summary(event,result),'invariant_signature':eq}
                    summaries.append(row);detailed.append({'summary':row,'fixed_hop_result':original,
                                                            'event_result':result,'signature':sig})
            dump(out/'ledgers'/f'{tag}.json',detailed)
            dump(out/'paths'/f'{tag}.json',event.public_paths())
            maps=[{'record':rid,'metric':m,**v} for (rid,m),v in event.event_maps.items()]
            dump(out/'event_maps'/f'{tag}.json',maps)
            event_issues.extend({'window':window['name'],'factors':factors,**v} for v in maps if v['status']!='resolved_numeric_domain')
        assert wb==window['records'],'in_memory_source_mutation'
        print('WINDOW',window['name'],'done',flush=True)
    after={str(p.relative_to(SOURCE)):sha(p) for p in source_files}
    assert before==after,'source_file_changed'
    dump(out/'source_manifest_after.json',after)
    dump(out/'summary.json',summaries);dump(out/'invariance_checks.json',comparisons)
    dump(out/'subdivision_validations.json',all_validations);dump(out/'unresolved_event_domains.json',event_issues)
    actual=[r for r in comparisons if r['factors']!=[1,1] and tuple(r['factors'])!=(1,1)]
    mismatch=[r for r in actual if not r['full_candidate_and_witness_signature_equal_to_original']]
    verification={'source_files_unchanged':before==after,'original_counterexample_exactly_reproduced':oldrow==saved['result'],
                  'original_counterexample_event_status':newrow['status'],
                  'fixed_windows':len(windows),'source_real_windows':len(windows)-1,'base_settings':len(windows)*9,
                  'total_variant_settings':len(summaries),'nonbaseline_invariance_comparisons':len(actual),
                  'invariance_mismatches':mismatch,'unresolved_event_domains':len(event_issues),
                  'maximum_subdivision_arc_additivity_error_deg':max(v['maximum_arc_additivity_error_deg'] for r in all_validations for v in r['validations']),
                  'GT_or_reference_files_read':False,'human_labels_read_by_construction':False,
                  'identity_or_vote_updates_performed':False,
                  'policy_sha256':sha(HERE/'frozen_policy.json')}
    dump(out/'verification.json',verification)
    print(json.dumps(verification,indent=2),flush=True)
    if mismatch or event_issues: print('Retained all mismatches/unresolved cases; no parameter tuning.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    run(p.parse_args().out)
