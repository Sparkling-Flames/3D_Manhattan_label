"""Verify provided originals; fetch only absent bytes for all 36 exceptions."""
from pathlib import Path
import csv,hashlib,json,shutil,sys,zipfile,zlib
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parent;OUT=ROOT/'stage01_half_team'
sys.path.insert(0,str(ROOT/'scripts/vendor'))
from fetch_originals_range import RemoteZip,BASE,SIZES
def main():
    index=OUT/'originals/FROZEN_RELEASE_IMAGE_INDEX.csv'
    if not index.exists():index=WS/'HOHONET_v21_reaudit_20261029/stage04_cases/six_cases/source/release_IMAGE_INDEX.csv'
    zindex=WS/'HOHONET_v21_reaudit_20261029/stage04_cases/six_cases/source/ZIP_MEMBER_INDEX.csv'
    wanted={r['image'] for r in csv.DictReader((OUT/'LATEST_HALF_ALL_EXCEPTION_IMAGES.csv').open(encoding='utf-8-sig'))}
    rows=[r for r in csv.DictReader(index.open(encoding='utf-8-sig')) if r['image_code'] in wanted]
    saved_receipt=OUT/'originals/ORIGINALS_VERIFICATION.json'
    if saved_receipt.exists():
        crc={(r['archive'],r['archive_path']):r['zip_crc32'] for r in json.loads(saved_receipt.read_text())}
    else:crc={(r['archive'],r['archive_path']):r['zip_crc32'] for r in csv.DictReader(zindex.open(encoding='utf-8-sig'))}
    assert len(rows)==len(wanted)==36
    folder=OUT/'originals';folder.mkdir(parents=True,exist_ok=True)
    oldbases=[WS/'HOHONET_v21_reaudit_20261029/stage04_cases',WS/'HOHONET_v21_AC_population_20261029/stage06_cases',WS/'audit_cases',WS/'audit_case_vfua']
    local={}
    for base in oldbases:
        for p in base.rglob('*.png'):
            if p.stem in wanted and 'originals' in p.parts:local.setdefault(p.stem,[]).append(p)
    receipts=[];missing=[]
    for row in rows:
        dest=folder/(row['image_code']+'.png');candidates=[dest]+local.get(row['image_code'],[]);found=None
        for p in candidates:
            if not p.exists() or p.stat().st_size!=int(row['bytes']):continue
            d=p.read_bytes()
            if f'{zlib.crc32(d)&0xffffffff:08x}'==crc[(row['archive'],row['archive_path'])]:found=p;break
        if found:
            if found!=dest:shutil.copyfile(found,dest)
            receipts.append({**row,'acquisition':'existing_exact_original','source':str(found),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'zip_crc32':crc[(row['archive'],row['archive_path'])]})
        else:missing.append(row)
    for archive in sorted({r['archive'] for r in missing}):
        remote=RemoteZip(BASE+archive,SIZES[archive])
        with zipfile.ZipFile(remote) as z:
            for row in missing:
                if row['archive']!=archive:continue
                d=z.read(row['archive_path']);assert len(d)==int(row['bytes'])
                c=f'{zlib.crc32(d)&0xffffffff:08x}';assert c==crc[(archive,row['archive_path'])]
                p=folder/(row['image_code']+'.png');p.write_bytes(d)
                receipts.append({**row,'acquisition':'public_release_exact_member_range','source':BASE+archive,'sha256':hashlib.sha256(d).hexdigest(),'zip_crc32':c})
                print('original',row['image_code'],len(d),flush=True)
    receipt_path=folder/('ORIGINALS_RECHECK.json' if saved_receipt.exists() else 'ORIGINALS_VERIFICATION.json')
    receipt_path.write_text(json.dumps(receipts,ensure_ascii=False,indent=2))
    if index.resolve()!=(folder/'FROZEN_RELEASE_IMAGE_INDEX.csv').resolve():shutil.copyfile(index,folder/'FROZEN_RELEASE_IMAGE_INDEX.csv')
    print('verified originals',len(receipts),'new range images',len(missing),flush=True)
if __name__=='__main__':main()
