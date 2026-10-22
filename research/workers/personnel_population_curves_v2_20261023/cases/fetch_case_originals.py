"""Fetch just five original PNG members through verified ZIP range reads."""
from pathlib import Path
import csv,hashlib,io,json,urllib.request,zipfile,zlib
OUT=Path(__file__).resolve().parent/'originals'
BASE='https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/download/quality-original-images-20261015/'
SIZES={'quality_original_images_20261015_01_of_03.zip':165604756,'quality_original_images_20261015_02_of_03.zip':165701699,'quality_original_images_20261015_03_of_03.zip':164293015}
WANTED=['UwV83HsGsw3-12','pa4otMbVnkk-09','UwV83HsGsw3-09','uNb9QFRL6hY-60','B6ByNegPMKs-33']

class RemoteZip(io.RawIOBase):
    def __init__(self,url,size):self.url=url;self.size=size;self.pos=0;self.transferred=0;self.ranges=[]
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
        with urllib.request.urlopen(req,timeout=45) as r:
            if r.status!=206 or r.headers.get('Content-Range')!=f'bytes {lo}-{hi}/{self.size}':raise ValueError('Server did not honor bounded ZIP range request')
            data=r.read()
        if len(data)!=n:raise ValueError('Incomplete range')
        self.pos+=n;self.transferred+=n;self.ranges.append([lo,hi]);return data

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    index=(OUT/'IMAGE_INDEX.csv').read_bytes()
    assert hashlib.sha256(index).hexdigest()=='eb2c1537d886138af63f6b1690fe114f42bcabe5fa926cee7482f6be3a76868a'
    rows=[r for r in csv.DictReader(index.decode('utf-8-sig').splitlines()) if r['image_code'] in WANTED]
    receipts=[];archives=[]
    for arc in sorted({r['archive'] for r in rows}):
        remote=RemoteZip(BASE+arc,SIZES[arc])
        with zipfile.ZipFile(remote) as z:
            for r in rows:
                if r['archive']!=arc:continue
                info=z.getinfo(r['archive_path']);data=z.read(info)
                assert len(data)==int(r['bytes']) and zlib.crc32(data)&0xffffffff==info.CRC
                dest=OUT/(r['image_code']+'.png');dest.write_bytes(data)
                receipts.append(dict(r,local_path=dest.name,sha256=hashlib.sha256(data).hexdigest(),zip_crc32=f'{info.CRC:08x}',source_url=BASE+arc,verification='Release index hash, bounded ZIP member transfer, member CRC and size; complete archive SHA not recomputed'))
                print('Saved '+dest.name,flush=True)
        archives.append(dict(archive=arc,full_archive_bytes=SIZES[arc],transferred_bytes=remote.transferred,ranges=remote.ranges))
    (OUT/'ORIGINALS_RECEIPT.json').write_text(json.dumps(dict(images=receipts,archives=archives,total_transferred=sum(a['transferred_bytes'] for a in archives),full_dataset_not_extracted=True),ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
