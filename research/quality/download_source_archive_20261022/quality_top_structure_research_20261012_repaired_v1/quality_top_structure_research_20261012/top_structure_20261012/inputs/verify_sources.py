#!/usr/bin/env python3
"""Re-read immutable current sources and archive bytes, without re-extraction."""
from __future__ import annotations
import argparse,hashlib,io,json,zipfile
from pathlib import Path
from PIL import Image

def sha(b):return hashlib.sha256(b).hexdigest()
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path.cwd());a=ap.parse_args();r=a.root.resolve();o=r/'top_structure_20261012/inputs'
    previous=json.loads((r/'new_main_snapshot/SOURCE_MANIFEST.json').read_text());old={v['path']:v for v in previous['files']};fresh=[]
    for p in sorted((o/'github_responses').glob('*.json')):
        x=json.loads(p.read_text());assert x['encoding']=='utf-8';b=x['content'].encode();h=sha(b)
        git=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
        assert git==x['sha']==old[x['path']]['git_blob']
        assert h==old[x['path']]['sha256']
        assert b==(r/'new_main_snapshot'/x['path']).read_bytes()
        q=o/'main_snapshot'/x['path'];q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b)
        fresh.append({'path':x['path'],'bytes':len(b),'git_blob':git,'sha256':h,'fresh_fetch_matches_previous_snapshot':True})
    assert len(fresh)==12
    prior=[(r/'delivery/quality_representation_severe_research_20261011.zip','0ab95337296d4ff94b462f124a0e3d299ab382feb00ed4364e0fae8c0db52608'),(r/'recovered_archives/quality_calibration_research_20261011.zip','ca67b40f30646dd039788db367971a18f8019f4ed30dc8aae797ab6e7fcfcb80')]
    archive=[]
    for p,h in prior:
        b=p.read_bytes();assert sha(b)==h
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            assert z.testzip() is None
            entries=[{'path':i.filename,'bytes':i.file_size,'crc32':f'{i.CRC:08x}'} for i in z.infolist()]
        archive.append({'archive':p.name,'bytes':len(b),'sha256':h,'all_crc_read_this_turn':True,'role':'historical_research_package','entries':entries})
    oldarch=json.loads((r/'study_data/current_archive_inventory.json').read_text())
    seen={};photos=[]
    for v in oldarch:
        p=r/'recovered_archives/3d全景图'/v['archive'];b=p.read_bytes();assert sha(b)==v['sha256']
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            assert z.testzip() is None
            entries=[{'path':i.filename,'bytes':i.file_size,'crc32':f'{i.CRC:08x}'} for i in z.infolist()]
            for i in z.infolist():
                if i.filename.lower().endswith(('.png','.jpg','.jpeg')):
                    raw=z.read(i);h=sha(raw)
                    with Image.open(io.BytesIO(raw)) as im:im.load();size=list(im.size)
                    is_original=v['archive'].startswith('pro_quality_original_images_')
                    photos.append({'archive':v['archive'],'internal_path':i.filename,'sha256':h,'resolution':size,'is_original_archive':is_original,'decoded_this_turn':True})
                    if is_original:
                        assert size==[2048,1024]
                        assert h not in seen,(i.filename,seen.get(h))
                        seen[h]=i.filename
        archive.append({'archive':p.name,'bytes':len(b),'sha256':sha(b),'all_crc_read_this_turn':True,'role':'original_images' if p.name.startswith('pro_quality_original_images_') else 'expanded_data_not_original_library','entries':entries})
    index=json.loads((r/'study_data/original_image_index.json').read_text())
    assert len(index)==261 and len(seen)==261
    for x in index:
        raw=Path(x['local_path']).read_bytes();assert sha(raw)==x['sha256'] and sha(raw) in seen
    summary={'actual_main_sha':previous['main_sha'],'main_files_freshly_read':len(fresh),'zip_archives_read':len(archive),'original_images_read_and_decoded':len(seen),'original_image_ids':len({v['image_id'] for v in index}),'original_id_hash_duplicates':0,'base_image_archives_missing':[],'expanded_original_library_count':0,'all_immutable_inputs_unchanged':True,'new_clarification_file':'USER_CLARIFICATIONS_THIS_TURN.txt','new_clarifications_assumed_in_main':False}
    dump(o/'source_verification.json',summary);dump(o/'main_source_manifest.json',fresh);dump(o/'archive_inventory_this_turn.json',archive);dump(o/'image_inventory_this_turn.json',photos)
    print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
