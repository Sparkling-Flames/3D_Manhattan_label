"""Fetch only Release archives needed for explicit Part A case images.

Archive download and verification reuse the preserved Pro fetch function. Only
requested image bytes are extracted, with both archive and old audited image
SHA256 checked. Downloading is not visual inspection.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse,hashlib,importlib.util,json,zipfile,datetime
HERE=Path(__file__).resolve().parent;WORK=HERE.parent;OLD=WORK/'recovered/work_v2_20261019'

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--cases',type=Path,default=HERE/'CASE_SELECTION.json');args=ap.parse_args()
    selection=json.loads(args.cases.read_text());cases=selection.get('cases',[]) if isinstance(selection,dict) else selection
    event_ids={x['event_id'] for x in cases}
    import pandas as pd
    e=pd.read_csv(WORK/'events/event_design.csv.gz',usecols=['event_id','image_id'],low_memory=False)
    chosen=e[e.event_id.isin(event_ids)];assert set(chosen.event_id)==event_ids
    ids=set(chosen.image_id)
    audit=json.loads((OLD/'original_images/ORIGINAL_IMAGE_AUDIT.json').read_text())
    images={x['image_id']:x for x in audit['images']}
    required=sorted({images[i]['archive'] for i in ids if images[i].get('archive')})
    spec=importlib.util.spec_from_file_location('frozen_pro_image_fetcher',OLD/'fetch_original_images.py')
    fetcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(fetcher)
    fetcher.OUT=HERE/'release_cache'
    with ThreadPoolExecutor(max_workers=3) as ex:assets=list(ex.map(fetcher.fetch,required))
    rows=[];target=HERE/'case_originals';target.mkdir(exist_ok=True)
    for iid in sorted(ids):
        old=images[iid]
        if not old.get('archive'):
            rows.append(dict(image_id=iid,status='repository_preview_only_no_original_release',local_path=None,preview_path=old.get('preview_path'),original_visual_review=False));continue
        with zipfile.ZipFile(fetcher.OUT/'archives'/old['archive']) as z:data=z.read(old['archive_path'])
        digest=hashlib.sha256(data).hexdigest();assert digest==old['sha256'] and len(data)==old['original_bytes']
        p=target/(iid+Path(old['archive_path']).suffix);p.write_bytes(data)
        rows.append(dict(image_id=iid,image_code=old['image_code'],status='original_release_archive_and_image_sha_verified',
                         local_path=str(p.relative_to(HERE)),bytes=len(data),sha256=digest,archive=old['archive'],archive_path=old['archive_path'],
                         original_visual_review=False))
    receipt=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),selection_sha256=hashlib.sha256(args.cases.read_bytes()).hexdigest(),
                 archived_fetch_script_sha256=hashlib.sha256((OLD/'fetch_original_images.py').read_bytes()).hexdigest(),
                 requested_case_events=len(event_ids),requested_images=len(ids),archives=assets,images=rows,
                 extracted_only_selected_images=True,original_visual_review='not automatically reviewed by retrieval',
                 other_images='not embedded in Part A viewer; this is not evidence that their originals are unavailable')
    (HERE/'CASE_IMAGE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['images']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
