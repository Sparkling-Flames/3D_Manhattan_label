#!/usr/bin/env python3
"""Independently validate a retrieved deliverable against its external manifest."""
from pathlib import Path
import argparse,csv,hashlib,json,zipfile


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('archive',type=Path);ap.add_argument('--expected',type=Path,required=True);ap.add_argument('--members',type=Path,required=True);ap.add_argument('--fresh-extract',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    v=json.loads(a.expected.read_text());assert a.archive.stat().st_size==v['bytes'] and sha(a.archive)==v['sha256']
    with a.members.open(encoding='utf-8',newline='') as f:members=list(csv.DictReader(f,delimiter='\t'))
    assert not a.fresh_extract.exists()
    with zipfile.ZipFile(a.archive) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(set(z.namelist()))==v['members']==len(members)
        assert set(z.namelist())=={r['path'] for r in members}
        for r in members:
            name=Path(r['path']);assert not name.is_absolute() and '..' not in name.parts
            b=z.read(r['path']);assert len(b)==int(r['bytes']) and hashlib.sha256(b).hexdigest()==r['sha256']
        z.extractall(a.fresh_extract)
    for r in members:
        p=a.fresh_extract/r['path'];assert p.stat().st_size==int(r['bytes']) and sha(p)==r['sha256']
    report={**v,'actual_delivered_copy_validation':'pass','actual_retrieved_path':str(a.archive.resolve()),
          'actual_retrieved_bytes':a.archive.stat().st_size,'actual_retrieved_sha256':sha(a.archive),
          'actual_retrieved_full_crc':'pass','actual_retrieved_member_sha256':'pass',
          'actual_retrieved_fresh_extraction_all_member_sha256':'pass','actual_retrieved_fresh_extract':str(a.fresh_extract.resolve())}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
