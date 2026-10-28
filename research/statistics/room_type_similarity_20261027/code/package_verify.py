#!/usr/bin/env python3
"""Build/verify actual delivery archives, including compressed member EOF and keys."""
from pathlib import Path
import argparse,csv,gzip,hashlib,io,json,zipfile
from PIL import Image

def sha(b):return hashlib.sha256(b).hexdigest()

def inspect_archive(p):
    rows=[]; csv_sets={}; manifest=None
    with zipfile.ZipFile(p) as z:
        assert z.testzip() is None
        assert len(set(z.namelist()))==len(z.namelist())
        for n in z.namelist():
            if n.endswith('/'):continue
            data=z.read(n);r={'path':n,'bytes':len(data),'sha256':sha(data)}
            raw=gzip.decompress(data) if n.endswith('.gz') else data
            stem=n[:-3] if n.endswith('.gz') else n
            if stem.endswith('.csv'):
                reader=csv.reader(io.StringIO(raw.decode('utf-8-sig')))
                fields=next(reader,[]);count=0;objects=set();tuplekeys=set()
                assert fields, f'No CSV header: {n}'
                assert len(set(fields))==len(fields),f'Duplicate fields: {n}'
                obj=fields.index('object_id') if 'object_id' in fields else None
                for row in reader:
                    assert len(row)==len(fields),(n,count+2,len(row),len(fields))
                    count+=1
                    if obj is not None:objects.add(row[obj])
                r.update(rows=count,fields=fields)
                if obj is not None:r['unique_object_ids']=len(objects);csv_sets[Path(stem).name]=objects
            elif stem.endswith('.jsonl'):
                count=0;objects=set()
                for line in raw.decode('utf-8').splitlines():
                    if not line.strip():continue
                    x=json.loads(line);count+=1
                    if 'object_id' in x:objects.add(str(x['object_id']))
                r['jsonl_records']=count
                if objects:r['unique_object_ids']=len(objects);csv_sets[Path(stem).name]=objects
            elif stem.endswith('.json'):
                x=json.loads(raw.decode('utf-8-sig'));r['json_valid']=True
                if Path(n).name=='PACKAGE_MANIFEST.json':manifest=x
            elif stem.endswith(('.md','.py','.txt','.html','.sh','.css','.js','.mjs')):
                raw.decode('utf-8-sig');r['utf8_valid']=True
            elif stem.lower().endswith(('.png','.jpg','.jpeg','.webp')):
                with Image.open(io.BytesIO(raw)) as im:
                    im.load()
                    r.update(image_decoded=True,image_size=list(im.size),image_mode=im.mode)
            rows.append(r)
        if manifest:
            for x in manifest['files']:
                data=z.read(x['archive_path']);assert sha(data)==x['sha256'] and len(data)==x['bytes'],x['archive_path']
    associations=[]
    for l,r in [('CASE_ALL_FORMAL_ANSWERS.csv','CASE_GEOMETRY.jsonl'),('annotations.csv','annotation_geometry.jsonl')]:
        if l in csv_sets and r in csv_sets:
            assert csv_sets[l]==csv_sets[r],(l,r)
            associations.append({'left':l,'right':r,'matched_objects':len(csv_sets[l])})
    return {'archive':str(p.resolve()),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes()),'files':len(rows),
            'csv_rows':sum(r.get('rows',0) for r in rows),'jsonl_records':sum(r.get('jsonl_records',0) for r in rows),
            'all_members_read_to_eof':True,'gzip_decoded_to_eof':True,'manifest_hashes_verified':manifest is not None,
            'associations':associations,'members':rows}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--zip',type=Path,required=True);ap.add_argument('--receipt',type=Path,required=True);a=ap.parse_args()
    r=inspect_archive(a.zip);a.receipt.parent.mkdir(parents=True,exist_ok=True);a.receipt.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k!='members'},ensure_ascii=False))

if __name__=='__main__':main()
