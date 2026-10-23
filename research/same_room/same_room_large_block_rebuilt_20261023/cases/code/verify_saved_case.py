#!/usr/bin/env python3
"""Read every saved case CSV/gzip/image/PDF and verify exact case joins.

This is delivery verification of stored results, not a new experiment.
"""
from pathlib import Path
import argparse,csv,gzip,hashlib,json,sys
import pandas as pd
from PIL import Image
from pypdf import PdfReader

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--case',type=Path,required=True);a=ap.parse_args();p=a.case.resolve()
    e=pd.read_csv(p/'STRICT_ABC_EVENT.csv.gz',keep_default_na=False).iloc[0]
    needed={e[f'team_key_{arm}_{view}'] for arm in 'ABC' for view in 'ab'}
    with gzip.open(p/'SIX_TEAM_NATIVE_GEOMETRY.jsonl.gz','rb') as f:lines=list(f)
    states=[json.loads(line) for line in lines];assert len(states)==6 and {z['team_key'] for z in states}==needed
    scalars=pd.read_csv(p/'SIX_TEAM_NATIVE_SCALARS.csv.gz');assert len(scalars)==6 and set(scalars.team_key)==needed
    index=pd.read_csv(p/'SOURCE_STATE_INDEX.csv');assert len(index)==6
    for r in index.itertuples():
        line=lines[int(r.case_geometry_line_1based)-1];assert hashlib.sha256(line).hexdigest()==r.native_line_sha256;assert json.loads(line)['team_key']==r.team_key
    pools=json.load(gzip.open(p/'FROZEN_TWO_POOLS.json.gz','rt'))['images'];assert {z['pool_id'] for z in pools}=={e.pool_id_a,e.pool_id_b}
    for z in states:
        pool=next(x for x in pools if x['pool_id']==z['pool_id']);raw={r['worker_id']:r for r in pool['records']};assert set(z['member_workers'])<=set(raw);assert z.get('full_state') is not None
    groups=pd.read_csv(p/'tables/IDENTITY_GROUPS.csv');members=pd.read_csv(p/'tables/IDENTITY_MEMBERS.csv')
    n=members.groupby(['team_key','feature_id']).worker_id.nunique().rename('actual_people').reset_index();check=groups.merge(n,on=['team_key','feature_id'],validate='one_to_one');assert (check.identity_support==check.actual_people).all()
    rawused=pd.read_csv(p/'tables/USED_RAW_ANSWERS.csv');assert not rawused.object_id.duplicated().any()
    assert len(rawused)==2*len(set('|'.join(e[x+'_members'] for x in 'DXYZ').split('|')))
    rows=[];root=p.parents[1]
    files=[f for f in p.rglob('*') if f.is_file() and '__pycache__' not in f.parts and f.name not in ['PACKAGE_FILES.csv','CASE_READ_RECEIPT.json']]
    for name in ['select_explanatory_case.py','extract_exact_case.py','render_exact_case.py','describe_structure_case.py','verify_saved_case.py','requirements_case.txt','README_ZH.md']:
        f=p.parent/'code'/name;assert f.is_file();files.append(f)
    for f in sorted(files):
        assert f.stat().st_size>0;count=None;fields=[];status='full_bytes_read'
        if f.name.endswith(('.csv','.csv.gz')):
            opener=gzip.open if f.name.endswith('.gz') else open
            with opener(f,'rt',encoding='utf-8-sig',newline='') as stream:
                reader=csv.DictReader(stream);fields=reader.fieldnames;count=sum(1 for _ in reader)
            status='CSV_read_to_EOF_gzip_CRC_when_applicable'
        elif f.name.endswith('.jsonl.gz'):
            with gzip.open(f,'rt') as stream:count=sum(1 for line in stream if json.loads(line) is not None)
            status='JSONL_gzip_read_to_EOF_CRC_checked'
        elif f.name.endswith(('.json','.json.gz')):
            opener=gzip.open if f.name.endswith('.gz') else open
            with opener(f,'rt',encoding='utf-8-sig') as stream:json.load(stream)
            status='JSON_read_to_EOF_gzip_CRC_when_applicable'
        elif f.suffix=='.png':
            with Image.open(f) as im:im.load();count=im.width*im.height
            status='PNG_fully_decoded'
        elif f.suffix=='.pdf':
            reader=PdfReader(f);count=len(reader.pages)
            for page in reader.pages:
                contents=page.get_contents()
                if contents is not None:contents.get_data()
            assert f.read_bytes().rstrip().endswith(b'%%EOF');status='PDF_parsed_pages_content_and_EOF'
        else:f.read_bytes()
        rows.append(dict(package_relative_path=f.relative_to(root).as_posix(),bytes=f.stat().st_size,sha256=digest(f),rows_or_pixels_or_pages=count,field_count=len(fields),fields='|'.join(fields),read_status=status))
    with (p/'PACKAGE_FILES.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    receipt=dict(event_id=e.event_id,input_commit=e.input_commit,all_listed_files_actual_nonempty=True,all_csv_gzip_read_to_EOF=True,
        exact_case_join_verified=True,geometry_native_lines_byte_exact_verified=True,unique_endpoints=6,full_states=6,raw_pool_records=sum(len(z['records']) for z in pools),used_raw_answers=len(rawused),identity_groups=len(groups),identity_members=len(members),files_in_manifest=len(rows),bytes_in_manifest=sum(r['bytes'] for r in rows),
        figure_PNGs_fully_decoded=sum(r['read_status']=='PNG_fully_decoded' and '/figures/' in r['package_relative_path'] for r in rows),original_PNGs_fully_decoded=sum(r['read_status']=='PNG_fully_decoded' and '/originals/' in r['package_relative_path'] for r in rows),PDFs_parsed=sum(r['read_status']=='PDF_parsed_pages_content_and_EOF' for r in rows),
        new_fusion=0,new_labels=0,note='Directory verification. Final ZIP entries must also be read by the packaging step; this does not substitute for ZIP verification.')
    (p/'CASE_READ_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()
