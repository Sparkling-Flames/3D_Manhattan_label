"""Read-only retrieval of pinned research sources and caches. Honors configured proxy/CA."""
from pathlib import Path
import urllib.request,ssl,os,json,hashlib,time,argparse,concurrent.futures
ROOT=Path(__file__).resolve().parents[1]
COMMIT='e1873bfadc1d0e61499809c91fba9dc39c717f83'
REPO='Sparkling-Flames/3D_Manhattan_label'
CTX=ssl.create_default_context(cafile=os.environ.get('REQUESTS_CA_BUNDLE'))

def fetch(item):
    rel=item['path'];dest=ROOT/'source/repo'/rel;dest.parent.mkdir(parents=True,exist_ok=True)
    url=item.get('url') or f'https://raw.githubusercontent.com/{REPO}/{COMMIT}/{rel}'
    expected=item.get('size');reused=dest.exists() and (expected is None or dest.stat().st_size==expected)
    if not reused:
        tmp=dest.with_name(dest.name+'.download')
        for attempt in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'HOHONET-research-reuse'}),context=CTX,timeout=90) as r,tmp.open('wb') as f:
                    while True:
                        chunk=r.read(1024*1024)
                        if not chunk:break
                        f.write(chunk)
                if expected is not None:assert tmp.stat().st_size==expected,(rel,tmp.stat().st_size,expected)
                tmp.replace(dest);break
            except Exception:
                if attempt==2:raise
                time.sleep(1+attempt)
    h=hashlib.sha256()
    with dest.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    row=dict(path=rel,url=url,bytes=dest.stat().st_size,sha256=h.hexdigest(),reused_local=reused)
    print(json.dumps({k:v for k,v in row.items() if k not in ('url','sha256')},ensure_ascii=False),flush=True)
    return row

def main():
    ap=argparse.ArgumentParser();ap.add_argument('plan');args=ap.parse_args()
    plan=Path(args.plan);j=json.loads(plan.read_text());items=j['files']
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:rows=list(ex.map(fetch,items))
    out=ROOT/'stage01_intake';out.mkdir(exist_ok=True)
    (out/(plan.stem+'_FETCH_RECEIPT.json')).write_text(json.dumps({'commit':COMMIT,'files':rows},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
