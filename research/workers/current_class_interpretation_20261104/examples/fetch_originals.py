#!/usr/bin/env python3
"""Fetch only four required original PNG entries from the cited release ZIPs.

Uses validated HTTP byte ranges and ZipFile CRC validation; no image resampling.
Run from anywhere after the repo source IMAGE_INDEX.csv is available.
"""
from pathlib import Path
import csv, hashlib, io, json, shutil, urllib.request, zipfile, zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RELEASE = 'https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/download/quality-original-images-20261015/'
ASSET_BYTES = {
    'quality_original_images_20261015_01_of_03.zip': 165604756,
    'quality_original_images_20261015_02_of_03.zip': 165701699,
    'quality_original_images_20261015_03_of_03.zip': 164293015,
}
CODES = ['jtcxE69GiFV-10', 'jtcxE69GiFV-09', 'jtcxE69GiFV-26', 'yqstnuAEVhm-01']

class RemoteRangeFile(io.RawIOBase):
    def __init__(self, url, length):
        self.url, self.length, self.pos = url, length, 0
        self.blocks = []
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.length + off
        return self.pos
    def read(self, size=-1):
        if size < 0: size = self.length - self.pos
        end = min(self.length, self.pos + size)
        if end <= self.pos: return b''
        for a, b, data in self.blocks:
            if a <= self.pos and end <= b:
                result = data[self.pos-a:end-a]; self.pos=end; return result
        a = self.pos
        req = urllib.request.Request(self.url, headers={
            'User-Agent':'HOHONET-current-class-annotation-examples',
            'Range':f'bytes={a}-{end-1}'})
        with urllib.request.urlopen(req, timeout=60) as response:
            expected = f'bytes {a}-{end-1}/{self.length}'
            if response.status != 206 or response.headers.get('Content-Range') != expected:
                raise RuntimeError(f'Unvalidated byte range: {response.status}, {response.headers.get("Content-Range")}')
            data=response.read()
        if len(data) != end-a: raise RuntimeError('Truncated range')
        self.blocks.append((a,end,data)); self.pos=end; return data

def main():
    index_path = ROOT/'analysis_results/quality/quality_scope_model_handoff_20261015/original_images/IMAGE_INDEX.csv'
    index = {r['image_code']:r for r in csv.DictReader(index_path.open(encoding='utf-8-sig'))}
    out = HERE/'originals'; out.mkdir(exist_ok=True)
    archives = {}; receipt = []
    old = ROOT.parent/'HOHONET/research/statistics/research_explorer_v1_r2_20261017/v21-manual-order/original_images'
    for code in CODES:
        r=index[code]; asset=r['archive']; url=RELEASE+asset
        if asset not in archives: archives[asset]=zipfile.ZipFile(RemoteRangeFile(url,ASSET_BYTES[asset]))
        z=archives[asset]; info=z.getinfo(r['archive_path'])
        dest=out/(code+'.png'); prior=old/(r['image_id']+'.png')
        local=dest if dest.is_file() else prior
        data=local.read_bytes() if local.is_file() else None
        if data is not None and (len(data)!=info.file_size or zlib.crc32(data)!=info.CRC): data=None
        retrieval='same_crc_existing_original' if data is not None else 'release_zip_validated_byte_ranges'
        if data is None: data=z.read(info)
        if len(data)!=int(r['bytes']): raise ValueError('Index size mismatch')
        dest.write_bytes(data)
        receipt.append(dict(image_code=code,image_id=r['image_id'],path='originals/'+dest.name,
            width=int(r['width']),height=int(r['height']),bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
            zip_crc32=f'{info.CRC:08x}',release_url=url,archive_entry=r['archive_path'],
            source_path=r['source_path'],retrieval=retrieval))
        print(code,retrieval,len(data),flush=True)
    (HERE/'ORIGINAL_IMAGE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for z in archives.values(): z.close()

if __name__=='__main__': main()
