"""Recover unchanged selected Release PNGs with indexed ZIP CRC verification.

Reads only the needed original members; it never generates or edits a photo.
Existing copies are accepted only when their exact bytes satisfy the frozen ZIP
member size and CRC. HTTP transfers verify the requested Content-Range.
"""
from __future__ import annotations
import concurrent.futures,hashlib,json,struct,urllib.request,zlib
from pathlib import Path
import pandas as pd
from PIL import Image
from mechanism_core import ROOT,OUT,save_csv,save_json,sha,read_json

SOURCE=ROOT/'research/workers/personnel_ac_v21_20261030/stage06_cases/source'
RELEASE='https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/download/quality-original-images-20261015/'
SIZES={'quality_original_images_20261015_01_of_03.zip':165604756,'quality_original_images_20261015_02_of_03.zip':165701699,'quality_original_images_20261015_03_of_03.zip':164293015}

def ranged(url,size,lo,hi):
    req=urllib.request.Request(url,headers={'Range':f'bytes={lo}-{hi}','User-Agent':'HOHONET-current-DSTRUCT-AC-originals'})
    with urllib.request.urlopen(req,timeout=60) as r:
        assert r.status==206 and r.headers.get('Content-Range')==f'bytes {lo}-{hi}/{size}','Server did not honor exact bounded request.'
        data=r.read()
    assert len(data)==hi-lo+1
    return data

def fetch_one(row):
    code=row['image_code'];dest=OUT/'originals'/(code+'.png');crc=int(str(row['zip_crc32']),16)
    candidates=[dest,
        ROOT/'research/workers/current_class_interpretation_20261104/examples/originals'/(code+'.png'),
        ROOT.parent/'HOHONET/research/statistics/research_explorer_v1_r2_20261017/v21-manual-order/original_images'/(row['image_id']+'.png')]
    data=None;retrieval=None
    for p in candidates:
        if not p.exists():continue
        b=p.read_bytes()
        if len(b)==int(row['uncompressed_bytes']) and zlib.crc32(b)==crc:
            data=b;retrieval='existing_original_exact_size_and_ZIP_CRC';break
    archive=row['archive'];url=RELEASE+archive;transferred=0
    if data is None:
        off=int(row['header_offset']);header=ranged(url,SIZES[archive],off,off+29);transferred+=len(header)
        sig,version,flags,compression,mtime,mdate,localcrc,cs,us,namelen,extralen=struct.unpack('<IHHHHHIIIHH',header)
        assert sig==0x04034b50 and not(flags&1) and compression in (0,8)
        start=off+30;stop=start+namelen+extralen+int(row['compressed_bytes'])-1
        payload=ranged(url,SIZES[archive],start,stop);transferred+=len(payload)
        filename=payload[:namelen].decode('utf-8' if flags&0x800 else 'cp437')
        assert filename==row['archive_path']
        compressed=payload[namelen+extralen:]
        data=zlib.decompress(compressed,-15) if compression==8 else compressed
        retrieval='release_exact_member_byte_ranges'
    assert len(data)==int(row['uncompressed_bytes'])==int(row['bytes']) and zlib.crc32(data)==crc
    dest.parent.mkdir(parents=True,exist_ok=True);tmp=dest.with_suffix('.png.writing');tmp.write_bytes(data);tmp.replace(dest)
    with Image.open(dest) as im:
        assert im.size==(int(row['width']),int(row['height']));im.verify()
    return dict(row,path=str(dest.relative_to(OUT)),source_release_url=url,retrieval=retrieval,
                sha256=hashlib.sha256(data).hexdigest(),transferred_bytes=transferred,original_bytes_unchanged=True)

def main():
    codes=set(pd.read_csv(OUT/'CASE_SELECTION.csv').image)
    ac_codes=set(codes)
    appendix=OUT/'cases/APPENDIX_EXISTING_ABC.json.gz'
    if appendix.exists():codes.add(read_json(appendix)['image'])
    saved=OUT/'source/SELECTED_ORIGINAL_IMAGE_INDEX.csv'
    d=pd.read_csv(saved,dtype=str) if saved.exists() else pd.DataFrame()
    if d.empty or not codes<=set(d.image_code):
        index=pd.read_csv(SOURCE/'release_IMAGE_INDEX.csv',dtype=str);index=index[index.image_code.isin(codes)]
        members=pd.read_csv(SOURCE/'ZIP_MEMBER_INDEX.csv',dtype=str)
        d=index.merge(members,on=['archive','archive_path'],validate='one_to_one')
    d=d[d.image_code.isin(codes)];assert set(d.image_code)==codes
    save_csv(OUT/'source/SELECTED_ORIGINAL_IMAGE_INDEX.csv',d)
    with concurrent.futures.ThreadPoolExecutor(3) as ex:receipts=list(ex.map(fetch_one,d.to_dict('records')))
    save_json(OUT/'ORIGINAL_IMAGE_RECEIPT.json',dict(images=receipts,count=len(receipts),AC_case_originals=len(ac_codes),existing_ABC_appendix_originals=len(codes-ac_codes),release=RELEASE,
        source_selected_index_sha256=sha(saved),
        source_index_sha256=sha(SOURCE/'release_IMAGE_INDEX.csv') if (SOURCE/'release_IMAGE_INDEX.csv').exists() else None,
        source_zip_index_sha256=sha(SOURCE/'ZIP_MEMBER_INDEX.csv') if (SOURCE/'ZIP_MEMBER_INDEX.csv').exists() else None,
        photo_edits=0,resampling_of_saved_originals=False))
    print(json.dumps(dict(images=len(receipts),total_bytes=sum(int(r['bytes']) for r in receipts),transferred_bytes=sum(r['transferred_bytes'] for r in receipts))),flush=True)

if __name__=='__main__':main()
