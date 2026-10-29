"""Record successful persistent uploads and optionally remove verified local ZIP duplicates."""
import argparse,hashlib,json
from pathlib import Path

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda:f.read(1<<20),b''):h.update(part)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--response',required=True);ap.add_argument('--drop-local-zips',action='store_true');args=ap.parse_args()
    root=Path(__file__).resolve().parents[1];folder=root/'delivery'
    results=json.loads(Path(args.response).read_text())['results'];rp=folder/'UPLOAD_RECEIPTS.json';old=json.loads(rp.read_text())
    removed=[];updated=[]
    for item in results:
        assert item['status']=='succeeded',item
        p=Path(item['local_path']);digest=sha(p)
        entry={'name':p.name,'library_file_id':item['library_file_id'],'file_id':item['file_id'],'directory_id':'6ae32cc49d208191a5daeb7833e7671f','sha256':digest,'bytes':p.stat().st_size}
        if p.suffix=='.zip':
            check=json.loads(p.with_name(p.stem+'_READABILITY.json').read_text())
            assert check['passed'] and digest==check['archive_sha256'] and p.stat().st_size==check['archive_bytes']
            entry['files']=check['files']
        matches=[x for x in old if x['name']==p.name]
        assert not matches or all(x['sha256']==digest and x['library_file_id']==entry['library_file_id'] for x in matches)
        if not matches:old.append(entry)
        updated.append(entry)
        if args.drop_local_zips and p.suffix=='.zip':
            removed.append({'local_path':str(p),'sha256':digest,'bytes':p.stat().st_size,'persistent_library_file_id':item['library_file_id']});p.unlink()
    rp.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n')
    note={'successful_uploads':updated,'removed_only_verified_local_zip_duplicates':removed,'source_tree_and_old_versions_preserved':True}
    out=folder/(Path(args.response).stem+'_RECORDED.json');out.write_text(json.dumps(note,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'recorded':len(updated),'local_zip_duplicates_removed':len(removed),'receipt':str(out)},ensure_ascii=False))

if __name__=='__main__':main()
