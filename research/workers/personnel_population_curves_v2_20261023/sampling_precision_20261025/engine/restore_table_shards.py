"""Restore published logical row shards, verifying actual gzip contents to EOF."""
from pathlib import Path
import argparse,csv,gzip,hashlib,io,json
from package_table_shards import sha_file,canonical_update,key_update


def restore(manifest_path,output,only=None):
    manifest=json.loads(manifest_path.read_text());base=manifest_path.parent;output.mkdir(parents=True,exist_ok=True)
    receipts=[]
    for ds in manifest['datasets']:
        if only and ds['source_filename'] not in only:continue
        kind=ds['kind'];fields=ds['columns'];target=output/ds['source_filename'];temp=target.with_name(target.name+'.restoring')
        whole=hashlib.sha256();wholekey=hashlib.sha256();total=0
        with temp.open('wb') as raw:
            with gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=5,mtime=0) as z:
                with io.TextIOWrapper(z,encoding='utf-8',newline='') as out:
                    if kind=='csv':writer=csv.writer(out,lineterminator='\n');writer.writerow(fields);ki=fields.index('team_key')
                    for part in ds['parts']:
                        path=base/part['file'];assert sha_file(path)==part['sha256'],str(path)
                        ph=hashlib.sha256();pk=hashlib.sha256();n=0
                        with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:
                            if kind=='csv':reader=csv.reader(f);assert next(reader)==fields
                            else:reader=(json.loads(line) for line in f)
                            for row in reader:
                                if kind=='csv':
                                    assert len(row)==len(fields);writer.writerow(row);key=row[ki]
                                else:
                                    assert list(row)==fields
                                    out.write(json.dumps(row,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n');key=row['team_key']
                                canonical_update(ph,row);canonical_update(whole,row)
                                key_update(pk,key);key_update(wholekey,key);n+=1;total+=1
                        assert n==part['rows'] and ph.hexdigest()==part['semantic_sha256']
                        assert pk.hexdigest()==part['ordered_team_key_sha256']
        assert total==ds['rows'] and whole.hexdigest()==ds['semantic_sha256']
        assert wholekey.hexdigest()==ds['ordered_team_key_sha256']
        temp.replace(target)
        # Validate the reconstructed file itself, not only its source shards.
        h=hashlib.sha256();n=0
        with gzip.open(target,'rt',encoding='utf-8-sig',newline='') as f:
            if kind=='csv':reader=csv.reader(f);assert next(reader)==fields
            else:reader=(json.loads(line) for line in f)
            for row in reader:canonical_update(h,row);n+=1
        assert n==total and h.hexdigest()==ds['semantic_sha256']
        r=dict(file=str(target),rows=n,columns=len(fields),semantic_sha256=h.hexdigest(),
            compressed_sha256=sha_file(target),all_input_and_restored_gzip_read_to_eof=True)
        receipts.append(r);print(json.dumps(r,ensure_ascii=False),flush=True)
    (output/'RESTORED_TABLE_VALIDATION.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path);p.add_argument('--only',action='append')
    a=p.parse_args();restore(a.manifest,a.output or a.manifest.parent,a.only)
