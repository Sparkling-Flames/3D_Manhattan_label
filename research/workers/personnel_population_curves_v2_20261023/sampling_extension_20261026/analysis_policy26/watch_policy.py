"""Incremental paired-policy analysis; no partial pool is analysed."""
import argparse,json,subprocess,sys,time
from pathlib import Path
import pandas as pd

def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);a=p.parse_args();base=a.base.resolve()
    script=Path(__file__).with_name('analyze_policy32.py');meta=pd.read_csv(base/'analysis_policy26/COMMON_IMAGES.csv')
    while True:
        done=[x for x in meta.pool_id if (base/'analysis_policy26/parts'/x/'RECEIPT.json').exists()]
        ready=[x for x in meta.pool_id if x not in done and (base/'new_endpoints26/stage1/prefix_values'/(x+'.receipt.json')).exists()]
        for pid in ready:
            subprocess.run([sys.executable,str(script),'--base',str(base),'--only-pool',pid],check=True)
        receipt=dict(expected_pools=len(meta),complete_pools=len(done)+len(ready),complete=(len(done)+len(ready)==len(meta)),
                     missing_pool_ids=sorted(set(meta.pool_id)-set(done)-set(ready)))
        path=base/'analysis_policy26/WATCH_STATUS.json';temp=path.with_suffix('.tmp');temp.write_text(json.dumps(receipt,indent=2));temp.replace(path)
        if receipt['complete']:
            subprocess.run([sys.executable,str(script),'--base',str(base),'--aggregate'],check=True);break
        time.sleep(30)

if __name__=='__main__':main()
