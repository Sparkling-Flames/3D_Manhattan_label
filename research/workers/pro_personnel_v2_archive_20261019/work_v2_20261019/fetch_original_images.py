"""Fetch the user-specified public Release, verify archive hashes, extract current images."""
from pathlib import Path
import concurrent.futures, csv, hashlib, json, urllib.request, zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work_v2_20261019/original_images'
BASE='https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/download/quality-original-images-20261015/'
ASSETS={
 'IMAGE_INDEX.csv':('eb2c1537d886138af63f6b1690fe114f42bcabe5fa926cee7482f6be3a76868a',74379),
 'MANIFEST.json':('255f42a9db12476445def78ef5aa58e4c38466c76bb851dc06ae2b47a3db4d51',703),
 'quality_original_images_20261015_01_of_03.zip':('629287aa9de2273a5e1d432cf0f6107f4d5f31468511f76cdc387124a0ce1bab',165604756),
 'quality_original_images_20261015_02_of_03.zip':('7d2ccaed54f754ed4e92eb8a064f08a94f8d4d1f82eac8373b84be71a63b003b',165701699),
 'quality_original_images_20261015_03_of_03.zip':('014cac37de5b95d09def60d21e32f329feb890bb4ca572143cebe7fec2b5f1f8',164293015)}

def fetch(name):
    sha,size=ASSETS[name];p=OUT/'archives'/name;p.parent.mkdir(parents=True,exist_ok=True)
    if not p.exists() or p.stat().st_size!=size or hashlib.sha256(p.read_bytes()).hexdigest()!=sha:
        with urllib.request.urlopen(BASE+name,timeout=50) as src,p.open('wb') as dst:
            while data:=src.read(1024*1024):dst.write(data)
    if p.stat().st_size!=size or hashlib.sha256(p.read_bytes()).hexdigest()!=sha:raise ValueError('Release digest mismatch '+name)
    print('verified '+name,flush=True);return dict(name=name,bytes=size,sha256=sha,url=BASE+name)

def run():
    OUT.mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:assets=list(ex.map(fetch,ASSETS))
    current=list(csv.DictReader((ROOT/'repo_main_20261019/research/workers/pro_personnel_v2_20261019/IMAGE_INDEX.csv').open(encoding='utf-8-sig')))
    release={r['image_id']:r for r in csv.DictReader((OUT/'archives/IMAGE_INDEX.csv').open(encoding='utf-8-sig'))}
    archives={name:zipfile.ZipFile(OUT/'archives'/name) for name in ASSETS if name.endswith('.zip')}
    results=[]
    for row in current:
        original=release.get(row['image_id']);x=dict(row)
        if original:
            arc=archives[original['archive']];data=arc.read(original['archive_path'])
            assert len(data)==int(original['bytes'])
            ext=Path(original['archive_path']).suffix
            dest=OUT/'images'/(row['image_id']+ext);dest.parent.mkdir(exist_ok=True);dest.write_bytes(data)
            x.update(local_path=str(dest.relative_to(ROOT)),original_bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),crc_checked=True,status='original_release_bytes_verified')
        else:x.update(local_path=row.get('preview_path'),status='repository_preview_only_no_original_release')
        results.append(x)
    for arc in archives.values():arc.close()
    manifest=dict(assets=assets,current_images=len(results),originals=sum(x['status']=='original_release_bytes_verified' for x in results),images=results,visual_review_status='not_automatically_reviewed_by_download')
    (OUT/'ORIGINAL_IMAGE_AUDIT.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:manifest[k] for k in ['current_images','originals','visual_review_status']},ensure_ascii=False),flush=True)
if __name__=='__main__':run()
