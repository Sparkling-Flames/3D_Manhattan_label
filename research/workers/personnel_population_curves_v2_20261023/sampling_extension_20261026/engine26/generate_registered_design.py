"""Official from-seed design entry: unchanged selection, short pool transactions.

The original registrar's selection functions are retained. Its four long-open
global writers are replaced with complete per-pool gzip files. This changes
storage only. No fusion is performed, no Q values enter seeds or selections.
"""
from pathlib import Path
import argparse,csv,io,json
import register_extension as original
from execute_extension import save_csv,savejson,atomic_bytes

GLOBAL={'NEW_EXACT_ORDER_DESIGN.csv.gz','NEW_PREFIX_TEAM_LINKS.csv.gz',
        'ENDPOINT_DEPENDENCIES.csv.gz','NEW_NATIVE_ENDPOINT_REQUESTS.csv.gz'}

class ShortWriter:
    def __init__(self,path,fields):
        self.path=Path(path);self.fields=fields;self.rows=[];self.n=0;self.parts=[];self.pid=None;self.global_file=self.path.name in GLOBAL
    def put(self,row):
        if self.global_file and self.pid is not None and row['pool_id']!=self.pid:self.flush()
        self.pid=row.get('pool_id');self.rows.append({k:row.get(k,'') for k in self.fields});self.n+=1
    def flush(self):
        if not self.rows:return
        if self.global_file:
            path=self.path.parent/'logical_shards'/self.path.name.replace('.csv.gz','')/(self.pid+'.csv.gz')
        else:path=self.path
        if path.suffix=='.gz':
            cols=save_csv(path,self.rows)
        else:
            s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=self.fields,lineterminator='\n');w.writeheader();w.writerows(self.rows);atomic_bytes(path,s.getvalue().encode('utf-8-sig'));cols=len(self.fields)
        self.parts.append(dict(file=str(path),rows=len(self.rows),columns=cols,sha256=original.sha(path),complete_EOF=True));self.rows=[]
    def close(self):
        self.flush();assert sum(r['rows'] for r in self.parts)==self.n
        if self.global_file:
            if self.path.name=='NEW_EXACT_ORDER_DESIGN.csv.gz':
                rows=[]
                for p in self.parts:rows.extend(original.csvread(p['file']))
                save_csv(self.path,rows)
            manifest=self.path.with_suffix('').with_suffix('.manifest.json')
            receipt=dict(file=str(manifest),rows=self.n,columns=len(self.fields),parts=self.parts,complete_EOF=True)
            savejson(manifest,receipt);return receipt
        return self.parts[0] if self.parts else dict(file=str(self.path),rows=0,columns=len(self.fields),complete_EOF=True)

def run(base):
    original.Writer=ShortWriter
    original.run(base,natural=208,stage_n=104,policy_bases=16)
    from finalize_registration_shards import run as finish
    return finish(base)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--base',type=Path,required=True);args=a.parse_args();r=run(args.base)
    print(json.dumps({k:v for k,v in r.items() if k!='parts'}))
