#!/usr/bin/env python3
"""Parallel pool orchestration for analyze_response; estimators are unchanged."""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import pandas as pd
import analyze_response as ar

_bands=None
_root=None
_out=None
def initialize(root,out):
    global _bands,_root,_out
    _root=Path(root);_out=Path(out);_bands=ar.load_bands(_root)

def work(row):
    return ar.process_pool(row,_root,_out,_bands,save_events=True,resume=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=ar.ROOT)
    p.add_argument('--input-index',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--workers',type=int,default=4)
    a=p.parse_args();root=a.root.resolve();src=a.input_index if a.input_index.is_absolute() else root/a.input_index
    out=a.output if a.output.is_absolute() else root/a.output;out.mkdir(parents=True,exist_ok=True)
    index=pd.read_csv(src);assert not index.pool_id.duplicated().any()
    (out/'ANALYSIS_CONFIG.json').write_text(json.dumps(ar.CONFIG,ensure_ascii=False,indent=2))
    results=[]
    with ProcessPoolExecutor(max_workers=a.workers,initializer=initialize,initargs=(str(root),str(out))) as ex:
        futures={ex.submit(work,row):row['pool_id'] for row in index.to_dict('records')}
        for f in as_completed(futures):
            r=f.result();results.append(r)
            print(json.dumps(dict(done=len(results),total=len(index),pool_id=r['pool_id'],N=r['N'],rows=r['path_rows']),ensure_ascii=False),flush=True)
    order={v:i for i,v in enumerate(index.pool_id)};results.sort(key=lambda x:order[x['pool_id']])
    combined=ar.combine_pool_outputs(results,out,root)
    ar.write_csv(pd.DataFrame(results),out/'ANALYSIS_POOL_INDEX.csv')
    final=dict(pools=len(results),images=len(set(r['image'] for r in results)),
       input_path_rows=sum(r['path_rows'] for r in results),new_fusion=False,new_quality_scores=False,
       sum_finite_Q_not_complete=sum(r['finite_Q_but_not_complete_main_rows'] for r in results),
       band_estimate_mismatches=sum(r['mismatching_band_rows'] for r in results),
       output_rows=combined,all_input_indexes=[str(src)],workers=a.workers,
       parallelization_changes_only_pool_scheduling=True)
    (out/'ANALYSIS_COMPLETION.json').write_text(json.dumps(final,ensure_ascii=False,indent=2))
    print(json.dumps(final,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
