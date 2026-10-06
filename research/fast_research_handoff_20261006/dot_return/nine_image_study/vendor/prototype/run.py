from __future__ import annotations
import sys,json,gzip,time,copy,hashlib,platform,io
from contextlib import contextmanager
from pathlib import Path
import numpy as np
from baseline import nodes_from_records,distances,partition
from structure import PathBank,filter_partition,report_groups,partition_changes,ring_diagnostics

ROOT=Path(__file__).resolve().parents[1]
def dump(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

@contextmanager
def text_gzip(path):
    # The filename and timestamp do not encode the output directory or runtime.
    with open(path,'wb') as raw:
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as compressed:
            with io.TextIOWrapper(compressed,encoding='utf-8',newline='\n') as text:
                yield text

def run(out,images=None):
    out=Path(out);out.mkdir(exist_ok=False,parents=True)
    config=json.loads((ROOT/'config.json').read_text());dump(out/'frozen_config.json',config)
    input_paths=[p for p in sorted((ROOT/'inputs').glob('*.json')) if p.name!='human_review.json']
    if images:input_paths=[p for p in input_paths if p.stem in images]
    summary=[]
    for f in input_paths:
        im=json.loads(f.read_text());records=im['records'];before=copy.deepcopy(records)
        nodes=nodes_from_records(records);D=distances(nodes);bank=PathBank(records,nodes,config)
        path=out/im['image'];path.mkdir();dump(path/'nodes.json',nodes)
        print('IMAGE',im['image'],len(records),len(nodes),flush=True)
        for metric in config['endpoint_metrics']:
            for tau in config['thresholds_deg']:
                start=time.monotonic();tag=f'{metric}_{tau}'
                base,_=partition(nodes,D[metric],tau)
                ledger=[]
                for i in range(len(nodes)):
                    for j in range(i+1,len(nodes)):
                        if nodes[i]['worker']==nodes[j]['worker'] or D[metric][i,j]>tau+1e-10:continue
                        ledger.append(bank.witness(i,j,metric,tau,D))
                new=filter_partition(nodes,D,metric,tau,ledger)
                state={'image':im['image'],'metric':metric,'threshold_deg':tau,'vote_denominator':len(records),
                       'status':'computed_on_available_previous_input_not_new_local_bundle','records':[r['id'] for r in records]}
                for name,groups in [('raw_MV',base),('path_witness_MV',new)]:
                    gg,lut=report_groups(nodes,groups,D,len(records))
                    state[name]={'groups':gg,'ring':ring_diagnostics(records,nodes,gg,lut)}
                state['changes']=partition_changes(nodes,base,new)
                state['path_evidence_summary']={'tested_node_pairs':len(ledger),'witnessed':sum(x['status']=='witnessed' for x in ledger),
                    'numeric_unresolved':sum(x['status']=='numerically_unresolved' for x in ledger),
                    'no_witness':sum(x['status']=='not_witnessed' for x in ledger)}
                state['source_unchanged']=records==before
                dump(path/(tag+'.json'),state)
                with text_gzip(path/(tag+'_path_evidence.jsonl.gz')) as z:
                    for r in ledger:z.write(json.dumps(r,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
                row={'image':im['image'],'metric':metric,'threshold_deg':tau,'n':len(records),**state['path_evidence_summary'],
                    'raw_selected':state['raw_MV']['ring']['selected_pair_count'],'path_selected':state['path_witness_MV']['ring']['selected_pair_count'],
                    'raw_groups':len(base),'path_groups':len(new),'lost_relations':len(state['changes']['lost_comemberships']),
                    'new_relations':len(state['changes']['new_comemberships']),'affected_observations':len(state['changes']['affected_nodes'])}
                summary.append(row)
                print(tag,row,'seconds',round(time.monotonic()-start,2),flush=True)
        dump(path/'source_path_catalogue.json',bank.public_paths())
        dump(path/'compute_counts.json',dict(bank.calls))
    dump(out/'summary.json',summary)
    dump(out/'input_manifest.json',[{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in input_paths])
    return summary
if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('--out',required=True);a.add_argument('--images',nargs='*');args=a.parse_args()
    run(args.out,args.images)
