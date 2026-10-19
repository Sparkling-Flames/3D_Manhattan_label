#!/usr/bin/env python3
"""Replay available frozen v2 statistical-source context, without recollection.

Calls the unchanged main generator's computational functions, directs receipts
only to this research output, and compares each typed table with the published
gzip. Personnel/historical tables imported by the generator are explicitly
identified as inherited table reads, not independent refits.
"""
from pathlib import Path
import gzip,hashlib,json,math,sys,time,traceback
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT/'repo_main_20261019'),str(ROOT/'runtime_deps')]
from tools.thesis_main.analysis import v2_integrated_statistics_20261019 as native

def compare(a,b):
    result={'differences':0,'compared_leaves':0,'max_abs_numeric_difference':0.,'examples':[]}
    def visit(x,y,p):
        if isinstance(x,dict) and isinstance(y,dict):
            if set(x)!=set(y):diff(p+'.keys',sorted(x),sorted(y))
            for k in set(x)&set(y):visit(x[k],y[k],p+'.'+k)
        elif isinstance(x,list) and isinstance(y,list):
            if len(x)!=len(y):diff(p+'.length',len(x),len(y))
            for i,(u,v) in enumerate(zip(x,y)):visit(u,v,p+f'[{i}]')
        else:
            result['compared_leaves']+=1
            if isinstance(x,(int,float)) and not isinstance(x,bool) and isinstance(y,(int,float)) and not isinstance(y,bool):
                delta=abs(x-y);result['max_abs_numeric_difference']=max(result['max_abs_numeric_difference'],delta)
                if delta>1e-8:diff(p,x,y)
            elif x!=y:diff(p,x,y)
    def diff(p,x,y):
        result['differences']+=1
        if len(result['examples'])<5:result['examples'].append({'path':p,'replay':str(x)[:300],'published':str(y)[:300]})
    visit(a,b,'$');return result

def main():
    started=time.monotonic();old=json.load(gzip.open(native.OUT/'tables.json.gz','rt'))['tables']
    print('loading frozen minimal source context',flush=True)
    records,bundle,objects,refs,bindings,evidence_status=native.load_records()
    summaries=[];errors=[];seen=set()
    for block,fn in [('base',lambda:native.base_tables(records,refs)),('direct_room',lambda:native.room_tables(records)),('raw_floor_disagreement',lambda:native.raw_disagreement(records,objects)),('inherited_personnel_and_history',lambda:native.historical_and_personnel_tables(records))]:
        print('computing',block,flush=True);start=time.monotonic()
        try:tables=fn()
        except Exception as e:
            errors.append({'block':block,'error':str(e),'traceback':traceback.format_exc()});print('BLOCK UNAVAILABLE',block,str(e),flush=True);continue
        for name,frame in tables.items():
            table_id='quality__shared_records' if name=='shared_records' else 'statistics__'+name
            typed=native.public_value(json.loads(frame.to_json(orient='records',force_ascii=False,double_precision=15)))
            cmp=compare(typed,old[table_id]);summaries.append({'table':table_id,'block':block,'rows':len(typed),'published_rows':len(old[table_id]),'pass':cmp['differences']==0,
                 'replay_kind':'inherited_table_read' if name.startswith('personnel_') or name.startswith('historical_') else 'computed_from_frozen_source_columns',**cmp})
            seen.add(table_id)
        print(block,'done',round(time.monotonic()-start,1),'seconds',flush=True)
    pd.DataFrame([{k:v for k,v in r.items() if k!='examples'} for r in summaries]).to_csv(HERE/'integrated_table_replay.csv',index=False)
    receipt={'source_commit':'82c6164b0d4630de5316199c92aa405930973168','generator_sha256':hashlib.sha256(Path(native.__file__).read_bytes()).hexdigest(),
        'repro_context_sha256':hashlib.sha256(native.CONTEXT.read_bytes()).hexdigest(),'expected_tables':len(old),'tables_checked':len(summaries),'all_checked_pass':all(r['pass'] for r in summaries),
        'unavailable_tables':sorted(set(old)-seen),'blocks_unavailable':errors,'seconds':time.monotonic()-started,'table_checks':summaries,
        'scope':'Statistical replay of frozen audited minimal-source columns using unchanged published computational functions; not independent collection/preprocessing/runtime audit. Published personnel/history inputs remain inherited reads; separate profiles module independently refits personnel effects.'}
    (HERE/'INTEGRATED_STATISTICS_REPLAY.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2,allow_nan=False))
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['table_checks','blocks_unavailable']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
