"""Verify pinned source bytes without changing the accepted repository overlay."""
from pathlib import Path
import hashlib,json
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent

def main():
    table=pd.read_csv(OUT/'inputs/PINNED_CORE_INPUTS.csv');checks=[]
    for r in table.to_dict('records'):
        path=ROOT/r['path']
        if not path.is_file():
            checks.append(dict(path=r['path'],status='source_not_materialized',expected_sha256=r['sha256']))
            continue
        b=path.read_bytes();h=hashlib.sha256(b).hexdigest()
        blob=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
        checks.append(dict(path=r['path'],status='matches' if h==r['sha256'] and blob==r['git_blob'] else 'different',expected_sha256=r['sha256'],observed_sha256=h))
    out=dict(source_commit=table.commit.iloc[0],checks=checks,changed_sources=sum(r['status']=='different' for r in checks),
             missing_sources=sum(r['status']=='source_not_materialized' for r in checks),
             note='No automatic replacement or reference/classification change. Use the input manifest to restore missing source files at the pinned commit.')
    (OUT/'inputs/LOCAL_VERSION_VERIFICATION.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps(out,ensure_ascii=False))
    assert out['changed_sources']==0,'A pinned source differs; inspect its version before reusing this analysis.'

if __name__=='__main__':main()
