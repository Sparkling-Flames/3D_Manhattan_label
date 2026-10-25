#!/usr/bin/env python3
"""Download only selected original Release ZIP members, verifying index, size, CRC."""
from pathlib import Path
import argparse,csv,hashlib,importlib.util,json,shutil,sys,zlib,zipfile
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'recovery/prior_population/research/workers/personnel_population_curves_v2_20261023/cases'
spec=importlib.util.spec_from_file_location('old_range_fetch',OLD/'fetch_case_originals.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--image',action='append',required=True);a=ap.parse_args();dest=HERE/'originals';dest.mkdir(parents=True,exist_ok=True)
 index=OLD/'originals/IMAGE_INDEX.csv';raw=index.read_bytes();assert hashlib.sha256(raw).hexdigest()=='eb2c1537d886138af63f6b1690fe114f42bcabe5fa926cee7482f6be3a76868a';shutil.copy2(index,dest/'IMAGE_INDEX.csv')
 rows=[r for r in csv.DictReader(raw.decode('utf-8-sig').splitlines()) if r['image_code'] in a.image];assert set(a.image)=={r['image_code'] for r in rows}
 receipt=dest/'ORIGINALS_RECEIPT.json';saved=json.loads(receipt.read_text()) if receipt.exists() else {'images':[],'archives':[]};by={r['image_code']:r for r in saved['images']}
 needed=[]
 for r in rows:
  target=dest/(r['image_code']+'.png');previous=OLD/'originals'/target.name
  if target.exists() and r['image_code'] in by:continue
  if previous.exists():
   shutil.copy2(previous,target);data=target.read_bytes();assert len(data)==int(r['bytes']);by[r['image_code']]={**r,'sha256':hashlib.sha256(data).hexdigest(),'local_path':target.name,'origin':'reused_verified_population_case_original','receipt_pointer':str(OLD/'originals/ORIGINALS_RECEIPT.json')};continue
  needed.append(r)
 for arc in sorted({r['archive'] for r in needed}):
  remote=module.RemoteZip(module.BASE+arc,module.SIZES[arc])
  with zipfile.ZipFile(remote) as z:
   for r in needed:
    if r['archive']!=arc:continue
    info=z.getinfo(r['archive_path']);data=z.read(info);assert len(data)==int(r['bytes']);assert zlib.crc32(data)&0xffffffff==info.CRC
    target=dest/(r['image_code']+'.png');target.write_bytes(data);by[r['image_code']]={**r,'sha256':hashlib.sha256(data).hexdigest(),'zip_crc32':f'{info.CRC:08x}','local_path':target.name,'origin':'new_release_zip_range_member','source_url':module.BASE+arc,'verification':'frozen image index SHA, member size and CRC; not complete archive SHA'};print('Saved original '+target.name,flush=True)
  saved['archives'].append({'archive':arc,'full_archive_bytes':module.SIZES[arc],'transferred_bytes':remote.transferred,'ranges':remote.ranges})
 saved['images']=list(by.values());receipt.write_text(json.dumps(saved,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
