"""Byte provenance and narrowly scoped historical-reference search.
This is an audit of available artifacts, not a claim that no other reference
exists anywhere. All source bytes remain immutable.
"""
import argparse,zipfile,hashlib
from pathlib import Path
from core import *

TARGETS=['B6ByNegPMKs-43','B6ByNegPMKs_d2dcbd73533446dcaf50e6be98c30386']
MEMBERS=[
'quality_multispace_joint_calibration_20261013/routing/inputs/prepared_input.json',
'quality_multispace_joint_calibration_20261013/routing/results/reference_candidates.json',
'quality_multispace_joint_calibration_20261013/sources/routing/research/quality_scope_review_complete_20261010/data/reference_registry.json']

def main(source_zip=None,history_zip=None):
    if source_zip:
        archive=Path(source_zip)
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            records=[]
            for n in z.namelist():
                if n.endswith('/'):continue
                # Source has no enclosing directory; explicitly reject path escapes.
                p=(INPUT/n).resolve();assert p.is_relative_to(INPUT.resolve())
                b=z.read(n);hs=hashlib.sha256(b).hexdigest()
                assert p.exists() and sha(p)==hs,n
                records.append(dict(path=n,bytes=len(b),sha256=hs))
        dump(ROOT/'evidence/frozen_source_hashes.json',dict(archive=archive.name,archive_bytes=archive.stat().st_size,
             archive_sha256=sha(archive),file_count=len(records),zip_crc_passed=True,all_extracted_files_equal=True,records=records))
        print('source files',len(records),'all exact')
    if history_zip:
        history=Path(history_zip);records=[]
        with zipfile.ZipFile(history) as z:
            for i,n in enumerate(MEMBERS):
                b=z.read(n);out=ROOT/'evidence/legacy_Q01_registry_search'/f'{i}_{Path(n).name}';out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(b)
                hits={term:b.count(term.encode()) for term in TARGETS}
                records.append(dict(member=n,bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),copied_path=str(out.relative_to(ROOT)),literal_occurrences=hits))
        objs=read(INPUT/'data/objects.json')['objects']
        refs=[r['object_id'] for r in objs if r['image_id']==TARGETS[1] and r['object_kind']!='annotation']
        dump(ROOT/'evidence/Q01_reference_search.json',dict(history_archive=history.name,archive_sha256=sha(history),actual_members_read=records,
            current_snapshot_reference_ids=refs,exact_small_room_reference_found_in_inspected_sources=False,
            search_limit='Three concrete historical routing/registry JSONs and the current 907-object snapshot only. No assertion about all Library or current GitHub.',
            accepted_scope='both small room and larger scope permitted by latest receipt',decision='do not rank R03332 against broad GT; do not use its own geometry as GT',
            next_required_only_for_small_scope_quality='An independently supplied exact small-scope floor ring with its own top reference or an explicit floor-only reference.'))
        print('Q01 historical source bytes checked',records)
    # Recheck from the recorded per-file hashes, including portable copies.
    source=read(ROOT/'evidence/frozen_source_hashes.json')
    assert all(sha(INPUT/r['path'])==r['sha256'] for r in source['records'])
    hist=read(ROOT/'evidence/Q01_reference_search.json')
    for r in hist['actual_members_read']:
        b=(ROOT/r['copied_path']).read_bytes();assert hashlib.sha256(b).hexdigest()==r['sha256']
        assert {t:b.count(t.encode()) for t in TARGETS}==r['literal_occurrences']
    print('portable source provenance verified')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-zip');p.add_argument('--history-zip');a=p.parse_args();main(a.source_zip,a.history_zip)
