"""Read exact committed strict-ABC endpoint artifacts; never run its design."""
import argparse,hashlib,json,subprocess,time
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',required=True);ap.add_argument('--commit',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    repo=Path(a.repo);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    base='research/workers/strict_large_blocks_v21_20261029'
    names=[base+'/endpoints/pools',base+'/RUN_RECEIPT.json',base+'/INPUT_SNAPSHOT.json',base+'/CACHE_COVERAGE.json']
    started=time.monotonic();manifest=[];expected={}
    tree=subprocess.check_output(['git','ls-tree','-r',a.commit,base],cwd=repo,text=True)
    for line in tree.splitlines():
        metadata,name=line.split('\t',1);expected[name]=metadata.split()[2]
    selected=[name for name in expected if any(name==prefix or name.startswith(prefix+'/') for prefix in names)]
    # Read exact blobs directly. ``git archive`` can consult repository-wide
    # attributes and stalled in this partial clone before emitting a first file.
    p=subprocess.Popen(['git','cat-file','--batch'],cwd=repo,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    for name in selected:
        p.stdin.write((expected[name]+'\n').encode());p.stdin.flush()
        header=p.stdout.readline().decode().strip().split()
        assert len(header)==3 and header[0]==expected[name] and header[1]=='blob',header
        size=int(header[2]);content=p.stdout.read(size);assert len(content)==size
        assert p.stdout.read(1)==b'\n'
        path=Path(name);relative=path.relative_to(base);assert '..' not in relative.parts
        blob=hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()
        assert blob==expected[name],name
        target=out/relative;target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert target.read_bytes()==content
        else:target.write_bytes(content)
        manifest.append({'source_commit':a.commit,'source_path':name,'git_blob':blob,'sha256':hashlib.sha256(content).hexdigest(),'bytes':len(content),'local_path':str(target.resolve())})
        if len(manifest)%50==0:print(json.dumps({'files_done':len(manifest),'files_expected':len(selected),'seconds':time.monotonic()-started}),flush=True)
    p.stdin.close()
    assert p.wait()==0
    parts=[r for r in manifest if r['source_path'].endswith('.jsonl.gz')]
    result={'source_commit':a.commit,'extracted_files':len(manifest),'endpoint_chunks':len(parts),'endpoint_bytes':sum(r['bytes'] for r in parts),'files':manifest,'seconds':time.monotonic()-started,'new_fusions':0,'new_scores':0,'working_tree_unchanged':True}
    (out/'EXTRACTION_RECEIPT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files'}),flush=True)

if __name__=='__main__':main()
