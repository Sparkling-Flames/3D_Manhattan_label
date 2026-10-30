"""Stage archives with per-file SHA256 and complete nested-format read checks.

Usage: python scripts/package_delivery.py stage03_speed_difficulty [more stages]
       python scripts/package_delivery.py core
No scientific source is deleted or rewritten. Archives can be independently
unpacked into the same parent directory; the study root prefix is preserved.
"""
from pathlib import Path
import argparse,csv,gzip,hashlib,io,json,os,zipfile
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];DEST=ROOT/'delivery';DEST.mkdir(exist_ok=True)
def verify_member(name,data):
    detail={};logical=name
    if name.endswith('.gz'):
        data=gzip.decompress(data);logical=name[:-3];detail['gzip_crc_and_footer']='passed'
    if logical.endswith('.json'):
        obj=json.loads(data.decode('utf-8-sig'));detail['format']='json';detail['top_items']=len(obj) if isinstance(obj,(list,dict)) else 1
    elif logical.endswith('.jsonl'):
        lines=data.decode('utf-8-sig').splitlines();n=0
        for l in lines:
            if l.strip():json.loads(l);n+=1
        detail.update(format='jsonl',rows=n)
    elif logical.endswith(('.csv','.tsv')):
        rows=csv.reader(io.StringIO(data.decode('utf-8-sig')),delimiter='\t' if logical.endswith('.tsv') else ',');n=0;header=next(rows,None);columns=len(header or [])
        for row in rows:
            if row and len(row)!=columns:raise ValueError((name,'CSV width',n,len(row),columns))
            n+=1
        detail.update(format='csv',rows=n,columns=columns)
    elif logical.endswith(('.png','.jpg','.jpeg','.webp')):
        with Image.open(io.BytesIO(data)) as im:im.verify()
        detail['format']='image_verified'
    elif logical.endswith(('.md','.html','.py','.js','.txt','.log','.svg','.patch','.toml','.yaml','.yml','.ini')):
        data.decode('utf-8-sig');detail['format']='utf8_text'
    else:detail['format']='binary_read_complete'
    return detail
def build(stage):
    if stage=='core':
        targets=[ROOT/'source',ROOT/'scripts',ROOT/'stage00_intake',ROOT/'stage06_synthesis',ROOT/'repository_update']
        targets += [ROOT/n for n in ['README.md','REPORT_ZH.md','REPORT_ZH.html','REPRODUCE.md','ENVIRONMENT_LOCK.json','requirements.txt'] if (ROOT/n).exists()]
        archive_name='00_CODE_SOURCES_SYNTHESIS_AND_REPOSITORY_UPDATE.zip'
    elif stage in ['stage02_abc','stage02_prediction']:
        targets=[ROOT/'stage02_same_room'];archive_name='STAGE02A_SAME_ROOM_ABC.zip' if stage=='stage02_abc' else 'STAGE02B_SAME_ROOM_PREDICTION.zip'
    else:
        p=ROOT/stage
        if not p.is_dir():raise FileNotFoundError(p)
        targets=[p];archive_name=stage.upper()+'.zip'
    files=sorted({p for t in targets for p in ([t] if t.is_file() else t.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and not p.name.endswith(('.pyc','.writing','.partial','.tmp'))})
    if stage in ['stage02_abc','stage02_prediction']:
        def abc_file(p):
            q=p.relative_to(ROOT/'stage02_same_room')
            return q.parts[0]=='abc' or q.name in ['EXISTING_VALID_EVENT_SOURCE.csv.gz','VALID_CLASS_RELATION_SOURCE.csv.gz']
        files=[p for p in files if abc_file(p)==(stage=='stage02_abc')]
    manifest=[]
    for p in files:
        manifest.append({'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest()})
    ms=io.StringIO(newline='');w=csv.DictWriter(ms,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(manifest)
    path=DEST/archive_name
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for p in files:
            compression=zipfile.ZIP_STORED if p.suffix.lower() in {'.gz','.png','.jpg','.jpeg','.webp','.zip'} else zipfile.ZIP_DEFLATED
            z.write(p,arcname=ROOT.name+'/'+str(p.relative_to(ROOT)),compress_type=compression)
        z.writestr(ROOT.name+'/delivery_manifests/'+stage+'_MANIFEST.csv',ms.getvalue().encode('utf-8-sig'))
    # Read every archive member completely; validate compressed nested contents.
    verified=[]
    with zipfile.ZipFile(path) as z:
        expected={ROOT.name+'/'+r['path']:r for r in manifest}
        for member in z.infolist():
            if member.is_dir():continue
            data=z.read(member.filename)
            sha=hashlib.sha256(data).hexdigest()
            if member.filename in expected:
                assert sha==expected[member.filename]['sha256']
                assert len(data)==expected[member.filename]['bytes']
            try:
                format_result=verify_member(member.filename,data)
            except Exception as error:
                raise ValueError('Archive member failed complete format validation: '+member.filename) from error
            verified.append({'member':member.filename,'bytes':len(data),'sha256':sha,**format_result})
    receipt={'stage':stage,'archive':archive_name,'bytes':path.stat().st_size,'sha256':hashlib.file_digest(path.open('rb'),'sha256').hexdigest(),'source_files':len(files),'archive_members':len(verified),'full_read_and_crc_passed':True,'nested_gzip_json_csv_images_validated':True,'all_source_hashes_match':True,'verification':verified}
    receipt_path=DEST/(archive_name+'.VALIDATION.json');receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='verification'}),flush=True)
    return receipt
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('stages',nargs='+');args=a.parse_args()
    for stage in args.stages:build(stage)
