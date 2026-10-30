#!/usr/bin/env python3
"""Fetch selected ERP PNGs only, using Release ZIP byte ranges and indexed CRC."""
import argparse,csv,gzip,hashlib,io,json,os,urllib.request,zipfile,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]
BASE='https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/download/quality-original-images-20261015/'
SIZES={'quality_original_images_20261015_01_of_03.zip':165604756,'quality_original_images_20261015_02_of_03.zip':165701699,'quality_original_images_20261015_03_of_03.zip':164293015}
class RemoteZip(io.RawIOBase):
    def __init__(self,url,size):
        self.url=url;self.size=size;self.pos=0;self.transferred=0;self.ranges=[]
        # Public release; no session/cookie/credential involved.
        self.opener=urllib.request.build_opener()
    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.pos
    def seek(self,offset,whence=0):
        self.pos=offset if whence==0 else self.pos+offset if whence==1 else self.size+offset
        return self.pos
    def read(self,n=-1):
        if n<0:n=self.size-self.pos
        n=min(n,self.size-self.pos)
        if n<=0:return b''
        lo=self.pos;hi=lo+n-1
        req=urllib.request.Request(self.url,headers={'Range':f'bytes={lo}-{hi}','User-Agent':'HOHONET-research'})
        with self.opener.open(req,timeout=45) as r:
            if r.status!=206 or r.headers.get('Content-Range')!=f'bytes {lo}-{hi}/{self.size}':
                raise ValueError('Server did not honor bounded ZIP range request')
            data=r.read()
        if len(data)!=n:raise ValueError('Incomplete range')
        self.pos+=n;self.transferred+=n;self.ranges.append([lo,hi])
        return data
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--image',action='append',default=[]);ap.add_argument('--inspect-archives',action='store_true');args=ap.parse_args()
    index=HERE/'source/release_IMAGE_INDEX.csv'
    rows=list(csv.DictReader(index.open(encoding='utf-8-sig')))
    missing=set(args.image)-{r['image_code'] for r in rows}
    if missing:raise ValueError('Not in frozen Release index:'+str(sorted(missing)))
    selected=[r for r in rows if r['image_code'] in args.image]
    out=HERE/'originals';out.mkdir(parents=True,exist_ok=True)
    receipt=out/'ORIGINALS_RECEIPT.json'
    saved=json.loads(receipt.read_text()) if receipt.exists() else {'images':[],'archives':[],'index_local_sha256':hashlib.sha256(index.read_bytes()).hexdigest()}
    previous={r['image_code']:r for r in saved['images']}
    wanted=[r for r in selected if r['image_code'] not in previous or not (out/previous[r['image_code']]['local_path']).exists()]
    archives=sorted(SIZES if args.inspect_archives else {r['archive'] for r in wanted})
    entries=[]
    for arc in archives:
        remote=RemoteZip(BASE+arc,SIZES[arc])
        with zipfile.ZipFile(remote) as z:
            if args.inspect_archives:
                for info in z.infolist():
                    entries.append({'archive':arc,'archive_path':info.filename,'uncompressed_bytes':info.file_size,'compressed_bytes':info.compress_size,'zip_crc32':f'{info.CRC:08x}','header_offset':info.header_offset})
            for r in wanted:
                if r['archive']!=arc:continue
                info=z.getinfo(r['archive_path']);data=z.read(info)
                assert len(data)==int(r['bytes']) and (zlib.crc32(data)&0xffffffff)==info.CRC
                dest=out/(r['image_code']+'.png');temp=dest.with_suffix('.png.partial')
                with temp.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
                temp.replace(dest)
                previous[r['image_code']]={**r,'local_path':dest.name,'sha256':hashlib.sha256(data).hexdigest(),'zip_crc32':f'{info.CRC:08x}','source_url':BASE+arc,'verification':'frozen image index size;ZIP member CRC;only needed member byte ranges'}
                print('saved',dest.name,len(data),flush=True)
        saved['archives'].append({'archive':arc,'full_archive_bytes':SIZES[arc],'transferred_bytes':remote.transferred,'ranges':remote.ranges,'inspection_only':args.inspect_archives and not wanted})
        print('range transfer',arc,remote.transferred,flush=True)
    if entries:
        with (HERE/'source/ZIP_MEMBER_INDEX.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,entries[0].keys());w.writeheader();w.writerows(entries)
    saved['images']=list(previous.values());saved['full_dataset_downloaded']=False
    receipt.write_text(json.dumps(saved,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()

